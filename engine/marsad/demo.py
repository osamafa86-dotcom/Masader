"""Loads the synthetic demo dataset (fictional sources, clearly labelled) and runs it through the pipeline."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from marsad.ai.demo import DEMO, demo_handler
from marsad.ai.llm import FakeLLM
from marsad.config import Settings
from marsad.models import Document, PublishLevel, RawItem, RightsLevel, Source, Stage
from marsad.normalize import content_hash, url_hash, word_count
from marsad.authors import link_authors
from marsad.pipeline import advance, publish
from marsad.rights import max_publish_level


def load_demo(session: Session, settings: Settings, publish_items: bool = True) -> list[int]:
    sources = {}
    for row in DEMO["sources"]:
        src = session.scalar(select(Source).where(Source.slug == row["slug"]))
        if src is None:
            src = Source(slug=row["slug"], fetch_method="none", is_active=False)
            session.add(src)
        for key in ("name", "name_ar", "homepage", "kind", "description_ar", "license"):
            setattr(src, key, row[key])
        src.content_mode = row.get("content_mode", "full")
        src.language = row.get("language", "en")
        src.rights_level = RightsLevel(row["rights_level"])
        sources[row["slug"]] = src
    session.flush()

    ids = []
    llm = FakeLLM(demo_handler)
    for art in DEMO["articles"]:
        h = url_hash(art["url"])
        if session.scalar(select(RawItem.id).where(RawItem.url_hash == h)):
            continue
        src = sources[art["source"]]
        published = datetime.fromisoformat(art["published_at"])
        raw = RawItem(source_id=src.id, url=art["url"], url_hash=h, title=art["title_en"], published_at=published,
                      feed_authors=art["authors"])
        session.add(raw)
        session.flush()
        paras = art["paragraphs_en"]
        doc = Document(source_id=src.id, raw_item_id=raw.id, url=art["url"], title_en=art["title_en"],
                       authors=art["authors"], published_at=published, paragraphs_en=paras,
                       abstract_en=art.get("abstract_en"), meta=art.get("meta", {}),
                       word_count=word_count(paras), content_hash=content_hash(paras) if paras else None,
                       stage=Stage.extracted)
        doc.source = src
        doc.max_level = max_publish_level(src, "\n".join(paras), settings) if paras else PublishLevel.summary
        session.add(doc)
        session.flush()
        link_authors(session, doc)
        doc.language = art.get("language", "en")
        for _ in range(3):
            advance(session, doc, llm=llm, client=None, storage=None, settings=settings)
        if publish_items and doc.stage == Stage.review:
            publish(session, doc, user=None)
        ids.append(doc.id)
    session.commit()
    return ids
