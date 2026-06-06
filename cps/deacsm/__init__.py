# -*- coding: utf-8 -*-

"""Public, import-light DeACSM (ACSM Input) facade for Calibre-Web-NextGen.

Vendors the ACSM Input plugin under ``_vendor/`` (plus the OpenSSL-3 compatible
``oscrypto`` fork + ``asn1crypto``) and exposes a small Calibre-free API to
activate an Adobe account and fulfill ``.acsm`` files. As with the DeDRM facade,
importing this module stays cheap: the heavy vendored crypto code runs only in
the isolated :mod:`cps.deacsm.engine` subprocess.

Account activation provides the Adobe encryption key that DeDRM needs to decrypt
Adobe-DRM EPUB/PDF, so :func:`activate_*` / :func:`deactivate` keep DeDRM's
``adeptkeys`` in sync (the "auto-bridge").
"""

import os
import sys
import json
import tempfile
import subprocess

from cps import logger
from .prefs_store import (
    DEACSM_DIR,
    ACCOUNT_DIR,
    PREFS_PATH,
    get_prefs,
    save_prefs,
    is_activated,
    ensure_dirs,
)

log = logger.create()

_ENGINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.py")

# Activation/fulfillment hit Adobe servers; allow a generous timeout.
_ENGINE_TIMEOUT = 300


def _run_engine(command, extra_args=None, timeout=_ENGINE_TIMEOUT):
    """Run an engine subcommand and return its parsed JSON result (or None).

    Never raises for an ordinary failure; logs and returns ``None`` so callers
    (ingest, admin routes) can degrade gracefully.
    """
    ensure_dirs()
    result_fd, result_file = tempfile.mkstemp(prefix="deacsm-result-", suffix=".json")
    os.close(result_fd)
    cmd = [
        sys.executable, _ENGINE_PATH, command,
        "--config-dir", DEACSM_DIR,
        "--account-dir", ACCOUNT_DIR,
        "--result-file", result_file,
    ]
    if extra_args:
        cmd.extend(extra_args)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if completed.stdout:
            log.debug("DeACSM engine [%s] stdout:\n%s", command, completed.stdout.strip())
        if completed.returncode != 0 and completed.stderr:
            log.warning("DeACSM engine [%s] stderr:\n%s", command, completed.stderr.strip())
        try:
            with open(result_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return None
    except subprocess.TimeoutExpired:
        log.error("DeACSM engine [%s] timed out after %ss", command, timeout)
        return None
    except Exception as exc:  # noqa: BLE001
        log.error("DeACSM engine [%s] failed to launch: %s", command, exc)
        return None
    finally:
        try:
            os.unlink(result_file)
        except OSError:
            pass


def get_deacsm_dir():
    return DEACSM_DIR


# Name under which the Adobe account encryption key is mirrored into DeDRM's
# adept key store (the "auto-bridge"), so activating the account once enables
# both .acsm fulfillment AND Adobe-DRM decryption.
_BRIDGE_KEY_NAME = "Adobe account (DeACSM)"


def account_status():
    """Return ``{activated, uuid, account_type}`` for the local Adobe account.

    Cheap and subprocess-free: derived from the on-disk device files plus the
    uuid/type cached in prefs at activation time. Use this for rendering.
    """
    if not is_activated():
        return {"activated": False, "uuid": None, "account_type": None, "email": None}
    prefs = get_prefs()
    return {
        "activated": True,
        "uuid": prefs.get("account_uuid"),
        "account_type": prefs.get("account_type"),
        "email": prefs.get("account_email"),
    }


def account_status_live():
    """Like :func:`account_status` but verified by the engine (spawns a
    subprocess). Reserved for explicit checks, not page rendering."""
    result = _run_engine("status", timeout=60)
    if result and result.get("status") == "ok":
        return result.get("account", {"activated": False})
    return account_status()


def _bridge_key_to_dedrm(key_hex):
    """Mirror the Adobe account key into DeDRM's adeptkeys (idempotent)."""
    try:
        from cps.dedrm import prefs_store as dedrm_prefs
        prefs = dedrm_prefs.get_prefs()
        prefs.setdefault("adeptkeys", {}).pop(_BRIDGE_KEY_NAME, None)
        if key_hex:
            prefs["adeptkeys"][_BRIDGE_KEY_NAME] = key_hex
        dedrm_prefs.save_prefs(prefs)
    except Exception as exc:  # noqa: BLE001 - bridging must not break activation
        log.warning("Could not bridge Adobe key into DeDRM: %s", exc)


def _unbridge_from_dedrm():
    """Remove the bridged Adobe account key from DeDRM, if present."""
    try:
        from cps.dedrm import prefs_store as dedrm_prefs
        prefs = dedrm_prefs.get_prefs()
        if prefs.get("adeptkeys", {}).pop(_BRIDGE_KEY_NAME, None) is not None:
            dedrm_prefs.save_prefs(prefs)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not unbridge Adobe key from DeDRM: %s", exc)


def _finish_activation(result):
    """On a successful activation result, bridge the key and persist state."""
    if not (result and result.get("status") == "ok"):
        message = (result or {}).get("message", "Activation failed.")
        return {"ok": False, "message": message}
    _bridge_key_to_dedrm(result.get("key_hex"))
    # Cache account state in DeACSM prefs so the admin page renders without
    # spawning the engine on every load.
    account = result.get("account", {"activated": True})
    try:
        prefs = get_prefs()
        prefs["configured"] = True
        prefs["account_uuid"] = account.get("uuid")
        prefs["account_type"] = account.get("account_type")
        prefs["account_email"] = account.get("email")
        save_prefs(prefs)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "account": account}


def activate_anonymous():
    """Create + activate an anonymous Adobe account (no credentials)."""
    return _finish_activation(_run_engine("activate-anon"))


def activate_adobeid(user, password):
    """Activate with an Adobe ID. The password is passed once and not stored."""
    pass_fd, pass_file = tempfile.mkstemp(prefix="deacsm-pass-", suffix=".txt")
    try:
        with os.fdopen(pass_fd, "w", encoding="utf-8") as handle:
            handle.write(password or "")
        os.chmod(pass_file, 0o600)
        result = _run_engine("activate-adobeid", ["--user", user, "--pass-file", pass_file])
    finally:
        # Best-effort secure-ish removal of the single-use password file.
        try:
            os.unlink(pass_file)
        except OSError:
            pass
    return _finish_activation(result)


def import_activation_zip(zip_path):
    """Import an existing Adobe activation from a backup ZIP.

    The ZIP is the ``adobe_account_backup_*.zip`` that DeACSM (desktop Calibre or
    another Calibre-Web) produces. Importing clones the SAME device, so books
    already fulfilled with that account stay decryptable and no new Adobe
    activation is spent. On success the key is bridged into DeDRM, exactly like a
    fresh activation.
    """
    result = _run_engine("import-activation", ["--input", zip_path], timeout=120)
    return _finish_activation(result)


def export_activation_zip():
    """Export the current Adobe activation as a ZIP; returns a temp path or None.

    Caller is responsible for sending and then deleting the returned file.
    """
    if not is_activated():
        return None
    fd, out_path = tempfile.mkstemp(prefix="adobe_account_backup_", suffix=".zip")
    os.close(fd)
    result = _run_engine("export-activation", ["--out", out_path], timeout=60)
    if result and result.get("status") == "ok" and os.path.exists(out_path):
        return out_path
    try:
        os.unlink(out_path)
    except OSError:
        pass
    return None


def export_key_der_bytes():
    """Return the Adobe account encryption key as DER bytes, or None.

    This is the same key DeDRM uses for Adobe DRM; downloadable for use with
    other tools / Adobe Digital Editions.
    """
    result = _run_engine("export-key", timeout=60)
    if result and result.get("status") == "ok":
        key_hex = result.get("key_hex")
        if key_hex:
            try:
                return bytes.fromhex(key_hex)
            except ValueError:
                return None
    return None


def fulfill(acsm_path, output_dir):
    """Fulfill an .acsm file and return the downloaded book path, or None.

    The returned book still carries Adobe DRM; the ingest pipeline runs DeDRM
    on it afterwards. Returns None when no Adobe account is activated or
    fulfillment failed (callers keep going without aborting ingest).
    """
    if not is_activated():
        return None
    os.makedirs(output_dir, exist_ok=True)
    result = _run_engine("fulfill", ["--input", acsm_path, "--output-dir", output_dir])
    if result and result.get("status") == "ok":
        out = result.get("output")
        if out and os.path.exists(out):
            log.info("DeACSM fulfilled %s", os.path.basename(acsm_path))
            return out
        return None
    if result:
        log.warning("DeACSM could not fulfill %s: %s",
                    os.path.basename(acsm_path), result.get("message", "unknown error"))
    return None


def deactivate():
    """Remove the local Adobe account and unlink DeDRM's bridged key."""
    result = _run_engine("deactivate", timeout=60)
    _unbridge_from_dedrm()
    try:
        prefs = get_prefs()
        prefs["configured"] = False
        prefs["account_uuid"] = None
        prefs["account_type"] = None
        prefs["account_email"] = None
        save_prefs(prefs)
    except Exception:  # noqa: BLE001
        pass
    return bool(result and result.get("status") == "ok")


__all__ = [
    "DEACSM_DIR",
    "ACCOUNT_DIR",
    "PREFS_PATH",
    "get_deacsm_dir",
    "get_prefs",
    "save_prefs",
    "is_activated",
    "account_status",
    "account_status_live",
    "activate_anonymous",
    "activate_adobeid",
    "deactivate",
    "fulfill",
    "import_activation_zip",
    "export_activation_zip",
    "export_key_der_bytes",
]
