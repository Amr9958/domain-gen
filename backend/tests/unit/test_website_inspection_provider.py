"""Website inspection provider tests."""

from __future__ import annotations

from uuid import uuid4

import pytest


pytest.importorskip("httpx")

import httpx

from domain_intel.core.enums import WebsitePageCategory
from domain_intel.enrichment.contracts import DomainTarget
from domain_intel.enrichment.providers import HttpWebsiteInspectionProvider


def _target(fqdn: str, sld: str | None = None) -> DomainTarget:
    domain_sld = sld or fqdn.split(".")[0]
    return DomainTarget(
        domain_id=uuid4(),
        fqdn=fqdn,
        sld=domain_sld,
        tld="com",
        punycode_fqdn=fqdn,
        unicode_fqdn=fqdn,
    )


def test_sales_landing_page_detection_sets_sales_category() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        html = "<html><title>Example</title><body>This domain is for sale. Make an offer today.</body></html>"
        return httpx.Response(200, text=html, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    provider = HttpWebsiteInspectionProvider(client=client)

    result = provider.inspect(_target("forsaleexample.com"))

    assert result.status.value == "completed"
    assert result.metadata["page_category"] == WebsitePageCategory.SALES_LANDING_PAGE.value
    assert result.verified_facts[1].fact_value_json["page_category"] == WebsitePageCategory.SALES_LANDING_PAGE.value


def test_parked_page_detection_sets_parked_category() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        html = "<html><title>Parking</title><body>Sponsored listings and related searches.</body></html>"
        return httpx.Response(200, text=html, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    provider = HttpWebsiteInspectionProvider(client=client)

    result = provider.inspect(_target("parkedexample.com"))

    assert result.metadata["page_category"] == WebsitePageCategory.PARKED_PAGE.value
    assert result.verified_facts[1].fact_value_json["page_category"] == WebsitePageCategory.PARKED_PAGE.value


def test_cross_domain_redirect_detection_sets_redirect_category() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "redirectme.com":
            return httpx.Response(
                302,
                headers={"location": "https://destination.example/landing"},
                request=request,
            )
        return httpx.Response(200, text="<html><title>Destination</title><body>Welcome.</body></html>", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    provider = HttpWebsiteInspectionProvider(client=client)

    result = provider.inspect(_target("redirectme.com"))

    assert result.metadata["page_category"] == WebsitePageCategory.REDIRECT.value
    assert result.verified_facts[1].fact_value_json["page_category"] == WebsitePageCategory.REDIRECT.value


def test_blank_page_detection_marks_inactive_pages() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="<html><body>Not found</body></html>", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    provider = HttpWebsiteInspectionProvider(client=client)

    result = provider.inspect(_target("inactiveexample.com"))

    assert result.metadata["page_category"] == WebsitePageCategory.BLANK_INACTIVE.value
    assert result.verified_facts[1].fact_value_json["page_category"] == WebsitePageCategory.BLANK_INACTIVE.value
