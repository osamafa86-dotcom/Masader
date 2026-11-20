from sqlalchemy import select

from marsad.demo import load_demo
from marsad.models import Document, PublishLevel, Stage
from marsad.seed import seed_all


def test_demo_loads_and_publishes_with_rights(db, settings):
    seed_all(db)
    ids = load_demo(db, settings)
    assert len(ids) == 6
    assert load_demo(db, settings) == []  # idempotent
    docs = {d.title_en: d for d in db.scalars(select(Document))}
    gray = docs["Deterrence in the Gray Zone: Lessons for Allied Planners"]
    arctic = docs["Arctic Competition and the Alliance"]
    assert gray.stage == Stage.published and gray.translation.publish_level == PublishLevel.full
    assert gray.translation.qa_report["score"] == 100
    assert arctic.stage == Stage.published and arctic.translation.paragraphs_ar is None
    assert arctic.translation.title_ar == "التنافس في القطب الشمالي والتحالف"
