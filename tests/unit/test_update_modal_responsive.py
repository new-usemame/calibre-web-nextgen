# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression test: the Update-now modal's setup-type selector must wrap on
narrow screens.

It was originally a Bootstrap ``btn-group`` — a single, non-wrapping row — so on
a phone-width modal the right-hand tabs ("Unraid", "Portainer / Synology") were
clipped off the right edge. This pins the responsive fix (a flex container that
wraps, and stacks the tabs full-width on phones)."""

import os


def _modal_src():
    path = os.path.join(
        os.path.dirname(__file__), "..", "..",
        "cps", "templates", "update_now_modal.html",
    )
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_setup_selector_is_a_wrapping_container_not_btn_group():
    src = _modal_src()
    selector_line = next(
        (l for l in src.splitlines() if 'id="update-setup-selector"' in l),
        "",
    )
    assert selector_line, "setup selector element missing"
    # A non-wrapping btn-group clips the later tabs on mobile — the selector
    # must not be one.
    assert "btn-group" not in selector_line, \
        "selector must not be a non-wrapping btn-group"
    assert "update-setup-tabs" in selector_line


def test_setup_selector_has_responsive_wrap_css():
    src = _modal_src()
    assert "flex-wrap: wrap" in src, "selector must wrap on narrow screens"
    # phones (<=480px) stack the tabs full-width so none are clipped
    assert "@media (max-width: 480px)" in src
