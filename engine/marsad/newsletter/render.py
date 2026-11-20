"""Email bodies (Arabic, RTL, inline styles for mail clients)."""

from html import escape

from marsad.config import Settings
from marsad.models import Document, PublishLevel

INK, MAGENTA, GRAPHITE, PAPER = "#14233a", "#a3195b", "#55606e", "#f3f5f4"


def _wrap(settings: Settings, body: str, footer: str) -> str:
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"></head>
<body style="margin:0;background:{PAPER};font-family:Tahoma,Arial,sans-serif;color:{INK};">
<div style="max-width:640px;margin:0 auto;padding:24px;background:#ffffff;text-align:right;direction:rtl;">
<div style="font-size:26px;font-weight:bold;margin-bottom:16px;">{escape(settings.site_name)}</div>
{body}
<hr style="border:none;border-top:1px solid #d5dcdf;margin:28px 0 12px;">
<div style="font-size:12px;color:{GRAPHITE};line-height:1.8;">{footer}</div>
</div></body></html>"""


def confirmation(settings: Settings, token: str) -> tuple[str, str, str]:
    link = f"{settings.site_url.rstrip('/')}/subscribe/confirm?token={token}"
    subject = f"أكّد اشتراكك في نشرة {settings.site_name}"
    body = (f'<p style="font-size:16px;line-height:1.9;">طلبتَ الاشتراك في النشرة الأسبوعية لـ{escape(settings.site_name)}. '
            f'لن نرسل إليك شيئاً قبل أن تؤكد.</p>'
            f'<p><a href="{link}" style="display:inline-block;background:{MAGENTA};color:#fff;padding:10px 22px;'
            f'border-radius:4px;text-decoration:none;font-weight:bold;">تأكيد الاشتراك</a></p>')
    footer = "إذا لم تطلب هذا الاشتراك فتجاهل هذه الرسالة، ولن تصلك أي رسالة أخرى."
    text = (f"طلبت الاشتراك في النشرة الأسبوعية لـ{settings.site_name}.\nلتأكيد الاشتراك افتح الرابط:\n{link}\n\n"
            f"إذا لم تطلب هذا الاشتراك فتجاهل هذه الرسالة.")
    return subject, _wrap(settings, body, footer), text


def digest(settings: Settings, subject: str, intro: str, docs: list[Document], token: str) -> tuple[str, str]:
    base = settings.site_url.rstrip("/")
    manage, unsub = f"{base}/subscribe/manage?token={token}", f"{base}/unsubscribe?token={token}"
    items_html, items_text = [], []
    for d in docs:
        tr = d.translation
        url = f"{base}/articles/{d.id}"
        kind = "نص كامل مترجم" if tr.publish_level == PublishLevel.full and tr.paragraphs_ar else "ملخص تحليلي"
        dek = (tr.summary or {}).get("dek_ar", "")
        items_html.append(
            f'<div style="padding:14px 0;border-bottom:1px solid #d5dcdf;">'
            f'<div style="font-size:12px;color:{GRAPHITE};">{escape(d.source.name_ar)}، {kind}</div>'
            f'<a href="{url}" style="font-size:18px;font-weight:bold;color:{INK};text-decoration:none;">{escape(tr.title_ar)}</a>'
            f'<p style="margin:6px 0 0;font-size:15px;line-height:1.9;">{escape(dek)}</p></div>')
        items_text.append(f"- {tr.title_ar}\n  {d.source.name_ar}، {kind}\n  {dek}\n  {url}")
    body = (f'<div style="font-size:20px;font-weight:bold;margin-bottom:8px;">{escape(subject)}</div>'
            f'<p style="font-size:15px;line-height:1.9;">{escape(intro)}</p>' + "".join(items_html))
    footer = (f'تصلك هذه النشرة لأنك اشتركت فيها من موقع {escape(settings.site_name)}. '
              f'<a href="{manage}" style="color:{MAGENTA};">اختر الموضوعات التي تهمك</a> '
              f'أو <a href="{unsub}" style="color:{MAGENTA};">ألغِ الاشتراك بنقرة واحدة</a>.')
    text = (f"{subject}\n\n{intro}\n\n" + "\n\n".join(items_text) +
            f"\n\n---\nاختر موضوعاتك: {manage}\nإلغاء الاشتراك: {unsub}")
    return _wrap(settings, body, footer), text


def login_link(settings: Settings, token: str) -> tuple[str, str, str]:
    link = f"{settings.site_url.rstrip('/')}/account/verify?token={token}"
    subject = f"رابط الدخول إلى حسابك في {settings.site_name}"
    body = (f'<p style="font-size:16px;line-height:1.9;">اضغط الزر للدخول إلى حسابك. الرابط صالح لمدة 20 دقيقة ولمرة واحدة.</p>'
            f'<p><a href="{link}" style="display:inline-block;background:{MAGENTA};color:#fff;padding:10px 22px;'
            f'border-radius:4px;text-decoration:none;font-weight:bold;">ادخل إلى حسابك</a></p>')
    footer = "إذا لم تطلب الدخول فتجاهل هذه الرسالة؛ لن يحدث شيء."
    text = f"للدخول إلى حسابك في {settings.site_name} افتح الرابط (صالح 20 دقيقة ولمرة واحدة):\n{link}"
    return subject, _wrap(settings, body, footer), text
