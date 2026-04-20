# Manual Setup Guide

هذا الملف يجمع كل الخطوات اليدوية المطلوبة لتشغيل المشروع بالكامل، خصوصًا الأشياء التي لا يمكن للكود إنشاؤها بنفسه مثل حسابات الخدمات الخارجية، مفاتيح الـ API، وتهيئة `GitHub Actions`.

## ملخص سريع

| العنصر | هل هو مطلوب؟ | المتغيرات | الاستخدام |
| --- | --- | --- | --- |
| Python dependencies | نعم | لا يوجد | تشغيل التطبيق والـ jobs |
| `.env` | مفضل جدًا | حسب الخدمات التي ستفعّلها | أسهل طريقة لتجميع الإعدادات |
| Hacker News | لا يحتاج تسجيل | لا يوجد | collector يعمل بدون حساب |
| GitHub API | اختياري ومهم | `GITHUB_TOKEN` | رفع limits وتحسين جمع إشارات GitHub |
| GNews | اختياري | `GNEWS_API_KEY` | تشغيل collector الأخبار |
| Supabase | اختياري | `SUPABASE_URL`, `SUPABASE_KEY`, `USE_SUPABASE=true` | تخزين سحابي بدل local فقط |
| LLM Provider | اختياري | مزود واحد على الأقل من `XAI_API_KEY` أو `GEMINI_API_KEY` أو `OPENROUTER_API_KEY` | اقتراحات وتحسينات AI داخل التطبيق |
| Namecheap | اختياري | `NAMECHEAP_API_USER`, `NAMECHEAP_API_KEY`, `NAMECHEAP_USERNAME` | تجهيز لاحق لعمليات registrar وربط الشراء |
| GitHub Actions | اختياري | Secrets / Variables في GitHub | جدولة الـ pipeline تلقائيًا |

## أين تضع القيم؟

المشروع يقرأ القيم بهذا الترتيب:

1. `Streamlit secrets`
2. قيم الـ sidebar داخل التطبيق لبعض مفاتيح الـ AI
3. متغيرات البيئة من `.env`

بالتالي عندك 3 أماكن مناسبة:

- ملف `.env` في root المشروع
- ملف `.streamlit/secrets.toml`
- إدخال يدوي من الـ sidebar داخل `Streamlit` لبعض مفاتيح AI وNamecheap

مهم:

- الملف `.env` يتم تحميله تلقائيًا من root المشروع
- لا ترفع أي مفاتيح حساسة إلى Git

## 1. أقل إعداد مطلوب للتشغيل المحلي

هذه الخطوات تكفي لتشغيل التطبيق محليًا بدون ربط كل الخدمات الخارجية:

1. انسخ ملف الإعدادات:

```bash
cp .env.example .env
```

2. ثبّت الاعتمادات:

```bash
pip install -r requirements.txt
```

3. اترك `USE_SUPABASE=false` إذا كنت لا تريد التخزين السحابي الآن.

4. شغّل التطبيق:

```bash
streamlit run app.py
```

5. إذا أردت تجربة الـ pipeline محليًا:

```bash
python jobs/collect_signals.py
```

ماذا سيعمل بدون مفاتيح إضافية؟

- `Hacker News` يعمل بدون تسجيل
- `GitHub` يمكن أن يعمل بدون `GITHUB_TOKEN` لكن limits ستكون أقل
- `GNews` سيتم تخطيه تلقائيًا إذا لم تضع `GNEWS_API_KEY`
- التطبيق الأساسي والـ scoring يعملان محليًا

## 2. إعداد ملف `.env`

ابدأ من `.env.example` واملأ فقط ما تحتاجه الآن.

مثال عملي:

```dotenv
USE_SUPABASE=false
GITHUB_TOKEN=
GNEWS_API_KEY=
XAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
NAMECHEAP_API_USER=
NAMECHEAP_API_KEY=
NAMECHEAP_USERNAME=
```

إذا أردت استخدام `Streamlit secrets` بدل `.env`، أنشئ الملف:

`.streamlit/secrets.toml`

ومثال له:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-key"
GITHUB_TOKEN = "your-github-token"
GNEWS_API_KEY = "your-gnews-key"
XAI_API_KEY = "your-xai-key"
GEMINI_API_KEY = "your-gemini-key"
OPENROUTER_API_KEY = "your-openrouter-key"
```

## 3. إعداد Supabase

فعّل هذا الجزء فقط لو تريد أن تحفظ البيانات في Supabase بدل الاعتماد على التخزين المحلي فقط.

المطلوب:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `USE_SUPABASE=true`

الخطوات:

1. أنشئ مشروعًا جديدًا على `Supabase`.
2. افتح `SQL Editor`.
3. شغّل محتوى الملف `supabase/schema.sql`.
4. انسخ `Project URL` وضعه في `SUPABASE_URL`.
5. انسخ الـ API key المناسبة لاستخدامك وضعها في `SUPABASE_KEY`.
6. غيّر `USE_SUPABASE=true` في `.env` أو `GitHub Actions vars`.
7. شغّل job واحدة للتأكد أن الإدخال يعمل:

```bash
python jobs/collect_signals.py
```

ملاحظات مهمة:

- الملف `supabase/schema.sql` آمن نسبيًا لإعادة التشغيل لأنه يستخدم `if not exists` و `add column if not exists`
- إذا كانت سياسات الأمان عندك تمنع الكتابة، ستحتاج إعطاء المفتاح المستخدم صلاحيات القراءة والكتابة على الجداول المطلوبة
- إذا كان `SUPABASE_URL` أو `SUPABASE_KEY` ناقصًا، سيعود المشروع تلقائيًا إلى التخزين المحلي

## 4. إعداد GitHub API

هذا الجزء اختياري، لكنه مفيد جدًا حتى لا تصطدم بسرعة بحدود الاستخدام أثناء تشغيل collector الخاص بـ GitHub.

المطلوب:

- `GITHUB_TOKEN`

الخطوات:

1. أنشئ token من حسابك على GitHub.
2. ضع قيمته في `GITHUB_TOKEN`.
3. شغّل ingestion للتأكد أن الجمع يعمل:

```bash
python jobs/ingest_signals.py
```

ملاحظات:

- لو لم تضع `GITHUB_TOKEN` فالمشروع قد يظل يعمل، لكن الاعتماد سيكون على rate limits أقل
- استخدام التوكن هنا هدفه الأساسي تحسين الثبات أثناء الجمع، وليس شرطًا لتشغيل التطبيق الأساسي

## 5. إعداد GNews

هذا الجزء مطلوب فقط إذا كنت تريد تشغيل collector الأخبار.

المطلوب:

- `GNEWS_API_KEY`

اختياري:

- `GNEWS_LANG`
- `GNEWS_COUNTRY`

الخطوات:

1. سجّل في `GNews` وخذ مفتاح API.
2. ضعه في `GNEWS_API_KEY`.
3. اضبط اللغة والدولة إذا لزم:

```dotenv
GNEWS_LANG=en
GNEWS_COUNTRY=us
```

4. شغّل ingestion:

```bash
python jobs/ingest_signals.py
```

ملاحظات:

- إذا لم تضف `GNEWS_API_KEY` فـ collector سيتم تخطيه بدون كسر الـ pipeline
- القيم الافتراضية الحالية هي `en` و `us`

## 6. إعداد مزود AI

هذا الجزء مطلوب فقط لو ستستخدم خصائص الذكاء الاصطناعي داخل التطبيق مثل:

- keyword suggestions
- naming boost
- selective refinement للـ themes / keywords / shortlist

اختر مزودًا واحدًا على الأقل:

- `xAI (Grok)`
- `Google Gemini`
- `OpenRouter`

### xAI

المطلوب:

- `XAI_API_KEY`

اختياري:

- `XAI_MODEL`

### Gemini

المطلوب:

- `GEMINI_API_KEY`

اختياري:

- `GEMINI_MODEL`

### OpenRouter

المطلوب:

- `OPENROUTER_API_KEY`

اختياري:

- `OPENROUTER_MODEL`

الخطوات:

1. أضف مفتاح مزود واحد على الأقل في `.env` أو `secrets.toml`.
2. شغّل التطبيق:

```bash
streamlit run app.py
```

3. من الـ sidebar افتح `AI Settings & Keys`.
4. اختر المزود.
5. لو أردت، اختبر الاتصال بزر `Test`.

ملاحظات:

- لا تحتاج تفعيل كل المزودين
- المشروع يدعم أيضًا إدخال بعض مفاتيح الـ AI يدويًا من الـ sidebar أثناء التشغيل

## 7. إعداد Namecheap

هذا الجزء اختياري بالكامل حاليًا.

المطلوب إذا أردت تجهيزه:

- `NAMECHEAP_API_USER`
- `NAMECHEAP_API_KEY`
- `NAMECHEAP_USERNAME`

مهم:

- وجود هذه القيم ليس شرطًا لتشغيل الـ pipeline
- التطبيق الحالي يحتفظ بمدخلات Namecheap في الـ sidebar، ويحتوي على روابط شراء، لكن الـ core pipeline لا يتوقف عليها

## 8. إعداد GitHub Actions

إذا أردت تشغيل الـ pipeline تلقائيًا من GitHub، استخدم الملف:

`.github/workflows/trend_pipeline.yml`

### GitHub Secrets المطلوبة

- `GNEWS_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_KEY`

بالنسبة إلى `GITHUB_TOKEN`:

- في معظم حالات `GitHub Actions` سيكفيك التوكن الافتراضي الذي يوفّره GitHub تلقائيًا
- إذا احتجت صلاحيات أو سلوكًا مختلفًا، أضف توكن مخصصًا بنفس الاسم

### GitHub Variables المقترحة

- `GNEWS_LANG`
- `GNEWS_COUNTRY`
- `USE_SUPABASE`

خطوات الإعداد:

1. افتح repository على GitHub.
2. ادخل إلى `Settings`.
3. افتح `Secrets and variables`.
4. أضف الـ `Secrets` السابقة.
5. أضف الـ `Variables` السابقة.
6. شغّل الـ workflow يدويًا من `Actions` أول مرة للتأكد أن كل شيء مضبوط.

ملاحظات:

- الـ workflow الحالية تشغل `python jobs/collect_signals.py`
- لو كان `USE_SUPABASE=false` فسيتم حفظ artifacts محلية ورفعها كـ artifact في GitHub Actions

## 9. أوامر التحقق بعد الإعداد

بعد إنهاء الإعدادات اليدوية، استخدم هذه الأوامر كـ smoke test:

تشغيل التطبيق:

```bash
streamlit run app.py
```

تشغيل الـ pipeline كاملة:

```bash
python jobs/collect_signals.py
```

تشغيل المراحل منفصلة:

```bash
python jobs/ingest_signals.py
python jobs/process_signals.py
python jobs/generate_domain_ideas.py
```

تشغيل الاختبارات:

```bash
python -m unittest discover -s tests -v
```

## 10. Checklist أخيرة

قبل أن تعتبر الإعداد مكتملًا، تأكد من الآتي:

- أنشأت `.env` من `.env.example`
- ثبّتت الحزم من `requirements.txt`
- فعّلت `SUPABASE` فقط إذا كنت أضفت URL وKey وشغّلت `schema.sql`
- أضفت `GITHUB_TOKEN` إذا كنت تريد GitHub collection أكثر استقرارًا
- أضفت `GNEWS_API_KEY` إذا كنت تريد news signals
- أضفت مفتاح AI واحدًا على الأقل إذا كنت تريد ميزات الذكاء الاصطناعي
- لا توجد أي مفاتيح حساسة مرفوعة إلى Git

## 11. ماذا يمكن تجاهله الآن؟

إذا كنت تريد البدء بسرعة، يمكنك تجاهل هذه الأشياء مؤقتًا:

- `Supabase`
- `GNews`
- `Namecheap`
- أي مزود AI
- `GitHub Actions`

في هذه الحالة سيظل بإمكانك:

- تشغيل التطبيق
- استخدام التخزين المحلي
- تجربة جزء كبير من الـ generation/scoring
- جمع إشارات `Hacker News`
