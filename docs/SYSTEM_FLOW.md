# System Flow

## 1. Streamlit Trend-to-Domain Flow

التدفق الحالي في الجذر:

```text
collectors -> raw signals -> processors -> themes -> keyword insights -> domain opportunities -> scoring -> review lanes
```

الملفات الأساسية:

- `collectors/hackernews.py`
- `collectors/github.py`
- `collectors/gnews.py`
- `jobs/ingest_signals.py`
- `jobs/process_signals.py`
- `jobs/generate_domain_ideas.py`
- `processors/themes.py`
- `processors/keywords.py`
- `processors/opportunities.py`
- `generator.py`
- `scoring/scoring.py`
- `workflows/generation.py`
- `app.py`

مخرجات هذا المسار هي `DomainOpportunity` في `models/shared.py`.

تعريف أنماط التوليد أصبح مصدره الواحد `constants.GENERATION_STYLES`. الأنماط الحالية:

- `exact`
- `brandable`
- `compound`
- `short`
- `invented`
- `geo`

الـ niches المعروضة في Streamlit محدثة داخل `constants.NICHE_OPTIONS`، والـ word banks مقسمة إلى ملفات متخصصة مثل `tech`, `finance`, `commerce`, `travel`, `education`, `legal`, `crypto`, و`common_modifiers`.

Auto mode يمر عبر فلترة تنوع داخل `generator.py`: تدوير بين user keywords وكلمات الدعم، توازن بين عائلات styles، رفض مبكر للأسماء الطويلة أو ضعيفة النطق، وحد أقصى للجذور المتكررة حتى لا تسيطر أسماء من نفس البداية مثل `agent*` أو `token*` على النتائج. أسماء `short` و`invented` تمر أيضًا بفحص pronounceability مبكر وتستفيد من CVCV/syllable patterns بدل الاعتماد فقط على قص الكلمات.

Scoring profile لم يعد اختيارًا يدويًا في الواجهة. مسار التوليد المعروض في Streamlit يمر عبر `workflows/generation.py`: يجمع candidates من الـ niches المختارة، يزيل التكرارات، يحسب `niche_affinity_score()` لكل candidate، ويقيّمه مرة واحدة فقط مع أقرب niche بدل تكرار نفس الدومين عبر كل niche. بعدها يستخدم `auto_detect_profile(name, tld, tokens, niche)` لاختيار `geo_local`, `seo_authority`, `flip_fast`, أو `startup_brand` لكل دومين.

الكلمات المدخلة من المستخدم، مثل `mcp`، تمر إلى التقييم كـ `user_keywords` حتى يحصل market-fit على سياقه الصحيح. الكلمات التي قد تبدو منخفضة الثقة خارج سياقها، مثل `crypto`، لا تعاقب كـ spam عندما تكون keyword أو niche term مشروعًا.

عند عرض النتائج، Streamlit يحاول قراءة أحدث `valuation_runs` من backend حسب `fqdn`. إذا كانت موجودة يعرض `Backend Valuation` و`Backend Status` بجانب legacy score داخل لوحة نتائج مقسمة حسب grade، وإذا لم تكن قاعدة backend متاحة أو لم تتم مزامنة الدومين يظهر `Not synced` بدون تعطيل التوليد.

أهم الحقول:

- `domain_name`
- `extension`
- `source_theme`
- `recommendation`
- `keyword`
- `niche`
- `buyer_type`
- `style`
- `score`
- `review_bucket`
- `scoring_profile`
- `grade`
- `value_estimate`
- `rationale`
- `risk_notes`
- `rejected_reason`

## 2. Backend Domain Intelligence Flow

التدفق المستهدف داخل `backend`:

```text
marketplace adapters -> raw auction items -> normalization -> domains/auctions/snapshots
-> enrichment -> verified facts
-> derived signals
-> classification results
-> valuation runs/reason codes
-> reports/watchlists/alerts
```

الملفات الأساسية:

- `backend/src/domain_intel/marketplaces/`
- `backend/src/domain_intel/normalization/`
- `backend/src/domain_intel/enrichment/`
- `backend/src/domain_intel/db/models/`
- `backend/src/domain_intel/services/derived_signal_service.py`
- `backend/src/domain_intel/services/classification_service.py`
- `backend/src/domain_intel/services/generated_domain_service.py`
- `backend/src/domain_intel/repositories/valuation_repository.py`
- `backend/src/domain_intel/valuation/`
- `backend/src/domain_intel/services/valuation_service.py`
- `backend/src/domain_intel/services/report_service.py`
- `backend/src/domain_intel/services/watchlist_service.py`
- `backend/src/domain_intel/services/alert_service.py`

## 3. الفرق بين scoring وvaluation

`scoring/` في الجذر:

- سريع ومفيد للتصفية الأولية.
- يعطي score/grade/value band.
- لا يحتاج قاعدة بيانات backend.
- مناسب لتوليد shortlist من أفكار كثيرة.

`backend valuation`:

- أكثر صرامة.
- يحتاج classification قبل التسعير.
- يرجع refusal عند نقص المتطلبات.
- ينتج wholesale/retail/BIN/MAO.
- يحفظ valuation runs قابلة للتتبع.
- مناسب للتقارير والتنبيهات والـ SaaS.

Generated domains يمكن تقييمها من job الجذر `jobs/sync_generated_opportunities_to_backend.py` أو من endpoint `POST /v1/generated-domains/valuation`. كلا المسارين يمر بنفس الحدود: legacy scoring يتحول إلى derived signals، ثم classification، ثم valuation، ثم حفظ valuation runs/reason codes.

Alerts تستخدم vocabulary موحد للـ rule thresholds داخل `AlertService`. تقييم القواعد ينتج `AlertEventCandidate` ثم يحفظ event واحد لكل `alert_rule_id + event_key`، والـ deliveries تحفظ محاولات الإرسال لكل `alert_event_id + channel`. حذف watchlist item يحتاج `organization_id` و`actor_user_id` حتى يبقى المسار organization-scoped.

قناة alert delivery الأولى المعتمدة هي Slack incoming webhook. التنفيذ يحافظ على الفصل الحالي بين alert events وdelivery attempts: `AlertService.dispatch_pending_deliveries()` يقرأ events المرشحة، يستدعي provider القناة، ثم يسجل outcome داخل `alert_deliveries` عبر `record_delivery()`. أي email provider يبقى مرحلة لاحقة بعد اعتماد مزود محدد.

Marketplace ingestion يعمل بسياسة v1 محافظة: Dynadot API-first مع skeleton آمن لا ينفذ network calls بدون concrete API client معتمد، Dynadot scraping fallback disabled افتراضيًا، DropCatch production disabled حتى مصدر رسمي، retries محدودة للـ transient HTTP فقط، وrobots/permission failures توقف المصدر. Enrichment يعمل RDAP-first عند توفر provider، ولا يكتب facts من WHOIS/RDAP/DNS عند عدم وجود دليل موثق.

## 4. التدفق النهائي المطلوب

الربط المستهدف:

```text
DomainOpportunity
-> BackendBridge
-> Domain row
-> DerivedSignalService writes DerivedSignal rows from old scoring output
-> DomainClassificationService writes ClassificationResult row with input refs
-> DomainValuationRequest
-> ValuationService
-> ValuationRun + ValuationReasonCode rows
-> Report / Watchlist / Alert
```

الـ job موجود في `jobs/sync_generated_opportunities_to_backend.py`، والـ API trigger موجود في `POST /v1/generated-domains/valuation`. Streamlit يعرض أحدث valuation مخزنة عند توفرها. التحقق المحلي يغطي pure Streamlit generation workflow وSQLite-backed repository paths، ويمكن توسيع integration tests لاحقًا حسب `TODO.md`.
