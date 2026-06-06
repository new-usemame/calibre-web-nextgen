#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Isolated subprocess that drives the vendored DeACSM (ACSM Input) engine.

Launched by the :mod:`cps.deacsm` facade as a separate process, never imported
into the Flask worker. Running headless we bypass the plugin's Calibre-coupled
``ACSMInput.initialize()`` (which would try to unpack zips and rename plugin
files) and call the ``libadobe*`` modules directly, after pointing Calibre's
``config_dir`` and the Adobe account folder at our own paths.

Subcommands (each writes a JSON result to ``--result-file``):

* ``status``           - report whether an Adobe account is activated.
* ``activate-anon``    - create + activate an anonymous Adobe account.
* ``activate-adobeid`` - sign in with an Adobe ID (``--user`` + ``--pass-file``)
                         and activate. The password file is single-use.
* ``export-key``       - write the account encryption key as hex to ``--out``.
* ``deactivate``       - wipe the local Adobe account files.
* ``fulfill``          - fulfill an ``.acsm`` (``--input``) to ``--output-dir``.

The biggest dependency risk (oscrypto vs OpenSSL 3) is handled by the bundled
oscrypto fork under ``_vendor/oscrypto``; the optional ``ACSM_LIBCRYPTO`` /
``ACSM_LIBSSL`` env vars can override library autodetection.
"""

import os
import sys
import json
import shutil
import argparse
import traceback


def _write_result(result_file, payload):
    try:
        with open(result_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError:
        traceback.print_exc()


def _bootstrap(config_dir, account_dir, work_dir):
    """Install the calibre shim, make the vendor importable, point Adobe paths.

    Returns the imported ``libadobe`` module. Importing it pulls in the bundled
    ``oscrypto`` / ``asn1crypto`` (the crypto stack), so this is also where the
    OpenSSL-3 compatibility is exercised.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    vendor_dir = os.path.join(here, "_vendor")

    os.makedirs(account_dir, exist_ok=True)

    # vendor_dir must come first so bare imports (``import libadobe``) and the
    # bundled ``oscrypto`` / ``asn1crypto`` resolve from the vendored copies.
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)
    if here not in sys.path:
        sys.path.insert(0, here)

    import _calibre_shim
    _calibre_shim.install(config_dir, vendor_dir, work_dir)

    # Optional OpenSSL path override (NixOS-style systems / unusual images).
    libcrypto = os.getenv("ACSM_LIBCRYPTO")
    libssl = os.getenv("ACSM_LIBSSL")
    if libcrypto and libssl and os.path.exists(libcrypto) and os.path.exists(libssl):
        import oscrypto
        oscrypto.use_openssl(libcrypto_path=libcrypto, libssl_path=libssl)

    import libadobe
    libadobe.update_account_path(account_dir)
    return libadobe


def _account_status(account_dir):
    """Return a status dict describing the local Adobe activation.

    ``account_type`` is detected from activation.xml: an Adobe-ID activation
    carries a ``credentials/username`` element (whose text is the email and
    whose ``method`` is e.g. "AdobeID"); an anonymous activation has none.
    """
    device_xml = os.path.join(account_dir, "device.xml")
    activation_xml = os.path.join(account_dir, "activation.xml")
    activated = os.path.exists(device_xml) and os.path.exists(activation_xml)
    status = {"activated": activated, "uuid": None, "account_type": None, "email": None}
    if not activated:
        return status
    try:
        import libadobeAccount
        status["uuid"] = libadobeAccount.getAccountUUID()
    except Exception:
        traceback.print_exc()
    try:
        from lxml import etree
        ad = lambda tag: "{http://ns.adobe.com/adept}%s" % tag
        tree = etree.parse(activation_xml)
        username = tree.find("./%s/%s" % (ad("credentials"), ad("username")))
        if username is not None and username.text:
            status["account_type"] = username.get("method", "AdobeID")
            status["email"] = username.text
        else:
            status["account_type"] = "anonymous"
    except Exception:
        traceback.print_exc()
    return status


def _default_version_index():
    """Return the ADE version index to authorize with (default build id)."""
    from libadobe import VAR_VER_BUILD_IDS, VAR_VER_DEFAULT_BUILD_ID
    try:
        return VAR_VER_BUILD_IDS.index(VAR_VER_DEFAULT_BUILD_ID)
    except ValueError:
        return 1  # ADE 2.0.1 fallback


def _clear_account(account_dir):
    """Wipe existing Adobe activation files so activation starts clean."""
    for name in ("device.xml", "activation.xml", "devicesalt"):
        try:
            os.unlink(os.path.join(account_dir, name))
        except OSError:
            pass


def _export_key_hex():
    """Return the account encryption key as a hex string, or None."""
    import binascii
    import libadobeAccount
    key = libadobeAccount.exportAccountEncryptionKeyBytes()
    if not key:
        return None
    return binascii.hexlify(key).decode("ascii")


def _activate(account_dir, account_type, username, password):
    """Run the full Adobe activation sequence (mirrors register_ADE_account.py).

    Returns a result dict. On success it includes the account status and the
    exported encryption key hex, so the caller can bridge it to DeDRM in one go.
    """
    from libadobe import createDeviceKeyFile
    from libadobeAccount import createDeviceFile, createUser, signIn, activateDevice

    version_index = _default_version_index()
    _clear_account(account_dir)

    createDeviceKeyFile()

    if not createDeviceFile(True, version_index):
        return {"status": "error", "message": "Could not create the device file."}

    ok, resp = createUser(version_index, None)
    if not ok:
        return {"status": "error", "message": "Could not create user: %s" % resp}

    ok, resp = signIn(account_type, username, password)
    if not ok:
        return {"status": "error", "message": "Sign-in failed: %s" % resp}

    ok, resp = activateDevice(version_index, None)
    if not ok:
        return {"status": "error", "message": "Device activation failed: %s" % resp}

    return {
        "status": "ok",
        "account": _account_status(account_dir),
        "key_hex": _export_key_hex(),
    }


def cmd_status(args, account_dir):
    return {"status": "ok", "account": _account_status(account_dir)}


def cmd_deactivate(args, account_dir):
    # Remove the local Adobe account files (device.xml/activation.xml/devicesalt).
    for name in ("device.xml", "activation.xml", "devicesalt"):
        try:
            os.unlink(os.path.join(account_dir, name))
        except OSError:
            pass
    return {"status": "ok", "account": _account_status(account_dir)}


def cmd_activate_anon(args, account_dir):
    """Create + activate an anonymous Adobe account."""
    return _activate(account_dir, "anonymous", "", "")


def cmd_activate_adobeid(args, account_dir):
    """Sign in with an Adobe ID and activate. Password comes from --pass-file."""
    if not args.user:
        return {"status": "error", "message": "Missing Adobe ID."}
    password = ""
    if args.pass_file:
        try:
            with open(args.pass_file, "r", encoding="utf-8") as handle:
                password = handle.read()
            # Strip a single trailing newline without touching a real password.
            if password.endswith("\n"):
                password = password[:-1]
        except OSError:
            return {"status": "error", "message": "Could not read the password file."}
    if not password:
        return {"status": "error", "message": "Empty password."}
    return _activate(account_dir, "AdobeID", args.user, password)


def cmd_export_key(args, account_dir):
    """Export the account encryption key as hex (and to --out if given)."""
    key_hex = _export_key_hex()
    if not key_hex:
        return {"status": "error", "message": "No account key available (not activated?)."}
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(key_hex)
    import libadobeAccount
    return {"status": "ok", "key_hex": key_hex, "uuid": libadobeAccount.getAccountUUID()}


def _load_acsm_plugin(vendor_dir):
    """Execute the vendored DeACSM __init__ as the ``calibre_plugins.deacsm``
    package and return it, so we can reuse the plugin's ``download`` method."""
    import importlib.util
    init_path = os.path.join(vendor_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location(
        "calibre_plugins.deacsm", init_path, submodule_search_locations=[vendor_dir]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["calibre_plugins.deacsm"] = module
    sys.modules["calibre_plugins.deacsm.__init__"] = module
    spec.loader.exec_module(module)
    return module


def _read_notify_pref(config_dir):
    """Read notify_fulfillment from DeACSM's prefs JSON (default True)."""
    path = os.path.join(config_dir, "plugins", "ACSMInput", "ACSMInput.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return bool(json.load(handle).get("notify_fulfillment", True))
    except (OSError, ValueError):
        return True


_ACCOUNT_FILES = ("device.xml", "activation.xml", "devicesalt")


def cmd_export_activation(args, account_dir):
    """Write the Adobe activation (3 files) as a ZIP to --out.

    This is the portable backup of the account/device. It can be imported into
    another DeACSM (desktop Calibre or another Calibre-Web) to clone the SAME
    device without spending a new Adobe activation.
    """
    import zipfile
    if not args.out:
        return {"status": "error", "message": "export-activation needs --out"}
    for name in _ACCOUNT_FILES:
        if not os.path.exists(os.path.join(account_dir, name)):
            return {"status": "error", "message": "No activated Adobe account to export."}
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in _ACCOUNT_FILES:
            zf.write(os.path.join(account_dir, name), name)
    return {"status": "ok", "output": args.out, "account": _account_status(account_dir)}


def cmd_import_activation(args, account_dir):
    """Import an Adobe activation ZIP (device.xml/activation.xml/devicesalt).

    Clones an existing activation exported from desktop Calibre's DeACSM (or
    another Calibre-Web) so the SAME device key is used — keeping access to books
    already fulfilled with that account, without burning a new activation.
    """
    import zipfile
    if not args.input or not os.path.exists(args.input):
        return {"status": "error", "message": "import-activation needs a valid --input zip"}
    os.makedirs(account_dir, exist_ok=True)
    try:
        with zipfile.ZipFile(args.input, "r") as zf:
            names = set(zf.namelist())
            if not set(_ACCOUNT_FILES).issubset(names):
                return {"status": "error",
                        "message": "ZIP is missing required files (device.xml, activation.xml, devicesalt)."}
            for name in _ACCOUNT_FILES:
                # Write under our account dir, ignoring any path components in the zip.
                data = zf.read(name)
                with open(os.path.join(account_dir, os.path.basename(name)), "wb") as handle:
                    handle.write(data)
    except zipfile.BadZipFile:
        return {"status": "error", "message": "The uploaded file is not a valid ZIP."}

    # Validate the imported activation actually parses (uuid present).
    status = _account_status(account_dir)
    if not status.get("uuid"):
        _clear_account(account_dir)
        return {"status": "error", "message": "The imported activation is invalid or corrupt."}
    return {"status": "ok", "account": status, "key_hex": _export_key_hex()}


def cmd_fulfill(args, account_dir):
    """Fulfill an .acsm against Adobe and download the (still DRM'd) book."""
    if not args.input or not args.output_dir:
        return {"status": "error", "message": "fulfill needs --input and --output-dir"}
    if not os.path.exists(os.path.join(account_dir, "activation.xml")):
        return {"status": "error", "message": "No activated Adobe account."}

    here = os.path.dirname(os.path.abspath(__file__))
    vendor_dir = os.path.join(here, "_vendor")

    from libadobeFulfill import fulfill
    notify = _read_notify_pref(args.config_dir)
    success, reply_data = fulfill(args.input, notify)
    if not success:
        return {"status": "error", "message": str(reply_data)[:1000]}

    # Reuse the plugin's own download() (parses the response, downloads the book,
    # detects EPUB/PDF, embeds rights.xml / patches the PDF). It returns a path
    # inside our work_dir via the shim's temporary_file().
    plugin = _load_acsm_plugin(vendor_dir).ACSMInput()
    book_path = plugin.download(reply_data)
    if not book_path or not os.path.exists(book_path):
        return {"status": "error", "message": "Download/fulfillment produced no file."}

    ext = os.path.splitext(book_path)[1] or ".bin"
    base = os.path.splitext(os.path.basename(args.input))[0]
    final_path = os.path.join(args.output_dir, base + ext)
    shutil.copy2(book_path, final_path)
    return {"status": "ok", "output": final_path}


_COMMANDS = {
    "status": cmd_status,
    "deactivate": cmd_deactivate,
    "activate-anon": cmd_activate_anon,
    "activate-adobeid": cmd_activate_adobeid,
    "export-key": cmd_export_key,
    "export-activation": cmd_export_activation,
    "import-activation": cmd_import_activation,
    "fulfill": cmd_fulfill,
}


def main():
    parser = argparse.ArgumentParser(description="Headless DeACSM engine")
    parser.add_argument("command", choices=sorted(_COMMANDS))
    parser.add_argument("--config-dir", required=True)
    parser.add_argument("--account-dir", required=True)
    parser.add_argument("--result-file", required=True)
    parser.add_argument("--input")
    parser.add_argument("--output-dir")
    parser.add_argument("--out")
    parser.add_argument("--user")
    parser.add_argument("--pass-file")
    args = parser.parse_args()

    import tempfile
    work_dir = tempfile.mkdtemp(prefix="deacsm-work-")

    try:
        _bootstrap(args.config_dir, args.account_dir, work_dir)
        result = _COMMANDS[args.command](args, args.account_dir)
        _write_result(args.result_file, result)
        return 0
    except Exception as exc:  # noqa: BLE001 - report everything to the parent
        traceback.print_exc()
        _write_result(args.result_file, {"status": "error", "message": str(exc)})
        return 1
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
