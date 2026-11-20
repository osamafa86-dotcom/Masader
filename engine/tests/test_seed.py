from sqlalchemy import func, select

from marsad.models import GlossaryTerm, RightsLevel, Source, TaxonomyTerm
from marsad.seed import seed_all


def test_seed_is_idempotent_and_sets_rights(db):
    first = seed_all(db)
    db.commit()
    glossary_count = db.scalar(select(func.count()).select_from(GlossaryTerm))
    taxonomy_count = db.scalar(select(func.count()).select_from(TaxonomyTerm))

    second = seed_all(db)
    db.commit()

    assert first == second
    assert db.scalar(select(func.count()).select_from(Source)) == 19
    assert db.scalar(select(func.count()).select_from(Source).where(Source.is_active)) == 16
    assert db.scalar(select(func.count()).select_from(GlossaryTerm)) == glossary_count >= 100
    assert db.scalar(select(func.count()).select_from(TaxonomyTerm)) == taxonomy_count

    tnsr = db.scalar(select(Source).where(Source.slug == "tnsr"))
    assert tnsr.rights_level == RightsLevel.a
    assert tnsr.license == "CC BY-NC 4.0"


def test_reseed_keeps_editorial_rights_decision(db):
    seed_all(db)
    wotr = db.scalar(select(Source).where(Source.slug == "wotr"))
    wotr.rights_level = RightsLevel.b  # permission granted by editor
    wotr.is_active = False
    db.commit()
    seed_all(db)
    db.commit()
    db.refresh(wotr)
    assert wotr.rights_level == RightsLevel.b
    assert wotr.is_active is False
