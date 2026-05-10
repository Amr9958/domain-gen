# Project Overview

تاريخ التنظيم: 2026-04-27

## الصورة الحالية

المشروع ليس تطبيقًا واحدًا فقط. يوجد مساران:

1. مسار `Trend-to-Domain` في جذر المشروع.
2. مسار `Domain Intelligence SaaS` داخل `backend/src/domain_intel`.

المطلوب الحالي هو الحفاظ على المفيد في المسارين وربطهما تدريجيًا بدل إعادة كتابة كل شيء مرة واحدة.

## المسار القديم في الجذر

هذا المسار يعمل حول:

- `app.py`
- `workflows/generation.py`
- `generator.py`
- `scoring/`
- `collectors/`
- `processors/`
- `jobs/`
- `pages/`
- `storage.py`
- `repositories/signals.py`

ما ينجزه فعليًا:

- يجمع إشارات من Hacker News وGitHub وGNews.
- ينظف ويدمج ويصنف الإشارات.
- يستخرج themes وkeywords.
- يولد domain opportunities.
- يستخدم generation styles موحدة من `constants.GENERATION_STYLES`: `exact`, `brandable`, `compound`, `short`, `invented`, `geo`.
- يستخدم niches محدثة مثل `Tech & SaaS`, `Finance & Fintech`, `E-commerce & Retail`, `Travel & Lifestyle`, `Health & Medical`, `Real Estate & Property`, `Education & Learning`, `Legal & Professional`, و`Crypto & Web3`.
- يوازن نتائج Auto mode عبر تدوير keywords/support terms، رفض المرشحين الضعفاء مبكرًا، تقليل تكرار جذور الأسماء، ومنع style واحد من السيطرة على أغلب المرشحين.
- يحسن جودة `short` و`invented` عبر vowel-ratio gates، CVCV short patterns، syllable-built invented names، ومزج مقاطع keywords.
- يحسن trend clustering عبر aliases للterms المتقاربة، ويوسع trademark heuristics، ويضيف source evidence داخل rationale.
- مخرجات LLM refinement في Streamlit تحمل `provenance` و`input_ref` حتى تبقى traceable ولا تختلط مع facts.
- مسار التوليد داخل Streamlit مفصول في `workflows/generation.py` كـ pure workflow قابل للاختبار، و`app.py` يركز على الواجهة وحالة الجلسة.
- يقيم كل دومين عبر `scoring.evaluate_domain` مع auto-detected scoring profile من `auto_detect_profile`.
- يمرر keywords المستخدم إلى التقييم حتى تبقى كلمات مثل `mcp` مدخلات توليد عادية وليست تكاملًا خارجيًا، وتوثيق اختبارات ذلك موجود في `docs/GENERATION_TESTING.md`.
- عند تعدد الـ niches، يستخدم `niche_affinity_score()` لاختيار أنسب niche لكل candidate قبل التقييم بدل عرض نفس الدومين مكررًا عبر niches مختلفة.
- يضع النتائج في `shortlist`, `watchlist`, أو `rejected`.
- يعرض النتائج في Streamlit كلوحة تشغيلية بتبويبات درجات، metrics مختصرة، وأحدث backend valuation بجانب legacy score عندما تكون valuation runs موجودة للدومين.
- يحفظ محليًا داخل `signals/` أو اختياريًا في Supabase.

هذا المسار عملي ومفيد، لكنه ليس مصممًا كـ SaaS كامل أو كمصدر الحقيقة النهائي للتقييمات.

## مسار backend الجديد

هذا المسار يوجد تحت:

- `backend/src/domain_intel`
- `backend/migrations`
- `backend/tests`

هدفه:

`marketplace ingestion -> normalization -> enrichment -> derived signals -> classification -> valuation -> reports -> watchlists -> alerts`

ما تم إنجازه فيه:

- schema وORM production-oriented.
- marketplace framework.
- Dynadot adapter/parser/normalizer.
- Dynadot API-first skeleton موجود، لكنه safe-by-default: لا توجد network calls أو credentials بدون concrete API client معتمد، وproduction scraping fallback يبقى disabled.
- DropCatch adapter/parser/normalizer.
- enrichment fact-only boundary.
- marketplace/enrichment operation policies موثقة في `docs/MANUAL_SETUP.md`: Dynadot API-first، DropCatch production disabled حتى اعتماد مصدر رسمي، user-agent/rate limits/retries، RDAP-first، DNS unavailable fallback، وretention للـ raw payloads وwebsite metadata.
- starter classification hints.
- `DerivedSignalService` لفصل بناء وحفظ الإشارات المشتقة عن jobs.
- `DomainClassificationService` كخدمة تصنيف مستقلة خارج `enrichment`.
- valuation engine explainable.
- report service.
- watchlist/alert service with event deduplication, delivery-attempt persistence, and actor/org-scoped remove item.
- Human decisions الأساسية أصبحت معتمدة كسياسة v1: valuation thresholds الحالية `v1 beta`، legal/trademark high risk يمنع priced output، OpenRouter عبر `OPENROUTER_API_KEY` هو online AI path الافتراضي في التوثيق والكود، وSlack هو أول alert delivery channel.
- opportunity screening endpoint للـ undervalued auctions.
- bridge من `signals/domain_ideas.jsonl` إلى backend valuation.
- API trigger لتقييم generated domain واحد عبر `POST /v1/generated-domains/valuation` مع aliases متوافقة مع النماذج المؤجلة.
- report generation يقرأ valuation runs الناتجة من bridge، ويدعم `refused` بوضوح، ولا يضم AI explanations إلا بعد validation.
- SQLite-backed repository tests تغطي مسارات watchlists/alerts/reports/opportunities بجانب service-level tests.

ما لم يكتمل بعد:

- تشغيل production integrations خارج البيئة المحلية يحتاج credentials ومراجعة تشغيل منفصلة.
- integration tests أوسع يمكن توسيعها لاحقًا حول قواعد بيانات وخدمات production-like.

## أهم قرار معماري

لا نستخدم AI explanations كحقائق. ولا نخلط بين:

- raw source payloads
- verified facts
- derived signals
- classification results
- valuation runs
- AI explanations
- reports

كل مرحلة تستهلك ما قبلها وتكتب في مكانها فقط.

## الملفات المرجعية الجديدة

- `docs/SYSTEM_FLOW.md`: يشرح التدفق العملي.
- `docs/GENERATION_TO_BACKEND_VALUATION.md`: يشرح الربط المطلوب بين التوليد والتقييم الجديد.
- `docs/MANUAL_SETUP.md`: خطوات التشغيل اليدوية.
- `docs/REVIEW_PROTOCOL.md`: قواعد التنفيذ والمراجعة.
- `TODO.md`: كل النواقص والمتابعة.
