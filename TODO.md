# TODO

هذا هو المرجع الواحد للنواقص. عند إنهاء أي بند، حدث هذا الملف والوثيقة المرتبطة داخل `docs/` في نفس التغيير.

## P0 - Security and Git Maintenance

- [x] إزالة secrets.toml من تاريخ Git بعد تفعيل GITHUB PUSH PROTECTION (تم إزالتها من commit 90cba0a وتعديله).
- [ ] فحص دوري للملفات المتجاهلة للتأكد من عدم تسرب مفاتيح برمجية.

## P0 - ربط التوليد بالـ Backend Valuation

- [x] تنفيذ `jobs/sync_generated_opportunities_to_backend.py` كـ bridge أولي end-to-end.
- [x] إنشاء bridge/job يقرأ `DomainOpportunity` من `signals/domain_ideas.jsonl` أو repository.
- [x] Upsert للدومينات في جدول `backend.domains`.
- [x] تحويل legacy scoring output إلى `derived_signals` بدل اعتباره facts.
- [x] إنشاء classification result مبدئية من starter classifier + profile/style/risk mapping.
- [x] بناء `DomainValuationRequest` من الدومين والتصنيف والإشارات.
- [x] تشغيل `ValuationService`.
- [x] حفظ `valuation_runs` و`valuation_reason_codes` end-to-end.
- [x] عرض backend valuation بجانب legacy score داخل Streamlit.
- [x] توثيق الربط النهائي في `docs/GENERATION_TO_BACKEND_VALUATION.md`.

## P0 - Backend Signals and Classification

- [x] إنشاء module مستقل للـ derived signals بدل بقاء المنطق مشتتًا.
- [x] إنشاء classification service مستقل خارج `enrichment`.
- [x] ربط classification بـ input fact ids وinput signal ids.
- [x] إضافة tests لحالات brandable/exact_match/geo/typo_risk/unknown.
- [x] التأكد أن valuation لا ينتج `valued` بدون classification.

## P0 - اختبار وتحسين توليد الدومينات من keyword `MCP`

- [x] إضافة اختبارات وتوثيق لمسار توليد الدومينات عندما تكون `MCP` keyword عادية داخل حقل Keywords، مع تغطية offline generator وOpenRouter mocked/live optional وbackend valuation bridge بدون استخدام MCP خارجي.
- [x] فرض ظهور primary keyword `mcp` في نتائج الاختبار المحلي والأونلاين، وتحديث snapshot النتائج بعد تحسين المولد المحلي وPrompt/normalization الخاص بـ OpenRouter.

## P0 - إعادة هيكلة محرك التوليد (Generation Restructuring)

### المرحلة 1: توحيد تعريف Generation Styles (Single Source of Truth)

- [x] إنشاء `GenerationStyle` dataclass في `constants.py` يحتوي: `key`, `label`, `description`, `llm_guidance`.
- [x] تعريف 6 styles موحدة في `GENERATION_STYLES` dict:
  - `exact` — Keyword + Head term. مباشر ووصفي.
  - `brandable` — اسم مبتكر مشتق من الـ keywords. يمتص logic الـ hybrid القديم الخاص بـ brand roots.
  - `compound` — Keyword + Anchor suffix (hub, flow, labs, forge...). يحل محل hybrid.
  - `short` — 4-6 حروف فقط. مقاطع مختصرة ونهايات نظيفة.
  - `invented` — أسماء مخترعة كلياً pronounceable بدون معنى مباشر. يحل محل legacy invent.
  - `geo` — Location + Service. للدومينات المحلية فقط عند وجود geo context.
- [x] تحديث `GENERATION_STYLE_OPTIONS` و`GENERATION_STYLE_LABELS` ليقرأوا من `GENERATION_STYLES`.
- [x] حذف `ai_futuristic` و`outbound` و`hybrid` من قوائم الـ styles.

### المرحلة 2: تبسيط الـ Offline Engine (`generator.py`)

- [x] إنشاء `_build_compound_candidates()` — يأخذ logic الـ `_build_hybrid_candidates` الحالي (keyword + HYBRID_SUFFIXES).
- [x] تحديث `_build_brandable_candidates()` — يمتص جزء من hybrid القديم الخاص بـ prefix + brand_root.
- [x] إنشاء `_build_invented_candidates()` — ينقل logic الـ `_invent_name()` + الجزء المتعلق من `_build_legacy_candidates`.
- [x] حذف `_build_ai_candidates()` — AI keywords تدخل عبر الـ niche في أي builder.
- [x] حذف `_build_action_candidates()` — نتائجه ضعيفة تجارياً (builddata, launchflow...).
- [x] حذف `_build_legacy_candidates()` — logic مفيد ينتقل إلى invented + brandable، الباقي noise.
- [x] تحديث `generate_domains()`:
  - حذف references للـ styles المحذوفة (ai_futuristic, outbound, hybrid).
  - إضافة calls لـ `_build_compound_candidates()` و`_build_invented_candidates()`.
  - حذف fallback call لـ `_build_legacy_candidates` في وضع Auto.
- [x] تحديث `GENERATION_STYLE_ORDER` ليطابق الـ 6 styles الجديدة.
- [x] تحديث `_auto_generation_styles()` — حذف ai_futuristic/outbound/hybrid، إضافة compound/invented.
- [x] التأكد أن `NICHE_BANKS`, `NICHE_STATIC_TERMS`, `COMMERCIAL_HEADS_BY_NICHE`, `ACTION_PREFIXES_BY_NICHE` تتوافق مع الـ styles الجديدة.
- [x] حذف `ACTION_PREFIXES_BY_NICHE` بالكامل (كان يخدم outbound فقط).
- [x] حذف `AI_SUFFIXES` و`AI_MODEL_ENDINGS` (كانوا يخدمون ai_futuristic فقط، AI keywords تدخل عبر niche).

### المرحلة 3: تبسيط الـ Online Engine (`providers/llm.py`)

- [x] حذف `DOMAIN_STYLE_GUIDANCE` dict — يُستبدل بقراءة `GENERATION_STYLES[style].llm_guidance` من constants.
- [x] حذف `_choose_domain_generation_styles()` المكرر — يستخدم نفس `_auto_generation_styles()` من generator أو نسخة واحدة مشتركة.
- [x] حذف `_normalize_requested_domain_styles()` المكرر — يستخدم نفس `_normalize_requested_styles()` من generator.
- [x] تحديث `_build_domain_generation_prompt()`:
  - يبني `style_instructions` من `GENERATION_STYLES[style].llm_guidance`.
  - يزيل references للـ styles المحذوفة.
  - يضيف `compound` و`invented` descriptions.
- [x] تحديث `DOMAIN_GENERATION_SYSTEM_PROMPT`:
  - حذف ذكر "AI / futuristic" و"outbound-friendly" من قائمة naming modes.
  - إضافة "compound" و"invented" بدلاً منهم.
- [x] التأكد أن `TOPIC_KEYWORD_SYSTEM_PROMPT` لا يذكر styles محذوفة.

### المرحلة 4: تحديث Niches وWord Banks

> **السياق**: الـ Niches الحالية (6) لا تغطي أقوى أسواق الدومينات مثل Education وLegal وTravel وCrypto.
> كذلك SaaS ليس niche بل نموذج أعمال (موجود خطأ في Finance & SaaS)، و"Creative & Arts" سوق ضعيف جداً تجارياً.
> الـ Word Banks الحالية فيها تكرار كبير: كلمات مثل flow, nova, cloud, zone موجودة في 4-5 ملفات مما يقلل تنوع التوليد.
> كل niche يؤثر في: `NICHE_BANKS` (أي word banks تُقرأ)، `NICHE_STATIC_TERMS` (كلمات ثابتة للـ niche)،
> `COMMERCIAL_HEADS_BY_NICHE` (suffixes تجارية)، `NICHE_HINTS` في scoring (كلمات تزيد market_fit score)،
> و`_auto_generation_styles()` (أي styles تُختار تلقائياً لكل niche).

- [x] تحديث `NICHE_OPTIONS` في `constants.py` — القائمة الجديدة (9 niches):
  - `Tech & SaaS` (كان Tech & AI — SaaS أدق لأن AI يدخل عبر keywords، وSaaS نموذج تقني وليس مالي).
  - `Finance & Fintech` (كان Finance & SaaS — Fintech أدق تجارياً).
  - `E-commerce & Retail` (توسيع ليشمل retail brands).
  - `Health & Medical` (كان Health & Wellness — Medical أقوى تجارياً وأغلى دومينات).
  - `Real Estate & Property` (توسيع طفيف).
  - `Travel & Lifestyle` (يحل محل Creative & Arts — سوق أقوى بكثير: trip.com بيع بـ $30M).
  - `Education & Learning` (جديد — سوق ضخم عالمياً مفقود تماماً).
  - `Legal & Professional` (جديد — دومينات غالية جداً تاريخياً: law.com, legal.com).
  - `Crypto & Web3` (جديد — سوق نشط ومتميز: defi.com, token.com).
- [x] تحديث `NICHE_BANKS` في `generator.py` — ربط كل niche جديد بملفات word banks المناسبة.
  - مثال: `"Education & Learning": ("education", "tech", "common_modifiers")`.
  - مثال: `"Crypto & Web3": ("crypto", "tech", "finance")`.
- [x] تحديث `NICHE_STATIC_TERMS` في `generator.py` — إضافة كلمات ثابتة لكل niche جديد.
  - مثال Education: `("learn", "course", "class", "tutor", "academy", "study", "mentor", "campus")`.
  - مثال Legal: `("law", "legal", "counsel", "patent", "comply", "contract", "court", "license")`.
  - مثال Travel: `("trip", "tour", "book", "stay", "flight", "lodge", "voyage", "resort")`.
  - مثال Crypto: `("chain", "token", "block", "mint", "swap", "stake", "defi", "dao")`.
- [x] تحديث `COMMERCIAL_HEADS_BY_NICHE` — إضافة commercial suffixes لكل niche جديد.
  - هذه الـ heads تُستخدم في `_build_exact_candidates()` كـ anchors (مثل: keyword + "hub", keyword + "labs").
- [x] تحديث `NICHE_HINTS` في `scoring/scoring.py` — يؤثر على `market_fit_score()`.
  - بدون hints، الـ niches الجديدة ستأخذ 0 bonus في market fit → scores منخفضة بدون سبب.
- [x] تحديث `_auto_generation_styles()` في `generator.py` — تحديد أي styles تُختار تلقائياً لكل niche جديد.
  - مثال: Crypto → `["brandable", "compound", "short", "invented"]` (لا يحتاج exact أو geo عادة).
  - مثال: Legal → `["exact", "compound", "brandable", "geo"]` (exact مهم جداً في Legal).
- [x] إنشاء word bank files جديدة في `word_banks/`:
  - `education.txt` — كلمات تعليمية: learn, course, class, tutor, study, academy, scholar, mentor, campus, quiz.
  - `legal.txt` — كلمات قانونية: law, legal, counsel, court, patent, comply, contract, license, justice, verdict.
  - `travel.txt` — كلمات سفر: trip, tour, book, stay, flight, lodge, voyage, resort, cruise, explore.
  - `crypto.txt` — كلمات كريبتو: chain, token, block, mint, swap, stake, defi, dao, yield, protocol.
  - `commerce.txt` — كلمات تجارة (كان ضمنياً في creative): cart, shop, store, market, supply, brand, deal, catalog.
- [x] إعادة هيكلة word banks الحالية لإزالة التكرار (16 كلمة مكررة في 4+ ملفات):
  - إنشاء `common_modifiers.txt` — نقل الكلمات المشتركة مثل flow, nova, pulse, core, edge, shift, mode, zone, drive, cloud, grid, loop, phase, aura, vibe, bound, mode, point, peak, glow.
  - تنظيف `tech.txt` — إبقاء كلمات تقنية فقط: code, stack, node, mesh, api, sync, byte, bot, dev, logic, data, cyber.
  - تنظيف `finance.txt` — إبقاء كلمات مالية فقط: pay, fund, equity, credit, audit, ledger, trade, hedge, stock, bond, tax.
  - تحويل `creative.txt` → `brandable_fragments.txt` — مقاطع للتركيب: spark, mind, idea, vision, pixel, muse, hue, tone, blend, fuse.
  - تنظيف `power.txt` — حذف المكرر، إبقاء: boost, pro, master, elite, ultra, titan, force, surge, apex, bold, hero.
  - تنظيف `abstract.txt` — حذف المكرر مع common_modifiers، إبقاء: nexus, quantum, vertex, prime, zenith, arc, flux, omni, prism, halo, atom.
  - تنظيف `short_prefixes.txt` — حذف weak prefixes التي تنتج أسماء ضعيفة (get, my, the, try, use, go, on, in, it, be).
- [x] تحديث `utils/word_banks.py` — إضافة أسماء الملفات الجديدة لقراءتها عند التحميل.

## P0 - Scoring Profile Auto-Detect (حذف من UI + اكتشاف تلقائي)

> **السياق**: الـ Scoring Profile حالياً يُختار يدوياً من الـ UI (5 خيارات) لكنه **لا يؤثر في التوليد أصلاً**.
> هو يؤثر فقط في التقييم بعد التوليد — نفس الـ 200 candidate يتولدون بغض النظر عن الـ profile.
> هذا يربك المستخدم: يختار profile قبل التوليد ويظن أنه يؤثر في النتائج المولدة.
> الحل المتفق عليه: حذف الاختيار من الـ UI وجعل النظام يكتشف تلقائياً أنسب profile لكل domain بناءً على خصائصه.
> مثال: `dubaidental.com` يأخذ تلقائياً `geo_local`، و`nexaflow.ai` يأخذ `startup_brand` — بدون تدخل المستخدم.

### المرحلة 1: بناء منطق الاكتشاف التلقائي

- [x] إنشاء دالة `auto_detect_profile(name, tld, tokens, niche)` في `scoring/score_profiles.py`.
  - **المدخلات**: اسم الدومين بدون TLD، الـ TLD، الـ tokens (نتيجة tokenize_name)، الـ niche.
  - **المنطق بالترتيب** (أول match يكسب):
    1. لو tokens تحتوي geo term (من `GEO_HINTS` في scoring.py) + local service term (من `LOCAL_SERVICE_TERMS`) → `geo_local`.
    2. لو tokens تحتوي exact match term (من `EXACT_MATCH_TERMS`) + TLD هو .com أو .net → `seo_authority` (الاسم الجديد لـ seo_exact).
    3. لو token واحد أو اثنين + الاسم أقل من 8 حروف + TLD هو .com → `flip_fast`.
    4. الباقي → `startup_brand` (الـ default الآمن).
  - **ملاحظة**: `portfolio_premium` مؤجل — حالياً `flip_fast` يغطيه. يُضاف لاحقاً لو احتجنا معايير أدق.
- [x] إضافة unit tests لـ `auto_detect_profile()` في `tests/test_auto_detect_profile.py`:
  - `dubaidental.com` → `geo_local` (geo "dubai" + local "dental").
  - `repairtools.com` → `seo_authority` (exact match "repair" + "tools" + .com).
  - `nexaflow.ai` → `startup_brand` (brandable، ليس geo ولا exact، TLD ليس .com).
  - `data.com` → `flip_fast` (token واحد، 4 حروف، .com).
  - `cloudstackpromptlabs.io` → `startup_brand` (طويل جداً لـ flip_fast).
  - `cairolegal.com` → `geo_local` (geo "cairo" + local "legal").
  - `payflow.io` → `startup_brand` (ليس .com → ليس flip_fast).

### المرحلة 2: تحديث مسار التقييم في `app.py`

> **السياق**: حالياً `app.py` فيه loop ثلاثي: `for niche → for candidate → for ext → for scoring_profile`.
> الـ profile loop يعني أن كل domain يتقيم عدة مرات (مرة لكل profile مختار). هذا يُحذف ويُستبدل بـ call واحد مع auto-detect.

- [x] حذف `Scoring Profile` multiselect من sidebar — سطر 399-413 في `render_sidebar()`.
  - حالياً يعرض: `st.sidebar.multiselect("Scoring Profile", SCORING_PROFILES, ...)`.
  - يُحذف بالكامل مع الـ caption و`session_state.scoring_profile`.
- [x] حذف `selected_profiles` من return tuple لـ `render_sidebar()`.
  - حالياً الـ return يحتوي 9 عناصر → يصبح أقل بعد حذف profiles.
  - تحديث `render_generator_tab()` signature ليطابق.
- [x] حذف imports غير مطلوبة: `DEFAULT_SCORING_PROFILE`, `SCORING_PROFILES` من `app.py` imports.
- [x] تحديث `render_generator_tab()` سطر 572-606 — الـ loop الحالي:
  ```python
  # حالياً:
  for scoring_profile in scoring_profiles:  # ← هذا الـ loop يُحذف
      appraisal = evaluate_domain(full_domain, profile=scoring_profile, ...)
  # يصبح:
  detected_profile = auto_detect_profile(name, ext, tokens, niche)
  appraisal = evaluate_domain(full_domain, profile=detected_profile, ...)
  ```
  - ملاحظة: `tokenize_name()` مطلوب هنا لتمرير tokens للـ auto_detect. يمكن استدعاؤه مرة واحدة.
- [x] عرض الـ profile المكتشف في النتائج بوضوح: `"Profile: Geo Local (auto)"`.
  - في سطر 659: تغيير `get_profile(appraisal['profile']).label` → إضافة `(auto)` بجانبه.
- [x] تحديث `render_generation_debug_panel()` — حذف أي ذكر لـ selected profiles.
- [x] تحديث `render_methodology_status()` — إضافة شرح أن الـ profile يُكتشف تلقائياً.

### المرحلة 3: تبسيط Scoring Profiles ذاتها

> **السياق**: `seo_exact` يُعاد تسميته لـ `seo_authority` (أوصف وأشمل). `ai_brand` يُحذف لأن "AI" هو niche
> وليس استراتيجية بيع — startup_brand يغطي نفس الحالات.

- [x] إعادة تسمية `seo_exact` → `seo_authority` في `scoring/score_profiles.py`:
  - تغيير الـ key في `PROFILE_MAP` + `ScoreProfile.key` + `ScoreProfile.label`.
  - الـ description يصبح: "Clear exact-match and commercial-intent names with authority-site potential."
- [x] حذف `ai_brand` من `PROFILE_MAP`:
  - السبب: auto-detect لا يحتاجه — الدومينات AI تأخذ `startup_brand` (نفس المعايير تقريباً).
  - الفرق الوحيد كان: `.ai` preferred بدل `.com` → لكن startup_brand يعطي `.ai` درجة 8/10 أصلاً.
- [x] تحديث `hard_filters.py` سطر 104 — تبديل `"seo_exact"` → `"seo_authority"`.
- [x] تحديث `scoring.py` — كل reference لـ `"seo_exact"` يصبح `"seo_authority"` (حوالي 4 أماكن).

### المرحلة 4: تحديث باقي الملفات المتأثرة

- [x] تحديث `constants.py`:
  - حذف `SCORING_PROFILES` list و`DEFAULT_SCORING_PROFILE` من الـ exports العامة.
  - الـ profiles تبقى في `score_profiles.py` كـ internal logic فقط.
- [x] تحديث `storage.py`:
  - `add_to_portfolio()` سطر يحفظ `scoring_profile` → يتأكد أنه يحفظ الـ auto-detected profile بشكل صحيح.
- [x] تحديث `providers/llm.py`:
  - `ai_suggest_keywords_from_topic()` سطر 819 تستقبل `profiles` parameter → تُحذف أو تُبسط.
  - حالياً تمرر profiles للـ prompt: `f"Selected scoring profiles: {profile_context}."` → يُحذف هذا الجزء.
- [x] فحص `pages/` و`utils/` — grep لأي reference لـ `scoring_profile` أو `SCORING_PROFILES` وتحديثه.
- [x] فحص `jobs/sync_generated_opportunities_to_backend.py` — لو يستخدم profile يتم تحديثه.

## P0 - التحقق والتوثيق (بعد المهمتين)

> **السياق**: بعد إنهاء إعادة الهيكلة + Auto-Detect، لازم نتأكد أن كل شيء يعمل صح
> وأن الـ docs محدثة لأن التغييرات تمس: constants, generator, scoring, llm, app, word_banks.

- [x] تشغيل `python3 -m pytest tests/ -q` — التأكد أن الـ tests القديمة ما انكسرت + الـ tests الجديدة تمر.
- [x] تشغيل التطبيق محلياً `streamlit run app.py` كـ startup smoke test.
- [x] اختبار يدوي داخل Streamlit:
  - التوليد offline بـ niches مختلفة (Tech & SaaS, Legal & Professional, Crypto & Web3) — التأكد أن كل niche يولد أسماء منطقية.
  - التوليد online (LLM) — التأكد أن الـ prompt الجديد يذكر compound/invented بدل hybrid/outbound.
  - التأكد أن auto-detect يعطي profiles منطقية — تجربة: keyword "dubai dental" → يجب أن يظهر "Profile: Geo Local (auto)".
  - التأكد أن الـ UI لا يعرض Scoring Profile selector في الـ sidebar.
  - التأكد أن النتائج تعرض "(auto)" بجانب الـ profile المكتشف.
  - التأكد أن Word Banks tab يعرض الملفات الجديدة (education, legal, travel, crypto, commerce, common_modifiers).
- [x] تحديث `docs/PROJECT_OVERVIEW.md`:
  - ذكر أن الـ Niches صارت 9 بدل 6 مع أسمائها الجديدة.
  - ذكر أن Generation Styles صارت 6 (exact, brandable, compound, short, invented, geo).
  - ذكر أن Scoring Profile أصبح auto-detect بدل اختيار يدوي.
- [x] تحديث `docs/SYSTEM_FLOW.md` — تحديث pipeline flow ليعكس: generation → auto_detect_profile → evaluate.
- [x] تحديث `README.md` — لو فيه ذكر للـ profiles أو styles القديمة (hybrid, outbound, ai_futuristic, ai_brand).

## P0 - تحسين وضع Auto وزيادة تنوع التوليد (Auto Mode Generation Boost)

> **السياق**: في وضع Auto كان `per_mode_limit` محدود بـ 8 فقط لكل نمط، والـ builders كانت تستخدم
> حدود داخلية ضيقة (5 keywords، 5 suffixes...). النتيجة: عدد دومينات قليل وتنوع محدود.
> المطلوب: عند اختيار Auto يتم توليد المزيد من الدومينات بجميع الأنماط الستة.

### توسيع مجموعات المفردات (Vocabulary Pools)

- [x] توسيع `INVENT_PREFIXES` من 12 → 21 عنصر مع تغطية صوتية أوسع.
- [x] توسيع `INVENT_SUFFIXES` من 12 → 15 عنصر.
- [x] توسيع `BRANDABLE_PREFIXES` من 12 → 23 عنصر مع إضافة بادئات جديدة (am, co, en, ev, in, lu, nav, qu, ri, su, vi).
- [x] توسيع `BRANDABLE_SUFFIXES` من 12 → 21 عنصر مع إضافة نهايات (ai, ana, ea, ify, ity, ly, o, on, ux).
- [x] توسيع `SHORT_ENDINGS` من 14 → 21 عنصر.
- [x] توسيع `HYBRID_SUFFIXES` من 13 → 44 عنصر — إضافة لواحق تجارية جديدة (bit, box, craft, deck, drop, edge, gate, hive, link, mark, mind, nest, node, ops, pad, path, pod, point, port, pulse, rise, shift, space, spark, spot, sync, verse, wave, wire, works, zone).

### رفع حدود التوليد في وضع Auto

- [x] تحديث `generate_domains()` — إضافة `is_auto` detection:
  - Auto: `per_mode_limit = max(15, min(num_per_tier + 10, 30))` (كان max 8).
  - غير Auto: `per_mode_limit = max(6, min(num_per_tier, 12))` (كان max 8).
- [x] رفع limits لكل builder في الـ candidate_sets:
  - exact: `per_mode_limit + 5` (كان +2).
  - compound: `per_mode_limit + 5` (كان +2).
  - brandable: `per_mode_limit + 3` (كان +1).
  - invented: `per_mode_limit + 2` (كان +0).
  - short: `max(8, per_mode_limit)` (كان max(4, -1)).
  - geo: `max(6, per_mode_limit - 2)` (كان max(4, -2)).

### تحسين الـ Builders الداخلية

- [x] `_support_terms_for_niche()` — رفع حدود الكلمات: static 14 (كان 10)، bank 14 (كان 8)، prefixes 6 (كان 4)، إجمالي 28 (كان 16).
- [x] `_build_exact_candidates()` — keywords[:8] (كان [:5])، heads[:10] (كان [:6])، إضافة تركيبات متقاطعة بين الكيوردز (exact_cross).
- [x] `_build_compound_candidates()` — keywords[:8] (كان [:5])، suffixes[:12] (كان [:5])، إضافة تركيبات عكسية (compound_reverse).
- [x] `_build_brandable_candidates()` — endings 10 (كان 6)، prefixes 10 (كان 6)، إضافة twist + نهايات مبتكرة (ify, ly, ux, ai).
- [x] `_build_invented_candidates()` — seed_terms[:6] (كان [:4])، إضافة تركيبات مع INVENT_PREFIXES + أسماء مخترعة بحتة.
- [x] `_build_short_candidates()` — roots 10 (كان 6)، endings[:6] (كان [:3])، keywords[:6] (كان [:3]).

## P0 - تنفيذ تحسينات جودة التوليد والتقييم الحالية

- [x] تنفيذ مراحل تحسين جودة الأسماء القصيرة والمخترعة، scoring/filtering، word banks، cross-niche dedup، وLLM prompt/count كما طلب المستخدم.
- [x] `_build_geo_candidates()` — geo[:5] (كان [:3])، services[:8] (كان [:4])، suffixes 7 (كان 4).

### التحقق

- [x] تشغيل `python3 -m pytest tests/ -q` — 38 passed بدون أخطاء.
- [x] اختبار يدوي: توليد offline بنفس المدخلات والتأكد من زيادة عدد وتنوع الدومينات.

## P1 - تحسين جودة نتائج التوليد (Generation Results Quality)

> **السياق**: الدومينات المولدة حالياً تعاني من عدة نقاط ضعف:
> 1. تكرار في الجذور — أسماء كثيرة تبدأ بنفس الـ root (مثل `agen*` عند keyword "agentic").
> 2. أسماء طويلة أو صعبة النطق تمر من الفلاتر وتأخذ scores منخفضة بدلاً من أن تُحذف مبكراً.
> 3. ضعف تنوع الأنماط — compound و exact يسيطرون، بينما invented و short ينتجون عدد أقل.
> 4. الـ scoring يعطي نتائج متقاربة لأسماء مختلفة الجودة.
> 5. keyword واحد يسيطر على الأغلبية — لا يوجد توزيع عادل بين الـ keywords.
> 6. عند اختيار أكثر من niche، التكرار يزيد لأن نفس الـ candidates تتقيم عدة مرات.

### المرحلة 1: تحسين تنوع التوليد (Generation Diversity)

- [x] إضافة `_diversity_filter()` في `generator.py` — بعد التوليد وقبل الإرجاع:
  - حساب root لكل candidate (أول 4 حروف).
  - لكل root مكرر أكثر من 3 مرات، الاحتفاظ بأفضل 3 فقط (حسب الطول والنهاية).
  - الهدف: تقليل `agentflow, agentlabs, agentmesh, agenthub, agentcore...` إلى أفضل 3.
- [x] إضافة `keyword_rotation` في الـ builders — بدل `for keyword in input_terms[:8]` متسلسل:
  - Round-robin بين الـ keywords: كل keyword يأخذ دوره قبل أن يعود الأول.
  - الهدف: keyword واحد لا يسيطر على كل النتائج.
- [x] إضافة `style_balance` في `generate_domains()`:
  - بعد التوليد، حساب عدد candidates لكل style.
  - لو style واحد أكثر من 40% من الإجمالي، تقليصه لـ 30% والاحتفاظ بالأفضل.
  - الهدف: توزيع متوازن بين الـ 6 أنماط.
- [x] إضافة تركيبات `multi-keyword` في `_build_exact_candidates()`:
  - دمج keyword1_front + keyword2_back (مثل: `agent` + `academy` → `agenacad` → يُفلتر لو ضعيف).
  - الهدف: أسماء فريدة لا يمكن توليدها من keyword واحد.

### المرحلة 2: تحسين جودة الأسماء القصيرة والمخترعة (Short & Invented Quality)

- [x] تحسين `_build_short_candidates()`:
  - إضافة `_is_pronounceable()` check سريع (نسبة vowels بين 30%-60%) — رفض الأسماء غير القابلة للنطق مبكراً.
  - إضافة تركيبات consonant+vowel+consonant+vowel (CVCV pattern) — أقوى أنماط الأسماء القصيرة (مثل: `vexa`, `nelo`, `zura`).
  - رفع حد الأسماء القصيرة من 6 إلى 7 حروف — يفتح المجال لأسماء مثل `nexflow`, `aistack`.
- [x] تحسين `_build_invented_candidates()`:
  - إضافة `syllable_builder` — بناء أسماء من مقاطع صوتية (CV+CV+CV) بدل prefix+suffix فقط.
  - إضافة `blend_keywords` — مزج مقطعين من كيوردز مختلفة (مثل: `agent`+`solution` → `agensol`).
  - إضافة rejection لأسماء مخترعة بدون vowels كافية.

### المرحلة 3: تحسين الـ Scoring والفلترة (Scoring & Filtering)

- [x] تحسين `pronounceability_score()` في `scoring.py`:
  - إضافة bonus للأسماء التي تتبع نمط CVCV أو CVC.
  - إضافة penalty أقوى للأسماء التي تحتوي 3+ consonants متتالية.
- [x] تحسين `brandability_score()`:
  - إضافة bonus للأسماء التي تنتهي بـ vowel (أسهل في النطق والتذكر).
  - إضافة bonus للأسماء المكونة من مقطعين صوتيين واضحين.
  - تقليل bonus الـ `GOOD_SUFFIXES` لو الاسم أطول من 12 حرف — suffix جيد لا يعوض طول مفرط.
- [x] تحسين `market_fit_score()`:
  - إضافة keyword_match bonus — لو الاسم يحتوي keyword المستخدم حرفياً.
  - إضافة `cross_niche_penalty` — لو الاسم يحتوي مصطلح من niche مختلف عن المختار.
- [x] إضافة `early_reject` في `generate_domains()`:
  - قبل إرسال الـ candidates للـ scoring الكامل، فحص سريع:
    - رفض أي اسم أطول من 15 حرف.
    - رفض أي اسم يحتوي 4+ consonants متتالية.
    - رفض أي اسم نسبة vowels فيه أقل من 20%.
  - الهدف: تقليل عدد الأسماء الضعيفة التي تأخذ وقت scoring كامل.

### المرحلة 4: تحسين Word Banks والمفردات (Vocabulary Enrichment)

- [x] إثراء `SPECIAL_ROOTS` في `generator.py`:
  - إضافة roots للكلمات الشائعة في كل niche: `crypto→cryp`, `travel→trav`, `academy→acad`, `solution→sol`.
  - الهدف: brandable و invented أفضل من كلمات طويلة.
- [x] إثراء `NICHE_STATIC_TERMS` — إضافة 5 كلمات إضافية لكل niche:
  - Tech: `saas`, `infra`, `deploy`, `pipeline`, `runtime`.
  - Crypto: `protocol`, `liquidity`, `governance`, `oracle`, `bridge`.
  - Travel: `discover`, `wander`, `roam`, `retreat`, `getaway`.
  - E-commerce: `checkout`, `listing`, `vendor`, `fulfil`, `dropship`.
- [x] إضافة `premium_words.txt` word bank جديد — كلمات معروفة بقيمة دومين عالية:
  - `core`, `nest`, `mint`, `vault`, `apex`, `prime`, `nexus`, `pulse`, `shift`, `edge`.
  - يُستخدم كـ fallback في كل الـ niches لإنتاج أسماء أقوى.
- [x] مراجعة `short_prefixes.txt` — حذف prefixes ضعيفة متبقية وإضافة prefixes أقوى:
  - حذف: أي prefix أقل من 3 حروف لا ينتج أسماء قابلة للبيع.
  - إضافة: `zen`, `neo`, `arc`, `lux`, `axi`, `ori`, `evo`.

### المرحلة 5: تحسين التعامل مع Multiple Niches (Cross-Niche Optimization)

- [x] تحسين deduplication عبر الـ niches في `app.py`:
  - حالياً كل candidate يتقيم × كل niche × كل extension — تكرار كبير.
  - المطلوب: كل candidate يتقيم مرة واحدة مع **أنسب niche** له (عبر auto-detect أو keyword match).
  - أو: الاحتفاظ بأعلى score لكل domain عبر الـ niches بدل عرض التكرارات.
- [x] إضافة `niche_affinity_score()`:
  - لكل candidate، حساب أي niche هو الأقرب بناءً على الـ tokens.
  - استخدام أعلى affinity niche للتقييم بدل تقييم كل الـ niches.

### المرحلة 6: تحسين الـ LLM Integration (Online Engine Quality)

- [x] زيادة `count` في `llm_creative_boost()` عند Auto mode:
  - حالياً `count = max(num_per_tier, len(user_keywords), 8)` — قد يكون 15 فقط.
  - في Auto: `count = max(num_per_tier * 2, len(user_keywords) * 3, 20)` — طلب عدد أكبر من الـ LLM.
- [x] إضافة `style_distribution` في الـ LLM prompt:
  - حالياً الـ prompt يعطي قائمة styles بدون توزيع.
  - المطلوب: `"Generate approximately {count_per_style} names per style."`.
  - الهدف: الـ LLM ينتج أسماء موزعة بالتساوي على كل الأنماط.
- [x] إضافة `negative_examples` في الـ LLM prompt:
  - تمرير أمثلة على أسماء ضعيفة مع سبب الرفض.
  - الهدف: الـ LLM يتعلم تجنب الأنماط الضعيفة.
- [x] تحسين `_build_domain_generation_prompt()` — إضافة قسم `naming patterns`:
  - أنماط أسماء ناجحة تاريخياً: `stripe`, `notion`, `linear`, `vercel`, `supabase`.
  - الهدف: توجيه الـ LLM نحو أنماط تسمية مثبتة تجارياً.

### المرحلة 7: هيكلة الأولوية للكلمات المفتاحية (Keyword-First Architecture)

- [x] تعديل `generator.py` للفصل بين الـ user_keywords والـ support_terms.
- [x] إزالة خوارزمية الـ round-robin التي كانت تهمش كلمات المستخدم.
- [x] تعديل جميع دوال الـ builders (`_build_exact_candidates` وغيرها) للتركيز على كلمات المستخدم في المرور الأول.
- [x] تقييد توليد الأسماء المخترعة العشوائية البحتة إلى 20٪ كحد أقصى.
- [x] إضافة مكافأة تطابق الكلمات المفتاحية (`market_fit_score`) في `scoring.py`.
- [x] تعديل `_diversity_filter` للسماح بتكرار جذور كلمات المستخدم بشكل أكبر (حتى 6 تكرارات بدلاً من 3).

### التحقق

- [x] اختبار A/B: توليد بنفس المدخلات قبل وبعد التحسينات ومقارنة:
  - عدد الأسماء الفريدة.
  - توزيع الأنماط (exact/brandable/compound/short/invented/geo).
  - متوسط الـ score.
  - نسبة الأسماء بـ Grade A+ و A.
  - نسبة الأسماء المرفوضة (Reject).
- [x] إضافة unit tests لـ `_diversity_filter()` و`_is_pronounceable()`.
- [x] تحديث `docs/PROJECT_OVERVIEW.md` بعد إنهاء التحسينات.

- [x] استكمال repository write path للـ valuation runs.
- [x] استكمال persistence للـ valuation reason codes.
- [x] إضافة endpoint أو job trigger لتقييم دومين مولد.
- [x] توحيد aliases بين API schemas وmodels المؤجلة.
- [x] إضافة integration tests لرحلة domain -> classification -> valuation -> report.

## P1 - Reports

- [x] جعل report generation يستهلك valuation runs الناتجة من bridge.
- [x] دعم refused valuation reports بوضوح.
- [x] إضافة AI explanation validation قبل إدخالها في التقرير.
- [x] توثيق report input requirements في docs عند اكتمالها.

## P1 - Watchlists and Alerts

- [x] استكمال alert events.
- [x] استكمال alert deliveries.
- [x] إضافة deduplication واضح للأحداث.
- [x] إضافة actor/org context لمسار remove watchlist item.
- [x] ضبط vocabulary للـ alert rules.

## P1 - Marketplace and Enrichment

- [x] توثيق قرار rate limits وuser agent لكل marketplace.
- [x] اختيار WHOIS/RDAP provider حقيقي أو policy واضحة للـ unavailable providers.
- [x] إضافة DNS provider إنتاجي أو توثيق fallback.
- [x] إضافة website-check retention policy.

## P2 - Streamlit Trend Pipeline

- [x] تحسين clustering وربط themes المتقاربة.
- [x] تحسين trademark awareness بقوائم أوسع.
- [x] إضافة source-driven explanations أعمق في UI.
- [x] جعل LLM refinement يكتب مخرجات قابلة للتتبع لا تختلط بالحقائق.
- [x] توحيد عرض legacy score وbackend valuation.

## P2 - Testing and Hardening

- [x] تثبيت pytest في البيئة المحلية أو توثيق venv رسمي.
- [x] تشغيل `python3 -m unittest discover -s tests -v`.
- [x] تشغيل `python3 -m pytest backend/tests -q`.
- [x] إضافة CI يفحص root tests وbackend tests.
- [x] إضافة smoke test للـ bridge المقترح.
- [x] إضافة logging/correlation ids للـ jobs الجديدة.

## Tests

- [x] تنفيذ Full App Restructure And Integration Hardening:
  - [x] استخراج Streamlit generation workflow إلى module pure قابل للاختبار.
  - [x] تحسين واجهة Streamlit كلوحة تشغيلية بدون تغيير semantics.
  - [x] تقوية generated-domain backend integration مع الحفاظ على API compatibility.
  - [x] إضافة SQLite-backed repository tests للـ watchlists/alerts/reports/opportunities.
  - [x] إضافة Dynadot API skeleton آمن بدون تفعيل production fetching.
    - [x] Worker 3: إضافة Dynadot API-first skeleton/config/tests مع بقاء production scraping disabled افتراضيًا.
  - [x] تحديث docs وتشغيل root/backend verification.
- [x] مراجعة tests الحالية في مسار الجذر والـ backend مقابل الكود الفعلي.
- [x] تشغيل test suites الحالية وتسجيل failures والاختناقات البطيئة.
- [x] تحسين test output ليكون أوضح عند الفشل ويعرض سياقًا عمليًا.
- [x] إضافة أو تحسين اختبارات تغطي وظائف التطبيق الأساسية end-to-end حيث يمكن ذلك محليًا.
- [x] إضافة performance smoke checks للوظائف الحرجة بدون الاعتماد على خدمات خارجية.
- [x] تحديث توثيق التشغيل أو CI إذا تغيّر أمر تشغيل الاختبارات أو مخرجاتها.
- [x] إضافة SQLite-backed repository tests لمسارات watchlists/alerts/reports/opportunities بدل الاعتماد الكامل على fake services.
- [x] إضافة tests لمسار Streamlit generation workflow بعد استخراج منطق pure أو mocking واضح لـ Streamlit.
- [x] توسيع tests لـ LLM JSON parsing وnormalization edge cases.
- [x] توسيع tests لـ LLM provider branches مثل no-key وprimary success وfallback failure.
- [x] توسيع tests مباشرة لـ scoring hard filters وgrade/tier boundaries وkeyword market-fit bonus.

## Human Decisions

- [x] الموافقة على طريقة الوصول لـ Dynadot وDropCatch — Dynadot API-first، وDropCatch production disabled حتى اعتماد مصدر رسمي.
- [x] تحديد scraping frequency وretry policy — delay `1.5s`, max `10` pages/run, retries `3` مع backoff `1.5s` للـ transient HTTP فقط.
- [x] اختيار RDAP/WHOIS provider — RDAP-first، WHOIS fallback اختياري، وUnavailable provider لا يكتب facts.
- [x] اعتماد valuation thresholds — thresholds الحالية معتمدة كـ `v1 beta` محافظة وليست pricing guarantee.
- [x] اعتماد legal/trademark risk policy — high risk يمنع priced output، medium risk يفرض `needs_review`.
- [x] تحديد أول alert delivery channels — Slack incoming webhook أولًا، email مؤجل.
- [x] اعتماد AI provider/model policy — OpenRouter عبر `OPENROUTER_API_KEY` هو online path الافتراضي مع offline fallback.
- [x] تحديد retention policy للـ raw payloads وwebsite artifacts — raw marketplace payloads `30 days`، website raw artifacts disabled، website metadata `90 days` أو حتى superseded.

## Policy Implementation Follow-ups

- [x] تنفيذ Slack alert delivery provider وربطه بـ `alert_deliveries` بدون خلطه مع alert events.
- [x] إضافة dispatcher/job يستدعي delivery providers للأحداث الجديدة أو retryable failures.
- [x] إضافة enforcement/cleanup job لـ raw marketplace payload retention لمدة `30 days`.
- [x] إضافة enforcement/cleanup job لـ website metadata retention لمدة `90 days` أو superseded.
- [x] توثيق/تنفيذ Dynadot API adapter path قبل أي production Dynadot scraping fallback.
- [x] إبقاء DropCatch production fetching disabled حتى اعتماد source رسمي أو إذن واضح.
