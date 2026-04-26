# Domain Intelligence Database Schema

## Purpose
This document defines the shared database entities and relationships for the domain intelligence SaaS. It is written as a logical schema, not a complete SQL migration. Worker agents must treat these names and relationships as stable unless a schema change is approved.

## Global Database Rules
- Use PostgreSQL-compatible types and constraints.
- Use `uuid` primary keys unless a table explicitly uses a natural key.
- Use `created_at` and `updated_at` timestamps on mutable tables.
- Store timestamps in UTC using timezone-aware types.
- Store money as `numeric(14,2)` plus `currency char(3)`.
- Store raw source payloads as JSONB or object storage references when payloads are large.
- Never delete evidence required by a valuation, report, or alert without an approved retention policy.
- Use soft deletion for user-owned objects where auditability matters.

## Core Enums
`marketplace_code`:
- `dynadot`
- `dropcatch`
- `manual_import`

`auction_status`:
- `scheduled`
- `open`
- `closing`
- `closed`
- `sold`
- `unsold`
- `cancelled`
- `unknown`

`auction_type`:
- `expired`
- `closeout`
- `backorder`
- `private_seller`
- `registry`
- `unknown`

`domain_type`:
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

`valuation_status`:
- `valued`
- `refused`
- `needs_review`

`valuation_refusal_code`:
- `insufficient_evidence`
- `missing_classification`
- `unsupported_domain_type`
- `legal_or_trademark_risk`
- `invalid_domain`
- `stale_inputs`
- `conflicting_facts`
- `provider_failure`

`confidence_level`:
- `low`
- `medium`
- `high`

`value_tier`:
- `refusal`
- `low`
- `meaningful`
- `high`
- `premium`

## SaaS and Access Entities
### `organizations`
Stores customer accounts.

Required columns:
- `id uuid primary key`
- `name text not null`
- `slug text unique not null`
- `plan_code text not null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

### `users`
Stores application users.

Required columns:
- `id uuid primary key`
- `email citext unique not null`
- `display_name text`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

### `organization_members`
Links users to organizations.

Required columns:
- `organization_id uuid references organizations(id)`
- `user_id uuid references users(id)`
- `role text not null`
- `created_at timestamptz not null`

Constraints:
- Primary key on `organization_id, user_id`.
- `role` must be one of `owner`, `analyst`, or `viewer`.

## Marketplace Ingestion Entities
### `source_marketplaces`
Registry of marketplaces and source settings.

Required columns:
- `id uuid primary key`
- `code text unique not null`
- `display_name text not null`
- `base_url text`
- `terms_review_status text not null`
- `is_enabled boolean not null default false`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

### `ingest_runs`
Tracks each marketplace ingestion attempt.

Required columns:
- `id uuid primary key`
- `marketplace_id uuid references source_marketplaces(id)`
- `run_type text not null`
- `status text not null`
- `adapter_version text not null`
- `parser_version text not null`
- `started_at timestamptz not null`
- `completed_at timestamptz`
- `error_code text`
- `error_summary text`
- `metrics_json jsonb not null default '{}'::jsonb`

Indexes:
- `marketplace_id, started_at desc`
- `status, started_at desc`

### `raw_auction_items`
Stores raw marketplace observations before normalization.

Required columns:
- `id uuid primary key`
- `ingest_run_id uuid references ingest_runs(id)`
- `marketplace_id uuid references source_marketplaces(id)`
- `source_item_id text not null`
- `source_url text`
- `captured_at timestamptz not null`
- `raw_payload_hash text not null`
- `raw_payload_json jsonb`
- `raw_artifact_uri text`
- `adapter_version text not null`
- `parser_version text not null`

Constraints:
- Unique on `marketplace_id, source_item_id, raw_payload_hash`.
- At least one of `raw_payload_json` or `raw_artifact_uri` must be present.

## Domain and Auction Entities
### `domains`
Canonical domain identity.

Required columns:
- `id uuid primary key`
- `fqdn text unique not null`
- `sld text not null`
- `tld text not null`
- `punycode_fqdn text not null`
- `unicode_fqdn text`
- `is_valid boolean not null default true`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Indexes:
- `tld, sld`
- `punycode_fqdn`

### `auctions`
Canonical current auction state.

Required columns:
- `id uuid primary key`
- `marketplace_id uuid references source_marketplaces(id)`
- `domain_id uuid references domains(id)`
- `source_item_id text not null`
- `source_url text`
- `auction_type auction_type not null`
- `status auction_status not null`
- `starts_at timestamptz`
- `ends_at timestamptz`
- `currency char(3)`
- `current_bid_amount numeric(14,2)`
- `min_bid_amount numeric(14,2)`
- `bid_count integer`
- `watchers_count integer`
- `normalized_payload_json jsonb not null default '{}'::jsonb`
- `first_seen_at timestamptz not null`
- `last_seen_at timestamptz not null`
- `closed_at timestamptz`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Constraints:
- Unique on `marketplace_id, source_item_id`.
- `ends_at` must be greater than `starts_at` when both are present.

Indexes:
- `domain_id, last_seen_at desc`
- `status, ends_at`
- `marketplace_id, last_seen_at desc`

### `auction_snapshots`
Historical auction observations.

Required columns:
- `id uuid primary key`
- `auction_id uuid references auctions(id)`
- `raw_auction_item_id uuid references raw_auction_items(id)`
- `captured_at timestamptz not null`
- `status auction_status not null`
- `current_bid_amount numeric(14,2)`
- `currency char(3)`
- `bid_count integer`
- `watchers_count integer`
- `snapshot_json jsonb not null default '{}'::jsonb`

Constraints:
- Unique on `auction_id, captured_at`.

## Evidence and Enrichment Entities
### `verified_facts`
Evidence-backed observations.

Required columns:
- `id uuid primary key`
- `domain_id uuid references domains(id)`
- `auction_id uuid references auctions(id)`
- `fact_type text not null`
- `fact_key text not null`
- `fact_value_json jsonb not null`
- `source_system text not null`
- `source_url text`
- `evidence_ref text`
- `observed_at timestamptz not null`
- `valid_from timestamptz`
- `valid_until timestamptz`
- `provider_version text`
- `parser_version text`
- `created_at timestamptz not null`

Rules:
- `domain_id` is required unless the fact is only about an auction source artifact.
- `fact_value_json` must contain provider-returned or directly observed values, not AI summaries.
- Derived scores are not allowed in this table.

Indexes:
- `domain_id, fact_type, observed_at desc`
- `auction_id, fact_type, observed_at desc`

### `enrichment_runs`
Tracks enrichment attempts.

Required columns:
- `id uuid primary key`
- `domain_id uuid references domains(id)`
- `run_type text not null`
- `provider text not null`
- `status text not null`
- `started_at timestamptz not null`
- `completed_at timestamptz`
- `error_code text`
- `error_summary text`
- `raw_artifact_uri text`
- `created_fact_ids uuid[] not null default '{}'`

Indexes:
- `domain_id, started_at desc`
- `provider, status, started_at desc`

### `website_checks`
Stores parsed website check results and links to facts.

Required columns:
- `id uuid primary key`
- `domain_id uuid references domains(id)`
- `checked_at timestamptz not null`
- `start_url text not null`
- `final_url text`
- `http_status integer`
- `redirect_count integer not null default 0`
- `tls_valid boolean`
- `title text`
- `content_hash text`
- `technology_json jsonb not null default '{}'::jsonb`
- `created_fact_ids uuid[] not null default '{}'`

## Derived Intelligence Entities
### `derived_signals`
Computed signals from facts, domain text, and auction history.

Required columns:
- `id uuid primary key`
- `domain_id uuid references domains(id)`
- `auction_id uuid references auctions(id)`
- `signal_type text not null`
- `signal_key text not null`
- `signal_value_json jsonb not null`
- `input_fact_ids uuid[] not null default '{}'`
- `input_signal_ids uuid[] not null default '{}'`
- `algorithm_version text not null`
- `confidence_score numeric(5,4)`
- `generated_at timestamptz not null`

Rules:
- Signals must be reproducible from referenced inputs and algorithm version.
- Signals must not overwrite facts.

Indexes:
- `domain_id, signal_type, generated_at desc`
- `auction_id, signal_type, generated_at desc`

### `classification_results`
Domain classification output.

Required columns:
- `id uuid primary key`
- `domain_id uuid references domains(id)`
- `domain_type domain_type not null`
- `business_category text`
- `language_code text`
- `tokens_json jsonb not null default '[]'::jsonb`
- `risk_flags_json jsonb not null default '[]'::jsonb`
- `confidence_score numeric(5,4) not null`
- `algorithm_version text not null`
- `input_fact_ids uuid[] not null default '{}'`
- `input_signal_ids uuid[] not null default '{}'`
- `refusal_reason text`
- `created_at timestamptz not null`

Indexes:
- `domain_id, created_at desc`
- `domain_type, confidence_score desc`

### `valuation_runs`
Valuation output for a domain and optional auction context.

Required columns:
- `id uuid primary key`
- `domain_id uuid references domains(id)`
- `auction_id uuid references auctions(id)`
- `classification_result_id uuid references classification_results(id)`
- `status valuation_status not null`
- `refusal_code valuation_refusal_code`
- `refusal_reason text`
- `estimated_value_min numeric(14,2)`
- `estimated_value_max numeric(14,2)`
- `estimated_value_point numeric(14,2)`
- `currency char(3) not null default 'USD'`
- `value_tier value_tier not null`
- `confidence_level confidence_level not null`
- `algorithm_version text not null`
- `input_fact_ids uuid[] not null default '{}'`
- `input_signal_ids uuid[] not null default '{}'`
- `created_at timestamptz not null`

Rules:
- `classification_result_id` is required for `valued` status.
- `refusal_code` is required for `refused` status.
- `estimated_value_min` and `estimated_value_max` are required for `valued` status.
- `estimated_value_min` must be less than or equal to `estimated_value_max`.
- `value_tier` must be `refusal` for `refused` status.

Indexes:
- `domain_id, created_at desc`
- `auction_id, created_at desc`
- `status, value_tier, created_at desc`

### `valuation_reason_codes`
Structured valuation reasoning.

Required columns:
- `id uuid primary key`
- `valuation_run_id uuid references valuation_runs(id)`
- `code text not null`
- `label text not null`
- `direction text not null`
- `impact_amount numeric(14,2)`
- `impact_weight numeric(6,4)`
- `evidence_refs_json jsonb not null default '[]'::jsonb`
- `explanation text not null`

Rules:
- `direction` must be one of `positive`, `negative`, or `neutral`.
- Meaningful, high, and premium valuations must have at least one positive or neutral reason and one risk or confidence reason.

### `ai_explanations`
AI-generated readable explanations.

Required columns:
- `id uuid primary key`
- `subject_type text not null`
- `subject_id uuid not null`
- `explanation_type text not null`
- `model_name text not null`
- `prompt_version text not null`
- `input_refs_json jsonb not null`
- `structured_output_json jsonb not null default '{}'::jsonb`
- `text text not null`
- `validation_status text not null`
- `created_at timestamptz not null`

Rules:
- `validation_status` must be one of `pending`, `validated`, `rejected`.
- Reports may only use validated AI explanations.

## Reports, Watchlists, and Alerts
### `appraisal_reports`
Reproducible report records.

Required columns:
- `id uuid primary key`
- `organization_id uuid references organizations(id)`
- `domain_id uuid references domains(id)`
- `valuation_run_id uuid references valuation_runs(id)`
- `status text not null`
- `report_template_version text not null`
- `report_json jsonb not null`
- `public_token text unique`
- `generated_at timestamptz not null`
- `expires_at timestamptz`
- `created_by_user_id uuid references users(id)`

### `watchlists`
User or organization watchlists.

Required columns:
- `id uuid primary key`
- `organization_id uuid references organizations(id)`
- `owner_user_id uuid references users(id)`
- `name text not null`
- `visibility text not null`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`
- `deleted_at timestamptz`

Rules:
- `visibility` must be one of `private`, `organization`.

### `watchlist_items`
Watched domains and auctions.

Required columns:
- `id uuid primary key`
- `watchlist_id uuid references watchlists(id)`
- `domain_id uuid references domains(id)`
- `auction_id uuid references auctions(id)`
- `notes text`
- `created_at timestamptz not null`
- `created_by_user_id uuid references users(id)`

Constraints:
- At least one of `domain_id` or `auction_id` must be present.
- Unique on `watchlist_id, domain_id, auction_id`.

### `alert_rules`
Configurable alert rules.

Required columns:
- `id uuid primary key`
- `organization_id uuid references organizations(id)`
- `watchlist_id uuid references watchlists(id)`
- `rule_type text not null`
- `is_enabled boolean not null default true`
- `threshold_json jsonb not null default '{}'::jsonb`
- `channel_config_json jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

### `alert_events`
Deduplicated alert events.

Required columns:
- `id uuid primary key`
- `alert_rule_id uuid references alert_rules(id)`
- `domain_id uuid references domains(id)`
- `auction_id uuid references auctions(id)`
- `event_type text not null`
- `event_key text not null`
- `severity text not null`
- `payload_json jsonb not null`
- `created_at timestamptz not null`

Constraints:
- Unique on `alert_rule_id, event_key`.

### `alert_deliveries`
Delivery attempts for alert events.

Required columns:
- `id uuid primary key`
- `alert_event_id uuid references alert_events(id)`
- `channel text not null`
- `status text not null`
- `attempt_count integer not null default 0`
- `last_attempt_at timestamptz`
- `delivered_at timestamptz`
- `error_code text`
- `error_summary text`

## Audit Entity
### `audit_log`
Append-only record of important user and system actions.

Required columns:
- `id uuid primary key`
- `organization_id uuid references organizations(id)`
- `actor_user_id uuid references users(id)`
- `actor_type text not null`
- `action text not null`
- `subject_type text not null`
- `subject_id uuid`
- `payload_json jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null`

Rules:
- This table is append-only.
- Do not store secrets in `payload_json`.

## Future Reserved Entities
The following are reserved for future lead discovery and outbound readiness. Do not implement them until the requirements are approved:
- `lead_targets`
- `lead_sources`
- `lead_domain_matches`
- `outbound_readiness_checks`
- `outbound_compliance_reviews`

## Relationship Summary
- One marketplace has many ingest runs, raw auction items, and auctions.
- One raw auction item may produce or update one canonical auction and one auction snapshot.
- One domain has many auctions, verified facts, enrichment runs, website checks, derived signals, classification results, valuation runs, reports, watchlist items, and alert events.
- One auction has many auction snapshots, derived signals, valuation runs, watchlist items, and alert events.
- One classification result may feed many valuation runs if re-used, but a valuation run references exactly one classification result when valued.
- One valuation run has many valuation reason codes and may have many AI explanations and reports.
- One watchlist has many watchlist items and alert rules.
- One alert event has many alert delivery attempts.

## Rules for Proposing Schema Changes
Worker agents must not silently change stable table names, column names, enum values, or relationship rules.

Required proposal format:
- Problem: The user or system need that cannot be met by the current schema.
- Proposed change: Tables, columns, enums, indexes, constraints, and defaults.
- Data impact: Backfill, migration, retention, and compatibility impact.
- API impact: Contract changes required in `api_contracts.md`.
- Risk: Potential data loss, performance risk, privacy risk, or migration risk.
- Rollback: How the change can be reverted or safely ignored.
- Tests: Migration tests and module tests that prove compatibility.

Approval rules:
- Additive nullable columns may be proposed by a worker but still require reviewer approval.
- New tables require reviewer approval.
- New enum values require reviewer approval because they affect contracts and reports.
- Renames, drops, type changes, and constraint tightening require explicit human approval.
- Any schema change involving raw payload retention, lead data, personal data, or valuation outputs requires human approval.
