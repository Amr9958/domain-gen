"""Watchlist service for investor workflow reads and mutations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Protocol
from uuid import UUID


@dataclass(frozen=True)
class WatchlistItemRecord:
    """Read model for a watchlist item."""

    id: UUID
    watchlist_id: UUID
    domain_id: Optional[UUID]
    auction_id: Optional[UUID]
    notes: Optional[str]
    created_at: datetime
    created_by_user_id: UUID


@dataclass(frozen=True)
class WatchlistRecord:
    """Read model for a watchlist including current items."""

    id: UUID
    organization_id: UUID
    owner_user_id: UUID
    name: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime]
    items: List[WatchlistItemRecord] = field(default_factory=list)

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class CreateWatchlistCommand:
    """Command for creating a watchlist."""

    organization_id: UUID
    owner_user_id: UUID
    name: str
    visibility: str


@dataclass(frozen=True)
class AddWatchlistItemCommand:
    """Command for attaching a domain and/or auction to a watchlist."""

    watchlist_id: UUID
    created_by_user_id: UUID
    domain_id: Optional[UUID]
    auction_id: Optional[UUID]
    notes: Optional[str]


@dataclass(frozen=True)
class RemoveWatchlistItemCommand:
    """Command for removing a watchlist item."""

    watchlist_id: UUID
    watchlist_item_id: UUID


class WatchlistRepositoryProtocol(Protocol):
    """Persistence boundary for watchlist operations."""

    def list_watchlists(self, organization_id: UUID, owner_user_id: Optional[UUID]) -> List[WatchlistRecord]:
        """List current watchlists for an organization or owner."""

    def create_watchlist(self, command: CreateWatchlistCommand) -> WatchlistRecord:
        """Create a watchlist."""

    def add_item(self, command: AddWatchlistItemCommand) -> WatchlistItemRecord:
        """Add a watchlist item."""

    def remove_item(self, command: RemoveWatchlistItemCommand) -> bool:
        """Remove a watchlist item and return whether a row was deleted."""


class WatchlistService:
    """Service facade for watchlist CRUD skeleton flows."""

    def __init__(self, repository: WatchlistRepositoryProtocol) -> None:
        self.repository = repository

    def list_watchlists(self, organization_id: UUID, owner_user_id: Optional[UUID] = None) -> List[WatchlistRecord]:
        """Return watchlists in scope."""

        return self.repository.list_watchlists(organization_id, owner_user_id)

    def create_watchlist(self, command: CreateWatchlistCommand) -> WatchlistRecord:
        """Create a watchlist."""

        return self.repository.create_watchlist(command)

    def add_item(self, command: AddWatchlistItemCommand) -> WatchlistItemRecord:
        """Add a domain and/or auction to a watchlist."""

        if command.domain_id is None and command.auction_id is None:
            raise ValueError("At least one of domain_id or auction_id is required.")
        return self.repository.add_item(command)

    def remove_item(self, command: RemoveWatchlistItemCommand) -> bool:
        """Remove a watchlist item."""

        return self.repository.remove_item(command)
