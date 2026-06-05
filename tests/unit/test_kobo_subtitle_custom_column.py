# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Kobo sync Subtitle field — configurable column with zero-config autodetect.

Origin. The fork first surfaced a Kobo "Subtitle" by auto-detecting a Calibre
custom column *labeled* "subtitle" at sync time (backport of janeczku #3358,
@dotknott). The CWA `subtitle-config` feature later made the Kobo subtitle
source *admin-configurable* (`config_kobo_subtitle_cc`) and added optional
prefix/suffix. Merging the two would have silently dropped the zero-config
behavior every existing fork user relied on.

Reconciled design (pinned here):

1. `cps.kobo.get_subtitle(book)` reads the configured column
   `config.config_kobo_subtitle_cc`, applies the prefix/suffix, and returns ""
   defensively at every fork (unconfigured, missing attribute, empty list,
   NULL cell) so a sync is never broken by a missing subtitle.
2. `get_metadata` always emits a `"Subtitle"` key (Kobo device contract — some
   firmware rejects entries that omit it).
3. Zero-config is preserved by AUTO-DETECTION AT CREATION rather than at sync
   time: `cps.__init__._autodetect_subtitle_column()` runs when the subtitle
   config columns are first migrated in, finds the single custom column labeled
   "subtitle", and sets `config_kobo_subtitle_cc` (and the book-detail
   `config_subtitle_column`) to it — only when still unset, so an admin's
   explicit choice is never overwritten. `config_sql.load_configuration`
   returns truthy to trigger it when either column is newly added.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
KOBO_PY = REPO_ROOT / "cps" / "kobo.py"
INIT_PY = REPO_ROOT / "cps" / "__init__.py"
CONFIG_SQL_PY = REPO_ROOT / "cps" / "config_sql.py"


def _kobo_source() -> str:
    return KOBO_PY.read_text()


# --------------------------------------------------------------------------
# Source pins
# --------------------------------------------------------------------------

def test_get_subtitle_function_defined():
    """`get_subtitle` must exist alongside the other `get_*` helpers so the
    metadata builder can call it."""
    assert re.search(r"^def get_subtitle\(book\):", _kobo_source(), re.MULTILINE), (
        "cps/kobo.py must define `def get_subtitle(book):` so the metadata "
        "block can populate the Kobo Subtitle field."
    )


def test_get_metadata_emits_subtitle_key():
    """The metadata dict in `get_metadata` must carry a `Subtitle` key, always
    present even when empty (some Kobo firmware rejects entries that omit it)."""
    assert re.search(r"[\"']Subtitle[\"']\s*:\s*subtitle\b", _kobo_source()), (
        "cps/kobo.py:get_metadata must include a `\"Subtitle\": subtitle` entry "
        "(subtitle derived from get_subtitle) so the device receives the key "
        "every sync."
    )


def test_get_subtitle_reads_configured_column():
    """get_subtitle must source the column from config_kobo_subtitle_cc, not a
    hard-coded label lookup — the admin-configurable design."""
    src = inspect.getsource(
        __import__("cps.kobo", fromlist=["get_subtitle"]).get_subtitle
    )
    assert "config.config_kobo_subtitle_cc" in src, (
        "get_subtitle must read config.config_kobo_subtitle_cc. Source: " + repr(src)
    )


def test_autodetect_sets_kobo_subtitle_column():
    """Zero-config preservation: the creation-time autodetect must wire the
    'subtitle'-labeled column into config_kobo_subtitle_cc (case-sensitive,
    matching Calibre's convention)."""
    src = INIT_PY.read_text()
    func = src[src.index("def _autodetect_subtitle_column"):]
    func = func[: func.index("\ndef ")]
    assert re.search(r"CustomColumns\.label\s*==\s*[\"']subtitle[\"']", func), (
        "_autodetect_subtitle_column must filter CustomColumns.label == 'subtitle'."
    )
    assert "config.config_kobo_subtitle_cc" in func, (
        "_autodetect_subtitle_column must set config.config_kobo_subtitle_cc so "
        "the Kobo subtitle works zero-config when a 'subtitle' column exists."
    )


def test_load_configuration_triggers_autodetect_for_kobo_column():
    """load_configuration must return truthy (triggering autodetect) when the
    Kobo subtitle column is newly migrated in, not only the detail column."""
    src = CONFIG_SQL_PY.read_text()
    assert "config_kobo_subtitle_cc' in new_columns" in src, (
        "load_configuration must trigger subtitle autodetect when "
        "config_kobo_subtitle_cc is a newly added column."
    )


# --------------------------------------------------------------------------
# Behavioral tests against get_subtitle (config-driven)
# --------------------------------------------------------------------------

def _patch_config(mp, cc_id, prefix="", suffix=""):
    from cps import kobo
    mp.setattr(kobo.config, "config_kobo_subtitle_cc", cc_id, raising=False)
    mp.setattr(kobo.config, "config_kobo_subtitle_prefix", prefix, raising=False)
    mp.setattr(kobo.config, "config_kobo_subtitle_suffix", suffix, raising=False)


def test_get_subtitle_returns_empty_when_unconfigured():
    """config_kobo_subtitle_cc == 0 (None/unset) → "" by design."""
    from cps import kobo
    with pytest.MonkeyPatch.context() as mp:
        _patch_config(mp, 0)
        assert kobo.get_subtitle(MagicMock()) == ""


def test_get_subtitle_returns_empty_when_book_has_no_value():
    """Column configured but the book has no value (empty list) → ""."""
    from cps import kobo
    book = SimpleNamespace(custom_column_7=[])
    with pytest.MonkeyPatch.context() as mp:
        _patch_config(mp, 7)
        assert kobo.get_subtitle(book) == ""


def test_get_subtitle_returns_value_when_book_has_subtitle():
    """Happy path: configured column + value → value string."""
    from cps import kobo
    book = SimpleNamespace(custom_column_7=[SimpleNamespace(value="A Study in Sherlock")])
    with pytest.MonkeyPatch.context() as mp:
        _patch_config(mp, 7)
        assert kobo.get_subtitle(book) == "A Study in Sherlock"


def test_get_subtitle_applies_prefix_and_suffix():
    """Prefix/suffix are applied and the result is stripped."""
    from cps import kobo
    book = SimpleNamespace(custom_column_7=[SimpleNamespace(value="Vol 1")])
    with pytest.MonkeyPatch.context() as mp:
        _patch_config(mp, 7, prefix="[", suffix="]")
        assert kobo.get_subtitle(book) == "[ Vol 1 ]"


def test_get_subtitle_returns_empty_when_attribute_missing():
    """Defense in depth: book row lacks the custom_column_N attribute entirely
    (schema drift / lazy-load) → "" not AttributeError."""
    from cps import kobo
    book = object()  # has no custom_column_999
    with pytest.MonkeyPatch.context() as mp:
        _patch_config(mp, 999)
        assert kobo.get_subtitle(book) == ""


def test_get_subtitle_returns_empty_when_value_is_none():
    """Cell exists but value is None (Calibre allows NULL) → ""."""
    from cps import kobo
    book = SimpleNamespace(custom_column_7=[SimpleNamespace(value=None)])
    with pytest.MonkeyPatch.context() as mp:
        _patch_config(mp, 7)
        assert kobo.get_subtitle(book) == ""
