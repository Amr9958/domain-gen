"""Typed enrichment response models and example payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from domain_intel.enrichment.contracts import EnrichmentResult


class EnrichmentErrorRead(BaseModel):
    """Stable error shape for enrichment service responses."""

    code: str
    message: str
    retryable: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class UnresolvedObservationRead(BaseModel):
    """Serialization model for unresolved enrichment outputs."""

    scope: str
    key: str
    reason: str
    retryable: bool


class ProviderOutcomeRead(BaseModel):
    """Serialized summary for one provider execution."""

    check: str
    provider_name: str
    status: str
    created_fact_ids: List[UUID] = Field(default_factory=list)
    cache_hit: bool = False
    unresolved: List[UnresolvedObservationRead] = Field(default_factory=list)
    errors: List[EnrichmentErrorRead] = Field(default_factory=list)


class EnrichmentResponseRead(BaseModel):
    """Contract-aligned response for `EnrichmentService.enrich_domain`."""

    enrichment_run_id: UUID
    status: str
    created_fact_ids: List[UUID] = Field(default_factory=list)
    website_check_id: Optional[UUID] = None
    errors: List[EnrichmentErrorRead] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: EnrichmentResult) -> "EnrichmentResponseRead":
        return cls(
            enrichment_run_id=result.enrichment_run_id,
            status=result.status.value,
            created_fact_ids=result.created_fact_ids,
            website_check_id=result.website_check_id,
            errors=[
                EnrichmentErrorRead(
                    code=error.code,
                    message=error.message,
                    retryable=error.retryable,
                    details=error.details,
                )
                for error in result.errors
            ],
        )


class EnrichmentDocumentRead(BaseModel):
    """Richer JSON shape for internal inspection and future API expansion."""

    enrichment_run_id: UUID
    status: str
    created_fact_ids: List[UUID] = Field(default_factory=list)
    website_check_id: Optional[UUID] = None
    provider_outcomes: List[ProviderOutcomeRead] = Field(default_factory=list)
    errors: List[EnrichmentErrorRead] = Field(default_factory=list)
    generated_at: datetime

    @classmethod
    def from_result(cls, result: EnrichmentResult, generated_at: datetime) -> "EnrichmentDocumentRead":
        return cls(
            enrichment_run_id=result.enrichment_run_id,
            status=result.status.value,
            created_fact_ids=result.created_fact_ids,
            website_check_id=result.website_check_id,
            provider_outcomes=[
                ProviderOutcomeRead(
                    check=outcome.check.value,
                    provider_name=outcome.provider_name,
                    status=outcome.status.value,
                    created_fact_ids=outcome.created_fact_ids,
                    cache_hit=outcome.cache_hit,
                    unresolved=[
                        UnresolvedObservationRead(
                            scope=item.scope,
                            key=item.key,
                            reason=item.reason,
                            retryable=item.retryable,
                        )
                        for item in outcome.unresolved
                    ],
                    errors=[
                        EnrichmentErrorRead(
                            code=error.code,
                            message=error.message,
                            retryable=error.retryable,
                            details=error.details,
                        )
                        for error in outcome.errors
                    ],
                )
                for outcome in result.provider_outcomes
            ],
            errors=[
                EnrichmentErrorRead(
                    code=error.code,
                    message=error.message,
                    retryable=error.retryable,
                    details=error.details,
                )
                for error in result.errors
            ],
            generated_at=generated_at,
        )


ENRICHMENT_RESPONSE_EXAMPLE: Dict[str, Any] = {
    "enrichment_run_id": "2da750d9-0d40-48b8-bdbb-d90fb80746f8",
    "status": "partial",
    "created_fact_ids": [
        "2c32ed42-a964-4525-8b69-489260f83431",
        "986e4d26-0fe3-49d6-b774-c0db65b7bd89",
    ],
    "website_check_id": "7f7804ff-b43e-4378-9f1b-84477fd88f7a",
    "errors": [
        {
            "code": "dns_provider_unavailable",
            "message": "DNS provider is not configured for atlasai.com.",
            "retryable": True,
            "details": {},
        }
    ],
}


ENRICHMENT_DOCUMENT_EXAMPLE: Dict[str, Any] = {
    "enrichment_run_id": "2da750d9-0d40-48b8-bdbb-d90fb80746f8",
    "status": "completed",
    "created_fact_ids": [
        "2c32ed42-a964-4525-8b69-489260f83431",
        "986e4d26-0fe3-49d6-b774-c0db65b7bd89",
        "53619dc4-9d35-4437-9d8f-e9e8125fe88a",
    ],
    "website_check_id": "7f7804ff-b43e-4378-9f1b-84477fd88f7a",
    "provider_outcomes": [
        {
            "check": "website",
            "provider_name": "http_website_inspector",
            "status": "completed",
            "created_fact_ids": ["53619dc4-9d35-4437-9d8f-e9e8125fe88a"],
            "cache_hit": False,
            "unresolved": [],
            "errors": [],
        }
    ],
    "errors": [],
    "generated_at": "2026-04-23T18:05:00Z",
}
