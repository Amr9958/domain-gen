# Manual Setup

## 1. أقل تشغيل محلي

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

ما يعمل بدون مفاتيح:

- Streamlit UI.
- generator.
- scoring.
- local portfolio storage.
- Hacker News collector.

## 2. ملف البيئة للجذر

انسخ:

```bash
cp .env.example .env
```

القيم الاختيارية:

```dotenv
USE_SUPABASE=false
SUPABASE_URL=
SUPABASE_KEY=
GITHUB_TOKEN=
GNEWS_API_KEY=
GNEWS_LANG=en
GNEWS_COUNTRY=us
XAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
NAMECHEAP_API_USER=
NAMECHEAP_API_KEY=
NAMECHEAP_USERNAME=
```

## 3. تشغيل Trend Pipeline

تشغيل كل شيء:

```bash
python3 jobs/collect_signals.py
```

تشغيل منفصل:

```bash
python3 jobs/ingest_signals.py
python3 jobs/process_signals.py
python3 jobs/generate_domain_ideas.py
```

## 4. Supabase اختياري

لتفعيل التخزين السحابي:

1. أنشئ مشروع Supabase.
2. شغل `supabase/schema.sql`.
3. ضع `SUPABASE_URL` و`SUPABASE_KEY`.
4. اضبط `USE_SUPABASE=true`.

لو القيم غير موجودة سيبقى التخزين المحلي هو الافتراضي.

## 5. Backend API

```bash
cd backend
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
PYTHONPATH=src uvicorn domain_intel.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints مفيدة:

```text
GET /health
GET /v1/health
GET /v1/auctions
GET /v1/opportunities/undervalued-auctions
POST /v1/reports/appraisals
```

## 6. GitHub API

اختياري لكنه يقلل مشاكل rate limits:

```dotenv
GITHUB_TOKEN=
```

## 7. GNews

مطلوب فقط لو تريد news collector:

```dotenv
GNEWS_API_KEY=
GNEWS_LANG=en
GNEWS_COUNTRY=us
```

## 8. AI Providers

السياسة المعتمدة حاليًا:

- OpenRouter هو المزود الافتراضي الموصى به للـ online mode.
- استخدم `OPENROUTER_API_KEY` لتفعيل online LLM generation/refinement.
- `OPENROUTER_MODEL` اختياري، والافتراضي الحالي يبقى configurable من الإعدادات.
- `DEFAULT_AI_PROVIDER` الافتراضي في الكود و`.env.example` هو `OpenRouter`.
- fallback المجاني الحالي عند فشل موديل OpenRouter الأساسي هو `openai/gpt-oss-20b:free`.
- يمكن وضع قيم OpenRouter داخل `.streamlit/secrets.toml` محليًا؛ هذا الملف موجود في `.gitignore` ولا يجب إدخاله في git.
- عند غياب المفتاح أو فشل المزود، يجب أن يبقى offline generator/refinement fallback متاحًا.
- لا تسجل secrets أو raw prompts في logs.
- AI output يستخدم كـ refinement/report prose فقط، وليس verified facts أو valuation evidence مستقل.

القيم الاختيارية:

```dotenv
XAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
```

الـ AI اختياري ويستخدم لتحسين keywords/naming/review، وليس مصدر حقائق.

اختبارات جودة التوليد موثقة في:

- [Generation Testing](GENERATION_TESTING.md)

## 9. Namecheap

اختياري حاليًا:

```dotenv
NAMECHEAP_API_USER=
NAMECHEAP_API_KEY=
NAMECHEAP_USERNAME=
```

## 10. Verification

```bash
python3 -m pytest tests -q
python3 -m pytest backend/tests -q
```

استخدم `pytest` كأمر التحقق الأساسي لأن `unittest discover` لا يلتقط اختبارات pytest-only مثل bridge smoke tests.
إعداد `pytest.ini` يعرض أبطأ الاختبارات محليًا ويخفي warnings خارجية معروفة من dependencies حتى يبقى output واضحًا.

لتشغيل performance smoke checks فقط:

```bash
python3 -m pytest -m performance -q
```

في البيئة الحالية قد تحتاج تثبيت `pytest` أولًا لأن النظام أظهر أن `python3` موجود لكن `pytest` غير مثبت.

## 11. Approved Marketplace and Enrichment Policies

هذه هي السياسة التشغيلية المعتمدة حاليًا بدون تغيير schema أو valuation thresholds:

### Marketplace HTTP access

- Dynadot production access يكون API-first عندما يغطي المطلوب. لا نستخدم scraping لـ Dynadot إلا كfallback صريح بعد مراجعة terms وrobots.
- DropCatch production access يبقى disabled حتى يتم اعتماد مصدر رسمي أو إذن واضح. اختبارات fixtures/local parsing مسموحة.
- Dynadot API skeleton موجود عبر `DynadotAuctionApiConfig` و`DynadotAuctionApiClient`. الإعداد الافتراضي `enabled=False` ولا يوجد concrete API client مرفق، لذلك لا تحدث أي network calls أو قراءة credentials.
- عند تفعيل API path مستقبلًا يجب حقن concrete `DynadotAuctionApiClient` بعد مراجعة منفصلة. بدون client يرجع adapter خطأ محليًا `api_client_unavailable`.
- Dynadot production scraping fallback مغلق افتراضيًا في adapter التنفيذية؛ تفعيله يحتاج `production_scraping_fallback_enabled=True` بعد مراجعة منفصلة.
- Dynadot fixture/local parsing يحتاج injected fetcher مع `fixture_fetching_enabled=True`، ولا يغير حالة production scraping fallback.
- DropCatch production fetching مغلق افتراضيًا عبر `production_fetch_enabled=False` ولا يسمح إلا بـ `dropcatch.test` للfixtures/local parsing.
- أي HTTP fetching يستخدم `SafeHttpPageFetcher`.
- الـ user-agent الافتراضي: `DomainIntelBot/0.1 (+https://example.invalid/contact)`.
- الحد الأدنى بين الطلبات لكل adapter: `1.5s`.
- الحد الأقصى الحالي لكل run: `10` صفحات.
- retries: `3` محاولات مع backoff `1.5s` على `408, 425, 429, 500, 502, 503, 504`.
- `robots.txt` مفعل افتراضيًا ويفشل closed عند عدم السماح.
- `401`, `403`, وrobots disallow توقف المصدر بدل retry aggressive.

### RDAP/WHOIS

- السياسة المعتمدة هي RDAP-first.
- استخدم RDAP authoritative/bootstrap عندما يتوفر provider production.
- WHOIS fallback اختياري فقط عند نقص RDAP، ولا يكتب facts غير موثقة.
- عند عدم وجود provider فعلي، يبقى `UnavailableWhoisRdapProvider` هو fallback، ويسجل `rdap_provider_unavailable` كحالة retryable ولا يكتب verified facts.
- لا نخزن personal registrant data إلا بعد موافقة retention/privacy منفصلة.

### DNS

- لا يوجد DNS resolver production معتمد حاليًا.
- للاختبارات/local fixtures يمكن استخدام `StaticDnsProvider`.
- في production fallback الحالي هو `UnavailableDnsProvider`، ويسجل `dns_provider_unavailable` ولا يكتب facts غير موثقة.

### Website checks retention

- `HttpWebsiteInspectionProvider` يكتب facts منظمة و`website_checks` metadata فقط.
- لا نخزن HTML خام أو screenshots ضمن retention الحالي.
- TTL freshness الحالي للـ website checks هو `12h`.
- raw marketplace payloads تحتفظ لمدة `30 days` افتراضيًا للتدقيق وإعادة المعالجة.
- normalized auctions/facts/signals/valuation/report records ليست raw artifacts وتخضع لسياسة المنتج/قاعدة البيانات.
- website check metadata يحتفظ به لمدة `90 days` أو حتى superseded، أيهما أنسب للتنظيف التشغيلي.
- raw website artifacts غير معتمدة للتخزين حتى تصدر موافقة منفصلة.

## 12. Approved Valuation, Risk, and Alert Policies

### Valuation thresholds

- thresholds الحالية معتمدة كـ `v1 beta` محافظة.
- لا تعتبر pricing guarantee.
- أي تعديل لاحق في thresholds يحتاج calibration set وموافقة بشرية جديدة.
- valuation عالي يجب أن يحمل confidence وreason codes واضحة.
- نقص classification أو evidence يرجع `refused` أو `needs_review` بدل priced output.

### Legal and trademark risk

- high legal/trademark risk يمنع priced output أو يحوله إلى refused.
- medium risk يرجع `needs_review` ولا يحصل على auto-buy recommendation.
- typo/confusable patterns تعامل كخطر قانوني عالٍ.
- AI prose لا يستخدم كدليل قانوني أو fact.

### Alert delivery

- أول قناة delivery معتمدة هي Slack incoming webhook.
- إعداد rule لقناة Slack يستخدم `channel_config_json` بالشكل:

```json
{
  "channels": ["slack"],
  "slack_webhook_url": "https://hooks.slack.com/services/..."
}
```

- الشكل المتداخل مدعوم أيضًا: `{"channels": ["slack"], "slack": {"webhook_url": "..."}}`.
- email delivery مؤجل للمرحلة التالية، ويفضل Postmark أو SendGrid بعد اعتماد provider.
- alert event deduplication وdelivery attempts يبقيان منفصلين كما هو موثق في system flow.

## 13. Retention Cleanup

تشغيل cleanup يدويًا:

```bash
python3 jobs/run_backend_retention_cleanup.py
```

القيم الافتراضية تطبق السياسة المعتمدة:

- raw marketplace payloads: `30 days`، مع scrub للـ payload/artifact content وإبقاء raw observation row للتتبع والـ idempotency.
- website check metadata: `90 days`.

يمكن تعديل النوافذ للتجارب فقط:

```bash
python3 jobs/run_backend_retention_cleanup.py --raw-marketplace-payload-days 30 --website-metadata-days 90
```
