# Generation Test Results

تم تحديث هذه النتائج يوم 2026-05-10 بعد تشديد ربط نتائج التوليد بالـ primary keyword `mcp`.

مهم: اختبارات pytest تتحقق من الجودة والربط، وهذا الملف هو snapshot عملي لآخر تشغيل يدوي من نفس المسار.

## التغيير المهم

قبل التحسين، نتائج كثيرة في الحالتين لم تكن تحتوي `mcp` في اسم الدومين نفسه. الآن:

```text
visible_primary_keyword_anchor = true
all_generated_names_contain_mcp = true
mcp_anchor_count_top_12 = 12/12
```

تم تطبيق ذلك في:

- المولد المحلي: final visible-keyword guard للأكronym الأساسي.
- المولد المحلي: تحسين فحص acronym boundaries حتى لا تُرفض أسماء مفهومة مثل `mcpcloud`.
- OpenRouter: prompt يطلب ظهور `mcp` صراحة.
- OpenRouter: normalization يرفض أي LLM suggestion لا تحتوي `mcp`.

## الحالة 1: keyword `mcp` - Offline Generator

الإعداد:

```text
niche = Tech & SaaS
keywords = mcp
extensions = .com
num_per_tier = 12
use_llm = False
```

الملخص:

```text
count = 50
styles = {
  exact: 21,
  compound: 14,
  brandable: 13,
  invented: 1,
  short: 1
}
all_generated_names_contain_mcp = true
mcp_anchor_count_top_12 = 12
```

أفضل 20 نتيجة حسب `evaluate_domain()`:

| Domain | Grade | Score | Method |
|---|---:|---:|---|
| mcpcloud.com | A+ | 93 | exact |
| cloudmcp.com | A | 89 | exact_reverse |
| mcplogic.com | A | 88 | exact |
| mcpforge.com | A | 88 | compound |
| mcpagent.com | A | 84 | exact |
| mcpbase.com | A | 83 | exact |
| logicmcp.com | A | 82 | exact_reverse |
| apimcp.com | A | 81 | exact_reverse |
| agentmcp.com | A | 81 | exact_reverse |
| mcpcore.com | A | 80 | compound |
| mcpora.com | B | 77 | brandable |
| mcpedge.com | B | 77 | compound |
| mcpira.com | B | 76 | brandable |
| mcpia.com | B | 76 | short |
| mcpgate.com | B | 76 | compound |
| mcpera.com | B | 76 | brandable |
| mcpara.com | B | 76 | invented |
| mcpaa.com | B | 76 | brandable |
| pilotmcp.com | B | 75 | exact_reverse |
| coremcp.com | B | 75 | compound_reverse |

## الحالة 2: keywords `mcp, agent, workflow` - Offline Generator

الإعداد:

```text
niche = Tech & SaaS
keywords = mcp, agent, workflow
extensions = .com
num_per_tier = 12
use_llm = False
```

الملخص:

```text
count = 44
styles = {
  exact: 16,
  compound: 14,
  brandable: 13,
  short: 1
}
all_generated_names_contain_mcp = true
mcp_anchor_count_top_12 = 12
```

أفضل 20 نتيجة حسب `evaluate_domain()`:

| Domain | Grade | Score | Method |
|---|---:|---:|---|
| mcpcloud.com | A+ | 93 | exact |
| cloudmcp.com | A | 89 | exact_reverse |
| mcpforge.com | A | 88 | compound |
| mcpagent.com | A | 84 | exact |
| mcpbase.com | A | 83 | exact |
| mcpapi.com | A | 83 | exact |
| agentmcp.com | A | 81 | exact_reverse |
| mcpcore.com | A | 80 | compound |
| mcpora.com | B | 77 | brandable |
| mcpedge.com | B | 77 | exact |
| mcpiva.com | B | 76 | brandable |
| mcpio.com | B | 76 | short |
| mcpgate.com | B | 76 | compound |
| mcpara.com | B | 76 | brandable |
| pilotmcp.com | B | 75 | exact_reverse |
| coremcp.com | B | 75 | compound_reverse |
| vimcp.com | C | 58 | brandable |
| vermcp.com | C | 58 | brandable |
| velmcp.com | C | 58 | brandable |
| sumcp.com | C | 58 | brandable |

## OpenRouter Mocked Test

هذا ليس output من الموديل الحقيقي. هذا fixture ثابت داخل الاختبار للتأكد أن مسار LLM ينظف ويدمج النتائج ويرفض الأسماء غير المرتبطة:

```text
accepted:
- mcpalo
- mcpora

rejected:
- cleansignal
```

## OpenRouter Live Test

تم تشغيل `llm_creative_boost()` live باستخدام `OPENROUTER_API_KEY` من الإعدادات المحلية بدون طباعة أو حفظ المفتاح.

الموديل الأساسي في secrets رجع rate limit، ثم نجح fallback:

```text
status = fallback_free
model_used = openai/gpt-oss-20b:free
count = 10
all_generated_names_contain_mcp = true
```

النتائج:

| Name | Method |
|---|---|
| mcpeon | brandable |
| mcpify | brandable |
| mcpora | brandable |
| mcplum | brandable |
| mcpspace | compound |
| mcpcloud | compound |
| mcpgrid | compound |
| mcpion | invented |
| mcpiva | invented |
| mcpier | invented |

لتكرار live smoke يدويًا:

```bash
RUN_LIVE_OPENROUTER=1 python3 -m pytest -m live_openrouter tests/test_openrouter_live_smoke.py -q
```
