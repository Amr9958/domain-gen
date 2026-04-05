"""Browser helpers for outbound registrar search links."""

import webbrowser
from urllib.parse import quote


def open_namecheap_purchase(domain: str) -> None:
    """Open a registrar search page for the exact selected domain.

    This is only a convenience link. It does not perform automated checkout
    or confirm registrability.
    """
    webbrowser.open(
        f"https://www.namecheap.com/domains/registration/results/?domain={quote(domain)}"
    )
