"""Public API request and response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from domain_intel.contracts.appraisal import AppraisalReportContract
from domain_intel.services.auction_service import (
    AuctionListingPage,
    AuctionListingRecord,
    DomainSummary,
    MarketplaceSummary,
)
from domain_intel.services.alert_service import AlertRuleRecord
from domain_intel.services.opportunity_service import UndervaluedAuctionPage, UndervaluedAuctionRecord, ValueRangeValue
from domain_intel.services.report_service import AppraisalReportRecord
from domain_intel.services.saved_search_service import (
    SavedSearchListResult,
    SavedSearchMutationResult,
    SavedSearchRecord,
    SavedSearchServiceError,
)
from domain_intel.services.shared_types import MoneyValue
from domain_intel.services.watchlist_service import WatchlistItemRecord, WatchlistRecord


class ModuleError(BaseModel):
    """Stable error shape from api_contracts.md."""

    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_service_error(cls, error: SavedSearchServiceError) -> "ModuleError":
        return cls(code=error.code, message=error.message, details=dict(error.details))


class HealthResponse(BaseModel):
    """Health-check response."""

    status: str
    database: str


class Money(BaseModel):
    """Money contract: decimal string plus ISO currency."""

    amount: str
    currency: str

    @classmethod
    def from_value(cls, value: Optional[MoneyValue]) -> Optional["Money"]:
        if value is None:
            return None
        return cls(amount=value.amount, currency=value.currency)


class MarketplaceRead(BaseModel):
    """Marketplace read summary."""

    id: UUID
    code: str
    display_name: str

    @classmethod
    def from_record(cls, record: MarketplaceSummary) -> "MarketplaceRead":
        return cls(id=record.id, code=record.code, display_name=record.display_name)


class DomainRead(BaseModel):
    """Canonical domain read summary."""

    id: UUID
    fqdn: str
    sld: str
    tld: str
    punycode_fqdn: str
    unicode_fqdn: Optional[str]
    is_valid: bool

    @classmethod
    def from_record(cls, record: DomainSummary) -> "DomainRead":
        return cls(
            id=record.id,
            fqdn=record.fqdn,
            sld=record.sld,
            tld=record.tld,
            punycode_fqdn=record.punycode_fqdn,
            unicode_fqdn=record.unicode_fqdn,
            is_valid=record.is_valid,
        )


class AuctionListingRead(BaseModel):
    """Normalized auction listing read model."""

    id: UUID
    source_item_id: str
    source_url: Optional[str]
    auction_type: str
    status: str
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    current_bid: Optional[Money]
    min_bid: Optional[Money]
    bid_count: Optional[int]
    watchers_count: Optional[int]
    first_seen_at: datetime
    last_seen_at: datetime
    closed_at: Optional[datetime]
    marketplace: MarketplaceRead
    domain: DomainRead

    @classmethod
    def from_record(cls, record: AuctionListingRecord) -> "AuctionListingRead":
        return cls(
            id=record.id,
            source_item_id=record.source_item_id,
            source_url=record.source_url,
            auction_type=record.auction_type,
            status=record.status,
            starts_at=record.starts_at,
            ends_at=record.ends_at,
            current_bid=Money.from_value(record.current_bid),
            min_bid=Money.from_value(record.min_bid),
            bid_count=record.bid_count,
            watchers_count=record.watchers_count,
            first_seen_at=record.first_seen_at,
            last_seen_at=record.last_seen_at,
            closed_at=record.closed_at,
            marketplace=MarketplaceRead.from_record(record.marketplace),
            domain=DomainRead.from_record(record.domain),
        )


class AuctionListResponse(BaseModel):
    """Paginated normalized auction list response."""

    items: List[AuctionListingRead]
    total: int
    limit: int
    offset: int
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_page(cls, page: AuctionListingPage) -> "AuctionListResponse":
        return cls(
            items=[AuctionListingRead.from_record(item) for item in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
            errors=[],
        )


class ValueRange(BaseModel):
    """String-safe value range."""

    low: str
    high: str
    currency: str

    @classmethod
    def from_value(cls, value: Optional[ValueRangeValue]) -> Optional["ValueRange"]:
        if value is None:
            return None
        return cls(low=value.low, high=value.high, currency=value.currency)


class GenerateAppraisalReportRequest(BaseModel):
    """Request shape for composing an appraisal report."""

    organization_id: UUID
    domain_id: UUID
    valuation_run_id: UUID
    include_ai_explanations: bool = True
    report_template_version: str = "appraisal-v1"
    created_by_user_id: Optional[UUID] = None


class AppraisalReportRead(BaseModel):
    """Stored appraisal report response model."""

    id: UUID
    organization_id: UUID
    domain_id: UUID
    valuation_run_id: UUID
    status: str
    report_template_version: str
    generated_at: datetime
    expires_at: Optional[datetime]
    created_by_user_id: Optional[UUID]
    report_json: AppraisalReportContract
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: AppraisalReportRecord) -> "AppraisalReportRead":
        return cls(
            id=record.id,
            organization_id=record.organization_id,
            domain_id=record.domain_id,
            valuation_run_id=record.valuation_run_id,
            status=record.status,
            report_template_version=record.report_template_version,
            generated_at=record.generated_at,
            expires_at=record.expires_at,
            created_by_user_id=record.created_by_user_id,
            report_json=record.report_json,
            errors=[],
        )


class CreateWatchlistRequest(BaseModel):
    """Request shape for creating a watchlist."""

    organization_id: UUID
    owner_user_id: UUID
    name: str = Field(min_length=1, max_length=255)
    visibility: str


class AddWatchlistItemRequest(BaseModel):
    """Request shape for adding a watchlist item."""

    domain_id: Optional[UUID] = None
    auction_id: Optional[UUID] = None
    created_by_user_id: UUID
    notes: Optional[str] = Field(default=None, max_length=2000)


class WatchlistItemRead(BaseModel):
    """Watchlist item response model."""

    id: UUID
    watchlist_id: UUID
    domain_id: Optional[UUID]
    auction_id: Optional[UUID]
    notes: Optional[str]
    created_at: datetime
    created_by_user_id: UUID

    @classmethod
    def from_record(cls, record: WatchlistItemRecord) -> "WatchlistItemRead":
        return cls(
            id=record.id,
            watchlist_id=record.watchlist_id,
            domain_id=record.domain_id,
            auction_id=record.auction_id,
            notes=record.notes,
            created_at=record.created_at,
            created_by_user_id=record.created_by_user_id,
        )


class WatchlistRead(BaseModel):
    """Watchlist response model."""

    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    name: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    item_count: int
    items: List[WatchlistItemRead] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: WatchlistRecord) -> "WatchlistRead":
        return cls(
            id=record.id,
            organization_id=record.organization_id,
            owner_user_id=record.owner_user_id,
            name=record.name,
            visibility=record.visibility,
            created_at=record.created_at,
            updated_at=record.updated_at,
            deleted_at=record.deleted_at,
            item_count=record.item_count,
            items=[WatchlistItemRead.from_record(item) for item in record.items],
        )


class WatchlistListResponse(BaseModel):
    """Watchlist collection response."""

    items: List[WatchlistRead]
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_records(cls, records: List[WatchlistRecord]) -> "WatchlistListResponse":
        return cls(items=[WatchlistRead.from_record(record) for record in records], errors=[])


class WatchlistItemMutationResponse(BaseModel):
    """Stable response for adding or removing watchlist items."""

    watchlist_item: Optional[WatchlistItemRead] = None
    created: bool = False
    removed: bool = False
    errors: List[ModuleError] = Field(default_factory=list)


class AlertRuleCreateRequest(BaseModel):
    """Request shape for creating an alert rule."""

    organization_id: UUID
    watchlist_id: UUID
    rule_type: str
    is_enabled: bool = True
    threshold_json: Dict[str, Any] = Field(default_factory=dict)
    channel_config_json: Dict[str, Any] = Field(default_factory=dict)


class AlertRuleRead(BaseModel):
    """Alert-rule response model."""

    id: UUID
    organization_id: UUID
    watchlist_id: UUID
    rule_type: str
    is_enabled: bool
    threshold_json: Dict[str, Any]
    channel_config_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: AlertRuleRecord) -> "AlertRuleRead":
        return cls(
            id=record.id,
            organization_id=record.organization_id,
            watchlist_id=record.watchlist_id,
            rule_type=record.rule_type,
            is_enabled=record.is_enabled,
            threshold_json=record.threshold_json,
            channel_config_json=record.channel_config_json,
            created_at=record.created_at,
            updated_at=record.updated_at,
            errors=[],
        )


class SavedSearchCreateRequest(BaseModel):
    """Request shape for the saved-search skeleton."""

    organization_id: UUID
    owner_user_id: UUID
    name: str = Field(min_length=1, max_length=255)
    search_scope: str
    filters_json: Dict[str, Any] = Field(default_factory=dict)
    sort_json: Dict[str, Any] = Field(default_factory=dict)


class SavedSearchRead(BaseModel):
    """Saved-search response model."""

    id: Optional[UUID]
    organization_id: UUID
    owner_user_id: UUID
    name: str
    search_scope: str
    filters_json: Dict[str, Any]
    sort_json: Dict[str, Any]

    @classmethod
    def from_record(cls, record: SavedSearchRecord) -> "SavedSearchRead":
        return cls(
            id=record.id,
            organization_id=record.organization_id,
            owner_user_id=record.owner_user_id,
            name=record.name,
            search_scope=record.search_scope,
            filters_json=record.filters_json,
            sort_json=record.sort_json,
        )


class SavedSearchMutationResponse(BaseModel):
    """Saved-search mutation response, including placeholder support state."""

    supported: bool
    saved_search: Optional[SavedSearchRead]
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: SavedSearchMutationResult) -> "SavedSearchMutationResponse":
        return cls(
            supported=result.supported,
            saved_search=SavedSearchRead.from_record(result.saved_search) if result.saved_search else None,
            errors=[ModuleError.from_service_error(error) for error in result.errors],
        )


class SavedSearchListResponse(BaseModel):
    """Saved-search list response, including placeholder support state."""

    supported: bool
    items: List[SavedSearchRead]
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: SavedSearchListResult) -> "SavedSearchListResponse":
        return cls(
            supported=result.supported,
            items=[SavedSearchRead.from_record(item) for item in result.items],
            errors=[ModuleError.from_service_error(error) for error in result.errors],
        )


class UndervaluedAuctionRead(BaseModel):
    """Dashboard-ready undervalued-auction read model."""

    auction_id: UUID
    domain_id: UUID
    fqdn: str
    marketplace_code: str
    auction_type: str
    auction_status: str
    ends_at: Optional[datetime]
    current_bid: Optional[Money]
    estimated_wholesale_range: Optional[ValueRange]
    estimated_retail_range: Optional[ValueRange]
    bid_to_estimated_wholesale_ratio: Optional[str]
    bid_to_estimated_retail_ratio: Optional[str]
    confidence_level: str
    risk_score: Optional[str]
    risk_flags: List[dict] = Field(default_factory=list)
    status: str
    reasons: List[str] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: UndervaluedAuctionRecord) -> "UndervaluedAuctionRead":
        return cls(
            auction_id=record.auction_id,
            domain_id=record.domain_id,
            fqdn=record.fqdn,
            marketplace_code=record.marketplace_code,
            auction_type=record.auction_type,
            auction_status=record.auction_status,
            ends_at=record.ends_at,
            current_bid=Money.from_value(record.current_bid),
            estimated_wholesale_range=ValueRange.from_value(record.estimated_wholesale_range),
            estimated_retail_range=ValueRange.from_value(record.estimated_retail_range),
            bid_to_estimated_wholesale_ratio=record.bid_to_estimated_wholesale_ratio,
            bid_to_estimated_retail_ratio=record.bid_to_estimated_retail_ratio,
            confidence_level=record.confidence_level,
            risk_score=record.risk_score,
            risk_flags=record.risk_flags,
            status=record.status,
            reasons=record.reasons,
        )


class UndervaluedAuctionListResponse(BaseModel):
    """Paginated opportunity response for dashboard use."""

    items: List[UndervaluedAuctionRead]
    total: int
    limit: int
    offset: int
    errors: List[ModuleError] = Field(default_factory=list)

    @classmethod
    def from_page(cls, page: UndervaluedAuctionPage) -> "UndervaluedAuctionListResponse":
        return cls(
            items=[UndervaluedAuctionRead.from_record(item) for item in page.items],
            total=page.total,
            limit=page.limit,
            offset=page.offset,
            errors=[],
        )
