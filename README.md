# Trend-to-Domain Intelligence System

Free-first MVP for discovering domain-investing opportunities from fresh technology, AI, startup, dev-tool, and product-launch signals.

## Overview

This repository already contains a strong working core:

- a `Streamlit` app for domain generation and review
- a modular domain scoring engine
- hard filters for weak or risky names
- profile-based resale scoring
- optional LLM-assisted keyword and naming support
- session history, favorites, export, and portfolio storage

The next step is not to replace this codebase, but to evolve it into a broader `Trend-to-Domain Intelligence System` that starts from real external signals and ends with investor-grade domain shortlists.

## What This System Is

This project is being shaped into:

- a trend filtering engine
- a keyword intelligence engine
- a niche mapping engine
- a domain opportunity engine
- a resale-aware shortlist builder

This project is not intended to be:

- a generic chatbot
- a generic news dashboard
- a random domain generator
- a weak “available domains” scraper

## Current State

Today, the repository works as both:

- a domain generation and evaluation system
- a trend-to-domain intelligence review system

Alongside the original Streamlit workflow, the project now includes a broader trend-intelligence pipeline through Phase 8 with:

- raw ingestion jobs for Hacker News, GitHub, and GNews
- a separate processing job for cleaning, deduplication, clustering, and heuristic classification
- theme extraction with cross-run consolidation and raw/processed persistence metadata
- structured source tagging on themes via source names, source types, tags, and source entities
- keyword intelligence with niche and buyer hints
- a scored domain-opportunity job with `Buy / Watch / Skip` plus `shortlist / watchlist / rejected` review buckets
- source-aware exact-match and trademark-risk adjustments for generated domain ideas
- collector retry/backoff safety for transient API failures
- an integrated `Trends` tab in Streamlit for running the pipeline and reviewing outputs
- standalone Streamlit pages for `Trend Overview`, `Theme Explorer`, `Keyword Explorer`, `Shortlist Review`, `Watchlist Review`, and `Rejected Ideas`
- shared trend-dashboard helpers in `utils/trend_dashboard.py` so the tab and pages reuse the same logic
- optional AI refinement for the current visible theme, keyword, and shortlist slices inside Streamlit
- a scheduled GitHub Actions workflow for automated collection runs

The current user flow is:

1. Select niche, scoring profile, keywords, and extensions
2. Optionally ask AI for keyword suggestions
3. Generate domain candidates
4. Score each candidate with resale-aware heuristics
5. Optionally run conservative availability checks
6. Review, favorite, export, or save to portfolio

The trend-intelligence flow is:

1. Collect raw signals with `jobs/ingest_signals.py`
2. Process them into classified items, themes, and keywords with `jobs/process_signals.py`
3. Generate scored domain opportunities with `jobs/generate_domain_ideas.py`
4. Review `themes`, `keywords`, `shortlist`, `watchlist`, and `rejected` ideas in Streamlit
5. Optionally run selective AI refinement on the current visible slice

## Existing Strengths We Will Reuse

These parts already map very well to the target architecture:

### Streamlit UI

The current app already provides:

- generator workflow
- word bank editing
- trend intelligence review with pipeline controls
- favorites
- session history
- portfolio view
- stats view

Main entrypoints:

- `app.py`
- `domaintrade_pro_v4.py`

### Domain Generation Engine

`generator.py` already supports multiple generation patterns:

- keyword-based generation
- combine
- blend
- twist
- cut
- invent
- optional LLM creative boost

This is already a useful foundation for the broader `domain_engine` layer.

### Professional Scoring Core

The strongest existing asset in this repository is the scoring system:

- `scoring/scoring.py`
- `scoring/hard_filters.py`
- `scoring/score_profiles.py`
- `scoring/explanations.py`

It already includes:

- linguistic scoring
- brandability scoring
- market-fit scoring
- extension-fit scoring
- liquidity scoring
- hard rejection rules
- score caps and penalties
- resale tiers and value bands
- readable explanations

This matches the most important requirement: strong filtering and strong investor judgment.

### Unified LLM Layer

`providers/llm.py` already gives us:

- provider routing
- keyword suggestion from a topic
- word-bank enrichment
- domain naming boost
- selective review for visible theme, keyword, and shortlist slices
- preflight model checks

This now powers targeted refinement without turning the whole pipeline into an LLM-heavy workflow.

### Local Persistence and Utilities

The repo already has support for:

- local storage via `storage.py`
- session handling via `utils/session.py`
- word banks via `utils/word_banks.py`
- export helpers via `utils/export.py`
- browser helpers via `utils/browser.py`

## Target Evolution

The target product expands the current flow from:

`keywords -> generated domains -> scoring -> review`

into:

`signals -> cleaned items -> clustered topics -> themes -> keyword intelligence -> domain opportunities -> scoring -> shortlist -> review`

The expanded MVP should:

1. Collect fresh signals from:
   - Hacker News API
   - GitHub API
   - GNews Free
   - optional selective scraping of official sources
2. Normalize and deduplicate content
3. Cluster related topics
4. Classify topics into:
   - Investable
   - Watchlist
   - Low-value
   - Ignore
5. Extract:
   - raw terms
   - inferred commercial terms
   - naming components
   - niche tags
   - buyer-type hints
6. Generate domain opportunities
7. Filter weak domain ideas aggressively
8. Score and label results:
   - Buy
   - Watch
   - Skip
9. Store structured results in Supabase
10. Display everything in Streamlit

## Architecture Direction

The recommended architecture is modular and free-tier friendly.

### Infrastructure

- GitHub Free for repo and scheduled workflows
- Supabase Free for cloud storage
- Streamlit for the review dashboard
- low-cost LLM usage only for theme, keyword, and shortlist refinement
- No VPS
- No Raspberry Pi
- No Docker-first complexity
- No FastAPI in v1 unless a real need appears

### Recommended Modules

The long-term structure should move toward this:

```text
project/
  app/
    collectors/
    processors/
    intelligence/
    domain_engine/
    integrations/
    jobs/
    utils/
  pages/
  .github/workflows/
  streamlit_app.py
  README.md
```

## Gap Analysis

### Already Implemented

- Streamlit dashboard foundation
- domain generation engine
- investor-grade scoring engine
- LLM routing layer
- local portfolio storage
- export and review workflows
- collectors for Hacker News, GitHub, and GNews
- shared normalized content schema for collected items
- raw ingestion and processing jobs
- text cleaning, deduplication, clustering, and initial classification
- first-pass theme extraction with consolidation across similar historical themes
- structured source tagging for themes
- first-pass keyword intelligence, niche mapping, and buyer hints
- trend-derived domain opportunity generation with exact/descriptive/premium compact modes
- source-aware trademark and exact-match risk handling for trend-derived ideas
- review lanes for shortlist, watchlist, and rejected ideas
- multi-page Streamlit review surfaces for themes, keywords, shortlist, watchlist, and rejected ideas
- selective LLM refinement for visible theme, keyword, and shortlist slices
- scheduled GitHub Actions automation for the trend pipeline
- local JSONL and optional Supabase persistence for signal runs

### Missing for the Target

- advanced clustering and stronger topic-type heuristics
- stronger cross-source explanation detail and richer theme summaries
- stronger domain opportunity generation scoring and deeper trademark/exact-match heuristics
- broader closed-loop refinement that feeds AI review signals back into heuristics over time
- deeper automated test coverage around processors, jobs, and review helpers

## Merge Strategy

We will treat the current repository as the domain-evaluation core of the larger system.

That means:

- keep the existing app working
- keep the current scoring logic
- keep the current generator as the first domain engine
- add new ingestion and intelligence layers around it
- migrate storage gradually from local-only `SQLite` to cloud-backed `Supabase`

This is lower risk than a full rewrite and preserves the highest-value logic already built.

## Proposed Phased Plan

### Phase 0: Preserve the Working Core

Keep the current app operational while documenting the intended architecture.

Current status:

- completed
- the original generator, scorer, export flow, favorites, history, and portfolio workflows remain intact

### Phase 1: Foundation

Add:

- centralized config
- environment variable support
- logging
- Supabase client integration
- shared typed data models

Current status:

- completed through `config/`, `core/logging.py`, `integrations/supabase.py`, and `models/shared.py`
- `.env`-driven runtime settings and typed shared models are already in place

### Phase 2: Collection Layer

Implement collectors for:

- Hacker News API
- GitHub API
- GNews Free

Each collector should:

- fetch safely
- normalize output
- tag source metadata
- deduplicate before insert
- store raw items in Supabase

Current status:

- implemented with `jobs/ingest_signals.py`
- legacy compatibility kept through `jobs/collect_signals.py`, which now runs ingest, process, and domain-idea generation in sequence

### Phase 3: Processing Layer

Implement:

- text cleaning
- normalization
- deduplication
- lightweight clustering
- source tagging
- topic-type heuristics

Current status:

- implemented through `jobs/process_signals.py`
- now includes cleaning, deduplication, clustering, heuristic classification, source-aware theme building, and keyword intelligence extraction

### Phase 4: Intelligence Layer

Implement:

- theme extraction
- raw term extraction
- inferred commercial terms
- naming component extraction
- niche mapping
- buyer-type hints

Current status:

- implemented through `processors/themes.py` and `processors/keywords.py`
- now includes theme extraction, cross-run consolidation, raw/commercial/naming keyword layers, niche mapping, and buyer hints

### Phase 5: Domain Engine Expansion

Extend the current generator and scorer into a broader domain engine that adds:

- trend-derived domain generation
- exact/descriptive mode
- startup brandable mode
- premium compact mode
- dev-tool naming mode
- niche + action mode
- investor-style category naming
- buy/watch/skip labeling

Current status:

- implemented through `jobs/generate_domain_ideas.py`
- uses trend keywords to generate and score shortlist-ready `domain_ideas`
- now includes exact/descriptive/premium compact-style generation paths plus persisted review buckets

### Phase 6: Streamlit Dashboard Expansion

Add pages for:

- overview
- themes
- keywords
- domain ideas
- watchlist
- rejected items

Current status:

- dashboard integration is live inside `app.py` through the `🧭 Trends` tab
- the tab can run ingest/process/domain-idea jobs
- the tab now exposes dedicated `Shortlist`, `Watchlist`, and `Rejected` review lanes with exports and portfolio actions
- standalone Streamlit pages now exist in `pages/` for `Trend Overview`, `Theme Explorer`, `Keyword Explorer`, `Shortlist Review`, `Watchlist Review`, and `Rejected Ideas`
- shared trend-dashboard helpers now live in `utils/trend_dashboard.py` so the tab and pages reuse the same review logic

### Phase 7: Scheduled Automation

Add GitHub Actions workflows for:

- collection
- processing
- domain generation
- shortlist refresh

Current status:

- scheduled automation is live in `.github/workflows/trend_pipeline.yml`
- the workflow supports manual runs plus daily cron execution of `jobs/collect_signals.py`

### Phase 8: Selective LLM Refinement

Use a low-cost LLM only after filtering narrows the candidate set.

Good use cases:

- refining visible shortlisted themes
- improving inferred commercial terms
- improving niche classification
- explaining why a final domain idea is strong or weak

Bad use cases:

- processing every raw article
- bulk ingestion
- high-volume low-signal classification

Current status:

- selective refinement is live for the current visible `Themes`, `Keywords`, and `Shortlist` slices inside Streamlit
- theme and keyword review panels now run through `utils/trend_dashboard.py` and are exposed in both the unified tab and the standalone pages
- AI still reviews only filtered visible slices and returns investor-style notes instead of generating new names

### Roadmap Status

The roadmap defined in this README is currently implemented through `Phase 8`.

What remains now is not a missing numbered phase from this document, but follow-up improvement batches such as:

- stronger clustering and topic heuristics
- feedback loops from AI review into heuristics
- deeper exact-match / trademark safety
- stronger tests and deployment hardening

## Current Supabase-Aligned Data Model

The current schema in `supabase/schema.sql` centers on these tables:

### `portfolio_domains`

- `full_domain`
- `name`
- `ext`
- `niche`
- `appraisal_tier`
- `appraisal_value`
- `score`
- `scoring_profile`
- `explanation`
- `status`

### `content_items`

- `source_name`
- `source_type`
- `title`
- `url`
- `body`
- `summary`
- `author`
- `language`
- `content_hash`
- `cluster_key`
- `cluster_terms`
- `classification`
- `theme_name`
- `theme_description`
- `signal_score`
- `published_at`
- `fetched_at`
- `processed_at`
- `tags`
- `reasons`
- `raw_payload`
- `is_processed`
- `ingest_run_id`
- `processed_run_id`

### `themes`

- `canonical_name`
- `description`
- `classification`
- `source_count`
- `first_seen_at`
- `last_seen_at`
- `momentum_score`
- `related_terms`
- `source_names`
- `source_types`
- `source_tags`
- `source_entities`

### `keywords`

- `keyword`
- `keyword_type`
- `theme_name`
- `classification`
- `niche`
- `buyer_type`
- `commercial_score`
- `novelty_score`
- `brandability_score`
- `notes`

### `domain_ideas`

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

### `runs`

- `run_id`
- `job_name`
- `status`
- `started_at`
- `ended_at`
- `notes`

## Free-First Tradeoffs

To stay realistic and low-cost in v1:

- use lightweight heuristics before LLMs
- use selective scraping only for official sources
- avoid building a heavy backend service too early
- avoid real-time infrastructure unless truly needed
- keep Streamlit as the main review surface
- keep GitHub Actions as the scheduler

If a feature is expensive or operationally heavy, the correct v1 answer is a lighter version, not premature complexity.

## Running the Current App

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the current Streamlit app:

```powershell
streamlit run app.py
```

The trend pages will appear in the Streamlit sidebar automatically.

Alternative entrypoint:

```powershell
streamlit run domaintrade_pro_v4.py
```

Run the jobs directly:

```powershell
python jobs/ingest_signals.py
python jobs/process_signals.py
python jobs/generate_domain_ideas.py
python jobs/collect_signals.py
```

Run the unit tests:

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions automation:

- workflow file: `.github/workflows/trend_pipeline.yml`
- manual execution: `workflow_dispatch`
- scheduled execution: daily cron
- unit test workflow: `.github/workflows/unit_tests.yml`

## Current Dependencies

See `requirements.txt`.

The current project already depends on:

- `streamlit`
- `pandas`
- `python-whois`
- `openai`
- `google-genai`
- `openpyxl`
- `namecheap-python`
- `groq`
- `python-dotenv`
- `supabase`

## Documentation

Detailed current-project flow documentation is available in:

- `PROJECT_FLOW_EXPLAINED.md`
- `MANUAL_SETUP.md`
- `مرحلة 1.md`
- `مرحلة 2.md`

## Recommended Next Improvement Batch

The most useful follow-up batch from here is:

1. Strengthen clustering and topic-type heuristics
2. Feed AI review signals back into heuristics instead of keeping them review-only
3. Improve trademark / exact-match risk scoring and cross-source explanations
4. Add targeted tests for processors, jobs, and dashboard helpers
5. Harden Supabase-first deployments and schema evolution

This keeps momentum on the highest-value remaining work without reopening already-completed foundation phases.
