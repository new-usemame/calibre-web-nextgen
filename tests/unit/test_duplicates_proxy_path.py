# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests for fork issue #514 (@chloeroform) — Duplicate Books
page must build asset and API URLs with the application-root prefix so they
work behind a reverse proxy mounted on a sub-path.

Two symptoms the reporter hit behind a proxy:

1. ``generic_cover.svg`` loads forever. The cover ``<img>`` fell back to a
   hardcoded ``/static/generic_cover.svg`` on error, which 404s behind a
   sub-path proxy, re-firing ``onerror`` with no ``this.onerror=null`` guard
   — an infinite request loop. The canonical fallback used everywhere else
   (cover_picker.html, book_edit.html, hardcover_review_matches.html) is
   ``this.onerror=null; this.src='{{ url_for('static', ...) }}'``.

2. "Failed to update duplicate group" / failed resolve. The dismiss,
   preview-resolution and execute-resolution POSTs used bare ``/duplicates/...``
   URLs instead of routing through the existing ``duplicateScanEndpoint()``
   helper (which prepends ``getPath()``), so they 404 behind the proxy.

These are structural pin-checks on the template + JS plus one behavioural
check that proves ``url_for`` actually emits the prefix once the
ReverseProxied middleware has set ``SCRIPT_NAME`` from ``X-Script-Name``.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DUP_HTML = REPO_ROOT / "cps" / "templates" / "duplicates.html"
DUP_JS = REPO_ROOT / "cps" / "static" / "js" / "duplicates.js"


@pytest.mark.unit
class TestDuplicatesTemplateCoverFallback:
    """The cover <img> onerror fallback must be proxy-safe and loop-guarded."""

    def _cover_img_line(self):
        for line in DUP_HTML.read_text().splitlines():
            if "generic_cover.svg" in line and "onerror" in line:
                return line
        raise AssertionError("no cover <img> with generic_cover.svg onerror found in duplicates.html")

    def test_fallback_uses_url_for_not_hardcoded_static(self):
        line = self._cover_img_line()
        assert "url_for('static'" in line or 'url_for("static"' in line, (
            "fork #514: generic_cover.svg fallback must use url_for('static', ...) "
            "so it carries the reverse-proxy sub-path prefix"
        )
        assert "'/static/generic_cover.svg'" not in line and '"/static/generic_cover.svg"' not in line, (
            "fork #514: hardcoded /static/generic_cover.svg 404s behind a sub-path proxy"
        )

    def test_fallback_has_onerror_guard(self):
        line = self._cover_img_line()
        assert "this.onerror=null" in line.replace(" ", ""), (
            "fork #514: without this.onerror=null a failing fallback re-fires "
            "onerror forever (the infinite-loading symptom)"
        )


@pytest.mark.unit
class TestDuplicatesJsProxySafeEndpoints:
    """The dismiss/preview/execute POSTs must route through getPath()."""

    def _js(self):
        return DUP_JS.read_text()

    def test_no_bare_absolute_duplicates_urls(self):
        js = self._js()
        # bare `url: '/duplicates/...'` or `'/duplicates/' +` (not wrapped by getPath/duplicateScanEndpoint)
        bare_url = re.findall(r"""url:\s*['"]/duplicates/""", js)
        bare_concat = re.findall(r"""=\s*['"]/duplicates/['"]\s*\+""", js)
        assert not bare_url, (
            f"fork #514: bare absolute /duplicates/ url(s) bypass the proxy prefix: {bare_url}"
        )
        assert not bare_concat, (
            f"fork #514: bare '/duplicates/' concatenation bypasses the proxy prefix: {bare_concat}"
        )

    def test_dismiss_endpoint_routes_through_getpath(self):
        js = self._js()
        # the dismiss/undismiss endpoint must be built via the existing helper
        assert "duplicateScanEndpoint('/duplicates/'" in js.replace('"', "'") or \
               "getPath() + '/duplicates/'" in js.replace('"', "'") or \
               re.search(r"duplicateScanEndpoint\(\s*['\"]/duplicates/['\"]", js), (
            "fork #514: dismiss endpoint must be wrapped by duplicateScanEndpoint()/getPath()"
        )

    def test_resolution_endpoints_route_through_getpath(self):
        js = self._js()
        for path in ("/duplicates/preview-resolution", "/duplicates/execute-resolution"):
            assert f"duplicateScanEndpoint('{path}')" in js or \
                   f'duplicateScanEndpoint("{path}")' in js, (
                f"fork #514: {path} POST must route through duplicateScanEndpoint() "
                f"so it carries the reverse-proxy prefix"
            )


@pytest.mark.unit
class TestReverseProxyUrlForPrefix:
    """Behavioural proof that url_for emits the sub-path prefix once the
    ReverseProxied middleware sets SCRIPT_NAME from X-Script-Name — the
    mechanism the template fix relies on."""

    def test_url_for_static_carries_x_script_name_prefix(self):
        from flask import Flask, url_for

        from cps.reverseproxy import ReverseProxied

        app = Flask(__name__)
        # ReverseProxied is WSGI middleware: it only sets SCRIPT_NAME when a
        # real request flows through wsgi_app, so exercise it via test_client,
        # not test_request_context (which bypasses the middleware stack).
        app.wsgi_app = ReverseProxied(app.wsgi_app)

        @app.route("/probe")
        def probe():
            return url_for("static", filename="generic_cover.svg")

        # Simulate a request arriving from a proxy mounted at /myprefix.
        resp = app.test_client().get("/myprefix/probe", headers={"X-Script-Name": "/myprefix"})
        url = resp.get_data(as_text=True)

        assert url == "/myprefix/static/generic_cover.svg", (
            f"expected proxy-prefixed static url, got {url!r}; the duplicates.html "
            f"fallback relies on this to avoid 404 + infinite retry behind a proxy"
        )
