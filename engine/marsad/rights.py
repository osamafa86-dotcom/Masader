"""Publishing rights rules (strategy plan 2.1)."""

import re

from marsad.config import Settings
from marsad.models import PublishLevel, RightsLevel, Source

COPYRIGHT_NOTICE = re.compile(r"(©|\(c\)|copyright)\s*(\d{4})", re.I)
NON_COMMERCIAL = re.compile(r"\bNC\b|non-?commercial", re.I)


def max_publish_level(source: Source, body_text: str, settings: Settings,
                      item_license: str | None = None) -> PublishLevel:
    if item_license:
        # An item-level open licence (e.g. an open-access journal article) overrides the source level.
        if settings.site_commercial and NON_COMMERCIAL.search(item_license):
            return PublishLevel.summary
        return PublishLevel.full
    if source.rights_level == RightsLevel.c:
        return PublishLevel.summary
    if settings.site_commercial and source.license and NON_COMMERCIAL.search(source.license):
        return PublishLevel.summary
    if source.per_item_copyright_check and COPYRIGHT_NOTICE.search(body_text or ""):
        return PublishLevel.summary
    return PublishLevel.full


def rights_note(source: Source, level: PublishLevel, item_license: str | None = None) -> str:
    """Attribution line shown with the published item (Arabic)."""
    if level == PublishLevel.full and item_license:
        return f"تُنشر هذه الترجمة بموجب ترخيص المادة: {item_license}. الحقوق الأصلية محفوظة لأصحابها."
    if level == PublishLevel.full and source.license:
        return f"تُنشر هذه الترجمة بموجب ترخيص المصدر: {source.license}. الحقوق الأصلية محفوظة لأصحابها."
    if level == PublishLevel.full:
        return "تُنشر هذه الترجمة بإذن من المصدر. الحقوق الأصلية محفوظة لأصحابها."
    return "هذا ملخص تحليلي بالعربية من إعداد المنصة. النص الكامل متاح لدى المصدر الأصلي عبر الرابط."
