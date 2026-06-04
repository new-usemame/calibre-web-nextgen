# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Pinning tests for SPA fragment compatibility (merge of cwa/single-page).

Under the single-page app, `render_title_template` flips the parent template to
`fragment.html` for fragment XHRs (X-CWA-Fragment) and to `layout.html` for full
loads. A content template therefore MUST inherit via
`{% extends parent_template|default("layout.html") %}` — if it hardcodes
`{% extends "layout.html" %}`, an SPA navigation injects the entire chrome
(sidebar + header) into `#main-content`, so the page renders a second sidebar
and header inside the content area.

Two templates regressed exactly this way after the merges and were fixed:
`grid2.html` (second-series grid view) and `cover_picker.html` (Change Cover).
These tests pin every SPA-navigable content template to the parent_template
idiom so the regression can't return.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = REPO_ROOT / "cps" / "templates"

# Content templates served through render_title_template and reachable via SPA
# link navigation. Each must inherit the SPA-aware parent template.
SPA_CONTENT_TEMPLATES = [
    "index.html",
    "list.html",
    "grid.html",
    "grid2.html",          # second-series grid view — regressed, fixed
    "detail.html",
    "author.html",
    "search.html",
    "shelf.html",
    "shelf_list.html",
    "magic_shelf_list.html",
    "cover_picker.html",   # Change Cover — regressed, fixed
    "config_edit.html",
    "config_view_edit.html",
]

PARENT_IDIOM = 'extends parent_template|default("layout.html")'
HARDCODED = '{% extends "layout.html" %}'


@pytest.mark.parametrize("template", SPA_CONTENT_TEMPLATES)
def test_spa_template_uses_parent_template(template):
    src = (TEMPLATES / template).read_text()
    assert PARENT_IDIOM in src, (
        f"cps/templates/{template} must inherit via "
        f"`{{% {PARENT_IDIOM} %}}` so SPA fragment swaps don't inject the full "
        f"layout (sidebar + header) into #main-content."
    )
    assert HARDCODED not in src, (
        f"cps/templates/{template} must not hardcode `{HARDCODED}` — that breaks "
        f"SPA fragment rendering (duplicate sidebar/header inside content)."
    )


def test_grid2_regression_specifically_pinned():
    """grid2.html (second-series grid) is the canonical regression: pin it
    explicitly so the fix is never lost."""
    src = (TEMPLATES / "grid2.html").read_text()
    assert PARENT_IDIOM in src and HARDCODED not in src
