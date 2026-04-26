"""Dynadot marketplace adapter."""

from domain_intel.marketplaces.dynadot.adapter import (
    ADAPTER_VERSION,
    DynadotAuctionAdapter,
    DynadotAuctionAdapterConfig,
)
from domain_intel.marketplaces.dynadot.parser import (
    PARSER_VERSION,
    DynadotParsedListing,
    DynadotParsedPage,
    parse_dynadot_listing_page,
)

__all__ = [
    "ADAPTER_VERSION",
    "DynadotAuctionAdapter",
    "DynadotAuctionAdapterConfig",
    "DynadotParsedListing",
    "DynadotParsedPage",
    "PARSER_VERSION",
    "parse_dynadot_listing_page",
]
