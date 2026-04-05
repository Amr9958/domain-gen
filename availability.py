"""Heuristic domain availability checks.

This module is intentionally conservative:
- it always evaluates the actual full domain the user sees
- it never falls back to checking a different TLD
- it prefers "Unknown" when the signal is weak

A future registrar-backed or registry-backed checker can replace
`check_availability_details` without changing the Streamlit UI contract.
"""

from __future__ import annotations

import contextlib
import io
import socket
from dataclasses import dataclass

import whois


LIKELY_REGISTERED = "likely_registered"
UNKNOWN = "unknown"

LIKELY_REGISTERED_LABEL = "🔴 Likely Registered"
UNKNOWN_LABEL = "🟡 Unknown"


@dataclass(frozen=True)
class AvailabilityResult:
    """Structured heuristic result for a single full domain name."""

    status: str
    label: str
    detail: str
    confidence: str


def _has_registration_signal(record: object) -> bool:
    """Return True when WHOIS data suggests the actual domain is registered."""
    for field_name in ("creation_date", "registrar", "name_servers", "status"):
        value = getattr(record, field_name, None)
        if value:
            return True
    return False


def check_availability_details(domain_with_ext: str) -> AvailabilityResult:
    """Return a conservative heuristic availability result.

    Limitations:
    - WHOIS coverage is inconsistent across TLDs.
    - DNS absence does not prove availability.
    - DNS presence is a useful registration signal, but not a registry guarantee.

    Because of those limits, this function only returns:
    - `Likely Registered` when it sees positive evidence
    - `Unknown` otherwise
    """
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            record = whois.whois(domain_with_ext)
        if _has_registration_signal(record):
            return AvailabilityResult(
                status=LIKELY_REGISTERED,
                label=LIKELY_REGISTERED_LABEL,
                detail="WHOIS returned registration signals for this exact domain.",
                confidence="medium",
            )
    except Exception:
        # WHOIS failures are common for some TLDs and do not imply availability.
        pass

    try:
        socket.gethostbyname(domain_with_ext)
        return AvailabilityResult(
            status=LIKELY_REGISTERED,
            label=LIKELY_REGISTERED_LABEL,
            detail="DNS resolves for this exact domain, which usually indicates registration.",
            confidence="low",
        )
    except socket.gaierror:
        return AvailabilityResult(
            status=UNKNOWN,
            label=UNKNOWN_LABEL,
            detail="No reliable registration signal was found for this exact domain.",
            confidence="low",
        )
    except Exception:
        return AvailabilityResult(
            status=UNKNOWN,
            label=UNKNOWN_LABEL,
            detail="Availability could not be verified confidently for this exact domain.",
            confidence="low",
        )


def check_availability(domain_with_ext: str) -> str:
    """Backward-compatible string label for the current UI."""
    return check_availability_details(domain_with_ext).label
