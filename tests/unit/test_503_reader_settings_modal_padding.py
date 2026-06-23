# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.
"""fork #503 (@sambong): the epub reader Settings modal must inset its body
content horizontally.

The #484 settings redesign moved every `.rs-section` to be a *direct child* of
`.md-content`. The base modal padding comes from `.md-content > div { padding:
15px 40px 30px; }` (main.css) — written for the old single-wrapper structure —
and is overridden for the redesigned sections by the higher-specificity scoped
rule `#settings-modal .rs-section { padding: 0.8em 0; }`. The net effect: zero
horizontal padding, so the section labels sat flush against the left edge and
the slider value readouts ("150%", "0px") were clipped at the right edge. The
reporter (on a short-but-wide NAS admin tab) saw this after the v4.0.169 scroll
fix made all the options reachable.

The fix restores a horizontal inset on `#settings-modal .md-content` itself and
bleeds the `<h3>` title bar back out past that padding so it keeps hugging the
modal's top corners. This pins both halves so a future template edit can't
silently drop the inset and reintroduce the flush-edge layout.

Verified live on cwn-local at 1100x560 (reporter's window shape) and 390x740
(mobile): section left/right insets non-zero and symmetric, value readouts no
longer clipped, title bar full-bleed.
"""

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
TEMPLATE = REPO / "cps" / "templates" / "read.html"


def _src():
    return TEMPLATE.read_text(encoding="utf-8")


def _rule_body(src, selector):
    """Return the declaration block for the first `selector { ... }` rule."""
    idx = src.find(selector)
    assert idx != -1, f"expected a CSS rule for `{selector}` in read.html"
    open_brace = src.index("{", idx)
    close_brace = src.index("}", open_brace)
    return src[open_brace + 1 : close_brace]


def _horizontal_padding_present(decl):
    """True if a `padding:` declaration in `decl` carries a non-zero left/right
    value (shorthand 1-4 values; vertical-only `0.8em 0` does NOT count)."""
    m = re.search(r"padding\s*:\s*([^;]+);", decl)
    if not m:
        return False
    parts = m.group(1).split()
    if len(parts) == 1:  # all sides
        horiz = parts[0]
    elif len(parts) == 2:  # vertical | horizontal
        horiz = parts[1]
    elif len(parts) == 3:  # top | horizontal | bottom
        horiz = parts[1]
    else:  # top right bottom left
        horiz = parts[1]
    return not re.fullmatch(r"0(px|em|rem|%)?", horiz)


def test_settings_modal_content_has_horizontal_padding():
    decl = _rule_body(_src(), "#settings-modal .md-content")
    assert _horizontal_padding_present(decl), (
        "#settings-modal .md-content must declare non-zero horizontal padding so "
        "the redesigned sections are inset from the modal edge (#503 — the base "
        "`.md-content > div` padding no longer reaches direct-child sections)"
    )


def test_settings_modal_title_bleeds_full_width():
    decl = _rule_body(_src(), "#settings-modal h3")
    m = re.search(r"margin\s*:\s*([^;]+);", decl)
    assert m, "#settings-modal h3 must declare a margin"
    parts = m.group(1).split()
    # Need a negative horizontal margin to pull the title bar back out past the
    # .md-content padding so it keeps hugging the top corners.
    horiz = parts[1] if len(parts) >= 2 else parts[0]
    assert horiz.startswith("-"), (
        "#settings-modal h3 must use a negative horizontal margin so its "
        "background title bar spans the full modal width despite the body inset "
        "(#503)"
    )


def test_settings_sections_still_present():
    # Guard the structural assumption the fix relies on: sections are direct
    # children of .md-content (so the inset must come from .md-content itself).
    src = _src()
    assert 'class="rs-section' in src, "reader settings sections must exist"
    assert "#settings-modal .rs-section { padding: 0.8em 0" in src, (
        "the scoped .rs-section rule that zeroes section horizontal padding is "
        "the reason the inset must live on .md-content — if this changes, revisit "
        "the #503 fix"
    )
