# Domain Intelligence Execution Plan

## Purpose
This plan breaks the domain intelligence SaaS into safe, reviewable implementation phases. Worker agents should complete phases in order unless a reviewer explicitly approves parallel work.

## Phase 0: Foundation
Goal: Establish shared contracts and review rules.

Deliverables:
- `requirements.md`
- `architecture.md`
- `db_schema.md`
- `api_contracts.md`
- `coding_conventions.md`
- `review_protocol.md`
- `execution_plan.md`

Acceptance criteria:
- Foundation docs define product scope, non-goals, database entities, module contracts, folder conventions, schema change rules, manual decisions, and review workflow.
- Worker agents can identify where a proposed feature belongs.

## Phase 1: Core Data Model and Repositories
Goal: Implement the minimum database and persistence layer needed for canonical domain intelligence.

Deliverables:
- Migration for organizations, users, marketplaces, ingest runs, raw auction items, domains, auctions, auction snapshots, verified facts, derived signals, classification results, valuation runs, reports, watchlists, alerts, and audit logs.
- Repository methods for creating and reading the core entities.
- Tests for uniqueness, idempotency, and relationship constraints.

Acceptance criteria:
- Raw payloads, facts, signals, classifications, valuations, explanations, reports, and alerts are stored separately.
- Repository tests prove that valuation runs can reference classifications, facts, and signals.
- Schema docs and migrations match.

## Phase 2: Marketplace Adapter Framework
Goal: Create a reusable ingestion framework before implementing source-specific details.

Deliverables:
- `MarketplaceAdapter` interface.
- Ingestion run orchestration.
- Raw item persistence with payload hash and idempotency.
- Fixture strategy for parser tests.
- Source access configuration for rate limits, user agent, retries, and feature flags.

Acceptance criteria:
- A mock marketplace adapter can create raw auction items without normalization.
- Duplicate source payloads are suppressed or linked idempotently.
- Adapter failures produce structured errors.

## Phase 3: Dynadot Ingestion and Normalization
Goal: Ingest and normalize Dynadot auction data from approved sources.

Deliverables:
- Dynadot adapter.
- Dynadot parser fixtures.
- Dynadot normalizer mapping to canonical auctions.
- Tests for open, closing, closed, sold, unsold, and malformed source records when fixtures exist.

Acceptance criteria:
- Dynadot raw payloads are stored before normalization.
- Dynadot auctions upsert into canonical `domains`, `auctions`, and `auction_snapshots`.
- Unmapped Dynadot fields are preserved in `normalized_payload_json`.

Manual gate:
- Human approval of Dynadot source access method and rate limits.

## Phase 4: DropCatch Ingestion and Normalization
Goal: Add DropCatch without changing downstream valuation logic.

Deliverables:
- DropCatch adapter.
- DropCatch parser fixtures.
- DropCatch normalizer mapping to canonical auctions.
- Tests for source-specific edge cases.

Acceptance criteria:
- DropCatch and Dynadot records share the same canonical auction schema.
- Downstream enrichment, classification, and valuation can consume either source.

Manual gate:
- Human approval of DropCatch source access method and rate limits.

## Phase 5: Domain Enrichment
Goal: Create verified facts for domains from WHOIS/RDAP, DNS, and website checks.

Deliverables:
- RDAP or WHOIS provider client.
- DNS check provider.
- Website status checker.
- Enrichment run orchestration.
- Fact persistence and staleness rules.

Acceptance criteria:
- Enrichment outputs are stored as `verified_facts`.
- Website status checks create evidence-backed facts and a `website_checks` record.
- Provider failures are captured and retryable.
- No derived scores are stored as facts.

Manual gate:
- Human approval of WHOIS/RDAP provider, website-check policy, and retention rules.

## Phase 6: Derived Signals and Classification
Goal: Build repeatable domain signals and classify domain type before valuation.

Deliverables:
- Signal builders for domain length, token quality, TLD quality, auction momentum, DNS presence, and website-live status.
- Classification service using facts and signals.
- Risk flag detection for invalid, typo-risk, adult or sensitive, and legal-risk indicators.
- Tests for supported domain types and refusal or unknown cases.

Acceptance criteria:
- Signals include input references and algorithm versions.
- Classification results include domain type, confidence, risk flags, and input references.
- Valuation cannot produce `valued` output without classification.

## Phase 7: Explainable Valuation Engine
Goal: Produce value ranges, confidence levels, tiers, reason codes, and refusal states.

Deliverables:
- Valuation input validator.
- Classification gate.
- Fact freshness gate.
- Rule-based v1 valuation model.
- Value tier assignment.
- Refusal and needs-review logic.
- Structured reason codes.

Acceptance criteria:
- Missing classification returns `refused` with `missing_classification`.
- Unsupported or risky domains return refusal or needs-review states.
- Meaningful, high, and premium valuations include structured reasoning and evidence references.
- Tests cover valued, refused, and needs-review paths.

Manual gate:
- Human approval of valuation thresholds and legal-risk policy.

## Phase 8: Appraisal Reports
Goal: Generate reproducible reports from stored valuation outputs and evidence.

Deliverables:
- Report assembler.
- Report JSON schema.
- Optional validated AI explanation generation.
- Report read API.
- Tests for valued and refused reports.

Acceptance criteria:
- Reports distinguish facts, signals, classification, valuation, and AI explanations.
- Reports can be regenerated or audited from stored IDs.
- AI explanations include model, prompt version, input refs, and validation status.

Manual gate:
- Human approval of report format and AI usage policy.

## Phase 9: Watchlists and Alerts
Goal: Let users monitor domains and auctions with deduplicated alerts.

Deliverables:
- Watchlist CRUD.
- Watchlist item support for domains and auctions.
- Alert rules for auction ending soon, bid threshold, valuation tier change, and enrichment failure.
- Alert event deduplication.
- Alert delivery tracking.

Acceptance criteria:
- Alert events and delivery attempts are stored separately.
- Duplicate alerts are suppressed by event key.
- Alerts cite facts, auctions, valuations, or signals as trigger evidence.

Manual gate:
- Human approval of initial delivery channels.

## Phase 10: Production Hardening
Goal: Prepare the system for production operation.

Deliverables:
- Authentication and authorization enforcement.
- Organization scoping in all user-facing queries.
- Job retry and dead-letter handling.
- Observability dashboards.
- Audit log coverage.
- Backup and retention policy.
- Security review.

Acceptance criteria:
- User data is organization-scoped.
- Critical jobs are observable and retryable.
- Secrets are not logged or committed.
- Audit events exist for sensitive actions.

## Future Phase: Lead Discovery and Outbound Readiness
Goal: Add lead discovery after domain intelligence is stable.

Potential deliverables:
- Lead target schema proposal.
- Buyer category matching.
- Outbound readiness checks.
- Compliance review workflow.
- Contact data retention policy.

Required constraints:
- Lead discovery consumes domain intelligence outputs but does not mutate facts, signals, classifications, valuations, or reports.
- Contact data storage requires explicit human approval.
- Outbound sending is out of scope until separately approved.

## Parallel Work Guidance
Safe parallel work:
- One worker builds repository tests while another builds parser fixtures.
- One worker builds Dynadot adapter while another builds DropCatch adapter after the adapter interface is stable.
- One worker builds signal builders while another builds enrichment provider clients after fact contracts are stable.
- One worker builds report templates while another builds alert rules after valuation outputs are stable.

Avoid parallel work:
- Do not change schema and repositories independently without coordination.
- Do not change valuation tiers while another worker builds reports or alerts.
- Do not change classifier enums while another worker builds valuation gates.
- Do not add scraping behavior before source access decisions are approved.

## Risk Register
- Marketplace access restrictions may block or limit scraping.
- WHOIS/RDAP data may be incomplete or privacy-redacted.
- Website checks can create operational load and retention concerns.
- AI explanations can hallucinate if not constrained to stored inputs.
- Valuation outputs can be overtrusted if confidence and refusal states are weak.
- Lead discovery may introduce personal data and compliance obligations.

## Definition of Done
A phase or task is done when:
- It follows the foundation docs.
- It has tests or a documented verification gap.
- It preserves traceability from user-facing output to stored evidence.
- It records manual decisions instead of assuming them.
- It is reviewed using `review_protocol.md`.
