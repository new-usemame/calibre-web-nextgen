# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Pinning tests for the second-series ORM wiring (merge of cwa/second-series).

The second-series feature exposes a second Calibre "series" custom column as
`Books.series2` plus the `db.series2_cc_class` / `db.series2_link_class`
globals (used by the sidebar route, book-detail view and the Kobo subtitle).

History worth pinning. The feature originally shipped a SECOND ORM builder
(`setup_series2_classes`) that created its own `custom_column_N` +
`books_custom_column_N_link` classes and targeted the value class by the
STRING name `'custom_column_N'`. On a Kobo sync — which calls
`reconnect_db -> dispose -> setup_db` on every request — the teardown/rebuild
cycle then crashed:

  * "Multiple classes found for path custom_column_N" — the string relationship
    target resolved lazily through SQLAlchemy's registry, where the freshly
    recreated class collided with the lingering old one;
  * then InstanceState / `persist_selectable` errors and
    "backref 'books' already exists" from the registry-reuse patches that
    followed.

The fix folded series2 into the single `setup_db_cc_classes` builder and
targets the value class by a DIRECT class reference. These tests pin the
invariants so a refactor can't silently reintroduce the crash:

1. There is no separate `setup_series2_classes` builder.
2. series2 is built inside `setup_db_cc_classes` from `config_series2_column`.
3. The link class's value relationship uses a DIRECT class reference
   (`relationship(series2_cc_class, ...)`), never the string `'custom_column_N'`.
4. `dispose()` clears `Books.series2` so the rebuild re-adds it fresh.
5. When series2 is unconfigured the builder restores the `[]` placeholder so
   listing/detail templates doing `entry.series2|length` still work.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PY = REPO_ROOT / "cps" / "db.py"


def _db_source() -> str:
    return DB_PY.read_text()


def _setup_cc_source() -> str:
    """Return the body of setup_db_cc_classes."""
    src = _db_source()
    start = src.index("def setup_db_cc_classes")
    # next top-level (8-space) method def after it
    rest = src[start + 1:]
    end = rest.index("\n    @classmethod")
    return src[start: start + 1 + end]


def _series2_block() -> str:
    src = _setup_cc_source()
    return src[src.index("# Second-series feature"):]


def test_no_separate_series2_builder():
    """series2 must be built by the single ORM builder — a second builder is
    what caused the reconnect 'Multiple classes found' crash."""
    assert "def setup_series2_classes" not in _db_source(), (
        "cps/db.py must NOT define a separate setup_series2_classes builder; "
        "build series2 inside setup_db_cc_classes (see reconnect crash history)."
    )


def test_series2_built_in_single_builder_from_config():
    """The series2 classes are derived from config_series2_column inside
    setup_db_cc_classes."""
    block = _series2_block()
    assert "config_series2_column" in block
    assert "series2_cc_class = type(" in block
    assert "series2_link_class = type(" in block


def test_series2_link_uses_direct_class_reference():
    """The link class's value relationship MUST target the value class by direct
    reference, never the lazily-resolved string 'custom_column_N' (the cause of
    the reconnect registry collision)."""
    block = _series2_block()
    assert re.search(r"'asoc':\s*relationship\(series2_cc_class", block), (
        "series2 link class must use relationship(series2_cc_class, ...) — a "
        "DIRECT class reference."
    )
    # No string-based relationship target for the series2 tables in the block.
    assert not re.search(r"relationship\(\s*['\"]custom_column_", block), (
        "series2 must not target a value class by the string 'custom_column_N' "
        "— that resolves through the registry and collides on reconnect."
    )
    assert not re.search(r"relationship\(\s*s2_cc_table", block), (
        "series2 must not target the value class by its table-name string."
    )


def test_dispose_clears_series2():
    """dispose() must clear Books.series2 alongside custom_column_* so the
    rebuild re-adds it fresh against the recreated link class."""
    src = _db_source()
    assert re.search(r'attr\s*==\s*["\']series2["\']', src), (
        "dispose() teardown loop must also clear the 'series2' attribute."
    )


def test_unconfigured_restores_list_placeholder():
    """When series2 is unconfigured the builder must restore Books.series2 = []
    so templates doing entry.series2|length don't hit NoneType."""
    block = _series2_block()
    assert re.search(r"setattr\(Books,\s*['\"]series2['\"],\s*\[\]\)", block), (
        "setup_db_cc_classes must restore Books.series2 = [] when series2 is "
        "not configured (dispose() cleared it to None)."
    )
