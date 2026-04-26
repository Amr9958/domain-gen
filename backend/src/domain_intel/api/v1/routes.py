"""Initial v1 REST routes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from domain_intel.api.dependencies import (
    get_alert_service,
    get_auction_service,
    get_health_service,
    get_opportunity_service,
    get_report_service,
    get_saved_search_service,
    get_watchlist_service,
)
from domain_intel.api.schemas import (
    AddWatchlistItemRequest,
    AlertRuleCreateRequest,
    AlertRuleRead,
    AppraisalReportRead,
    AuctionListResponse,
    CreateWatchlistRequest,
    GenerateAppraisalReportRequest,
    HealthResponse,
    SavedSearchCreateRequest,
    SavedSearchListResponse,
    SavedSearchMutationResponse,
    UndervaluedAuctionListResponse,
    WatchlistItemRead,
    WatchlistItemMutationResponse,
    WatchlistListResponse,
    WatchlistRead,
)
from domain_intel.core.enums import AuctionStatus, ConfidenceLevel, MarketplaceCode
from domain_intel.repositories.auction_repository import AuctionQueryFilters
from domain_intel.services.alert_service import AlertService, CreateAlertRuleCommand
from domain_intel.services.auction_service import AuctionService
from domain_intel.services.health_service import HealthService
from domain_intel.services.opportunity_service import OpportunityService, UndervaluationPolicy, UndervaluationQuery
from domain_intel.services.report_service import GenerateAppraisalReportCommand, ReportInputNotFoundError, ReportService
from domain_intel.services.saved_search_service import SavedSearchCommand, SavedSearchService
from domain_intel.services.watchlist_service import (
    AddWatchlistItemCommand,
    CreateWatchlistCommand,
    RemoveWatchlistItemCommand,
    WatchlistService,
)


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health(service: HealthService = Depends(get_health_service)) -> HealthResponse:
    """Return API and database health."""

    result = service.check()
    return HealthResponse(status=result.status, database=result.database)


@router.get("/auctions", response_model=AuctionListResponse, tags=["auctions"])
def list_auction_listings(
    source: Optional[MarketplaceCode] = Query(default=None, description="Marketplace code."),
    tld: Optional[str] = Query(default=None, min_length=1, description="TLD with or without leading dot."),
    closes_after: Optional[datetime] = Query(default=None, description="Only listings closing at or after this UTC time."),
    closes_before: Optional[datetime] = Query(default=None, description="Only listings closing at or before this UTC time."),
    min_price: Optional[Decimal] = Query(default=None, ge=0, description="Minimum current bid amount."),
    max_price: Optional[Decimal] = Query(default=None, ge=0, description="Maximum current bid amount."),
    status: Optional[AuctionStatus] = Query(default=None, description="Canonical auction status."),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AuctionService = Depends(get_auction_service),
) -> AuctionListResponse:
    """List normalized auctions with source, TLD, close time, and price filters."""

    filters = AuctionQueryFilters(
        source=source.value if source is not None else None,
        tld=tld,
        closes_after=closes_after,
        closes_before=closes_before,
        min_price=min_price,
        max_price=max_price,
        status=status,
        limit=limit,
        offset=offset,
    )
    page = service.list_listings(filters)
    return AuctionListResponse.from_page(page)


@router.post("/reports/appraisals", response_model=AppraisalReportRead, tags=["reports"])
def generate_appraisal_report(
    request: GenerateAppraisalReportRequest,
    service: ReportService = Depends(get_report_service),
) -> AppraisalReportRead:
    """Generate and persist a structured appraisal report."""

    try:
        record = service.generate_appraisal_report(
            GenerateAppraisalReportCommand(
                organization_id=request.organization_id,
                domain_id=request.domain_id,
                valuation_run_id=request.valuation_run_id,
                include_ai_explanations=request.include_ai_explanations,
                report_template_version=request.report_template_version,
                created_by_user_id=request.created_by_user_id,
            )
        )
    except ReportInputNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AppraisalReportRead.from_record(record)


@router.get("/reports/appraisals/{report_id}", response_model=AppraisalReportRead, tags=["reports"])
def get_appraisal_report(
    report_id: UUID,
    organization_id: Optional[UUID] = Query(default=None),
    service: ReportService = Depends(get_report_service),
) -> AppraisalReportRead:
    """Retrieve a stored appraisal report."""

    record = service.get_appraisal_report(report_id=report_id, organization_id=organization_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Appraisal report {report_id} was not found.")
    return AppraisalReportRead.from_record(record)


@router.get("/watchlists", response_model=WatchlistListResponse, tags=["watchlists"])
def list_watchlists(
    organization_id: UUID = Query(...),
    owner_user_id: Optional[UUID] = Query(default=None),
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistListResponse:
    """List watchlists in the requested organization scope."""

    records = service.list_watchlists(organization_id=organization_id, owner_user_id=owner_user_id)
    return WatchlistListResponse.from_records(records)


@router.post("/watchlists", response_model=WatchlistRead, tags=["watchlists"])
def create_watchlist(
    request: CreateWatchlistRequest,
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistRead:
    """Create a watchlist."""

    record = service.create_watchlist(
        CreateWatchlistCommand(
            organization_id=request.organization_id,
            owner_user_id=request.owner_user_id,
            name=request.name,
            visibility=request.visibility,
        )
    )
    return WatchlistRead.from_record(record)


@router.post("/watchlists/{watchlist_id}/items", response_model=WatchlistItemMutationResponse, tags=["watchlists"])
def add_watchlist_item(
    watchlist_id: UUID,
    request: AddWatchlistItemRequest,
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistItemMutationResponse:
    """Add a domain and/or auction to a watchlist."""

    try:
        record = service.add_item(
            AddWatchlistItemCommand(
                watchlist_id=watchlist_id,
                created_by_user_id=request.created_by_user_id,
                domain_id=request.domain_id,
                auction_id=request.auction_id,
                notes=request.notes,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WatchlistItemMutationResponse(
        watchlist_item=WatchlistItemRead.from_record(record),
        created=True,
        removed=False,
        errors=[],
    )


@router.delete(
    "/watchlists/{watchlist_id}/items/{watchlist_item_id}",
    response_model=WatchlistItemMutationResponse,
    tags=["watchlists"],
)
def remove_watchlist_item(
    watchlist_id: UUID,
    watchlist_item_id: UUID,
    service: WatchlistService = Depends(get_watchlist_service),
) -> WatchlistItemMutationResponse:
    """Remove a watchlist item."""

    removed = service.remove_item(
        RemoveWatchlistItemCommand(
            watchlist_id=watchlist_id,
            watchlist_item_id=watchlist_item_id,
        )
    )
    if not removed:
        raise HTTPException(status_code=404, detail=f"Watchlist item {watchlist_item_id} was not found.")
    return WatchlistItemMutationResponse(created=False, removed=True, errors=[])


@router.post("/alert-rules", response_model=AlertRuleRead, tags=["alerts"])
def create_alert_rule(
    request: AlertRuleCreateRequest,
    service: AlertService = Depends(get_alert_service),
) -> AlertRuleRead:
    """Create an alert rule."""

    try:
        record = service.create_rule(
            CreateAlertRuleCommand(
                organization_id=request.organization_id,
                watchlist_id=request.watchlist_id,
                rule_type=request.rule_type,
                is_enabled=request.is_enabled,
                threshold_json=request.threshold_json,
                channel_config_json=request.channel_config_json,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AlertRuleRead.from_record(record)


@router.get(
    "/opportunities/undervalued-auctions",
    response_model=UndervaluedAuctionListResponse,
    tags=["opportunities"],
)
def list_undervalued_auctions(
    source: Optional[MarketplaceCode] = Query(default=None, description="Marketplace code."),
    tld: Optional[str] = Query(default=None, min_length=1, description="TLD with or without leading dot."),
    min_confidence_level: ConfidenceLevel = Query(default=ConfidenceLevel.MEDIUM),
    max_risk_score: Decimal = Query(default=Decimal("0.35"), ge=0, le=1),
    max_bid_to_wholesale_ratio: Decimal = Query(default=Decimal("1.00"), gt=0),
    max_bid_to_retail_ratio: Decimal = Query(default=Decimal("0.35"), gt=0),
    include_rejected: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: OpportunityService = Depends(get_opportunity_service),
) -> UndervaluedAuctionListResponse:
    """List undervalued-auction candidates using configurable skeleton thresholds."""

    page = service.list_undervalued_auctions(
        UndervaluationQuery(
            source=source.value if source is not None else None,
            tld=tld,
            limit=limit,
            offset=offset,
            include_rejected=include_rejected,
            policy=UndervaluationPolicy(
                min_confidence_level=min_confidence_level.value,
                max_risk_score=max_risk_score,
                max_bid_to_wholesale_ratio=max_bid_to_wholesale_ratio,
                max_bid_to_retail_ratio=max_bid_to_retail_ratio,
            ),
        )
    )
    return UndervaluedAuctionListResponse.from_page(page)


@router.get("/saved-searches", response_model=SavedSearchListResponse, tags=["saved-searches"])
def list_saved_searches(
    organization_id: UUID = Query(...),
    owner_user_id: UUID = Query(...),
    service: SavedSearchService = Depends(get_saved_search_service),
) -> SavedSearchListResponse:
    """Return the saved-search placeholder response."""

    return SavedSearchListResponse.from_result(
        service.list_saved_searches(organization_id=organization_id, owner_user_id=owner_user_id)
    )


@router.post("/saved-searches", response_model=SavedSearchMutationResponse, tags=["saved-searches"])
def create_saved_search(
    request: SavedSearchCreateRequest,
    service: SavedSearchService = Depends(get_saved_search_service),
) -> SavedSearchMutationResponse:
    """Return the saved-search placeholder mutation response."""

    result = service.create_saved_search(
        SavedSearchCommand(
            organization_id=request.organization_id,
            owner_user_id=request.owner_user_id,
            name=request.name,
            search_scope=request.search_scope,
            filters_json=request.filters_json,
            sort_json=request.sort_json,
        )
    )
    return SavedSearchMutationResponse.from_result(result)
