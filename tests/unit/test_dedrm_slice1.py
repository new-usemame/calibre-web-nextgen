# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for the vendored DeDRM integration (Slice 1).

These cover the Calibre-free building blocks that land before any app wiring:

* ``cps.dedrm.prefs_store`` - the on-disk preferences layer shared by the Flask
  app and the ingest worker (round-trip, defaults, ``is_configured`` truth
  table, and the key/list mutation helpers).
* ``cps.dedrm.engine`` - the isolated subprocess that actually runs DeDRM. We
  feed it a synthetic, DRM-free EPUB and assert it reports a passthrough
  (``status == "none"``) without needing any real DRM-protected content.
* Import isolation - importing the public ``cps.dedrm`` facade must NOT pull the
  heavy vendored decryption modules into the parent interpreter; they belong in
  the subprocess only.
"""

from __future__ import annotations

import os
import sys
import json
import zipfile
import subprocess

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_drm_free_epub(path):
    """Write a minimal, valid, DRM-free EPUB to ``path``."""
    with zipfile.ZipFile(path, "w") as archive:
        # The mimetype entry must be first and stored uncompressed.
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:title>Test</dc:title><dc:identifier id="id">urn:uuid:1</dc:identifier>'
            '<dc:language>en</dc:language></metadata>'
            '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="c1"/></spine></package>',
        )
        archive.writestr(
            "OEBPS/c1.xhtml",
            '<?xml version="1.0"?><!DOCTYPE html>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title></head>'
            '<body><p>Hello, no DRM.</p></body></html>',
        )


# ---------------------------------------------------------------------------
# prefs_store
# ---------------------------------------------------------------------------

@pytest.fixture()
def prefs_store(tmp_path, monkeypatch):
    """Import prefs_store with its paths redirected into a temp directory."""
    from cps.dedrm import prefs_store as module

    dedrm_dir = tmp_path / "dedrm"
    monkeypatch.setattr(module, "DEDRM_DIR", str(dedrm_dir))
    monkeypatch.setattr(module, "PREFS_PATH", str(dedrm_dir / "plugins" / "dedrm.json"))
    monkeypatch.setattr(module, "KEYFILES_DIR", str(dedrm_dir / "keyfiles"))
    return module


def test_get_prefs_defaults_when_missing(prefs_store):
    prefs = prefs_store.get_prefs()
    # Every default key is present and matches the documented schema.
    assert prefs["configured"] is False
    assert prefs["deobfuscate_fonts"] is True
    assert prefs["adeptkeys"] == {}
    assert prefs["serials"] == []
    # The returned dict is independent of the module defaults.
    prefs["serials"].append("X")
    assert prefs_store.DEFAULTS["serials"] == []


def test_save_and_reload_round_trip(prefs_store):
    prefs = prefs_store.get_prefs()
    prefs["serials"].append("B0123456789")
    prefs["adeptkeys"]["main"] = "deadbeef"
    prefs_store.save_prefs(prefs)

    reloaded = prefs_store.get_prefs()
    assert reloaded["serials"] == ["B0123456789"]
    assert reloaded["adeptkeys"] == {"main": "deadbeef"}
    # The file is created with the nested plugins/dedrm.json layout.
    assert os.path.exists(prefs_store.PREFS_PATH)


def test_is_configured_truth_table(prefs_store):
    # Empty -> not configured.
    assert prefs_store.is_configured(dict(prefs_store.DEFAULTS)) is False
    # Explicit flag -> configured.
    flagged = dict(prefs_store.DEFAULTS)
    flagged["configured"] = True
    assert prefs_store.is_configured(flagged) is True
    # A single key present -> configured even without the flag.
    keyed = {**prefs_store.DEFAULTS, "adeptkeys": {"main": "abc"}}
    assert prefs_store.is_configured(keyed) is True
    # A single list value present -> configured.
    listed = {**prefs_store.DEFAULTS, "serials": ["123"]}
    assert prefs_store.is_configured(listed) is True


def test_add_named_key_dedup_and_unique_names(prefs_store):
    prefs = dict(prefs_store.DEFAULTS)
    prefs["adeptkeys"] = {}
    prefs, name = prefs_store.add_named_key(prefs, "adeptkeys", "k", "AAAA")
    assert name == "k"
    # Same value is ignored.
    prefs, name = prefs_store.add_named_key(prefs, "adeptkeys", "k", "AAAA")
    assert name is None
    # Same name, different value -> suffixed.
    prefs, name = prefs_store.add_named_key(prefs, "adeptkeys", "k", "BBBB")
    assert name == "k_2"
    assert prefs["adeptkeys"] == {"k": "AAAA", "k_2": "BBBB"}


def test_list_value_helpers(prefs_store):
    prefs = dict(prefs_store.DEFAULTS)
    prefs["serials"] = []
    prefs_store.add_list_value(prefs, "serials", "S1")
    prefs_store.add_list_value(prefs, "serials", "S1")  # dedup
    prefs_store.add_list_value(prefs, "serials", "S2")
    assert prefs["serials"] == ["S1", "S2"]
    prefs_store.delete_list_value(prefs, "serials", "S1")
    assert prefs["serials"] == ["S2"]


def test_cwa_labels_round_trip(prefs_store):
    # Optional friendly labels (e.g. naming each Kindle behind a serial) persist
    # in the app-private cwa_labels map, separate from DeDRM's own data.
    prefs = prefs_store.get_prefs()
    assert prefs["cwa_labels"] == {}
    prefs_store.add_list_value(prefs, "serials", "B0ABC")
    prefs_store.set_label(prefs, "serials", "B0ABC", "Living-room Kindle")
    prefs_store.save_prefs(prefs)

    reloaded = prefs_store.get_prefs()
    assert reloaded["serials"] == ["B0ABC"]
    assert prefs_store.get_labels(reloaded, "serials") == {"B0ABC": "Living-room Kindle"}


def test_delete_serial_cascades_label(prefs_store):
    prefs = prefs_store.get_prefs()
    prefs_store.add_list_value(prefs, "serials", "B0ABC")
    prefs_store.set_label(prefs, "serials", "B0ABC", "Kitchen")
    prefs_store.delete_list_value(prefs, "serials", "B0ABC")
    assert prefs["serials"] == []
    assert prefs_store.get_labels(prefs, "serials") == {}


def test_labels_do_not_count_as_configured(prefs_store):
    # A dangling label with no actual serial must not flip is_configured to True.
    prefs = dict(prefs_store.DEFAULTS)
    prefs["cwa_labels"] = {"serials": {"X": "name"}}
    assert prefs_store.is_configured(prefs) is False


def test_merge_imported_prefs(prefs_store):
    # Importing a whole desktop dedrm.json merges additively with dedup.
    prefs = prefs_store.get_prefs()
    prefs["serials"] = ["EXISTING"]
    prefs["adeptkeys"] = {"old": "aaaa"}
    imported = {
        "configured": True,
        "deobfuscate_fonts": False,
        "serials": ["EXISTING", "NEWSER"],
        "adeptkeys": {"k1": "bbbb", "k2": "aaaa"},  # k2 duplicates value -> skipped
        "pids": ["P1"],
        "cwa_labels": {"serials": {"NEWSER": "Office"}},
        "unknownkey": 123,  # ignored
    }
    prefs, added = prefs_store.merge_imported_prefs(prefs, imported)
    assert prefs["serials"] == ["EXISTING", "NEWSER"]
    assert prefs["adeptkeys"]["old"] == "aaaa" and prefs["adeptkeys"]["k1"] == "bbbb"
    assert "k2" not in prefs["adeptkeys"]  # duplicate value not re-added
    assert prefs["pids"] == ["P1"]
    assert prefs["deobfuscate_fonts"] is False and prefs["configured"] is True
    assert prefs_store.get_labels(prefs, "serials") == {"NEWSER": "Office"}
    assert added == 4


# ---------------------------------------------------------------------------
# engine (subprocess passthrough)
# ---------------------------------------------------------------------------

def test_engine_passthrough_on_drm_free_epub(tmp_path):
    """A DRM-free EPUB must round-trip as ``status == "none"``."""
    # The Adobe decryptors import these; skip cleanly if unavailable.
    pytest.importorskip("Crypto", reason="pycryptodome required by DeDRM engine")
    pytest.importorskip("lxml", reason="lxml required by DeDRM engine")

    engine_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cps", "dedrm", "engine.py",
    )

    epub = tmp_path / "book.epub"
    _make_drm_free_epub(str(epub))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    config_dir = tmp_path / "cfg"
    result_file = tmp_path / "result.json"

    completed = subprocess.run(
        [
            sys.executable, engine_path,
            "--input", str(epub),
            "--output-dir", str(out_dir),
            "--config-dir", str(config_dir),
            "--result-file", str(result_file),
        ],
        capture_output=True, text=True, timeout=300,
    )

    assert completed.returncode == 0, completed.stderr
    with open(result_file, "r", encoding="utf-8") as handle:
        result = json.load(handle)
    assert result["status"] == "none"


# ---------------------------------------------------------------------------
# import isolation
# ---------------------------------------------------------------------------

def test_public_facade_does_not_import_vendor():
    """Importing the public facade must keep the heavy vendor out of memory."""
    import cps.dedrm  # noqa: F401 - import for its side effects only

    # None of the vendored decryption modules (which mutate global state) should
    # be loaded into the parent interpreter just by importing the facade.
    for vendored in ("ineptepub", "ineptpdf", "k4mobidedrm", "mobidedrm", "kfxdedrm"):
        assert vendored not in sys.modules
    # The fake calibre tree only exists inside the engine subprocess.
    assert "calibre_plugins" not in sys.modules
