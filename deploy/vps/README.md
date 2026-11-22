# تشغيل «مصادر» على خادم فيد نيوز

الموقع يعمل على النطاق الفرعي `masader.feedsnews.net`، على خادم فيد نيوز الخاص
(`37.148.202.122`)، بجانب المواقع الموجودة دون أن يمسّها:

- قاعدته (PostgreSQL) وحاوياته في حزمة مستقلة في `/opt/sites/masader`.
- لا يفتح منافذ: Caddy المشترك (`deploy-caddy-1`) هو الذي يوزّع الطلبات بحسب
  النطاق، ويصل إلى `masader-web` و`masader-api` عبر شبكة `deploy_default`.
- Caddy الخاص بالحزمة معطَّل في هذا الوضع.

| الملف | ماذا يفعل |
|---|---|
| `docker-compose.vps.yml` | طبقة فوق `docker-compose.yml`: تعطّل Caddy الخاص وتربط الويب والمحرك بالشبكة المشتركة |
| `masader.caddy.tmpl` | كتلة الموقع في Caddy المشترك: `/v1` للمحرك والباقي للموقع |
| `install.sh` | التثبيت والتحديث: يسحب `main`، ويُنشئ `.env` بأسرار جديدة أول مرة، ويبني، ويثبّت كتلة Caddy ويتحقق منها قبل إعادة التحميل ويتراجع إن رُفضت |

## الخطوات (مرة واحدة)

1. **DNS**: سجل `A` لـ `masader` في منطقة `feedsnews.net` يشير إلى `37.148.202.122`.
2. **على الخادم بصلاحية root**:
   ```sh
   curl -fsSL https://raw.githubusercontent.com/osamafa86-dotcom/masader/main/deploy/vps/install.sh | sh
   ```
3. أضف مفتاح النموذج — `ANTHROPIC_API_KEY`، أو `MARSAD_LLM_BACKEND=gemini` مع `MARSAD_GEMINI_API_KEY` — (واختيارياً Voyage وSMTP) إلى `/opt/sites/masader/.env`، ثم أعد الأمر في الخطوة 2.
4. حساب المحرر الأول (يسأل عن كلمة المرور):
   ```sh
   cd /opt/sites/masader
   docker compose -f docker-compose.yml -f deploy/vps/docker-compose.vps.yml exec api marsad create-user EMAIL 'هيئة التحرير' --role admin
   ```

إن قال السكربت إن إعداد Caddy الرئيسي لا يحمّل `masader.caddy`، فأضف سطر
`import` بجانب السطر الذي يحمّل `newsfeed.caddy` ثم أعد تشغيل السكربت.

## التحديث

أعد تشغيل الأمر نفسه في الخطوة 2. يحتفظ السكربت بـ `.env` وبالبيانات.

## الذاكرة

الحزمة تحتاج نحو 1.2 جيجابايت، والخادم يخدم مواقع أخرى. لذلك يتوقف السكربت
قبل أن يغيّر أي شيء إن كانت الذاكرة المتاحة أقل من 900 ميجابايت.

## على خادم فيد نيوز تحديداً

هذا الخادم لا يُدخَل إليه مباشرة: التنفيذ يمرّ بقناة التشغيل في مستودع البنية
`mahfazapay` (`deploy/ops/task.sh`). مهمّة النشر هناك تتبع أعراف الخادم: النسخة
في `/opt/sites/masader/repo`، والأسرار في `/opt/sites/masader/.env` (600)،
وسجل DNS في Cloudflare. أمّا `install.sh` فلخادمٍ تدخله بنفسك.
