# -*- coding: utf-8 -*-

"""A minimal fake ``calibre`` package so the vendored DeACSM code runs headless.

Mirrors ``cps/dedrm/_calibre_shim.py`` but covers the few extra Calibre touch
points the ACSM Input plugin needs:

* ``calibre.utils.config``   - ``config_dir`` + ``JSONConfig`` (prefs).
* ``calibre.customize``      - ``FileTypePlugin`` base class.
* ``calibre.utils.lock``     - ``singleinstance`` / ``SingleInstance``. DeACSM
  imports these at module top-level with no fallback for ``singleinstance``.
  We provide a no-op single-instance guard (we already run one operation per
  isolated subprocess, so there is never contention).
* ``calibre.customize.ui``   - ``_initialized_plugins`` / ``is_disabled``.
  DeACSM's ``run_single`` walks the initialized plugin list to hand the
  fulfilled (still Adobe-DRM) book to DeDRM. We deliberately expose an EMPTY
  plugin list so fulfillment returns the raw Adobe-DRM book unchanged; our own
  pipeline runs DeDRM afterwards.
* ``calibre.ebooks``         - ``BOOK_EXTENSIONS`` list.
* ``calibre_plugins.deacsm`` - real package mapped to the vendor dir so the
  plugin's ``import calibre_plugins.deacsm.prefs`` style imports resolve.

This runs ONLY inside the isolated engine subprocess (see ``engine.py``).
"""

import os
import sys
import types
import tempfile
from contextlib import contextmanager


def _make_filetype_plugin(vendor_dir, work_dir):
    """Build the ``FileTypePlugin`` base class bound to our directories."""

    class FileTypePlugin(object):
        """Headless stand-in for ``calibre.customize.FileTypePlugin``."""

        plugin_path = vendor_dir
        # DeACSM reads these from the plugin instance; harmless defaults.
        name = "ACSM Input"
        version = (0, 1, 0)

        def __init__(self, plugin_path=None, *args, **kwargs):
            if plugin_path is not None:
                self.plugin_path = plugin_path

        def temporary_file(self, suffix=""):
            """Open, persistent temp file with a ``.name`` (Calibre-compatible)."""
            return tempfile.NamedTemporaryFile(
                mode="w+b", suffix=suffix, dir=work_dir, delete=False
            )

        def load_resources(self, names):
            """Return ``{name: bytes}`` read from the vendored module directory."""
            result = {}
            for name in names:
                path = os.path.join(vendor_dir, *name.split("/"))
                try:
                    with open(path, "rb") as handle:
                        result[name] = handle.read()
                except OSError:
                    continue
            return result

    return FileTypePlugin


def _make_module(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def install(config_dir, vendor_dir, work_dir):
    """Register the fake ``calibre`` package tree in ``sys.modules``.

    Must be called before importing the vendored DeACSM package. ``config_dir``
    becomes Calibre's ``config_dir`` (DeACSM stores prefs under
    ``<config_dir>/plugins/ACSMInput/``); ``vendor_dir`` is the unpacked module
    directory (also holds the bundled ``oscrypto`` / ``asn1crypto``).
    """
    from standalone.jsonconfig import JSONConfig as _VendorJSONConfig

    class JSONConfig(_VendorJSONConfig):
        """JSONConfig whose default base path is our DeACSM config directory."""

        def __init__(self, rel_path_to_cf_file, base_path=None):
            if base_path is None:
                base_path = config_dir
            super(JSONConfig, self).__init__(rel_path_to_cf_file, base_path=base_path)

    # calibre
    calibre = _make_module("calibre")

    # calibre.utils / calibre.utils.config
    _make_module("calibre.utils")
    utils_config = _make_module("calibre.utils.config")
    utils_config.config_dir = config_dir
    utils_config.JSONConfig = JSONConfig
    utils_config.dynamic = {}
    calibre.utils = sys.modules["calibre.utils"]

    # calibre.utils.lock — single-instance guard.
    utils_lock = _make_module("calibre.utils.lock")

    def singleinstance(name):
        # Headless: always "the only instance".
        return True

    @contextmanager
    def SingleInstance(name):
        # No-op context manager that always grants the lock.
        yield True

    utils_lock.singleinstance = singleinstance
    utils_lock.SingleInstance = SingleInstance

    # calibre.customize
    customize = _make_module("calibre.customize")
    customize.FileTypePlugin = _make_filetype_plugin(vendor_dir, work_dir)

    # calibre.customize.ui — expose an EMPTY plugin list so DeACSM does NOT chain
    # into DeDRM internally (we run DeDRM ourselves on the fulfilled book).
    customize_ui = _make_module("calibre.customize.ui")
    customize_ui._initialized_plugins = []
    customize_ui.is_disabled = lambda plugin: False
    customize.ui = customize_ui

    # calibre.ebooks
    ebooks = _make_module("calibre.ebooks")
    ebooks.BOOK_EXTENSIONS = [
        "epub", "pdf", "acsm", "mobi", "azw", "azw3", "azw4", "kepub",
        "fb2", "djvu", "cbz", "cbr", "txt", "rtf", "lit", "prc", "pdb",
    ]

    # calibre.constants
    constants = _make_module("calibre.constants")
    constants.iswindows = sys.platform.startswith("win")
    constants.isosx = sys.platform == "darwin"
    constants.islinux = sys.platform.startswith("linux")

    # calibre_plugins.deacsm package mapped to the vendor dir, so the plugin's
    # ``import calibre_plugins.deacsm.prefs`` style imports resolve.
    calibre_plugins = _make_module("calibre_plugins")
    calibre_plugins.__path__ = []
    deacsm_pkg = _make_module("calibre_plugins.deacsm")
    deacsm_pkg.__path__ = [vendor_dir]
    calibre_plugins.deacsm = deacsm_pkg
