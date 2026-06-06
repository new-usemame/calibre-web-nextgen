# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Unit tests for the vendored DeACSM (ACSM Input) integration.

Covers the Calibre-free building blocks that do not hit Adobe's servers:

* ``cps.deacsm.prefs_store`` - prefs round-trip + ``is_activated`` file check.
* ``cps.deacsm.engine`` - the headless subprocess for the non-network commands
  (``status`` / ``export-key`` error / ``deactivate``). This also exercises the
  full vendored stack (calibre shim + libadobe + the OpenSSL-3 oscrypto fork).
* the DeACSM -> DeDRM key auto-bridge.

Live activation / fulfillment are intentionally NOT tested here (they register a
real Adobe device and download from Adobe).
"""

from __future__ import annotations

import os
import sys
import json
import subprocess

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture()
def deacsm_prefs(tmp_path, monkeypatch):
    """Import deacsm.prefs_store with its paths redirected into a temp dir."""
    from cps.deacsm import prefs_store as module

    root = tmp_path / "deacsm"
    plugin_dir = root / "plugins" / "ACSMInput"
    account = plugin_dir / "account"
    monkeypatch.setattr(module, "DEACSM_DIR", str(root))
    monkeypatch.setattr(module, "PLUGIN_DIR", str(plugin_dir))
    monkeypatch.setattr(module, "PREFS_PATH", str(plugin_dir / "ACSMInput.json"))
    monkeypatch.setattr(module, "ACCOUNT_DIR", str(account))
    monkeypatch.setattr(module, "DEVICE_XML", str(account / "device.xml"))
    monkeypatch.setattr(module, "ACTIVATION_XML", str(account / "activation.xml"))
    monkeypatch.setattr(module, "DEVICE_KEY", str(account / "devicesalt"))
    return module


def test_prefs_defaults_and_round_trip(deacsm_prefs):
    prefs = deacsm_prefs.get_prefs()
    assert prefs["configured"] is False
    assert prefs["notify_fulfillment"] is True
    assert prefs["list_of_rented_books"] == []

    prefs["configured"] = True
    prefs["delete_acsm_after_fulfill"] = True
    deacsm_prefs.save_prefs(prefs)

    reloaded = deacsm_prefs.get_prefs()
    assert reloaded["configured"] is True
    assert reloaded["delete_acsm_after_fulfill"] is True
    assert os.path.exists(deacsm_prefs.PREFS_PATH)


def test_is_activated_checks_device_files(deacsm_prefs):
    assert deacsm_prefs.is_activated() is False
    deacsm_prefs.ensure_dirs()
    # Only one file present -> still not activated.
    open(deacsm_prefs.DEVICE_XML, "w").close()
    assert deacsm_prefs.is_activated() is False
    # Both device files present -> activated.
    open(deacsm_prefs.ACTIVATION_XML, "w").close()
    assert deacsm_prefs.is_activated() is True


def test_engine_non_network_commands(tmp_path):
    """status / export-key(error) / deactivate run headless without Adobe."""
    pytest.importorskip("Crypto", reason="pycryptodome required by DeACSM engine")
    pytest.importorskip("lxml", reason="lxml required by DeACSM engine")

    engine = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cps", "deacsm", "engine.py",
    )
    cfg = tmp_path / "deacsm"
    account = cfg / "plugins" / "ACSMInput" / "account"

    def run(command, *extra):
        result_file = tmp_path / (command + ".json")
        proc = subprocess.run(
            [sys.executable, engine, command, "--config-dir", str(cfg),
             "--account-dir", str(account), "--result-file", str(result_file), *extra],
            capture_output=True, text=True, timeout=180,
        )
        assert proc.returncode == 0 or command == "export-key", proc.stderr
        with open(result_file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    status = run("status")
    assert status["account"]["activated"] is False

    export = run("export-key")
    assert export["status"] == "error"  # no account yet

    deactivate = run("deactivate")
    assert deactivate["status"] == "ok"


def test_export_import_activation_roundtrip(tmp_path):
    """Export the activation to a ZIP, wipe it, import it back (no network)."""
    pytest.importorskip("Crypto", reason="pycryptodome required by DeACSM engine")
    pytest.importorskip("lxml", reason="lxml required by DeACSM engine")

    engine = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "cps", "deacsm", "engine.py",
    )
    cfg = tmp_path / "deacsm"
    account = cfg / "plugins" / "ACSMInput" / "account"
    account.mkdir(parents=True)
    (account / "device.xml").write_text("<device/>")
    (account / "devicesalt").write_bytes(b"\x01" * 16)
    (account / "activation.xml").write_text(
        '<activationInfo xmlns="http://ns.adobe.com/adept"><credentials>'
        '<user>urn:uuid:12345678-1234-1234-1234-123456789abc</user>'
        "</credentials></activationInfo>"
    )

    def run(command, *extra):
        result_file = tmp_path / (command + ".json")
        subprocess.run(
            [sys.executable, engine, command, "--config-dir", str(cfg),
             "--account-dir", str(account), "--result-file", str(result_file), *extra],
            capture_output=True, text=True, timeout=180,
        )
        with open(result_file, "r", encoding="utf-8") as handle:
            return json.load(handle)

    backup = tmp_path / "backup.zip"
    export = run("export-activation", "--out", str(backup))
    assert export["status"] == "ok" and backup.exists()

    for name in ("device.xml", "activation.xml", "devicesalt"):
        (account / name).unlink()

    imported = run("import-activation", "--input", str(backup))
    assert imported["status"] == "ok"
    assert imported["account"]["uuid"] == "12345678-1234-1234-1234-123456789abc"
    assert imported["account"]["account_type"] == "anonymous"

    bad = tmp_path / "bad.zip"
    bad.write_text("not a zip")
    assert run("import-activation", "--input", str(bad))["status"] == "error"


def test_bridge_to_dedrm(tmp_path, monkeypatch):
    """Activating bridges the Adobe key into DeDRM; deactivating removes it."""
    import cps.deacsm as deacsm
    from cps.dedrm import prefs_store as dedrm_prefs

    # Redirect DeDRM prefs into a temp file.
    dedrm_dir = tmp_path / "dedrm"
    monkeypatch.setattr(dedrm_prefs, "DEDRM_DIR", str(dedrm_dir))
    monkeypatch.setattr(dedrm_prefs, "PREFS_PATH", str(dedrm_dir / "plugins" / "dedrm.json"))

    deacsm._bridge_key_to_dedrm("deadbeefcafe")
    prefs = dedrm_prefs.get_prefs()
    assert prefs["adeptkeys"].get(deacsm._BRIDGE_KEY_NAME) == "deadbeefcafe"

    # Bridging again replaces (idempotent), does not duplicate.
    deacsm._bridge_key_to_dedrm("0011223344")
    prefs = dedrm_prefs.get_prefs()
    assert prefs["adeptkeys"][deacsm._BRIDGE_KEY_NAME] == "0011223344"
    assert sum(1 for k in prefs["adeptkeys"] if k == deacsm._BRIDGE_KEY_NAME) == 1

    deacsm._unbridge_from_dedrm()
    prefs = dedrm_prefs.get_prefs()
    assert deacsm._BRIDGE_KEY_NAME not in prefs["adeptkeys"]
