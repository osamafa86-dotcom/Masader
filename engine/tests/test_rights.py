from marsad.models import PublishLevel, RightsLevel, Source
from marsad.rights import max_publish_level


def src(level, license=None, per_item=False):
    return Source(slug="s", rights_level=level, license=license, per_item_copyright_check=per_item)


def test_levels(settings):
    assert max_publish_level(src(RightsLevel.a), "text", settings) == PublishLevel.full
    assert max_publish_level(src(RightsLevel.b), "text", settings) == PublishLevel.full
    assert max_publish_level(src(RightsLevel.c), "text", settings) == PublishLevel.summary


def test_non_commercial_licence_downgrades_on_commercial_site(settings):
    s = src(RightsLevel.a, license="CC BY-NC 4.0")
    assert max_publish_level(s, "text", settings) == PublishLevel.full
    settings.site_commercial = True
    assert max_publish_level(s, "text", settings) == PublishLevel.summary
    assert max_publish_level(src(RightsLevel.a, license="CC BY 4.0"), "text", settings) == PublishLevel.full


def test_per_item_copyright_notice_downgrades(settings):
    s = src(RightsLevel.a, license="Public domain", per_item=True)
    assert max_publish_level(s, "Plain government work.", settings) == PublishLevel.full
    assert max_publish_level(s, "Body text. ©2025 Spenser A. Warren", settings) == PublishLevel.summary
    assert max_publish_level(s, "Copyright 2024 the author", settings) == PublishLevel.summary
    # Without the per-item flag the notice is ignored (source-level licence governs).
    assert max_publish_level(src(RightsLevel.a), "©2025 X", settings) == PublishLevel.full
