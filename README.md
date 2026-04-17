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

Today, the app works as a domain generation and evaluation system.

The current user flow is:

1. Select niche, scoring profile, keywords, and extensions
2. Optionally ask AI for keyword suggestions
3. Generate domain candidates
4. Score each candidate with resale-aware heuristics
5. Optionally run conservative availability checks
6. Review, favorite, export, or save to portfolio

## Existing Strengths We Will Reuse

These parts already map very well to the target architecture:

### Streamlit UI

The current app already provides:

- generator workflow
- word bank editing
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

This is already a useful foundation for the future `domain_engine` layer.

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
- preflight model checks

This can be extended into selective Gemini-style refinement later.

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

The future MVP should:

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
- Gemini Flash-Lite only for shortlist refinement
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

### Missing for the Target

- collectors for Hacker News, GitHub, and GNews
- shared normalized content schema
- topic deduplication and clustering
- theme extraction layer
- inferred commercial term extraction
- buyer-type mapping
- watchlist and rejected pipelines
- Supabase integration
- scheduled GitHub Actions jobs
- multi-page trend intelligence dashboard
- explicit `Buy / Watch / Skip` system for trend-derived opportunities

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

### Phase 1: Foundation

Add:

- centralized config
- environment variable support
- logging
- Supabase client integration
- shared typed data models

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

### Phase 3: Processing Layer

Implement:

- text cleaning
- normalization
- deduplication
- lightweight clustering
- source tagging
- topic-type heuristics

### Phase 4: Intelligence Layer

Implement:

- theme extraction
- raw term extraction
- inferred commercial terms
- naming component extraction
- niche mapping
- buyer-type hints

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

### Phase 6: Streamlit Dashboard Expansion

Add pages for:

- overview
- themes
- keywords
- domain ideas
- watchlist
- rejected items

### Phase 7: Scheduled Automation

Add GitHub Actions workflows for:

- collection
- processing
- domain generation
- shortlist refresh

### Phase 8: Selective LLM Refinement

Use Gemini only after filtering narrows the candidate set.

Good use cases:

- refining shortlisted themes
- improving inferred commercial terms
- improving niche classification
- explaining why a final domain idea is strong or weak

Bad use cases:

- processing every raw article
- bulk ingestion
- high-volume low-signal classification

## Proposed Supabase Data Model

The target MVP should introduce cloud tables close to:

### `content_items`

- `id`
- `source_name`
- `source_type`
- `title`
- `url`
- `body`
- `summary`
- `published_at`
- `fetched_at`
- `content_hash`
- `cluster_key`
- `language`
- `is_processed`

### `themes`

- `id`
- `canonical_name`
- `description`
- `first_seen_at`
- `last_seen_at`
- `momentum_score`
- `source_count`
- `status`

### `keywords`

- `id`
- `keyword`
- `keyword_type`
- `theme_id`
- `niche`
- `buyer_type`
- `commercial_score`
- `novelty_score`
- `brandability_score`
- `final_score`

### `domain_ideas`

- `id`
- `domain_name`
- `extension`
- `style`
- `root_keyword`
- `theme_id`
- `niche`
- `buyer_type`
- `linguistic_score`
- `commercial_score`
- `risk_score`
- `final_score`
- `status`
- `why_good`
- `why_risky`

### `runs`

- `id`
- `job_name`
- `started_at`
- `ended_at`
- `status`
- `notes`

### `rejected_items`

- `id`
- `item_type`
- `raw_value`
- `rejection_reason`
- `created_at`

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

Alternative entrypoint:

```powershell
streamlit run domaintrade_pro_v4.py
```

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

Future phases will likely add:

- `supabase`
- `httpx` or `requests`
- optional `pydantic`

## Documentation

Detailed current-project flow documentation is available in:

- `PROJECT_FLOW_EXPLAINED.md`

## Recommended Next Implementation Batch

The best first batch for the architecture upgrade is:

1. Add config management
2. Add `.env` support
3. Add a typed shared model layer
4. Add Supabase integration
5. Add the first collector: Hacker News

This keeps the scope controlled while moving the project toward the target system immediately.
