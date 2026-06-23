# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression: the persistent ``.alert-cwa`` flash toasts must STACK.

caliBlur turns every ``.alert`` into a ``position: fixed`` toast, so when more
than one persistent notice fires at once (e.g. the duplicate-scan-setup notice
+ the "update available" banner on the same page) they all anchor to the same
spot and render on top of each other — the garbled overlap a user reported.

The fix wraps the persistent toasts in a single ``.cwa-toast-stack`` flex
container so they lay out in a column. These are structural pins; the
behavioural "two toasts don't overlap" proof is the Playwright pass.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
LAYOUT = REPO / "cps" / "templates" / "layout.html"
CSS_OVERRIDE = REPO / "cps" / "static" / "css" / "caliBlur_override.css"

PERSISTENT = [
    "cwa_update", "duplicate_scan_setup", "cwa_arch_warning",
    "translation_missing", "theme_migration", "cwa_refresh",
]


def test_persistent_toasts_live_in_a_stack_container():
    src = LAYOUT.read_text()
    assert "cwa-toast-stack" in src, (
        "persistent toasts need a .cwa-toast-stack container so they stack "
        "instead of overlapping"
    )
    stack_at = src.index("cwa-toast-stack")
    for cat in PERSISTENT:
        marker = 'message[0] == "%s"' % cat
        assert marker in src, "toast category missing: " + cat
        assert src.index(marker) > stack_at, (
            cat + " toast must render inside the .cwa-toast-stack container"
        )


def test_inline_flashes_stay_outside_the_floating_stack():
    """error/success flashes belong inline at the top, not in the floating
    toast stack — only the persistent .alert-cwa popups stack."""
    src = LAYOUT.read_text()
    stack_at = src.index("cwa-toast-stack")
    for cat in ("error", "success"):
        marker = 'message[0] == "%s"' % cat
        assert marker in src
        assert src.index(marker) < stack_at, (
            "inline '" + cat + "' flash must render before/outside the toast stack"
        )


def test_stack_css_is_a_vertical_flex_column():
    css = CSS_OVERRIDE.read_text()
    m = re.search(r"\.cwa-toast-stack\b[^{]*\{([^}]*)\}", css, re.S)
    assert m, ".cwa-toast-stack rule must exist in caliBlur_override.css"
    body = m.group(1)
    assert "fixed" in body, "the stack must be position:fixed (the toast anchor point)"
    assert "column" in body, "the stack must lay toasts out in a column so they stack"
