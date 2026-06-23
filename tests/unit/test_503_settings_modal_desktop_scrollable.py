# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Acceptance test for fork #503.

The epub reader's redesigned Settings modal (#484) is `position: fixed`
and vertically centred. Its `.md-content` only received `max-height` +
`overflow-y: auto` inside a `@media (max-width: 600px)` block, so the
scroll cap was gated on viewport *width*. On a short-but-wide window
(e.g. a NAS admin browser) the modal grew taller than the viewport,
clipped at the top and bottom, and could not be scrolled — the Font,
Spread and Reflow options at the bottom were physically unreachable.

Reporter's "body has height:0" theory is a red herring: a position:fixed
modal is sized against the viewport, not the body. The real cause is the
missing base-rule scroll cap.

Fix: the `max-height: 86vh; overflow-y: auto` cap moves to the *base*
`#settings-modal .md-content` rule so it applies at every viewport size;
the media query keeps only the mobile `max-width: 92vw` override.

This test pins that the scroll cap lives in the base rule and is NOT
gated behind a `@media` block, so a future edit can't silently move it
back to mobile-only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
READ_HTML = REPO_ROOT / "cps" / "templates" / "read.html"


def _settings_style_block() -> str:
    """Return the inline <style> block that styles #settings-modal."""
    src = READ_HTML.read_text()
    for block in re.findall(r"<style>(.*?)</style>", src, re.DOTALL):
        if "#settings-modal" in block:
            return block
    raise AssertionError("no inline <style> block scoping #settings-modal found")


def _base_region(style_block: str) -> str:
    """CSS that applies at all viewport sizes (everything before the first @media)."""
    media = re.search(r"@media", style_block)
    return style_block[: media.start()] if media else style_block


def test_md_content_base_rule_caps_height_and_scrolls():
    base = _base_region(_settings_style_block())
    rule = re.search(
        r"#settings-modal\s+\.md-content\s*\{([^}]*)\}", base, re.DOTALL
    )
    assert rule, "base (non-@media) #settings-modal .md-content rule must exist"
    body = rule.group(1)
    assert re.search(r"max-height:\s*\d+\w+", body), (
        "base .md-content must set max-height so the modal can't exceed the viewport"
    )
    assert re.search(r"overflow-y:\s*auto", body), (
        "base .md-content must set overflow-y: auto so tall content scrolls internally "
        "at every viewport width, not just <=600px"
    )


def test_scroll_cap_is_not_mobile_only():
    """The scroll cap must not be reachable solely from inside a media query."""
    block = _settings_style_block()
    base = _base_region(block)
    base_rule = re.search(
        r"#settings-modal\s+\.md-content\s*\{([^}]*)\}", base, re.DOTALL
    )
    assert base_rule and "overflow-y" in base_rule.group(1), (
        "regression #503: overflow-y on .md-content must live in the base rule, "
        "not only inside @media (max-width: 600px)"
    )
