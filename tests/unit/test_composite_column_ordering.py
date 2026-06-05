# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Pinning tests for composite-column display ordering (merge of
cwa/composite-column-ordering).

The feature lets an admin order custom columns, mark some as clickable search
links, hide some, and renders Calibre "composite" (template-formatted) columns
on the book-detail page. It spans:

  * config_sql.py — three config columns: config_cc_display_order,
    config_cc_link_columns, config_cc_hidden_columns.
  * template_formatter.py — evaluate_composite_template() computes composite
    column values from the Calibre template language.
  * web.py:show_book — builds `composite_vals` (evaluated composites) and
    `cc_link_cols` (set of columns to render as links) and passes both to
    detail.html.
  * detail.html — renders composite columns via composite_vals and wraps
    linkable text/enumeration columns in a cc_search anchor; numeric columns go
    through the format_cc_number filter.
  * admin.py — persists the per-column link/hide checkboxes.

These source-pins guard the wiring so a future merge/refactor doesn't silently
drop a leg of it (the detail.html template in particular was reconciled by hand
against the single-page + subtitle + second-series rewrites).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CPS = REPO_ROOT / "cps"


def _read(rel: str) -> str:
    return (CPS / rel).read_text()


def test_config_columns_present():
    src = _read("config_sql.py")
    for col in (
        "config_cc_display_order",
        "config_cc_link_columns",
        "config_cc_hidden_columns",
    ):
        assert col in src, f"config_sql.py must define {col}."


def test_template_formatter_evaluates_composites():
    assert (CPS / "template_formatter.py").is_file(), (
        "cps/template_formatter.py must exist (composite template evaluation)."
    )
    assert "def evaluate_composite_template" in _read("template_formatter.py"), (
        "template_formatter.py must define evaluate_composite_template()."
    )


def test_show_book_passes_composite_and_link_context():
    src = _read("web.py")
    assert "composite_vals=composite_vals" in src, (
        "web.py:show_book must pass composite_vals to detail.html."
    )
    assert "cc_link_cols=cc_link_cols" in src, (
        "web.py:show_book must pass cc_link_cols to detail.html."
    )


def test_detail_template_renders_composites_and_links():
    src = _read("templates/detail.html")
    assert "composite_vals.get(c.id)" in src, (
        "detail.html must look up evaluated composite values via "
        "composite_vals.get(c.id)."
    )
    assert "c.datatype == 'composite'" in src, (
        "detail.html must special-case composite datatype rendering."
    )
    assert "cc_link_cols" in src, (
        "detail.html must consult cc_link_cols to render linkable columns."
    )
    assert "format_cc_number" in src, (
        "detail.html must format int/float columns via the format_cc_number "
        "filter."
    )


def test_admin_persists_link_and_hide_columns():
    src = _read("admin.py")
    assert "config_cc_link_columns" in src and "config_cc_hidden_columns" in src, (
        "admin.py must persist the per-column link/hide selections into "
        "config_cc_link_columns / config_cc_hidden_columns."
    )
