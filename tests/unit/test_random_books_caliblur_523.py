# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression test for fork #523 — "No. of Random Books to Display" did nothing.

Reporter @chloeroform (v4.0.170): enabling "Show Random Books in Detail View"
never showed the random-books row anywhere.

Root cause: the random-books strip IS rendered server-side
(``cps/templates/index.html``: ``<div class="discover random-books">`` gated by
``current_user.show_detail_random()``), but the caliBlur theme carried a leftover
rule ``.pace-progress, .random-books { display: none }`` that hid the whole strip.
caliBlur is the ONLY shipped theme (``admin.py`` forces ``g.current_theme = 1``),
so the feature was dead for every user — there was no other theme to fall back to.

These tests pin that caliBlur no longer hides the strip, and that the strip markup
the feature depends on is still present and still gated on the per-user setting.
"""

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CALIBLUR_CSS = REPO / "cps" / "static" / "css" / "caliBlur.css"
CALIBLUR_OVERRIDE = REPO / "cps" / "static" / "css" / "caliBlur_override.css"
INDEX_HTML = REPO / "cps" / "templates" / "index.html"


def _css_rules(css: str):
    """Yield (selector_list, body) for each top-level rule. Crude but sufficient
    for a flat stylesheet with no nested at-rules around these selectors."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        yield m.group(1).strip(), m.group(2)


@pytest.mark.unit
class TestCaliBlurDoesNotHideRandomBooks:
    def test_no_display_none_on_random_books(self):
        css = CALIBLUR_CSS.read_text(encoding="utf-8")
        offenders = [
            sel.strip()[:90]
            for sel, body in _css_rules(css)
            if ".random-books" in sel and re.search(r"display\s*:\s*none", body)
        ]
        assert not offenders, (
            "caliBlur hides the Discover/Random Books strip via display:none on "
            ".random-books. caliBlur is the only shipped theme, so 'Show Random "
            "Books in Detail View' is dead for everyone (#523 @chloeroform). "
            "Offending rule(s): " + " | ".join(offenders)
        )

    def test_pace_progress_still_hidden(self):
        """The fix splits the shared rule — .pace-progress (the loading bar) must
        STILL be hidden; only .random-books should be released."""
        css = CALIBLUR_CSS.read_text(encoding="utf-8")
        hidden = any(
            ".pace-progress" in sel and re.search(r"display\s*:\s*none", body)
            for sel, body in _css_rules(css)
        )
        assert hidden, (
            ".pace-progress must remain display:none after splitting the rule — "
            "don't accidentally un-hide the pace.js loading bar. #523"
        )


@pytest.mark.unit
class TestRandomBooksHeadingNotPinnedToHeader:
    def test_override_unpins_random_heading(self):
        """Showing the strip means caliBlur's `.discover > h2` rule would pin the
        'Discover (Random Books)' heading to the fixed header bar (position:fixed,
        top:60), colliding with the page title. caliBlur_override.css must reset
        the random heading to static flow above the covers."""
        css = CALIBLUR_OVERRIDE.read_text(encoding="utf-8")
        offending = [
            (sel.strip()[:90], body)
            for sel, body in _css_rules(css)
            if "h2.random-books" in sel and "random-books" in sel
        ]
        assert offending, (
            "caliBlur_override.css must carry a rule targeting the random-books "
            "heading (h2.random-books inside .discover.random-books). #523"
        )
        assert any(re.search(r"position\s*:\s*static", body) for _sel, body in offending), (
            "the random-books heading override must set position:static so the "
            "heading sits above the covers instead of being pinned (position:fixed) "
            "into the header bar where it collides with the page title. #523"
        )


@pytest.mark.unit
class TestRandomBooksStripMarkupIntact:
    def test_strip_container_present_and_gated(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        assert 'class="discover random-books"' in html, (
            "index.html must still render the random-books strip container. #523"
        )
        assert "show_detail_random()" in html, (
            "the random-books strip must stay gated on the per-user "
            "show_detail_random() setting. #523"
        )
