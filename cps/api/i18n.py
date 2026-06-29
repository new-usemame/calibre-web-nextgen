# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Locale catalog endpoint for the SPA i18n bridge.

The React SPA can't use server-side gettext, so it loads a per-locale JSON
catalog ({ msgid: translation }) derived from the SAME .po files the server
compiles — single source of truth, no parallel string set (design §10). The
SPA's English source strings ARE the gettext msgids, so:

  * any string already translated for the legacy UI is translated in the SPA
    for free (e.g. "Books" -> "Bücher"), and
  * anything not yet in the catalog falls back to the English source key.

This gives graceful degradation (never a missing-key placeholder) and makes
adding a translation a pure .po edit — exactly the parity the design requires.
"""
import os

from flask import jsonify
from babel.messages.pofile import read_po

from . import api_v1
from .. import logger

log = logger.create()

# cps/translations/<locale>/LC_MESSAGES/messages.po — the .po ships in the image
# (the compiled .mo is build-time only and not always present, e.g. the
# bind-mount dev container), so we read the .po directly: it's the single source
# of truth and always available.
_TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "translations"
)

# Parsed catalogs are immutable for the process lifetime; cache so each .po is
# parsed at most once (a ~278 KB .po parses in ~30 ms — fine cold, wasteful per
# session load).
_catalog_cache = {}

# Locales we ship a .po for. Derived from the filesystem (NOT
# babel.list_translations(), which keys off the compiled .mo — those are
# build-time only and absent in the bind-mount dev container). This is the
# allowlist the route validates against, consistent with what we actually read.
_available_locales = None


def _po_locales():
    global _available_locales
    if _available_locales is None:
        try:
            _available_locales = {
                name for name in os.listdir(_TRANSLATIONS_DIR)
                if os.path.isfile(os.path.join(_TRANSLATIONS_DIR, name, "LC_MESSAGES", "messages.po"))
            }
        except OSError:
            _available_locales = set()
    return _available_locales


def _load_catalog(locale):
    """Return { msgid: translation } for a locale, mirroring msgfmt semantics
    (skip the header, fuzzy entries, and empty translations). Returns an empty
    dict for 'en'/unknown so the SPA falls back to its English source keys."""
    if locale in _catalog_cache:
        return _catalog_cache[locale]
    catalog = {}
    po_path = os.path.join(_TRANSLATIONS_DIR, locale, "LC_MESSAGES", "messages.po")
    if os.path.isfile(po_path):
        try:
            with open(po_path, "rb") as f:
                parsed = read_po(f)
            for message in parsed:
                # Skip the header (empty id) and fuzzy entries (msgfmt drops
                # them). Plurals carry a list/tuple id; the SPA uses singular
                # keys today, so skip them (plural support is a later step).
                if not message.id or message.fuzzy:
                    continue
                if isinstance(message.id, (list, tuple)):
                    continue
                if message.string and isinstance(message.string, str):
                    catalog[message.id] = message.string
        except Exception:
            log.error("Failed to parse translation catalog for %s", locale, exc_info=True)
    _catalog_cache[locale] = catalog
    return catalog


@api_v1.route("/i18n/<locale>.json")
def i18n_catalog(locale):
    """Public: serve the per-locale string catalog for the SPA.

    Public because the login screen needs strings before a session exists and
    translations aren't sensitive. Unknown locales return an empty catalog
    (English fallback) rather than 404, so the SPA never special-cases a missing
    locale. The locale is validated against the set we actually ship before any
    path is built, so it can't be used to probe the filesystem (Flask's
    <locale> converter also rejects slashes)."""
    if locale != "en" and locale not in _po_locales():
        catalog = {}
    else:
        catalog = _load_catalog(locale)
    resp = jsonify({"locale": locale, "catalog": catalog})
    # Catalogs are immutable for the life of an image; let the browser cache.
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp
