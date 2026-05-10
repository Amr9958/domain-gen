# Review Protocol

## الهدف

أي تعديل في المشروع يجب أن يحافظ على الحدود بين:

- raw payloads
- verified facts
- derived signals
- classification results
- valuation runs
- AI explanations
- reports

## Workflow إلزامي

1. اقرأ الملف المرتبط في `docs/`.
2. راجع `TODO.md` قبل التنفيذ.
3. حدد المسار المتأثر: root Streamlit pipeline أم backend SaaS.
4. نفذ بأصغر نطاق آمن.
5. أضف أو حدث tests عند الحاجة.
6. شغل التحقق المتاح.
7. حدث `TODO.md` إذا أنهيت بندًا أو اكتشفت نقصًا جديدًا.
8. حدث الوثيقة المرتبطة في `docs/` عند تغيير flow أو setup أو architecture.

## Gates تحتاج موافقة بشرية

توقف واطلب موافقة قبل:

- إضافة أو حذف جدول قاعدة بيانات.
- تغيير enum مستخدم في API أو valuation أو reports أو alerts.
- تغيير valuation thresholds.
- تغيير معنى confidence أو refusal.
- إضافة marketplace جديد أو تغيير scraping behavior.
- تخزين بيانات شخصية أو screenshots أو website content.
- استخدام AI output كحقيقة.
- تغيير auth أو org boundaries.

## Human Decisions المعتمدة حاليًا

- Dynadot: production access يكون API-first. scraping fallback يحتاج مراجعة terms/robots قبل تفعيله.
- DropCatch: production access disabled حتى اعتماد مصدر رسمي أو إذن واضح. fixtures/local parsing مسموح.
- Scraping policy: delay `1.5s`, max `10` pages/run, retries `3` مع backoff `1.5s` على transient HTTP فقط، و`401/403/robots disallow` توقف المصدر.
- RDAP/WHOIS: RDAP-first، WHOIS fallback اختياري، ولا يتم تخزين personal registrant data بدون موافقة منفصلة.
- Valuation thresholds: الحالية معتمدة كـ `v1 beta` محافظة وليست pricing guarantee.
- Legal/trademark risk: high risk يمنع priced output، medium risk يفرض `needs_review`.
- Alert delivery: Slack incoming webhook هو أول channel معتمد، وemail مؤجل.
- AI provider/model: OpenRouter عبر `OPENROUTER_API_KEY` هو default online path، مع offline fallback دائمًا.
- Retention: raw marketplace payloads لمدة `30 days`; website raw artifacts disabled; website metadata لمدة `90 days` أو حتى superseded.

## Valuation Checklist

أي تعديل في valuation يجب أن يثبت:

- classification مطلوبة قبل priced output.
- missing/stale inputs ترجع refusal أو needs_review.
- confidence مبنية على منطق واضح.
- reason codes تشير إلى facts/signals وليس AI prose فقط.
- meaningful/high/premium outputs لديها structured reasoning.

## Ingestion Checklist

أي adapter أو normalizer يجب أن يثبت:

- raw payload محفوظ قبل normalization.
- source item id وsource url وcaptured at محفوظة.
- adapter/parser versions محفوظة.
- idempotency موجود.
- source-specific fields محفوظة في payload مناسب.
- marketplace logic لا يتسرب إلى valuation.

## Enrichment Checklist

أي enrichment يجب أن:

- يكتب verified facts فقط.
- لا يكتب derived scores داخل facts.
- يسجل provider/version/observed time.
- يسجل failed attempts مع retry eligibility.

## Reports and AI Checklist

أي report أو AI explanation يجب أن:

- يفرق بين facts/signals/valuation/AI prose.
- يكون قابلًا للإعادة من stored IDs وreport JSON.
- لا يقدم AI prose كدليل مستقل.

## Handoff Template

```text
Scope:
Changed:
Tests run:
Facts/signals/AI separation impact:
Schema impact:
API impact:
TODO/docs updated:
Known risks:
```
