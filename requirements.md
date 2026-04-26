# Domain Intelligence SaaS Requirements

## Purpose
This document defines the product and system requirements for a production-oriented domain intelligence SaaS. It is the shared source of truth for worker agents implementing auction ingestion, enrichment, classification, valuation, reports, watchlists, alerts, and future lead discovery.

## Product Scope
The product helps users discover, evaluate, monitor, and explain domain investment opportunities from domain marketplaces and enrichment sources.

In scope:
- Auction scraping and ingestion from domain marketplaces, starting with Dynadot and DropCatch.
- Normalization of source-specific auction data into one canonical auction schema.
- Domain enrichment using WHOIS/RDAP, DNS records, HTTP/HTTPS website checks, redirects, status codes, and basic content metadata.
- Domain classification before valuation, including domain type, commercial category, language, structure, and risk flags.
- Explainable valuation with value ranges, confidence levels, refusal states, and structured reasoning.
- Appraisal report generation from verified facts, derived signals, classification, valuation, and AI explanations.
- Watchlists and alerts for saved domains, auction changes, valuation changes, and expiration or closing windows.
- SaaS-oriented foundations including users, organizations, audit logs, background jobs, observability, and role-aware access.
- Future support for lead discovery and outbound readiness without coupling it to the v1 valuation pipeline.

## Non-Goals
The following are explicitly out of scope unless added by a future approved requirements change:
- Automated bidding, payment processing, registrar account control, or auction settlement.
- Guaranteeing resale prices, legal advice, trademark clearance, tax advice, or investment advice.
- Circumventing marketplace security controls, paywalls, CAPTCHAs, access restrictions, or terms of service.
- Full CRM functionality, email campaign sending, inbox management, or lead enrichment in v1.
- Real-time market making or high-frequency bid monitoring.
- Using AI-generated explanations as authoritative facts.

## User Roles
- `owner`: Manages organization settings, billing, users, integrations, and data retention rules.
- `analyst`: Reviews auctions, classifications, valuations, watchlists, alerts, and reports.
- `viewer`: Reads saved domains, reports, and alert history but cannot change scoring logic or integrations.
- `system_worker`: Internal service identity used for scheduled ingestion, enrichment, valuation, and alert jobs.

## Functional Requirements
Marketplace ingestion:
- The system must support independent source adapters for each marketplace.
- The first marketplace adapters must target Dynadot and DropCatch.
- Each adapter must preserve raw source payloads before normalization.
- Each adapter must record source URL, capture time, adapter version, parser version, and ingestion run ID.
- Ingestion must be idempotent for the same marketplace, source item ID, and auction snapshot time.
- Source adapters must not write directly to valuation, classification, report, or alert tables.

Auction normalization:
- The system must normalize all source-specific auction records into a canonical auction entity.
- Normalized auction fields must include marketplace, source item ID, domain, auction type, status, start time, end time, current bid, currency, bid count, source URL, first seen time, and last seen time.
- Source-specific fields that do not fit the canonical schema must be retained in `normalized_payload_json`.
- Auction snapshots must capture changing auction facts over time instead of overwriting all history.
- Normalization must preserve evidence references back to raw payloads.

Domain enrichment:
- The system must enrich domains through WHOIS/RDAP, DNS, and website status checks.
- Enrichment jobs must store verified facts separately from derived signals.
- Enrichment must record provider, observed time, raw artifact reference, parser version, and verification method.
- DNS checks must support common record families including A, AAAA, NS, MX, TXT, CNAME, SOA, and DNSSEC status when available.
- Website checks must follow redirects with a bounded redirect limit and record final URL, status code, TLS status, title when available, and content hash when captured.
- Failed enrichment attempts must be stored with failure reason and retry eligibility.

Classification:
- The system must classify domain type before pricing.
- Classification must produce a stable `domain_type` enum, confidence score, and reasoning inputs.
- Classification must identify risk flags that can block or reduce valuation confidence.
- Classification must not overwrite verified facts.
- Classification must be repeatable for the same input facts, signals, and classifier version.

Valuation:
- The valuation engine must run only after classification is available, unless it returns a refusal state explaining missing prerequisites.
- The engine must return one of: `valued`, `refused`, or `needs_review`.
- The engine must support confidence levels: `low`, `medium`, `high`.
- The engine must support refusal codes for insufficient evidence, unsupported domain type, legal risk, invalid domain, stale inputs, and conflicting facts.
- The engine must produce value ranges rather than a single unsupported price.
- Any valuation at or above the `meaningful` tier must include structured reasoning, evidence references, positive drivers, negative drivers, comparable logic when available, and confidence rationale.
- Valuation output must include the classification result ID used as an input.

Appraisal reports:
- Reports must be generated from stored facts, signals, classification results, valuation runs, and approved AI explanations.
- Reports must identify data freshness and confidence.
- Reports must include refusal state details when valuation is refused.
- Reports must not present AI prose as verified evidence.
- Reports must be reproducible from stored report JSON and referenced run IDs.

Watchlists and alerts:
- Users must be able to add domains and auctions to watchlists.
- Alert rules must support auction ending soon, bid threshold crossed, valuation tier change, domain status change, and enrichment failure.
- Alert events must be deduplicated by rule, subject, event type, and time bucket.
- Alert delivery must be recorded separately from alert event creation.
- Failed alert deliveries must be retryable without recreating the alert event.

Future lead discovery and outbound readiness:
- The data model must leave room for future lead targets, buyer categories, outbound readiness checks, and contactability signals.
- Future lead discovery must consume domain intelligence outputs without modifying verified facts or valuation runs.
- Outbound readiness must include compliance gates before any sending or campaign automation is introduced.

## Technical Requirements
- Use a modular architecture with clear boundaries between ingestion, normalization, enrichment, classification, signals, valuation, reports, watchlists, alerts, and future lead discovery.
- Use a relational database as the source of truth, preferably PostgreSQL-compatible.
- Treat raw payload storage, verified facts, derived signals, AI explanations, and user-facing reports as separate data categories.
- Use background jobs for scraping, enrichment, classification, valuation, report generation, and alert evaluation.
- Use deterministic IDs or uniqueness constraints where duplicate ingestion is likely.
- Store all timestamps in UTC with timezone-aware types.
- Store money as decimal numeric values plus ISO currency code.
- Version all adapters, parsers, classifiers, signal builders, valuation algorithms, prompts, and report templates.
- Require structured errors with stable error codes across module boundaries.
- Log job IDs, organization IDs, domain IDs, marketplace IDs, source item IDs, and correlation IDs when available.
- Keep secrets out of source control and logs.
- Prefer explicit allowlists and typed enums over free-form strings for core statuses.
- Provide automated tests for each module boundary and for every schema migration.

## Verified Facts vs Derived Signals vs AI Explanations
Verified facts are observed or provider-returned data with evidence. Examples include auction current bid, auction end time, RDAP registrar, nameservers, DNS records, HTTP status code, final URL, and TLS validity. Verified facts must include source, observed time, evidence reference, and parser or provider version.

Derived signals are computed from verified facts, raw domain text, or other derived signals. Examples include domain length score, dictionary-word match, brandability score, CPC proxy score, comparable-sale similarity, website-live signal, and auction momentum. Derived signals must include algorithm version, input fact IDs or input signal IDs, generated time, and confidence score when applicable.

AI explanations are generated interpretations intended for readability. They may summarize facts and signals, but they are not facts. AI explanations must include model name, prompt version, input references, generated time, and structured output. AI explanations must never be used as the only support for a verified fact, price tier, or alert trigger.

Separation rules:
- Verified facts may be inputs to derived signals, classification, valuation, reports, and alerts.
- Derived signals may be inputs to classification, valuation, reports, and alerts.
- AI explanations may be inputs to reports only after validation against referenced facts and signals.
- AI explanations must not write to `verified_facts`.
- Valuation reasoning must reference facts and signals directly, not only AI prose.

## Value Tiers
The product uses stable value tiers so reports and alerts can reason consistently.

| Tier | Range USD | Required Support |
| --- | ---: | --- |
| `refusal` | no price | Refusal code and remediation path |
| `low` | 1 to 499 | Basic facts and classification |
| `meaningful` | 500 to 2,499 | Structured reasoning and evidence references |
| `high` | 2,500 to 9,999 | Structured reasoning, risk analysis, and comparable logic when available |
| `premium` | 10,000+ | Strong evidence, high scrutiny, reviewer-ready explanation, and confidence rationale |

If the valuation currency is not USD, the report must store the original currency and the conversion source used for USD tiering.

## Manual Requirements / Human Decisions
The following decisions require human approval before production launch or before the related feature is enabled:
- Marketplace terms review for Dynadot, DropCatch, and every future auction source.
- Allowed scraping frequency, user agent, retry policy, and robots or access policy interpretation for each marketplace.
- Whether marketplace ingestion uses official APIs, HTML scraping, partner feeds, or manual imports.
- WHOIS/RDAP provider selection, rate limits, data retention policy, and privacy treatment.
- DNS and website-check provider strategy, including whether checks run from one region or multiple regions.
- Default valuation tier thresholds and whether thresholds differ by TLD or domain type.
- Supported currencies and exchange-rate source.
- Initial alert channels, such as in-app, email, Slack, webhook, or SMS.
- AI provider, model policy, prompt review process, and allowed use of AI-generated text in customer-facing reports.
- Authentication provider, organization model, billing model, and role permissions.
- Data retention period for raw payloads, screenshots, website content hashes, and audit logs.
- Legal risk policy for trademarks, adult content, regulated industries, and protected terms.
- Whether any future outbound or lead discovery features are allowed to store contact data.

## Open Questions
- Which Dynadot and DropCatch pages or feeds are approved sources for v1?
- What is the minimum acceptable freshness for auction data before an alert becomes stale?
- Should valuation use only internal heuristics in v1, or may it call third-party appraisal APIs?
- Which TLDs are supported at launch?
- What report formats are required first: web view, PDF, JSON export, or all three?
- Should watchlists be organization-wide, user-specific, or both?
- What human review threshold is required before publishing `high` or `premium` appraisals?

## Acceptance Criteria
- Worker agents can add a new marketplace adapter without changing valuation code.
- Worker agents can add a new enrichment provider without changing auction ingestion code.
- Every valuation can be traced to classification, signals, facts, and source evidence.
- Every user-facing report identifies whether the valuation is valued, refused, or needs review.
- Every schema change follows the schema change rules in `db_schema.md` and review workflow in `review_protocol.md`.
