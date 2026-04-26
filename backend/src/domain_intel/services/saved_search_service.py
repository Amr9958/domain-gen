"""Saved-search contract skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from uuid import UUID


@dataclass(frozen=True)
class SavedSearchRecord:
    """Saved-search read model reserved for future persistence."""

    id: Optional[UUID]
    organization_id: UUID
    owner_user_id: UUID
    name: str
    search_scope: str
    filters_json: Dict[str, object]
    sort_json: Dict[str, object]


@dataclass(frozen=True)
class SavedSearchCommand:
    """Saved-search create command."""

    organization_id: UUID
    owner_user_id: UUID
    name: str
    search_scope: str
    filters_json: Dict[str, object]
    sort_json: Dict[str, object]


@dataclass(frozen=True)
class SavedSearchServiceError:
    """Stable service-layer error for the saved-search skeleton."""

    code: str
    message: str
    details: Dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SavedSearchMutationResult:
    """Mutation result for placeholder saved-search support."""

    supported: bool
    saved_search: Optional[SavedSearchRecord]
    errors: List[SavedSearchServiceError]


@dataclass(frozen=True)
class SavedSearchListResult:
    """List result for placeholder saved-search support."""

    supported: bool
    items: List[SavedSearchRecord]
    errors: List[SavedSearchServiceError]


class SavedSearchService:
    """Placeholder saved-search service until shared schema support exists."""

    def create_saved_search(self, command: SavedSearchCommand) -> SavedSearchMutationResult:
        """Return a structured blocker instead of inventing persistence."""

        return SavedSearchMutationResult(
            supported=False,
            saved_search=SavedSearchRecord(
                id=None,
                organization_id=command.organization_id,
                owner_user_id=command.owner_user_id,
                name=command.name,
                search_scope=command.search_scope,
                filters_json=command.filters_json,
                sort_json=command.sort_json,
            ),
            errors=[
                SavedSearchServiceError(
                    code="schema_contract_mismatch",
                    message="Saved-search persistence is not available in the approved shared schema.",
                    details={"required_patch": "saved_searches_table"},
                )
            ],
        )

    def list_saved_searches(self, organization_id: UUID, owner_user_id: UUID) -> SavedSearchListResult:
        """Return an explicit placeholder response until persistence exists."""

        return SavedSearchListResult(
            supported=False,
            items=[],
            errors=[
                SavedSearchServiceError(
                    code="schema_contract_mismatch",
                    message="Saved-search persistence is not available in the approved shared schema.",
                    details={
                        "organization_id": str(organization_id),
                        "owner_user_id": str(owner_user_id),
                        "required_patch": "saved_searches_table",
                    },
                )
            ],
        )
