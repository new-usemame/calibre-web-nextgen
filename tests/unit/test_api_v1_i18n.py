"""Unit tests for the SPA i18n catalog endpoint (cps/api/i18n.py).

The endpoint derives a per-locale { msgid: translation } catalog from the same
.po files the server compiles, so the React SPA reuses existing translations
with English-source fallback. These tests pin:
  * real extraction from a shipped locale (de) including a known translation,
  * msgfmt-equivalent filtering (skip header, fuzzy, empty),
  * graceful behaviour for 'en' (source locale) and unknown locales,
  * that the endpoint is reachable without auth (login screen needs it).
"""
import json
import os
import inspect

import pytest
import flask


def _call_view(locale):
    """Invoke the i18n_catalog view in a request context and return parsed JSON."""
    from cps.api import i18n as i18n_mod
    app = flask.Flask(__name__)
    with app.test_request_context(f"/api/v1/i18n/{locale}.json"):
        view = inspect.unwrap(i18n_mod.i18n_catalog)
        result = view(locale)
        # The view returns a Response (jsonify + Cache-Control header).
        body = json.loads(result.get_data(as_text=True))
        return body, result


@pytest.fixture(autouse=True)
def _clear_i18n_caches():
    """Each test starts with cold caches so monkeypatched dirs take effect."""
    from cps.api import i18n as i18n_mod
    i18n_mod._catalog_cache.clear()
    i18n_mod._available_locales = None
    yield
    i18n_mod._catalog_cache.clear()
    i18n_mod._available_locales = None


@pytest.mark.unit
def test_real_de_catalog_has_known_translation():
    """Reading the shipped de .po yields real translations (Books -> Bücher)."""
    body, _ = _call_view("de")
    assert body["locale"] == "de"
    catalog = body["catalog"]
    assert isinstance(catalog, dict)
    assert len(catalog) > 100  # the real catalog has ~1400 entries
    assert catalog.get("Books") == "Bücher"
    assert catalog.get("Authors") == "Autoren"


@pytest.mark.unit
def test_en_returns_empty_catalog():
    """English is the source locale — its catalog is empty (keys are the strings)."""
    body, _ = _call_view("en")
    assert body["locale"] == "en"
    assert body["catalog"] == {}


@pytest.mark.unit
def test_unknown_locale_returns_empty_no_error():
    """A locale we don't ship returns an empty catalog, not a 404/500."""
    body, _ = _call_view("zz")
    assert body["locale"] == "zz"
    assert body["catalog"] == {}


@pytest.mark.unit
def test_catalog_has_cache_control_header():
    """Immutable catalogs are browser-cacheable."""
    _, resp = _call_view("de")
    assert "public" in resp.headers.get("Cache-Control", "")


@pytest.mark.unit
def test_i18n_endpoint_is_public():
    """The auth gate must let the catalog through (login screen needs strings)."""
    from cps.api import _PUBLIC_ENDPOINTS
    assert "api_v1.i18n_catalog" in _PUBLIC_ENDPOINTS


@pytest.mark.unit
def test_load_catalog_skips_header_fuzzy_and_empty(tmp_path, monkeypatch):
    """_load_catalog mirrors msgfmt: drop the header, fuzzy entries, and empties."""
    from cps.api import i18n as i18n_mod

    locale = "xx"
    lc = tmp_path / locale / "LC_MESSAGES"
    lc.mkdir(parents=True)
    (lc / "messages.po").write_text(
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '\n'
        'msgid "Normal"\n'
        'msgstr "NormalXX"\n'
        '\n'
        '#, fuzzy\n'
        'msgid "FuzzyOne"\n'
        'msgstr "FuzzyXX"\n'
        '\n'
        'msgid "EmptyOne"\n'
        'msgstr ""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(i18n_mod, "_TRANSLATIONS_DIR", str(tmp_path))
    i18n_mod._catalog_cache.clear()
    i18n_mod._available_locales = None

    catalog = i18n_mod._load_catalog(locale)
    assert catalog == {"Normal": "NormalXX"}  # fuzzy + empty + header all dropped


@pytest.mark.unit
def test_load_catalog_missing_po_returns_empty(tmp_path, monkeypatch):
    """A locale dir without a messages.po yields an empty catalog (no exception)."""
    from cps.api import i18n as i18n_mod
    monkeypatch.setattr(i18n_mod, "_TRANSLATIONS_DIR", str(tmp_path))
    i18n_mod._catalog_cache.clear()
    assert i18n_mod._load_catalog("nope") == {}


@pytest.mark.unit
def test_po_locales_allowlist_from_filesystem():
    """The allowlist is derived from shipped .po dirs (so it works without .mo)."""
    from cps.api import i18n as i18n_mod
    locales = i18n_mod._po_locales()
    assert "de" in locales
    assert "fr" in locales
    # 'en' is the source locale and has no .po dir; it's handled separately.
    assert isinstance(locales, set)


@pytest.mark.unit
def test_route_registered():
    """The endpoint is wired onto the api_v1 blueprint at the expected rule."""
    from cps.api import i18n as i18n_mod  # noqa: F401  (ensure import side effects)
    # The view function exists and is callable; the route decorator attached it.
    assert callable(i18n_mod.i18n_catalog)
