"""Database schema. See docs/strategy-plan-ar.md section 6."""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RightsLevel(str, enum.Enum):
    a = "a"  # open licence, public domain, or partnership agreement
    b = "b"  # written permission with conditions
    c = "c"  # protected: analytical summary + link only


class PublishLevel(str, enum.Enum):
    full = "full"
    summary = "summary"


class Stage(str, enum.Enum):
    discovered = "discovered"
    extracted = "extracted"
    classified = "classified"
    summarized = "summarized"
    translated = "translated"
    review = "review"
    published = "published"
    rejected = "rejected"
    failed = "failed"


def _enum(e: type[enum.Enum], name: str) -> Enum:
    return Enum(e, name=name, values_callable=lambda x: [m.value for m in x])


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str] = mapped_column(String(200))
    homepage: Mapped[str] = mapped_column(String(500))
    kind: Mapped[str] = mapped_column(String(32))  # think_tank | journal | media | government
    description_ar: Mapped[str] = mapped_column(Text, default="")
    fetch_method: Mapped[str] = mapped_column(String(16), default="rss")  # rss | listing | none
    feed_url: Mapped[str | None] = mapped_column(String(500))
    listing_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    fetch_interval_min: Mapped[int] = mapped_column(Integer, default=60)
    language: Mapped[str] = mapped_column(String(8), default="en")
    rights_level: Mapped[RightsLevel] = mapped_column(_enum(RightsLevel, "rights_level"), default=RightsLevel.c)
    license: Mapped[str | None] = mapped_column(String(64))
    rights_evidence: Mapped[str] = mapped_column(Text, default="")
    per_item_copyright_check: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    feed_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class RawItem(Base):
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(1000))
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    feed_content: Mapped[str | None] = mapped_column(Text)  # full HTML when the feed carries it
    feed_summary: Mapped[str | None] = mapped_column(Text)
    feed_authors: Mapped[list] = mapped_column(JSONB, default=list)
    raw_key: Mapped[str | None] = mapped_column(String(300))  # storage key of downloaded page/PDF
    content_type: Mapped[str | None] = mapped_column(String(100))

    source: Mapped[Source] = relationship()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_stage", "stage"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    raw_item_id: Mapped[int] = mapped_column(ForeignKey("raw_items.id", ondelete="CASCADE"), unique=True)
    url: Mapped[str] = mapped_column(String(1000))
    stage: Mapped[Stage] = mapped_column(_enum(Stage, "stage"), default=Stage.discovered)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    title_en: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[list] = mapped_column(JSONB, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    abstract_en: Mapped[str | None] = mapped_column(Text)
    paragraphs_en: Mapped[list] = mapped_column(JSONB, default=list)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    doc_type: Mapped[str | None] = mapped_column(String(32))
    importance: Mapped[int | None] = mapped_column(Integer)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    max_level: Mapped[PublishLevel] = mapped_column(_enum(PublishLevel, "publish_level"), default=PublishLevel.summary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship()
    translation: Mapped["Translation | None"] = relationship(back_populates="document", uselist=False)
    tags: Mapped[list["DocumentTag"]] = relationship(cascade="all, delete-orphan")


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (Index("ix_translations_search", "search_vector", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), unique=True)
    title_ar: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    paragraphs_ar: Mapped[list | None] = mapped_column(JSONB)
    notes: Mapped[list] = mapped_column(JSONB, default=list)
    publish_level: Mapped[PublishLevel] = mapped_column(_enum(PublishLevel, "publish_level"), default=PublishLevel.summary)
    model: Mapped[str] = mapped_column(String(64), default="")
    prompt_version: Mapped[str] = mapped_column(String(32), default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    qa_report: Mapped[dict] = mapped_column(JSONB, default=dict)
    human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    search_text: Mapped[str] = mapped_column(Text, default="")
    search_vector = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', coalesce(search_text, ''))", persisted=True)
    )

    document: Mapped[Document] = relationship(back_populates="translation")
    reviewer: Mapped["User | None"] = relationship()


class TaxonomyTerm(Base):
    __tablename__ = "taxonomy_terms"
    __table_args__ = (UniqueConstraint("kind", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # topic | region | doc_type
    slug: Mapped[str] = mapped_column(String(64))
    name_ar: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str] = mapped_column(String(200))


class DocumentTag(Base):
    __tablename__ = "document_tags"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    term_id: Mapped[int] = mapped_column(ForeignKey("taxonomy_terms.id", ondelete="CASCADE"), primary_key=True)
    origin: Mapped[str] = mapped_column(String(8), default="ai")  # ai | human

    term: Mapped[TaxonomyTerm] = relationship()


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    term_en: Mapped[str] = mapped_column(String(200), unique=True)
    term_ar: Mapped[str] = mapped_column(String(200))
    variants_ar: Mapped[list] = mapped_column(JSONB, default=list)
    definition_ar: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(16), default="approved")  # approved | proposed
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(16), default="editor")  # admin | editor
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserSession(Base):
    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    task: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
