"""FastAPI dependency factories."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from domain_intel.db.session import get_session
from domain_intel.repositories.auction_repository import AuctionRepository
from domain_intel.repositories.opportunity_repository import OpportunityRepository
from domain_intel.repositories.report_repository import AppraisalReportRepository
from domain_intel.repositories.workflow_repository import AlertRuleRepository, WatchlistRepository
from domain_intel.services.alert_service import AlertService
from domain_intel.services.auction_service import AuctionService
from domain_intel.services.health_service import HealthService
from domain_intel.services.opportunity_service import OpportunityService
from domain_intel.services.report_service import ReportService
from domain_intel.services.saved_search_service import SavedSearchService
from domain_intel.services.watchlist_service import WatchlistService


def get_auction_service(session: Session = Depends(get_session)) -> AuctionService:
    """Build the auction service for a request."""

    return AuctionService(AuctionRepository(session))


def get_health_service(session: Session = Depends(get_session)) -> HealthService:
    """Build the health service for a request."""

    return HealthService(session)


def get_report_service(session: Session = Depends(get_session)) -> ReportService:
    """Build the appraisal report service for a request."""

    return ReportService(AppraisalReportRepository(session))


def get_watchlist_service(session: Session = Depends(get_session)) -> WatchlistService:
    """Build the watchlist service for a request."""

    return WatchlistService(WatchlistRepository(session))


def get_alert_service(session: Session = Depends(get_session)) -> AlertService:
    """Build the alert-rule service for a request."""

    return AlertService(AlertRuleRepository(session))


def get_saved_search_service() -> SavedSearchService:
    """Build the saved-search placeholder service for a request."""

    return SavedSearchService()


def get_opportunity_service(session: Session = Depends(get_session)) -> OpportunityService:
    """Build the opportunity screening service for a request."""

    return OpportunityService(OpportunityRepository(session))
