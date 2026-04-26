# Domain Intelligence Coding Conventions

## Purpose
This document defines file, folder, naming, testing, and implementation conventions for worker agents. Follow these conventions unless an existing module has a stronger local pattern.

## Target Folder Layout
New production modules should move toward this structure:

```text
backend/
  src/
    domain_intel/
      api/
      core/
      db/
      marketplaces/
        dynadot/
        dropcatch/
      normalization/
      enrichment/
      signals/
      classification/
      valuation/
      reports/
      watchlists/
      alerts/
      leads_future/
      observability/
  tests/
    unit/
    integration/
    fixtures/
docs/
  decisions/
  runbooks/
```

Current repository modules may remain in place until a migration is approved. When adding new code to the current layout, preserve existing import style and avoid large reorganizations unless explicitly requested.

## File Naming
- Use lowercase snake_case for Python files and folders.
- Use stable source names for marketplace adapters, such as `dynadot` and `dropcatch`.
- Use `*_service.py` for orchestration services.
- Use `*_repository.py` for database persistence boundaries.
- Use `*_client.py` for network clients.
- Use `*_normalizer.py` for source-to-canonical mapping.
- Use `*_schema.py` or `schemas.py` for typed request and response objects.
- Use `test_*.py` for tests.

## Module Boundary Rules
- Marketplace adapters fetch and parse source data only.
- Normalizers map source payloads to canonical auction data only.
- Enrichment modules create verified facts only.
- Signal builders create derived signals only.
- Classification must run before valuation.
- Valuation must create structured outputs and refusal states, not report prose.
- Report generation assembles stored outputs and validated explanations.
- Alert evaluation creates events; delivery sends events.
- Future lead discovery must remain isolated from v1 valuation and fact storage.

## Naming and Data Rules
- Use `domain_id`, `auction_id`, `valuation_run_id`, and similar explicit foreign key names.
- Use `fqdn` for full domain names and `sld` plus `tld` for parsed parts.
- Use `source_item_id` for marketplace-specific IDs.
- Use `marketplace_code` for stable marketplace identifiers.
- Use `*_json` suffix for JSONB-compatible dictionaries.
- Use `*_ids` suffix for arrays of IDs.
- Use UTC-aware timestamps and name them with `_at`.
- Use decimal strings for API money values and database numeric values for stored money.
- Use explicit enums for statuses, tiers, confidence, and refusal codes.

## Scraping and Source Access
- Respect approved source access decisions in `requirements.md`.
- Do not add scraping bypasses, CAPTCHA workarounds, hidden browser automation, or login automation without explicit human approval.
- Rate limits, retry counts, and user agents must be configurable.
- Store raw payloads before normalization.
- Add source-specific parser tests using saved fixtures.

## Facts, Signals, and AI
- Never store AI-generated text in `verified_facts`.
- Never use AI explanations as the only evidence for valuation, reports, or alerts.
- Every derived signal must include input fact IDs or input signal IDs when available.
- Every valuation at or above `meaningful` must include reason codes and evidence references.
- Preserve historical algorithm, adapter, parser, prompt, and report template versions.

## Error Handling
- Raise or return structured errors with stable codes from `api_contracts.md`.
- Include enough context for debugging, but do not log secrets, cookies, tokens, or private contact data.
- Treat network failures as retryable unless the provider response is clearly terminal.
- Treat invalid source payloads as parser errors with captured evidence, not silent skips.
- Store refusal states for valuation prerequisites rather than throwing generic exceptions.

## Testing Requirements
- Add unit tests for every normalizer, signal builder, classifier, valuation rule, and report assembler.
- Add fixture-based tests for Dynadot and DropCatch parsing.
- Add integration tests for repository methods that create facts, signals, classifications, valuations, reports, watchlists, and alerts.
- Add migration tests for schema changes.
- Add regression tests for every bug fix.
- Tests must prove that verified facts, derived signals, and AI explanations remain separate.

## Code Style
- Prefer typed functions and small request or response objects over loosely shaped dictionaries at module boundaries.
- Keep functions focused on one responsibility.
- Keep side effects at service, repository, adapter, or client boundaries.
- Do not mix HTTP fetching, parsing, persistence, and valuation in the same function.
- Use dependency injection for providers, clocks, HTTP clients, and repositories where practical.
- Prefer deterministic pure functions for classification rules, signal calculations, and valuation rules.
- Avoid broad exception swallowing.

## Configuration
- Use environment variables or managed secrets for credentials.
- Keep source-specific rate limits and feature flags configurable.
- Do not hardcode production credentials, cookies, API keys, or personal data.
- Provide safe defaults for local development.
- Document required manual setup in `MANUAL_SETUP.md` or a dedicated runbook.

## Database Change Conventions
- Schema changes must follow `db_schema.md`.
- Do not rename or drop stable columns without explicit approval.
- Prefer additive migrations with backfills.
- Migration names should be timestamped and descriptive.
- Update schema docs, API contracts, repositories, tests, and fixtures in the same change when behavior changes.

## Review Hygiene
- Keep changes small enough for another worker agent or reviewer to audit.
- Include tests or explain why tests were not run.
- Call out any manual decision required before production use.
- Do not reformat unrelated files.
- Do not revert user changes or other agents' changes without explicit instruction.
