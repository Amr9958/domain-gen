# Generation to Backend Valuation

## الهدف

ربط نظام توليد الدومينات الحالي بنظام valuation الجديد داخل `backend` بدون كسر المسار القديم.

## الوضع الحالي

`processors/opportunities.py` يولد `DomainOpportunity` ويستدعي:

```python
evaluate_domain(full_domain, profile=profile, niche=niche, word_banks=word_banks)
```

النتيجة الحالية من `scoring` تحتوي على:

- score
- grade
- value estimate نصي
- warnings
- explanation
- rejected flag
- profile
- subscores

أما `backend/src/domain_intel/services/valuation_service.py` فيحتاج:

- `DomainRecord`
- `ClassificationSnapshot`
- `HistoricalSignals`
- `MarketDemandSignals`
- `RiskSignals`
- `ComparableSalesSupport`
- `TldEcosystemSignals`

إذا لم توجد classification يرجع `MISSING_CLASSIFICATION`.
وإذا كانت البيانات الداعمة رفيعة جدًا يرجع `INSUFFICIENT_EVIDENCE`.

## الربط المنفذ أوليًا

تمت إضافة job أولي:

```text
jobs/sync_generated_opportunities_to_backend.py
```

تشغيله من جذر المشروع:

```bash
python3 jobs/sync_generated_opportunities_to_backend.py
```

أو مع مسار ملف مخصص:

```bash
python3 jobs/sync_generated_opportunities_to_backend.py --input signals/domain_ideas.jsonl
```

يمكن تمرير correlation id لتتبع logs:

```bash
python3 jobs/sync_generated_opportunities_to_backend.py --correlation-id local-bridge-smoke
```

كما يوجد trigger رسمي في API لتقييم دومين مولد واحد:

```text
POST /v1/generated-domains/valuation
```

هذا endpoint يستخدم نفس الحدود المعمارية: generated-domain inputs تتحول إلى `derived_signals`، ثم `classification_results`، ثم `ValuationService`، ثم `ValuationRunRepository`.
ويقبل aliases المستخدمة في النماذج المؤجلة بجانب الحقول canonical الحالية، مثل `fullDomain`/`fqdn` بدل `domain_name + extension`، و`scoringProfile`, `valueBand`, `sourceTheme`, `reviewBucket`, `buyerType`, و`riskNotes`.

مسؤولياته الحالية:

1. يقرأ آخر صفوف `signals/domain_ideas.jsonl` حسب `source_theme + domain_name + extension`.
2. يطبع summary عند عدم وجود الملف أو عند عدم وجود أفكار، ولا يفتح transaction بلا داع.
3. يعمل upsert في `backend.domains` حسب `fqdn`.
4. يستخدم `backend/src/domain_intel/services/derived_signal_service.py` لحفظ مخرجات التوليد والتقييم القديم في `derived_signals` فقط، باستخدام `generated-domain-bridge-v1`.
5. يستخدم `backend/src/domain_intel/services/classification_service.py` لإنشاء أو تحديث `classification_results` مبدئية من starter classifier مع mapping من `scoring_profile`, `style`, `niche`, `buyer_type`, `keyword`, و`risk_notes`.
6. يبني `DomainValuationRequest` من الدومين، التصنيف، وإشارات legacy المشتقة.
7. يشغل `ValuationService`.
8. يستخدم `backend/src/domain_intel/repositories/valuation_repository.py` لإنشاء أو تحديث `valuation_runs` ويمسح/يعيد حفظ `valuation_reason_codes` الخاصة بنفس run.

الـ job idempotent على مستوى الدومين و`algorithm_version`: يعيد استخدام domain row، ويحدث إشارات وتصنيف وتقييم bridge بدل تكرارها لكل تشغيل. كما يمرر `input_signal_ids` من الإشارات المشتقة إلى التصنيف والتقييم، ولا يمرر legacy output كـ verified facts. حفظ valuation runs/reason codes أصبح داخل `ValuationRunRepository` مستقل ويستخدمه كل من job الجذر وendpoint `POST /v1/generated-domains/valuation`.

## متطلبات تقارير الـ bridge

`ReportService` يستهلك `valuation_runs` الناتجة من bridge بنفس طريقة valuation runs القادمة من marketplace flow. متطلبات الإدخال:

1. `domain_id` و`valuation_run_id` لنفس الدومين.
2. `created_by_user_id` داخل نفس `organization_id` عند استخدام repository الحقيقي.
3. `valuation_run.classification_result_id` عندما تكون الحالة `valued` أو `needs_review`.
4. `valuation_run.input_signal_ids` لكي تظهر إشارات legacy scoring كـ derived signals في التقرير.
5. `valuation_reason_codes` محفوظة للـ run حتى تظهر أسباب التقييم.
6. AI explanations لا تدخل التقرير إلا إذا كانت `validation_status = validated` ونصها غير فارغ.

التقارير تدعم حالات `valued`, `needs_review`, و`refused`. في حالة `refused` لا يتم إظهار سعر مقترح، ويصبح final verdict واضحًا: `pricing_posture = do_not_list` و`action = resolve_blocker`.

## الربط الصحيح طويل المدى

نحتاج إضافة bridge واضح، مثل:

```text
backend/src/domain_intel/services/generated_domain_bridge.py
backend/src/domain_intel/repositories/generated_domain_repository.py
```

أو إذا أردنا إبقاء الربط خارج backend في البداية:

```text
jobs/sync_generated_opportunities_to_backend.py
```

## خطوات التحويل المطلوبة

1. Normalize domain:
   - `domain_name + extension` إلى `fqdn`.
   - استخراج `sld` و`tld`.
   - upsert داخل جدول `domains`.

2. Store old scoring output as derived signals:
   - `legacy_scoring_score`
   - `legacy_scoring_grade`
   - `legacy_scoring_profile`
   - `legacy_scoring_value_band`
   - `legacy_scoring_subscores`
   - `legacy_generation_theme`
   - `legacy_generation_keyword`
   - `legacy_generation_review_bucket`
   - `legacy_generation_recommendation`

3. Build classification:
   - استخدم starter classifier الموجود في `backend/src/domain_intel/enrichment/classification.py`.
   - استكمل mapping من `scoring_profile`, `style`, `keyword`, و`risk_notes`.
   - احفظ النتيجة في `classification_results`.

4. Build valuation request:
   - `DomainRecord` من جدول `domains`.
   - `ClassificationSnapshot` من `classification_results`.
   - `MarketDemandSignals` من old score/commercial score/theme momentum إن توفر.
   - `RiskSignals` من warnings/risk notes.
   - `TldEcosystemSignals` من tld وextension fit أو provider لاحق.

5. Run valuation:
   - استدعاء `ValuationService.value_domain(request)`.

6. Persist valuation:
   - حفظ `valuation_runs`.
   - حفظ `valuation_reason_codes`.
   - ربط `input_signal_ids` و`classification_result_id`.

7. Expose result:
   - Streamlit يعرض legacy score + backend valuation عند وجود valuation run مخزنة للدومين.
   - Reports تعتمد على backend valuation فقط عندما يكون موجودًا.

## قواعد مهمة

- لا تجعل `scoring` القديم يكتب مباشرة في `valuation_runs`.
- لا تحفظ AI text كـ verified fact.
- لا تنتج priced valuation بدون classification.
- legacy score يمكن أن يكون derived signal فقط.
- أي bridge يجب أن يكون idempotent حتى لا يكرر نفس الدومين أو نفس signal.

## أول تنفيذ مقترح

تم تنفيذ البداية كـ job واحد:

```text
jobs/sync_generated_opportunities_to_backend.py
```

المتبقي بعد هذا التنفيذ:

- نقل منطق الـ bridge إلى service/repository رسمي إذا احتجنا reuse عبر API.
- إضافة smoke/integration tests تستخدم قاعدة backend فعلية أو test database متوافقة مع PostgreSQL.
- جعل report generation يستهلك valuation runs الناتجة من bridge.

بعد نجاحه في التشغيل مع بيانات حقيقية، يمكن نقله أو إعادة تصميمه داخل service رسمي في `backend`.

## عرض Streamlit

`app.py` يقرأ أحدث backend valuation للدومينات المعروضة من `valuation_runs` عبر `fqdn`.
القراءة اختيارية ومخصصة للعرض فقط:

- إذا كانت قاعدة backend غير متاحة، لا يتوقف التوليد وتظهر الحالة `Not synced`.
- إذا لم يتم تشغيل bridge للدومين بعد، تظهر الحالة `Not synced`.
- إذا وُجدت valuation، يعرض جدول المقارنة `Backend Valuation` و`Backend Status` بجانب legacy score والgrade.
- تفاصيل النتيجة تعرض backend status وأول reason codes مخزنة عند توفرها.
