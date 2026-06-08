# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Admin blueprint for configuring the vendored DeDRM module.

DeDRM's configuration (keys, serials, PIDs, passphrases and a few flags) does
not fit the flat ``_Settings`` column model used by the main config page: it is
a set of dynamic, user-managed lists stored in a JSON file on disk
(``CONFIG_DIR/dedrm/plugins/dedrm.json``). This blueprint renders a dedicated
page for it and persists every change through :mod:`cps.dedrm.prefs_store`, so
the very same file is what the ingest worker reads when deciding whether DRM
removal is configured.

Routes (all admin-only):

* ``GET  /admin/dedrm``            - render the management page.
* ``POST /admin/dedrm/flags``      - save the boolean flags (enable + options).
* ``POST /admin/dedrm/key/add``    - add a named key, serial, PID or passphrase.
* ``POST /admin/dedrm/key/delete`` - remove one of the above.
"""

import os
import json
import binascii
import tempfile

from flask import Blueprint, redirect, url_for, request, flash, Response
from flask_babel import gettext as _
from flask_babel import lazy_gettext as N_

from . import logger
from .admin import admin_required
from .usermanagement import user_login_required
from .render_template import render_title_template
from . import dedrm
from .dedrm import prefs_store
from . import deacsm
from .string_helper import strip_whitespaces

log = logger.create()

dedrm_admin = Blueprint("dedrm_admin", __name__)

# Ordered, fully-described list of every configurable key store. One structure
# drives the whole UI so each section can show exactly what belongs there, in
# which format, and whether a file upload applies — avoiding the earlier
# confusion (e.g. a Kindle serial number is plain text and must NOT offer a file
# upload, while an Adobe key comes from a .der file).
#
# Field reference:
#   store         - the dedrm.json preference key.
#   kind          - "list" (flat values) or "named" (name -> key material).
#   label         - section heading.
#   description   - one-line explanation of what goes here.
#   placeholder   - example value shown in the text field.
#   file_ext      - accepted upload extension, or None when no file applies.
#   file_encoding - how an uploaded file is stored, matching DeDRM's own import
#                   (see ManageKeysDialog in the plugin's config.py):
#                     "hex"   -> hex of the raw bytes (.der / Adobe keys)
#                     "json"  -> parsed JSON object   (.k4i / Kindle for PC/Mac)
#                     "lines" -> list of text lines    (.k4a / Kindle Android)
#
# lazy_gettext (N_) is used because these are evaluated at import time, before
# any request/locale context exists; the strings resolve when rendered.
KEY_SECTIONS = [
    {
        "store": "serials",
        "kind": "list",
        "label": N_("eInk Kindle serial number"),
        "description": N_("For books from a physical Kindle e-reader. Enter the device serial number "
                          "(Settings → Device Info on the Kindle; 16 characters, usually starting with "
                          "'B' or 'G')."),
        "placeholder": N_("e.g. B0XXXXXXXXXXXXXX"),
        "file_ext": None,
        "file_encoding": None,
        # Allow an optional friendly name so several Kindles are easy to tell apart.
        "labeled": True,
    },
    {
        "store": "adeptkeys",
        "kind": "named",
        "label": N_("Adobe Digital Editions key"),
        "description": N_("For Adobe-DRM EPUB/PDF (e.g. from public libraries or many ebook stores). "
                          "Upload the .der key file exported by the DeDRM key-extraction tools, or paste "
                          "the key as a hex string."),
        "placeholder": N_("Paste the key as hex, or upload a .der file below"),
        "file_ext": ".der",
        "file_encoding": "hex",
        "allow_paste": True,
    },
    {
        "store": "kindlekeys",
        "kind": "named",
        "label": N_("Kindle for PC/Mac key"),
        "description": N_("For Kindle books downloaded through the Kindle for PC or Mac app. Upload the "
                          ".k4i key file produced by the DeDRM key-extraction tools."),
        "placeholder": N_("Upload a .k4i file below"),
        "file_ext": ".k4i",
        "file_encoding": "json",
        # The .k4i key is structured JSON; typing it by hand is not meaningful.
        "allow_paste": False,
    },
    {
        "store": "androidkeys",
        "kind": "named",
        "label": N_("Kindle for Android key"),
        "description": N_("For Kindle books from the Android app. Upload the .k4a key file produced by "
                          "the DeDRM key-extraction tools."),
        "placeholder": N_("Upload a .k4a file below"),
        "file_ext": ".k4a",
        "file_encoding": "lines",
        "allow_paste": False,
    },
    {
        "store": "bandnkeys",
        "kind": "named",
        "label": N_("Barnes & Noble / ADE PassHash key"),
        "description": N_("For Barnes & Noble (Nook) books, as a base64 PassHash key string."),
        "placeholder": N_("Paste the base64 key"),
        "file_ext": None,
        "file_encoding": None,
        "allow_paste": True,
    },
    {
        "store": "ereaderkeys",
        "kind": "named",
        "label": N_("eReader key (advanced)"),
        "description": N_("For older eReader (.pdb) books. Paste the key string."),
        "placeholder": N_("Paste the key"),
        "file_ext": None,
        "file_encoding": None,
        "allow_paste": True,
    },
    {
        "store": "pids",
        "kind": "list",
        "label": N_("Mobipocket PID"),
        "description": N_("For Mobipocket books. Enter the 8 or 10 character PID."),
        "placeholder": N_("e.g. 1234567*89"),
        "file_ext": None,
        "file_encoding": None,
    },
    {
        "store": "lcp_passphrases",
        "kind": "list",
        "label": N_("Readium LCP passphrase"),
        "description": N_("For Readium LCP protected books. Enter the passphrase."),
        "placeholder": N_("Enter the passphrase"),
        "file_ext": None,
        "file_encoding": None,
    },
    {
        "store": "adobe_pdf_passphrases",
        "kind": "list",
        "label": N_("Adobe PDF passphrase"),
        "description": N_("For password-protected Adobe PDFs. Enter the passphrase."),
        "placeholder": N_("Enter the passphrase"),
        "file_ext": None,
        "file_encoding": None,
    },
]

# Quick lookup by store name.
SECTIONS_BY_STORE = {section["store"]: section for section in KEY_SECTIONS}


@dedrm_admin.route("/admin/dedrm")
@user_login_required
@admin_required
def config_page():
    """Render the DeDRM management page with the current preferences."""
    prefs = dedrm.get_prefs()
    return render_title_template(
        "config_dedrm.html",
        title=_("DRM removal & Adobe (DeDRM + DeACSM)"),
        page="config_dedrm",
        prefs=prefs,
        key_sections=KEY_SECTIONS,
        deacsm_status=deacsm.account_status(),
        deacsm_prefs=deacsm.get_prefs(),
    )


@dedrm_admin.route("/admin/dedrm/flags", methods=["POST"])
@user_login_required
@admin_required
def save_flags():
    """Persist all DRM + ACSM behaviour flags from the unified settings form."""
    prefs = dedrm.get_prefs()
    prefs["deobfuscate_fonts"] = request.form.get("deobfuscate_fonts") == "on"
    prefs["remove_watermarks"] = request.form.get("remove_watermarks") == "on"
    dedrm.save_prefs(prefs)

    acsm_prefs = deacsm.get_prefs()
    acsm_prefs["notify_fulfillment"] = request.form.get("notify_fulfillment") == "on"
    acsm_prefs["delete_acsm_after_fulfill"] = request.form.get("delete_acsm_after_fulfill") == "on"
    acsm_prefs["detailed_logging"] = request.form.get("detailed_logging") == "on"
    deacsm.save_prefs(acsm_prefs)

    flash(_("Settings saved."), category="success")
    return redirect(url_for("dedrm_admin.config_page"))


def _encode_key_file(raw, encoding):
    """Encode an uploaded key file's bytes the way DeDRM stores that key type.

    Mirrors the import logic in the plugin's own ManageKeysDialog so a key
    imported here is byte-for-byte what the desktop plugin would have stored:
      * "hex"   -> hex string of the raw bytes (.der / Adobe keys)
      * "json"  -> parsed JSON object          (.k4i / Kindle for PC/Mac)
      * "lines" -> list of non-empty text lines (.k4a / Kindle for Android)
    """
    if encoding == "hex":
        return binascii.hexlify(raw).decode("ascii")
    if encoding == "json":
        return json.loads(raw.decode("utf-8"))
    if encoding == "lines":
        return [line for line in raw.decode("utf-8", "replace").splitlines() if line.strip()]
    # Fallback: store the file's text content as-is.
    return raw.decode("utf-8", "replace").strip()


@dedrm_admin.route("/admin/dedrm/key/add", methods=["POST"])
@user_login_required
@admin_required
def add_key():
    """Add a value to a named-key store or a flat list store.

    The accepted input and any file encoding are driven by KEY_SECTIONS, so each
    store behaves exactly as the DeDRM desktop plugin expects (e.g. a Kindle
    serial is plain text with no file, an Adobe key is hex from a .der file, a
    Kindle .k4i is stored as parsed JSON).
    """
    store = request.form.get("store", "")
    name = (request.form.get("name") or "").strip()
    value = (request.form.get("value") or "").strip()
    section = SECTIONS_BY_STORE.get(store)

    if section is None:
        flash(_("Unknown key store."), category="error")
        return redirect(url_for("dedrm_admin.config_page"))

    prefs = dedrm.get_prefs()

    if section["kind"] == "named":
        # Stores whose key material is structured (.k4i JSON, .k4a lines) accept
        # a file only; a pasted text value would be stored in the wrong shape.
        allow_paste = section.get("allow_paste", True)
        key_value = value if allow_paste else ""
        if section["file_ext"]:
            uploaded = request.files.get("keyfile")
            if uploaded and uploaded.filename:
                raw = uploaded.read()
                if not raw:
                    flash(_("The uploaded key file is empty."), category="error")
                    return redirect(url_for("dedrm_admin.config_page"))
                try:
                    key_value = _encode_key_file(raw, section["file_encoding"])
                except (ValueError, UnicodeDecodeError):
                    flash(_("The uploaded key file could not be read in the expected format."),
                          category="error")
                    return redirect(url_for("dedrm_admin.config_page"))
                if not name:
                    name = os.path.splitext(os.path.basename(uploaded.filename))[0]
        if not key_value:
            if section["file_ext"] and not allow_paste:
                flash(_("Please upload a %(ext)s key file.", ext=section["file_ext"]), category="error")
            else:
                flash(_("Please provide a key value or upload a key file."), category="error")
            return redirect(url_for("dedrm_admin.config_page"))
        if not name:
            name = _("key")
        prefs, resolved = prefs_store.add_named_key(prefs, store, name, key_value)
        if resolved is None:
            flash(_("That key is already present."), category="warning")
        else:
            dedrm.save_prefs(prefs)
            flash(_("Key '%(name)s' added.", name=resolved), category="success")
    else:  # list store: plain text only, never a file.
        if not value:
            flash(_("Please provide a value."), category="error")
            return redirect(url_for("dedrm_admin.config_page"))
        prefs_store.add_list_value(prefs, store, value)
        # Optional friendly label (e.g. which Kindle a serial belongs to).
        if section.get("labeled") and name:
            prefs_store.set_label(prefs, store, value, name)
        dedrm.save_prefs(prefs)
        flash(_("Value added."), category="success")

    return redirect(url_for("dedrm_admin.config_page"))


@dedrm_admin.route("/admin/dedrm/key/delete", methods=["POST"])
@user_login_required
@admin_required
def delete_key():
    """Remove a named key or a list value from the preferences."""
    store = request.form.get("store", "")
    name = request.form.get("name", "")
    value = request.form.get("value", "")

    prefs = dedrm.get_prefs()
    if store in prefs_store.NAMED_KEY_STORES:
        prefs_store.delete_named_key(prefs, store, name)
        dedrm.save_prefs(prefs)
        flash(_("Key removed."), category="success")
    elif store in prefs_store.LIST_STORES:
        prefs_store.delete_list_value(prefs, store, value)
        dedrm.save_prefs(prefs)
        flash(_("Value removed."), category="success")
    else:
        flash(_("Unknown key store."), category="error")

    return redirect(url_for("dedrm_admin.config_page"))


@dedrm_admin.route("/admin/dedrm/export", methods=["GET"])
@user_login_required
@admin_required
def dedrm_export():
    """Download the whole DeDRM configuration (keys/serials/…) as JSON."""
    data = json.dumps(dedrm.get_prefs(), ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        data, mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=dedrm.json"},
    )


@dedrm_admin.route("/admin/dedrm/import", methods=["POST"])
@user_login_required
@admin_required
def dedrm_import():
    """Import a DeDRM configuration (dedrm.json) from desktop Calibre.

    Merges additively into the current configuration: keys/serials are added
    (deduplicated), existing entries are kept. Lets you bring over a whole
    desktop DeDRM setup instead of re-entering every key.
    """
    uploaded = request.files.get("dedrm_json")
    if not uploaded or not uploaded.filename:
        flash(_("Please choose a dedrm.json file to import."), category="error")
        return redirect(url_for("dedrm_admin.config_page"))
    try:
        imported = json.loads(uploaded.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        flash(_("That file is not a valid dedrm.json."), category="error")
        return redirect(url_for("dedrm_admin.config_page"))

    prefs = dedrm.get_prefs()
    prefs, added = prefs_store.merge_imported_prefs(prefs, imported)
    dedrm.save_prefs(prefs)
    flash(_("Imported DeDRM configuration (%(n)s new entries).", n=added), category="success")
    return redirect(url_for("dedrm_admin.config_page"))


# --- DeACSM (Adobe account / ACSM fulfillment) -----------------------------

@dedrm_admin.route("/admin/deacsm/activate", methods=["POST"])
@user_login_required
@admin_required
def deacsm_activate():
    """Activate an Adobe account (anonymous or with an Adobe ID).

    Activation talks to Adobe's servers and can take a while; on success the
    account's encryption key is auto-bridged into DeDRM's adept keys, so Adobe
    EPUB/PDF decryption also starts working with no extra step.
    """
    method = request.form.get("method", "anonymous")
    if method == "adobeid":
        user = strip_whitespaces(request.form.get("email") or "")
        password = request.form.get("password") or ""
        if not user or not password:
            flash(_("Adobe ID and password are required."), category="error")
            return redirect(url_for("dedrm_admin.config_page"))
        result = deacsm.activate_adobeid(user, password)
    else:
        result = deacsm.activate_anonymous()

    if result.get("ok"):
        flash(_("Adobe account activated. The key is now shared with DeDRM."), category="success")
    else:
        flash(_("Adobe activation failed: %(msg)s", msg=result.get("message", "")), category="error")
    return redirect(url_for("dedrm_admin.config_page"))


@dedrm_admin.route("/admin/deacsm/deactivate", methods=["POST"])
@user_login_required
@admin_required
def deacsm_deactivate():
    """Remove the local Adobe account and the key bridged into DeDRM."""
    if deacsm.deactivate():
        flash(_("Adobe account deactivated."), category="success")
    else:
        flash(_("Could not deactivate the Adobe account."), category="error")
    return redirect(url_for("dedrm_admin.config_page"))


@dedrm_admin.route("/admin/deacsm/flags", methods=["POST"])
@user_login_required
@admin_required
def deacsm_flags():
    """Persist the DeACSM behaviour flags."""
    prefs = deacsm.get_prefs()
    prefs["notify_fulfillment"] = request.form.get("notify_fulfillment") == "on"
    prefs["delete_acsm_after_fulfill"] = request.form.get("delete_acsm_after_fulfill") == "on"
    prefs["detailed_logging"] = request.form.get("detailed_logging") == "on"
    deacsm.save_prefs(prefs)
    flash(_("Adobe/ACSM settings saved."), category="success")
    return redirect(url_for("dedrm_admin.config_page"))


@dedrm_admin.route("/admin/deacsm/import", methods=["POST"])
@user_login_required
@admin_required
def deacsm_import():
    """Import an existing Adobe activation from a backup ZIP.

    Use this to bring over an account already activated in desktop Calibre's
    DeACSM (anonymous or Adobe ID): it clones the SAME device so books already
    fulfilled with that account stay readable and no new activation is spent.
    """
    uploaded = request.files.get("activation_zip")
    if not uploaded or not uploaded.filename:
        flash(_("Please choose an activation .zip to import."), category="error")
        return redirect(url_for("dedrm_admin.config_page"))

    fd, tmp_path = tempfile.mkstemp(prefix="deacsm-import-", suffix=".zip")
    os.close(fd)
    try:
        uploaded.save(tmp_path)
        result = deacsm.import_activation_zip(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.get("ok"):
        flash(_("Adobe activation imported. The key is now shared with DeDRM."), category="success")
    else:
        flash(_("Import failed: %(msg)s", msg=result.get("message", "")), category="error")
    return redirect(url_for("dedrm_admin.config_page"))


@dedrm_admin.route("/admin/deacsm/export/activation", methods=["GET"])
@user_login_required
@admin_required
def deacsm_export_activation():
    """Download the Adobe activation as a ZIP (portable account backup)."""
    zip_path = deacsm.export_activation_zip()
    if not zip_path:
        flash(_("No activated Adobe account to export."), category="error")
        return redirect(url_for("dedrm_admin.config_page"))
    try:
        with open(zip_path, "rb") as handle:
            data = handle.read()
    finally:
        try:
            os.unlink(zip_path)
        except OSError:
            pass
    return Response(
        data, mimetype="application/zip",
        headers={"Content-Disposition": "attachment; filename=adobe_account_backup.zip"},
    )


@dedrm_admin.route("/admin/deacsm/export/key", methods=["GET"])
@user_login_required
@admin_required
def deacsm_export_key():
    """Download the Adobe account encryption key as a .der file."""
    der = deacsm.export_key_der_bytes()
    if not der:
        flash(_("No account key available to export."), category="error")
        return redirect(url_for("dedrm_admin.config_page"))
    return Response(
        der, mimetype="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=adobe_account_key.der"},
    )
