# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for User.view_settings None handling.

Discovered while exercising fork #218: hitting /admin/book/<id> as a
user whose view_settings DB column is NULL returned 500 with
AttributeError in User.get_view_property (called from layout.html
since v4.0.97 cover-settings cog toggle). Legacy user rows created
before view_settings had a JSON default were stored as NULL.

Fix: vs = self.view_settings or {} guard before .get(page).
set_view_property materializes the dict on NULL rows.
"""

from __future__ import annotations

import re
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
UB_PY = REPO_ROOT / "cps" / "ub.py"


def _ub_source() -> str:
    return UB_PY.read_text()


def test_get_view_property_handles_none_view_settings():
    src = _ub_source()
    match = re.search(
        r"def get_view_property\(self, page, prop\):.*?(?=\n    def )",
        src, re.DOTALL,
    )
    assert match, "Could not locate get_view_property"
    body = match.group(0)
    assert (
        re.search(r"self\.view_settings\s*or\s*\{\s*\}", body)
        or re.search(r"if\s+self\.view_settings\s+is\s+None", body)
    ), (
        "get_view_property must tolerate self.view_settings being None. "
        "Without this layout.html 500s for any user with NULL view_settings."
    )


def test_set_view_property_materializes_none_view_settings():
    src = _ub_source()
    match = re.search(
        r"def set_view_property\(self, page, prop, value\):.*?(?=\n    def )",
        src, re.DOTALL,
    )
    assert match, "Could not locate set_view_property"
    body = match.group(0)
    assert re.search(
        r"if not self\.view_settings:\s*\n\s*self\.view_settings\s*=\s*\{\s*\}",
        body,
    ), "set_view_property must materialize self.view_settings = {} on NULL."


def test_get_view_property_anchor_comment_present():
    src = _ub_source()
    match = re.search(
        r"def get_view_property\(self, page, prop\):.*?(?=\n    def )",
        src, re.DOTALL,
    )
    body = match.group(0)
    assert any(s in body for s in ("v4.0.97", "legacy user", "NULL view_settings")), (
        "get_view_property must reference v4.0.97 / legacy user / "
        "NULL view_settings in a comment so code archaeology finds it."
    )


def test_get_view_property_returns_none_for_null_user():
    """Behavioral check via inspect+rebind — avoids the cps import."""
    src = _ub_source()
    match = re.search(
        r"def get_view_property\(self, page, prop\):.*?(?=\n    def )",
        src, re.DOTALL,
    )
    body = match.group(0)
    lines = body.split("\n")
    dedented = "\n".join(
        ln[4:] if ln.startswith("    ") else ln for ln in lines
    )
    ns: dict = {}
    exec(dedented, ns)  # noqa: S102 — exec'ing fixture source, not user input
    fn = ns["get_view_property"]
    fake = types.SimpleNamespace(view_settings=None)
    result = fn(fake, "cover", "hide_shelf_badges")
    assert result is None, (
        f"get_view_property with view_settings=None must return None, "
        f"not raise. Got {result!r}."
    )


def test_get_view_property_returns_value_for_populated_user():
    src = _ub_source()
    match = re.search(
        r"def get_view_property\(self, page, prop\):.*?(?=\n    def )",
        src, re.DOTALL,
    )
    body = match.group(0)
    lines = body.split("\n")
    dedented = "\n".join(
        ln[4:] if ln.startswith("    ") else ln for ln in lines
    )
    ns: dict = {}
    exec(dedented, ns)  # noqa: S102
    fn = ns["get_view_property"]
    fake = types.SimpleNamespace(view_settings={"cover": {"hide_shelf_badges": True}})
    assert fn(fake, "cover", "hide_shelf_badges") is True
    assert fn(fake, "cover", "nonexistent") is None
    assert fn(fake, "nonexistent", "x") is None
