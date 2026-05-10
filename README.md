# Domain Intelligence

هذا الريبو يجمع مسارين يعملان معًا تدريجيًا:

- `Streamlit` في جذر المشروع لتوليد أفكار الدومينات من الكلمات والإشارات، تقييمها سريعًا، ومراجعة shortlist/watchlist/rejected.
- `backend/src/domain_intel` كنواة SaaS أكثر صرامة لتطبيع مزادات الدومينات، enrichment، التصنيف، valuation explainable، التقارير، watchlists، والتنبيهات.

## Documentation

الوثائق القديمة تم استبدالها بمرجع مرتب داخل `docs/`، وملف واحد حي للنواقص:

- [Project Overview](docs/PROJECT_OVERVIEW.md)
- [System Flow](docs/SYSTEM_FLOW.md)
- [Generation to Backend Valuation](docs/GENERATION_TO_BACKEND_VALUATION.md)
- [Generation Testing](docs/GENERATION_TESTING.md)
- [Manual Setup](docs/MANUAL_SETUP.md)
- [Review Protocol](docs/REVIEW_PROTOCOL.md)
- [TODO](TODO.md)

## Quick Start

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

تشغيل trend pipeline:

```bash
python3 jobs/collect_signals.py
```

تشغيل backend محليًا:

```bash
cd backend
cp .env.example .env
docker compose up -d postgres
alembic upgrade head
PYTHONPATH=src uvicorn domain_intel.main:app --reload --host 0.0.0.0 --port 8000
```

## Current Shape

المسار القديم في الجذر يعمل فعليًا:

```text
signals -> themes -> keywords -> generated domains -> auto profile scoring -> review lanes
```

واجهة Streamlit تستخدم generation styles موحدة (`exact`, `brandable`, `compound`, `short`, `invented`, `geo`) وniches محدثة. منطق التوليد والتقييم داخل الواجهة مستخرج في `workflows/generation.py` كمسار pure قابل للاختبار، بينما يبقى `app.py` مسؤولًا عن العرض وحالة Streamlit. Scoring profile يُكتشف تلقائيًا لكل دومين بدل اختياره يدويًا، ولوحة النتائج تعرض backend valuation بجانب legacy score عندما تكون نتائج bridge موجودة في قاعدة backend.

المسار الجديد في backend يستهدف:

```text
marketplace ingestion -> normalization -> enrichment -> signals -> classification -> valuation -> reports -> alerts
```

الربط بين المسارين بدأ عبر job مزامنة من generated opportunities إلى backend valuation، وStreamlit يقرأ أحدث valuation مخزنة للعرض فقط بدون تحويل legacy scoring إلى مصدر valuation مباشر. المرجع العملي لهذا الربط هو:

- [Generation to Backend Valuation](docs/GENERATION_TO_BACKEND_VALUATION.md)
- [TODO](TODO.md)

## Rule

`TODO.md` هو مرجع النواقص. عند إنهاء أي بند منه يجب تحديثه وتحديث ملف الوثائق المرتبط به في نفس التغيير.
