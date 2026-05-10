# Generation Testing

## ما الذي نختبره؟

هذا الملف يشرح اختبار جودة توليد الدومينات من مدخلات المستخدم داخل Streamlit، خصوصًا عندما تكون الكلمة المفتاحية:

```text
MCP
```

`MCP` هنا كلمة عادية داخل حقل:

```text
🎯 Keywords (comma separated)
```

ولا تعني استخدام MCP server أو تكامل خارجي.

آخر snapshot لنتائج التوليد موجود في:

- [Generation Test Results](GENERATION_TEST_RESULTS.md)

## مدخل keyword MCP

السيناريوهات الأساسية:

```text
mcp
mcp, agent, workflow
```

الغرض هو التأكد أن النظام ينتج أسماء قابلة للتقييم والتصفية بدل التعامل مع `mcp` كتقنية خارجية أو إعداد نظام.

## Offline Generator Test

مسار offline يعمل بدون مفاتيح أو شبكة:

```text
generator.generate_domains()
workflows.generation.run_generation_workflow()
scoring.evaluate_domain()
```

معايير النجاح:

- وجود عدد كاف من candidates.
- تنوع بين أكثر من generation style.
- ظهور الـ primary keyword بوضوح داخل اسم الدومين نفسه عندما تكون keyword قصيرة/اختصارية مثل `mcp`.
- في اختبار `mcp`، كل نتيجة مرئية يجب أن تحتوي `mcp` في الـ SLD، وليس فقط داخل metadata مثل `source_name`.
- عدم سيطرة جذر واحد على أغلب النتائج.
- عدم مرور أسماء بها trademark أو spam واضح.
- دخول النتائج في grading buckets بشكل طبيعي.

## OpenRouter Mocked Test

اختبار OpenRouter الأساسي لا يستدعي الشبكة. الاختبار يبدل `call_llm()` برد JSON ثابت حتى نتحقق من:

- بناء prompt صحيح.
- تنظيف أسماء LLM.
- دمج مخرجات LLM مع offline candidates.
- عدم تكرار نفس الاسم.
- بقاء fallback الداخلي متاحًا.

## OpenRouter Live Smoke من secrets.toml

الاختبار live اختياري، ولا يعمل في CI أو التشغيل العادي.

القيم تقرأ من:

```text
.streamlit/secrets.toml
```

المفاتيح المتوقعة:

```toml
OPENROUTER_API_KEY = "..."
OPENROUTER_MODEL = "..."
```

لا تطبع الاختبارات المفتاح ولا raw prompts. الملف موجود في `.gitignore` ويجب أن يبقى خارج git.

تشغيل live smoke يدويًا:

```bash
RUN_LIVE_OPENROUTER=1 python3 -m pytest -m live_openrouter tests/test_openrouter_live_smoke.py -q
```

لو لم يوجد المفتاح أو لم يتم ضبط `RUN_LIVE_OPENROUTER=1` يتم تخطي الاختبار.

## Backend Valuation Bridge Check

بعد توليد دومين مبني على `mcp`، يمكن تمريره إلى مسار backend generated-domain valuation:

```text
GeneratedDomainValuationService
```

معايير النجاح:

- legacy scoring يتحول إلى `derived_signals` فقط.
- `classification_results` تنشأ قبل valuation.
- `valuation_runs` يحمل `classification_result_id`.
- لا يتم تحويل AI prose أو legacy score إلى verified facts.

## أوامر التشغيل

اختبارات الجذر المركزة:

```bash
python3 -m pytest tests/test_mcp_generation_quality.py tests/test_llm_prompts.py tests/test_streamlit_generation_workflow.py -q
```

اختبارات backend المركزة:

```bash
python3 -m pytest backend/tests/unit/test_generated_domain_service.py -q
```

كل اختبارات الجذر:

```bash
python3 -m pytest tests -q
```

كل اختبارات backend:

```bash
python3 -m pytest backend/tests -q
```

## معايير النجاح والفشل

ينجح الاختبار عندما:

- `mcp` ينتج candidates متعددة الأنماط.
- `mcp` يظهر داخل كل SLD في نتائج اختبار `mcp`.
- `mcp, agent, workflow` يبقى مربوطًا بالـ primary keyword `mcp` داخل كل SLD، حتى مع وجود keywords إضافية.
- OpenRouter mocked يضيف أسماء LLM صالحة بدون شبكة.
- live OpenRouter smoke اختياري ولا يكسر suite عند غياب المفتاح.
- backend valuation bridge يحافظ على حدود: derived signals ثم classification ثم valuation.

يفشل الاختبار عندما:

- لا ينتج offline generator أسماء كافية.
- تظهر نتائج لا تحتوي `mcp` في اختبار `mcp`.
- style واحد أو root واحد يسيطر على النتائج.
- تمر أسماء ضعيفة جدًا أو risky بدون flags مناسبة.
- LLM output يكسر JSON parsing أو dedupe.
- backend valuation ينتج output بدون classification.
