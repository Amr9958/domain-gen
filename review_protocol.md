# Worker Agent Review Protocol

## Purpose
This protocol defines how worker agents should plan, implement, review, and hand off work in the domain intelligence SaaS. It is designed to keep parallel work safe, auditable, and aligned with the foundation docs.

## Review Priorities
Reviewers must prioritize:
- Correctness of data boundaries between raw payloads, verified facts, derived signals, AI explanations, and reports.
- Preservation of source evidence and traceability.
- Compliance with marketplace access decisions.
- Classification before valuation.
- Refusal states and confidence handling in valuation.
- Schema compatibility and migration safety.
- Tests for module contracts and edge cases.

## Required Worker Workflow
1. Read the relevant sections of `requirements.md`, `architecture.md`, `db_schema.md`, `api_contracts.md`, and `coding_conventions.md`.
2. Identify the module boundary affected by the task.
3. Check whether the task requires a schema, API contract, or manual requirements change.
4. Implement within the smallest safe scope.
5. Add or update tests and fixtures.
6. Run the relevant verification commands.
7. Self-review the diff before handoff.
8. Report what changed, what was tested, and any remaining risks.

## Design Review Gate
A worker must pause for reviewer or human approval before implementation when a change:
- Adds a new database table.
- Renames, drops, or changes the type of a database column.
- Adds or changes enum values used by APIs, reports, valuation, or alerts.
- Changes valuation tier thresholds.
- Changes confidence or refusal semantics.
- Adds a new marketplace source or changes scraping behavior.
- Stores personal data, contact data, screenshots, or website content.
- Uses AI output as anything other than an explanation.
- Changes authentication, authorization, billing, or organization boundaries.

## Schema Change Review
Schema proposals must include:
- Problem.
- Proposed change.
- Data impact.
- API impact.
- Risk.
- Rollback.
- Tests.

Reviewers must reject schema changes that:
- Combine unrelated schema and feature changes.
- Remove evidence needed by existing reports or valuations.
- Break historical reproducibility.
- Store derived signals in `verified_facts`.
- Store AI explanations as facts.
- Lack migration or repository tests.

## API Contract Review
API contract changes must include:
- Updated request and response shapes.
- Stable error codes.
- Versioning impact.
- Backward compatibility notes.
- Tests for success, refusal, and failure paths.

Reviewers must check that:
- Module contracts do not leak source-specific payloads into unrelated modules.
- Valuation responses include classification references.
- Meaningful, high, and premium valuations include structured reasoning.
- Refusal states are explicit and machine-readable.

## Valuation Review Checklist
A valuation change must prove:
- Classification is required before valued output.
- Refusal is returned for missing or stale prerequisites.
- Confidence level is assigned by explicit logic.
- Value tier is assigned consistently with `requirements.md`.
- Reason codes reference facts or signals.
- AI prose is not required for the valuation to be valid.
- Tests cover low, meaningful, high, premium, refused, and needs-review cases when relevant.

## Ingestion Review Checklist
An ingestion change must prove:
- Raw source payloads are stored before normalization.
- Source item ID, source URL, captured time, adapter version, and parser version are captured.
- Idempotency prevents duplicate raw or normalized records.
- Parser tests use fixtures.
- Normalization preserves source-specific unmapped fields.
- Marketplace-specific logic does not leak into valuation.

## Enrichment Review Checklist
An enrichment change must prove:
- Provider output is traceable to source, observed time, parser version, and enrichment run.
- Facts are stored in `verified_facts`.
- Computed scores are stored as `derived_signals`, not facts.
- Failed provider calls are captured with retry eligibility.
- Staleness rules are explicit.

## Report and AI Review Checklist
A report or AI explanation change must prove:
- Reports can be reproduced from stored IDs and `report_json`.
- AI explanations include model name, prompt version, input references, and validation status.
- Reports distinguish facts, signals, valuation, and explanation prose.
- Reports include refusal states when valuation is refused.
- AI text does not introduce unsupported claims.

## Alert Review Checklist
An alert change must prove:
- Alert events are deduplicated.
- Alert delivery attempts are separate from event creation.
- Failed deliveries can retry without duplicating events.
- Alert rules reference watchlists, domains, auctions, or valuation changes clearly.
- Alerts do not rely on AI explanations as trigger evidence.

## Self-Review Template
Worker agents should include this in handoff notes:

```text
Scope:
Changed:
Tests run:
Facts/signals/AI separation impact:
Schema impact:
API contract impact:
Manual decisions needed:
Known risks:
```

## Reviewer Response Format
Reviewers should report findings first, ordered by severity:

```text
Findings:
- [severity] file:line - Issue and why it matters.

Open questions:
- Question or assumption.

Verification:
- Commands or checks reviewed.
```

Severity levels:
- `blocker`: Unsafe to merge or violates core requirements.
- `high`: Likely production bug, data loss, security issue, or contract break.
- `medium`: Functional gap, missing test, unclear migration, or maintainability risk.
- `low`: Minor clarity, naming, or cleanup issue.

## Merge Readiness
A change is merge-ready only when:
- It follows the relevant foundation docs.
- It preserves traceability from outputs to inputs.
- It has tests or a documented reason tests were not possible.
- It has no unresolved blocker or high findings.
- Manual decisions are documented instead of assumed.
