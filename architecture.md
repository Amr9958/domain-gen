# Domain Intelligence SaaS Architecture

## Short Summary
The system is a modular, evidence-first domain intelligence platform. Marketplace adapters collect raw auction data, normalization converts it to canonical auctions, enrichment records verified facts, signal builders compute derived signals, classification determines domain type, valuation produces explainable price ranges or refusal states, and reports and alerts expose the results to users.

## Architecture Principles
- Preserve raw source evidence before transforming it.
- Normalize source-specific marketplace data into stable canonical entities.
- Store verified facts separately from derived signals and AI explanations.
- Classify every domain before valuation.
- Require structured reasoning for meaningful, high, and premium valuations.
- Keep modules independently testable and replaceable.
- Prefer asynchronous jobs for network-heavy and slow workflows.
- Make every customer-facing output traceable to stored input IDs.

## Logical Modules
`marketplaces`:
Responsible for source adapters such as Dynadot and DropCatch. Adapters fetch source data, capture raw payloads, and emit raw auction items.

`normalization`:
Converts raw source payloads into canonical domains, auctions, and auction snapshots. This module owns source-specific field mapping and validation.

`enrichment`:
Runs WHOIS/RDAP, DNS, and website checks. It stores verified facts and raw artifacts with provider metadata.

`signals`:
Computes derived signals from verified facts, domain text, auction history, and enrichment outputs. It owns algorithm versioning for non-AI computed features.

`classification`:
Classifies domain type, commercial category, language, structure, and risk flags before valuation. It consumes verified facts and derived signals.

`valuation`:
Produces value ranges, value tiers, confidence levels, structured reasoning, and refusal states. It consumes classification, verified facts, and derived signals.

`reports`:
Builds reproducible appraisal reports from valuation runs, facts, signals, classification results, and validated AI explanations.

`watchlists`:
Stores user and organization watchlists, watched domains, watched auctions, and rule subscriptions.

`alerts`:
Evaluates alert rules and records alert events and delivery attempts.

`ai_explanations`:
Generates readable explanations from approved structured inputs. It must not create verified facts or become the only support for a valuation.

`leads_future`:
Reserved boundary for future lead discovery and outbound readiness. It may consume domain intelligence outputs but must not mutate facts, signals, classifications, or valuations.

## Data Flow
1. A scheduled ingestion job starts an `ingest_run` for a marketplace.
2. The marketplace adapter captures raw source payloads as `raw_auction_items`.
3. The normalization module upserts `domains`, `auctions`, and `auction_snapshots`.
4. Enrichment jobs run for new or stale domains and store `verified_facts`.
5. Signal jobs compute `derived_signals` from facts, auction history, and domain text.
6. Classification jobs create `classification_results`.
7. Valuation jobs create `valuation_runs` and `valuation_reason_codes`.
8. Optional AI explanation jobs create `ai_explanations` from approved input references.
9. Report jobs create `appraisal_reports`.
10. Watchlist jobs evaluate `alert_rules`, create `alert_events`, and dispatch `alert_deliveries`.

## Runtime Shape
- API service handles authenticated user requests, admin requests, report reads, watchlist changes, and job scheduling requests.
- Worker service handles ingestion, enrichment, classification, valuation, reports, and alerts.
- Scheduler triggers recurring marketplace ingestion, stale enrichment refreshes, valuation refreshes, and alert evaluation.
- Database stores canonical state, audit logs, and relational links between evidence and outputs.
- Object storage may store large raw artifacts, screenshots, rendered reports, and archived payloads.
- Queue or job table coordinates retryable asynchronous work.

## Source Adapter Boundary
Marketplace adapters must return raw payload records and adapter metadata only. They must not classify, value, or alert.

Required adapter outputs:
- `marketplace_code`
- `source_item_id`
- `source_url`
- `captured_at`
- `raw_payload_json` or `raw_artifact_uri`
- `raw_payload_hash`
- `adapter_version`
- `parser_version`

## Normalization Boundary
Normalization owns canonical auction mapping. It must:
- Validate domain names and normalize to lowercase ASCII punycode where needed.
- Map source status to canonical auction status.
- Map source auction type to canonical auction type.
- Store unmapped source fields in `normalized_payload_json`.
- Create evidence references from normalized records back to raw auction items.

## Enrichment Boundary
Enrichment owns verified facts. It must:
- Record provider and observed time for every fact.
- Keep raw provider artifacts available by database JSON or object storage URI.
- Use explicit freshness rules per fact type.
- Avoid writing derived scores into fact storage.

## Classification Before Valuation
Valuation must depend on a classification result. If classification is missing, stale, or refused, valuation must return `refused` or `needs_review` rather than pricing the domain.

Initial domain types:
- `exact_match`
- `brandable`
- `keyword_phrase`
- `acronym`
- `numeric`
- `geo`
- `personal_name`
- `premium_generic`
- `typo_risk`
- `adult_or_sensitive`
- `unknown`

## Verified Facts, Derived Signals, and AI Explanations
Verified facts are stored as evidence-backed observations. Derived signals are computed outputs with algorithm versions. AI explanations are human-readable narratives with prompt and model metadata.

Hard rules:
- Facts can feed signals, classification, valuation, reports, and alerts.
- Signals can feed classification, valuation, reports, and alerts.
- AI explanations can feed reports only.
- AI explanations cannot create, edit, or replace facts.
- High-value outputs must cite fact and signal IDs, not only prose.

## Valuation Architecture
The valuation engine should be a pipeline:
- Input validation.
- Classification gate.
- Fact freshness gate.
- Risk gate.
- Signal aggregation.
- Comparable or heuristic valuation.
- Confidence assignment.
- Refusal or needs-review decision.
- Structured reasoning generation.
- Persistence of valuation run and reason codes.

Valuation must produce:
- `status`
- `refusal_code` when refused
- `estimated_value_min`
- `estimated_value_max`
- `estimated_value_point`
- `currency`
- `value_tier`
- `confidence_level`
- `reason_codes`
- `input_fact_ids`
- `input_signal_ids`
- `classification_result_id`
- `algorithm_version`

## Observability
Every job must log:
- Job ID.
- Correlation ID.
- Organization ID when applicable.
- Domain ID when applicable.
- Marketplace ID and source item ID when applicable.
- Adapter, parser, classifier, valuation, or prompt version when applicable.
- Retry count and terminal error code for failures.

Metrics should track:
- Ingested raw items by marketplace.
- Normalization success and failure counts.
- Enrichment latency and failure rates.
- Classification distribution by domain type.
- Valuation refusal rate by refusal code.
- Alert event and delivery counts.

## Security and Compliance
- Store secrets only in environment variables or a managed secret store.
- Redact credentials, cookies, API keys, and personal data from logs.
- Respect marketplace terms and approved scraping limits.
- Keep an audit log for user actions that affect watchlists, reports, settings, integrations, or schema-relevant configuration.
- Treat future lead data as sensitive and isolate it from v1 domain intelligence tables.

## Extension Rules
- Add new marketplaces by adding adapters and normalization mappings, not by changing valuation logic.
- Add new enrichment providers by implementing provider clients and fact mappers, not by changing report templates.
- Add new valuation models by creating a new algorithm version and migration path, not by mutating historical valuation outputs.
- Add future lead discovery behind a separate module boundary and separate database tables.
