"""Database schema. See docs/strategy-plan-ar.md section 6."""

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
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
from pgvector.sqlalchemy import Vector
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
    content_mode: Mapped[str] = mapped_column(String(16), default="full", server_default="full")  # full | abstract
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
    feed_meta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
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
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")  # journal, volume, issue, pages, doi
    in_batch_id: Mapped[int | None] = mapped_column(ForeignKey("ai_batches.id", ondelete="SET NULL"), index=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    item_license: Mapped[str | None] = mapped_column(String(64))
    item_rights_evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    source: Mapped[Source] = relationship()
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assigned_to])
    translation: Mapped["Translation | None"] = relationship(back_populates="document", uselist=False)
    tags: Mapped[list["DocumentTag"]] = relationship(cascade="all, delete-orphan")
    author_links: Mapped[list["DocumentAuthor"]] = relationship(cascade="all, delete-orphan",
                                                                 order_by="DocumentAuthor.position")


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
    sampled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_result: Mapped[str | None] = mapped_column(String(16))  # ok | fixed | unpublished
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
    __table_args__ = (UniqueConstraint("lang", "term_en", name="uq_glossary_lang_term"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), default="en", server_default="en")  # language of the source term
    term_en: Mapped[str] = mapped_column(String(200))  # the source-language term (English for most entries)
    term_ar: Mapped[str] = mapped_column(String(200))
    variants_ar: Mapped[list] = mapped_column(JSONB, default=list)
    definition_ar: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(64), default="general")
    status: Mapped[str] = mapped_column(String(16), default="approved")  # approved | proposed
    proposal_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    example_document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
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
    totp_secret_enc: Mapped[str | None] = mapped_column(Text)  # encrypted with MARSAD_SECRET_KEY
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    totp_last_step: Mapped[int | None] = mapped_column(Integer)


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


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    name_ar: Mapped[str | None] = mapped_column(String(300))
    affiliation: Mapped[str | None] = mapped_column(String(300))


class DocumentAuthor(Base):
    __tablename__ = "document_authors"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    author: Mapped[Author] = relationship()


EMBED_DIM = 1024


class DocEmbedding(Base):
    __tablename__ = "doc_embeddings"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    model: Mapped[str] = mapped_column(String(64))
    embedding = mapped_column(Vector(EMBED_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscriber(Base):
    __tablename__ = "subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)  # used in confirm / manage / unsubscribe links
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    topics: Mapped[list] = mapped_column(JSONB, default=list)
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    confirmation_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | sending | sent
    subject_ar: Mapped[str] = mapped_column(String(300), default="")
    intro_ar: Mapped[str] = mapped_column(Text, default="")
    document_ids: Mapped[list] = mapped_column(JSONB, default=list)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DigestDelivery(Base):
    __tablename__ = "digest_deliveries"
    __table_args__ = (UniqueConstraint("digest_id", "subscriber_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    digest_id: Mapped[int] = mapped_column(ForeignKey("digests.id", ondelete="CASCADE"))
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("subscribers.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | sent | skipped | failed
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- phase 3
class ApiClient(Base):
    __tablename__ = "api_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str] = mapped_column(String(200), default="")
    contact_email: Mapped[str] = mapped_column(String(320), default="")
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(16))
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiUsage(Base):
    """One row per client per minute: the rate-limit counter, and the usage history."""

    __tablename__ = "api_usage"

    client_id: Mapped[int] = mapped_column(ForeignKey("api_clients.id", ondelete="CASCADE"), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class Dossier(Base):
    __tablename__ = "dossiers"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    title_ar: Mapped[str] = mapped_column(String(300))
    intro_ar: Mapped[str] = mapped_column(Text, default="")
    intro_is_draft: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | published
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    items: Mapped[list["DossierItem"]] = relationship(cascade="all, delete-orphan", order_by="DossierItem.position")


class DossierItem(Base):
    __tablename__ = "dossier_items"

    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    note_ar: Mapped[str] = mapped_column(Text, default="")

    document: Mapped[Document] = relationship()


class TrendReport(Base):
    __tablename__ = "trend_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7), unique=True)  # YYYY-MM
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)  # frozen snapshot used for the narrative
    narrative_ar: Mapped[str] = mapped_column(Text, default="")
    narrative_is_draft: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | published
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Reader(Base):
    __tablename__ = "readers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReaderLoginToken(Base):
    __tablename__ = "reader_login_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class ReaderSession(Base):
    __tablename__ = "reader_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    reader_id: Mapped[int] = mapped_column(ForeignKey("readers.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    reader: Mapped[Reader] = relationship()


class SavedItem(Base):
    __tablename__ = "saved_items"

    reader_id: Mapped[int] = mapped_column(ForeignKey("readers.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiBatch(Base):
    """A Message Batches submission (half-price, asynchronous translation of non-urgent items)."""

    __tablename__ = "ai_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(100), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="submitted")  # submitted | collected
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiBatchRequest(Base):
    __tablename__ = "ai_batch_requests"

    custom_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("ai_batches.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    paragraph_ids: Mapped[list] = mapped_column(JSONB, default=list)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_email_time", "email", "created_at"),
                      Index("ix_login_attempts_addr_time", "client_address", "created_at"))

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320))
    client_address: Mapped[str] = mapped_column(String(64))
    success: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RateCounter(Base):
    __tablename__ = "rate_counters"

    bucket: Mapped[str] = mapped_column(String(32), primary_key=True)
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class SystemState(Base):
    """Small key/value store: worker heartbeat, last alert times."""

    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PageView(Base):
    """Readership count: item, day, number. No address, cookie or browser data is stored."""

    __tablename__ = "page_views"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
