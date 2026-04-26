"""Raw observation normalizers for marketplace evidence."""

from domain_intel.normalization.dynadot import DynadotAuctionNormalizer
from domain_intel.normalization.dropcatch import DropCatchAuctionNormalizer
from domain_intel.normalization.schemas import (
    AuctionNormalizer,
    AuctionSnapshot,
    CanonicalAuction,
    DomainIdentity,
    EvidenceRef,
    NormalizeRawItemRequest,
    NormalizeRawItemResponse,
)

__all__ = [
    "AuctionNormalizer",
    "AuctionSnapshot",
    "CanonicalAuction",
    "DomainIdentity",
    "DropCatchAuctionNormalizer",
    "DynadotAuctionNormalizer",
    "EvidenceRef",
    "NormalizeRawItemRequest",
    "NormalizeRawItemResponse",
]
