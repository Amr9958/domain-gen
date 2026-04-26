# Domain Intelligence API Contracts

## Purpose
This document defines contracts between backend modules and the external API shape. Worker agents must preserve these contracts unless an approved change updates this file, the schema, and tests together.

## Contract Rules
- All module contracts use explicit request and response objects.
- All IDs are UUID strings unless stated otherwise.
- All timestamps are ISO 8601 UTC strings.
- All money values use decimal strings plus ISO currency.
- All errors use stable `code`, `message`, and optional `details`.
- All write operations should accept an idempotency key when duplicate requests are possible.
- Module outputs must include input references used to create derived outputs.

## Shared Types
### `Money`
```json
{
  "amount": "1250.00",
  "currency": "USD"
}
```

### `EvidenceRef`
```json
{
  "type": "raw_auction_item|verified_fact|derived_signal|auction_snapshot|external_url",
  "id": "uuid-or-external-ref",
  "source": "dynadot",
  "observed_at": "2026-04-23T12:00:00Z"
}
```

### `ModuleError`
```json
{
  "code": "stable_error_code",
  "message": "Human readable summary",
  "details": {}
}
```

### `Confidence`
```json
{
  "level": "low|medium|high",
  "score": 0.74,
  "rationale": "Short structured explanation of confidence."
}
```

## Marketplace Adapter Contract
### `MarketplaceAdapter.fetch_auction_items`
Fetches source auction items and returns raw observations. Adapters do not normalize, classify, value, or alert.

Request:
```json
{
  "marketplace_code": "dynadot",
  "ingest_run_id": "uuid",
  "page_cursor": null,
  "limit": 100,
  "started_after": null
}
```

Response:
```json
{
  "items": [
    {
      "marketplace_code": "dynadot",
      "source_item_id": "source-123",
      "source_url": "https://example.test/auction/source-123",
      "captured_at": "2026-04-23T12:00:00Z",
      "raw_payload_json": {},
      "raw_payload_hash": "sha256:abc",
      "adapter_version": "dynadot-adapter-v1",
      "parser_version": "dynadot-parser-v1"
    }
  ],
  "next_page_cursor": null,
  "errors": []
}
```

## Normalization Contract
### `AuctionNormalizer.normalize_raw_item`
Converts one raw auction item into canonical domain, auction, and snapshot data.

Request:
```json
{
  "raw_auction_item_id": "uuid",
  "marketplace_code": "dynadot",
  "raw_payload_json": {},
  "source_url": "https://example.test/auction/source-123",
  "captured_at": "2026-04-23T12:00:00Z"
}
```

Response:
```json
{
  "domain": {
    "fqdn": "example.com",
    "sld": "example",
    "tld": "com",
    "punycode_fqdn": "example.com",
    "unicode_fqdn": "example.com",
    "is_valid": true
  },
  "auction": {
    "marketplace_code": "dynadot",
    "source_item_id": "source-123",
    "source_url": "https://example.test/auction/source-123",
    "auction_type": "expired",
    "status": "open",
    "starts_at": "2026-04-22T12:00:00Z",
    "ends_at": "2026-04-25T12:00:00Z",
    "current_bid": {
      "amount": "150.00",
      "currency": "USD"
    },
    "min_bid": {
      "amount": "69.00",
      "currency": "USD"
    },
    "bid_count": 5,
    "watchers_count": null,
    "normalized_payload_json": {}
  },
  "snapshot": {
    "captured_at": "2026-04-23T12:00:00Z",
    "status": "open",
    "current_bid": {
      "amount": "150.00",
      "currency": "USD"
    },
    "bid_count": 5,
    "watchers_count": null
  },
  "evidence_refs": [
    {
      "type": "raw_auction_item",
      "id": "uuid",
      "source": "dynadot",
      "observed_at": "2026-04-23T12:00:00Z"
    }
  ],
  "errors": []
}
```

## Enrichment Contract
### `EnrichmentService.enrich_domain`
Runs one or more enrichment checks and stores verified facts.

Request:
```json
{
  "domain_id": "uuid",
  "fqdn": "example.com",
  "checks": ["rdap", "dns", "website"],
  "force_refresh": false,
  "correlation_id": "uuid"
}
```

Response:
```json
{
  "enrichment_run_id": "uuid",
  "status": "completed|partial|failed",
  "created_fact_ids": ["uuid"],
  "website_check_id": "uuid",
  "errors": []
}
```

Verified fact output shape:
```json
{
  "domain_id": "uuid",
  "auction_id": null,
  "fact_type": "dns",
  "fact_key": "mx_records",
  "fact_value_json": {
    "records": []
  },
  "source_system": "dns_resolver",
  "source_url": null,
  "evidence_ref": "enrichment_run:uuid",
  "observed_at": "2026-04-23T12:00:00Z",
  "provider_version": "resolver-v1",
  "parser_version": "dns-parser-v1"
}
```

## Signal Contract
### `SignalBuilder.build_domain_signals`
Computes derived signals from facts, auction snapshots, and domain text.

Request:
```json
{
  "domain_id": "uuid",
  "auction_id": "uuid",
  "fact_ids": ["uuid"],
  "signal_keys": ["domain_length", "auction_momentum", "website_live"],
  "algorithm_version": "signals-v1"
}
```

Response:
```json
{
  "created_signal_ids": ["uuid"],
  "signals": [
    {
      "signal_type": "structure",
      "signal_key": "domain_length",
      "signal_value_json": {
        "length": 7,
        "score": 0.82
      },
      "input_fact_ids": [],
      "input_signal_ids": [],
      "algorithm_version": "signals-v1",
      "confidence_score": 0.95
    }
  ],
  "errors": []
}
```

## Classification Contract
### `ClassificationService.classify_domain`
Classifies domain type before valuation.

Request:
```json
{
  "domain_id": "uuid",
  "fqdn": "example.com",
  "fact_ids": ["uuid"],
  "signal_ids": ["uuid"],
  "algorithm_version": "classifier-v1"
}
```

Response:
```json
{
  "classification_result_id": "uuid",
  "domain_type": "brandable",
  "business_category": "software",
  "language_code": "en",
  "tokens": ["example"],
  "risk_flags": [],
  "confidence_score": 0.78,
  "input_fact_ids": ["uuid"],
  "input_signal_ids": ["uuid"],
  "refusal_reason": null,
  "errors": []
}
```

## Valuation Contract
### `ValuationService.value_domain`
Produces an explainable valuation or refusal state. This service must not run as `valued` without classification.

Request:
```json
{
  "domain_id": "uuid",
  "auction_id": "uuid",
  "classification_result_id": "uuid",
  "fact_ids": ["uuid"],
  "signal_ids": ["uuid"],
  "algorithm_version": "valuation-v1",
  "currency": "USD"
}
```

Valued response:
```json
{
  "valuation_run_id": "uuid",
  "status": "valued",
  "estimated_value_min": {
    "amount": "500.00",
    "currency": "USD"
  },
  "estimated_value_max": {
    "amount": "1800.00",
    "currency": "USD"
  },
  "estimated_value_point": {
    "amount": "1100.00",
    "currency": "USD"
  },
  "value_tier": "meaningful",
  "confidence": {
    "level": "medium",
    "score": 0.68,
    "rationale": "Supported by classification and auction facts, limited by missing comparable sales."
  },
  "reason_codes": [
    {
      "code": "short_clear_name",
      "label": "Short clear name",
      "direction": "positive",
      "impact_amount": {
        "amount": "300.00",
        "currency": "USD"
      },
      "impact_weight": 0.25,
      "evidence_refs": []
    }
  ],
  "input_fact_ids": ["uuid"],
  "input_signal_ids": ["uuid"],
  "classification_result_id": "uuid",
  "errors": []
}
```

Refusal response:
```json
{
  "valuation_run_id": "uuid",
  "status": "refused",
  "refusal_code": "missing_classification",
  "refusal_reason": "A current classification result is required before pricing.",
  "value_tier": "refusal",
  "confidence": {
    "level": "low",
    "score": 0.0,
    "rationale": "Required prerequisite is missing."
  },
  "remediation": ["Run classification for this domain."],
  "errors": []
}
```

## AI Explanation Contract
### `ExplanationService.generate_explanation`
Generates readable explanation text from approved structured inputs.

Request:
```json
{
  "subject_type": "valuation_run",
  "subject_id": "uuid",
  "explanation_type": "appraisal_summary",
  "input_refs": [
    {
      "type": "valuation_run",
      "id": "uuid"
    }
  ],
  "prompt_version": "appraisal-summary-v1",
  "model_name": "approved-model-name"
}
```

Response:
```json
{
  "ai_explanation_id": "uuid",
  "validation_status": "pending",
  "structured_output_json": {},
  "text": "Readable summary generated from referenced facts and signals.",
  "errors": []
}
```

## Report Contract
### `ReportService.generate_appraisal_report`
Builds a reproducible report.

Request:
```json
{
  "organization_id": "uuid",
  "domain_id": "uuid",
  "valuation_run_id": "uuid",
  "include_ai_explanations": true,
  "report_template_version": "appraisal-v1",
  "created_by_user_id": "uuid"
}
```

Response:
```json
{
  "appraisal_report_id": "uuid",
  "status": "generated",
  "report_json": {
    "domain": "example.com",
    "valuation_status": "valued",
    "data_freshness": {},
    "facts": [],
    "signals": [],
    "classification": {},
    "valuation": {},
    "explanations": []
  },
  "errors": []
}
```

## Watchlist and Alert Contracts
### `WatchlistService.add_item`
Request:
```json
{
  "watchlist_id": "uuid",
  "domain_id": "uuid",
  "auction_id": "uuid",
  "created_by_user_id": "uuid",
  "notes": "Track before close."
}
```

Response:
```json
{
  "watchlist_item_id": "uuid",
  "created": true,
  "errors": []
}
```

### `AlertService.evaluate_rules`
Request:
```json
{
  "organization_id": "uuid",
  "watchlist_id": "uuid",
  "rule_ids": ["uuid"],
  "evaluation_time": "2026-04-23T12:00:00Z"
}
```

Response:
```json
{
  "created_alert_event_ids": ["uuid"],
  "suppressed_duplicates": 3,
  "errors": []
}
```

### `AlertDeliveryService.deliver_event`
Request:
```json
{
  "alert_event_id": "uuid",
  "channel": "email",
  "idempotency_key": "alert-event-uuid:email"
}
```

Response:
```json
{
  "alert_delivery_id": "uuid",
  "status": "delivered|retryable_failure|terminal_failure",
  "error": null
}
```

## Public REST API Shape
Initial public API endpoints should follow this shape:
- `POST /v1/ingest-runs`: Start an ingestion run for an approved marketplace.
- `GET /v1/ingest-runs/{id}`: Read ingestion run status and metrics.
- `GET /v1/auctions`: List normalized auctions with filters.
- `GET /v1/domains/{fqdn}`: Read canonical domain summary.
- `POST /v1/domains/{fqdn}/enrich`: Request enrichment refresh.
- `POST /v1/domains/{fqdn}/classify`: Request classification.
- `POST /v1/domains/{fqdn}/value`: Request valuation.
- `POST /v1/reports/appraisals`: Generate an appraisal report.
- `GET /v1/reports/appraisals/{id}`: Read an appraisal report.
- `GET /v1/watchlists`: List watchlists.
- `POST /v1/watchlists`: Create a watchlist.
- `POST /v1/watchlists/{id}/items`: Add a watched item.
- `POST /v1/alert-rules`: Create an alert rule.
- `GET /v1/alert-events`: List alert history.

## Error Codes
Stable cross-module error codes:
- `source_unavailable`
- `source_rate_limited`
- `source_payload_invalid`
- `normalization_failed`
- `domain_invalid`
- `enrichment_provider_failed`
- `fact_stale`
- `classification_missing`
- `classification_failed`
- `valuation_refused`
- `valuation_needs_review`
- `report_input_invalid`
- `alert_duplicate_suppressed`
- `permission_denied`
- `schema_contract_mismatch`

## Versioning
- External REST APIs use `/v1`.
- Module contracts use semantic contract names and versioned algorithm fields.
- Historical valuation and report records must retain the algorithm and template versions used at generation time.
- Breaking changes require updating this file, migration notes, tests, and reviewer approval.
