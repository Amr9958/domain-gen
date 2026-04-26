"""Repositories for watchlists and alert rules."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from sqlalchemy import select

from domain_intel.db.models import AlertRule, OrganizationMember, Watchlist, WatchlistItem
from domain_intel.repositories.base import BaseRepository
from domain_intel.services.alert_service import AlertRuleRecord, CreateAlertRuleCommand
from domain_intel.services.watchlist_service import (
    AddWatchlistItemCommand,
    CreateWatchlistCommand,
    RemoveWatchlistItemCommand,
    WatchlistItemRecord,
    WatchlistRecord,
)


class WatchlistRepository(BaseRepository):
    """SQLAlchemy-backed watchlist repository."""

    def list_watchlists(self, organization_id, owner_user_id):
        """List watchlists with grouped items."""

        if owner_user_id is not None and not self._user_belongs_to_org(organization_id, owner_user_id):
            return []
        statement = select(Watchlist).where(
            Watchlist.organization_id == organization_id,
            Watchlist.deleted_at.is_(None),
        )
        if owner_user_id is not None:
            statement = statement.where(Watchlist.owner_user_id == owner_user_id)

        watchlists = list(self.session.scalars(statement.order_by(Watchlist.updated_at.desc())).all())
        if not watchlists:
            return []

        watchlist_ids = [watchlist.id for watchlist in watchlists]
        items = list(
            self.session.scalars(
                select(WatchlistItem)
                .where(WatchlistItem.watchlist_id.in_(watchlist_ids))
                .order_by(WatchlistItem.created_at.desc())
            ).all()
        )
        grouped_items: Dict[object, List[WatchlistItemRecord]] = defaultdict(list)
        for item in items:
            grouped_items[item.watchlist_id].append(self._item_to_record(item))

        return [
            self._watchlist_to_record(watchlist, grouped_items.get(watchlist.id, []))
            for watchlist in watchlists
        ]

    def create_watchlist(self, command: CreateWatchlistCommand) -> WatchlistRecord:
        """Create and return a watchlist."""

        if not self._user_belongs_to_org(command.organization_id, command.owner_user_id):
            raise PermissionError("owner_user_id is not a member of the requested organization.")
        watchlist = Watchlist(
            organization_id=command.organization_id,
            owner_user_id=command.owner_user_id,
            name=command.name,
            visibility=command.visibility,
        )
        self.session.add(watchlist)
        self.session.commit()
        self.session.refresh(watchlist)
        return self._watchlist_to_record(watchlist, [])

    def add_item(self, command: AddWatchlistItemCommand) -> WatchlistItemRecord:
        """Add and return a watchlist item."""

        watchlist = self.session.get(Watchlist, command.watchlist_id)
        if watchlist is None or watchlist.deleted_at is not None:
            raise ValueError("Watchlist was not found.")
        if not self._user_belongs_to_org(watchlist.organization_id, command.created_by_user_id):
            raise PermissionError("created_by_user_id is not allowed to modify this watchlist.")
        item = WatchlistItem(
            watchlist_id=command.watchlist_id,
            domain_id=command.domain_id,
            auction_id=command.auction_id,
            notes=command.notes,
            created_by_user_id=command.created_by_user_id,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return self._item_to_record(item)

    def remove_item(self, command: RemoveWatchlistItemCommand) -> bool:
        """Delete a watchlist item when it belongs to the requested watchlist."""

        item = self.session.get(WatchlistItem, command.watchlist_item_id)
        if item is None or item.watchlist_id != command.watchlist_id:
            return False
        self.session.delete(item)
        self.session.commit()
        return True

    def _watchlist_to_record(self, watchlist: Watchlist, items: List[WatchlistItemRecord]) -> WatchlistRecord:
        return WatchlistRecord(
            id=watchlist.id,
            organization_id=watchlist.organization_id,
            owner_user_id=watchlist.owner_user_id,
            name=watchlist.name,
            visibility=watchlist.visibility,
            created_at=watchlist.created_at,
            updated_at=watchlist.updated_at,
            deleted_at=watchlist.deleted_at,
            items=items,
        )

    def _item_to_record(self, item: WatchlistItem) -> WatchlistItemRecord:
        return WatchlistItemRecord(
            id=item.id,
            watchlist_id=item.watchlist_id,
            domain_id=item.domain_id,
            auction_id=item.auction_id,
            notes=item.notes,
            created_at=item.created_at,
            created_by_user_id=item.created_by_user_id,
        )

    def _user_belongs_to_org(self, organization_id, user_id) -> bool:
        return (
            self.session.scalar(
                select(OrganizationMember.user_id).where(
                    OrganizationMember.organization_id == organization_id,
                    OrganizationMember.user_id == user_id,
                )
            )
            is not None
        )


class AlertRuleRepository(BaseRepository):
    """SQLAlchemy-backed alert-rule repository."""

    def create_rule(self, command: CreateAlertRuleCommand) -> AlertRuleRecord:
        """Persist and return an alert rule."""

        watchlist = self.session.get(Watchlist, command.watchlist_id)
        if watchlist is None or watchlist.deleted_at is not None:
            raise ValueError("Watchlist was not found.")
        if watchlist.organization_id != command.organization_id:
            raise PermissionError("Alert rules must use the watchlist organization.")
        rule = AlertRule(
            organization_id=command.organization_id,
            watchlist_id=command.watchlist_id,
            rule_type=command.rule_type,
            is_enabled=command.is_enabled,
            threshold_json=command.threshold_json,
            channel_config_json=command.channel_config_json,
        )
        self.session.add(rule)
        self.session.commit()
        self.session.refresh(rule)
        return AlertRuleRecord(
            id=rule.id,
            organization_id=rule.organization_id,
            watchlist_id=rule.watchlist_id,
            rule_type=rule.rule_type,
            is_enabled=rule.is_enabled,
            threshold_json=dict(rule.threshold_json),
            channel_config_json=dict(rule.channel_config_json),
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
