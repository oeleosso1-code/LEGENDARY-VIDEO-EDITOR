# نشر LEGENDARY VIDEO EDITOR على Railway من GitHub

> هذا الملف يشرح النشر. لا تضع أي أسرار فعلية فيه أو في GitHub.

## المتطلبات

- مستودع GitHub يحتوي `Dockerfile`, `requirements.txt`, و`app/`.
- حساب Railway متصل بـ GitHub.
- Telegram Bot Token ومفتاحا OpenAI API صالحان. لا تشاركهما علناً.

## النشر

1. من لوحة Railway أنشئ New Project ثم Deploy from GitHub Repo واختر المستودع الذي يحتوي الشيفرة.
2. تأكد من اختيار جذر المشروع الصحيح. إذا كانت الملفات داخل مجلد فرعي، عيّن Root Directory لذلك المجلد في إعدادات الخدمة.
3. يستخدم Railway تلقائياً `Dockerfile`. يبدأ البوت بالأمر الموجود في الصورة: `python -m app.bot_pro` (Telegram long polling)، لذلك لا تحتاج نطاق ويب أو Webhook لهذا المسار.
4. في خدمة Railway افتح Variables وأضف الأسماء والقيم السرية مباشرة عبر الواجهة، لا عبر GitHub:

   - `TELEGRAM_BOT_TOKEN`: توكن البوت
   - `OPENAI_API_KEY`: المفتاح الأساسي
   - `OPENAI_API_KEY_SECONDARY`: المفتاح الاحتياطي
   - `ALLOWED_USER_IDS`: رقم حسابك العددي في Telegram فقط، لتعطيل الاستخدام العام
   - `OUTPUT_DIR`: `/studio/jobs`
   - `CLOUD_VISION_ENABLED`: `0` أثناء اختبار التشغيل الأولي
   - `MAX_DURATION_SECONDS`: `60` للتجربة الأولى

5. أضف Volume إلى خدمة Railway واربطه بمسار `/studio/jobs`؛ وإلا فقد تفقد الملفات عند إعادة النشر. وفق توثيق Railway، Volume يركّب بملكية root. إذا ظهر خطأ صلاحيات بسبب مستخدم Docker غير الجذر، فإعداد `RAILWAY_RUN_UID=0` موصى به لدى Railway؛ افهم أثر تشغيل العملية كجذر قبل استخدامه.
6. في Settings اترك نسخة واحدة من البوت (`1 replica`) لتجنب تضارب `getUpdates` مع polling.
7. راجع أسعار وحدود Railway قبل بدء الإنتاج؛ تحرير الفيديو الطويل يحتاج ذاكرة وتخزيناً ومعالجاً أكثر من خطة مجانية صغيرة.
8. انشر الخدمة، وافتح Deploy Logs لمعرفة الأخطاء. في تليگرام أرسل `/start` ثم `/connections` للتحقق من قراءة الإعدادات. لا يعني `/connections` نجاح المصادقة السحابية.
9. فعّل `CLOUD_VISION_ENABLED=1` فقط عندما تكون مستعداً لإرسال صور مصغرة من المواد المرفوعة إلى OpenAI مقابل استهلاك API، ثم استخدم `/aiscan openai` عند الحاجة.

## الأمان

- لا ترفع `.env` أو التوكنات أو ملفات الأغاني الخاصة إلى GitHub.
- إذا تسرب أي سر، ألغِه وأنشئ آخر من مزوّد الخدمة.
- قد يُنهي Railway الخدمة عند نفاد الرصيد أو الموارد؛ استخدام التخزين الدائم لا يضمن عدم توقف الخدمة.
- لم تُختبر هذه الخطوات بحساب المستخدم الفعلي؛ يلزم تطبيقها واختبارها على الاستضافة.


## عند فشل زر Ship: النشر المباشر من GitHub (نوفمبر 2026)

زر **Ship** الخاص بـ Railway Agent ليس مطلوباً. إذا فشل بسبب الشبكة أو صلاحيات العامل، استخدم لوحة Railway العادية:

1. افتح المشروع ثم **New / Add Service → GitHub Repo**.
2. اختر `oeleosso1-code/LEGENDARY-VIDEO-EDITOR`، الفرع `main`، وRoot Directory `/`.
3. يعتمد البناء على `Dockerfile` في جذر المستودع. البوت يعمل بالـTelegram Long Polling؛ **لا تنشئ Domain أو Webhook أو HTTP healthcheck**.
4. في Variables أضف `TELEGRAM_BOT_TOKEN` و`OPENAI_API_KEY` و`OPENAI_API_KEY_SECONDARY` و`ALLOWED_USER_IDS` بشكل سري. وللتجربة الأولى: `OUTPUT_DIR=/studio/jobs` و`CLOUD_VISION_ENABLED=0` و`MAX_DURATION_SECONDS=60`.
5. أضف Volume مرتبطاً بالخدمة، واجعل Mount Path هو `/studio/jobs`. يقوم `docker-entrypoint.sh` بإعداد ملكية المجلد بعد تركيب الـVolume، ثم يشغل Python كمستخدم غير مميز. اترك Start Command الافتراضي الخاص بـDockerfile.
6. اضبط Replicas على `1`، وأوقف أي نسخ أخرى تستخدم نفس Telegram Token.
7. طبّق التغييرات وانتقل إلى Build Logs وDeploy Logs. اختبر `/start` في Telegram بعد بدء الخدمة.

### تشخيص الأخطاء

- `TELEGRAM_BOT_TOKEN is missing`: التوكن غير موجود في Variables، أو لم تطبق التغييرات.
- `Permission denied /studio/jobs`: تحقق من ربط الـVolume والمسار ثم أعد النشر.
- `Conflict: terminated by other getUpdates request`: تعمل نسختان من البوت بنفس التوكن.
- Telegram `Unauthorized`: التوكن غير صالح.
- OpenAI `401` أو `429`: مشكلة مفاتيح أو صلاحيات أو حدود استعمال، لا يعني فشل Docker.
- فشل Ship أو الاتصال بالمنصة **قبل** إنشاء خدمة: راجع حالة شبكة Railway؛ قد تنجح محاولة من شبكة أخرى. لا يمكن إصلاح عطل خارجي مضموناً عن طريق تعديل كود Python.

**Railway 2026:** إعداد `railway.json` القديم (Config as Code) لم يعد متاحاً للمشاريع الجديدة وفق التوثيق الحالي. اضبط الإعدادات من لوحة Railway. يستخدم ملف Docker الجديد صلاحيات root فقط عند تحضير مجلد التخزين، ثم يشغل البوت كمستخدم `studio`.
