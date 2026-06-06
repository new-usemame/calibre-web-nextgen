# -*- coding: utf-8 -*-

"""A minimal fake ``calibre`` package so the vendored DeDRM code runs headless.

The vendored DeDRM modules were written as a Calibre plugin. Almost every
``from calibre...`` import in them is already wrapped in ``try/except`` with a
working non-Calibre fallback, EXCEPT for a few touch points that this shim must
provide:

* ``calibre.utils.config.config_dir``  - base directory for DeDRM's prefs/keys.
* ``calibre.utils.config.JSONConfig``  - the prefs container DeDRM writes to.
* ``calibre.customize.FileTypePlugin`` - the plugin base class, whose
  ``temporary_file()`` / ``load_resources()`` / ``plugin_path`` members the
  decryption code relies on.
* ``calibre.constants``                - ``iswindows`` / ``isosx`` / ``islinux``.
* ``calibre.ptempfile.TemporaryFile``  - a temp-path context manager.

:func:`install` registers these as in-memory modules in ``sys.modules`` BEFORE
the vendored package is imported. This runs ONLY inside the isolated engine
subprocess (see ``engine.py``) - never inside the Flask worker - so polluting
``sys.modules`` with a fake ``calibre`` is safe and short-lived.

Crucially, registering a ``calibre`` module makes DeDRM's modules prefer these
shimmed imports over their weaker fallbacks (e.g. a real ``config_dir`` instead
of the empty-string fallback), which is exactly what we want.
"""

import os
import sys
import types
import tempfile
from contextlib import contextmanager


def _make_filetype_plugin(vendor_dir, work_dir):
    """Build the ``FileTypePlugin`` base class bound to our directories.

    ``vendor_dir`` is where the plugin's own resource files live (used by
    ``load_resources``); ``work_dir`` is where temporary working files are
    created (used by ``temporary_file``).
    """

    class FileTypePlugin(object):
        """Headless stand-in for ``calibre.customize.FileTypePlugin``.

        Only the surface the vendored DeDRM code actually uses is implemented.
        """

        # DeDRM reads ``self.plugin_path`` (e.g. in its config widget path).
        plugin_path = vendor_dir

        def __init__(self, plugin_path=None, *args, **kwargs):
            # Calibre instantiates plugins with their zip path; accept and store
            # it, but default to the vendored module directory.
            if plugin_path is not None:
                self.plugin_path = plugin_path

        def temporary_file(self, suffix=""):
            """Return an open, persistent temp file with a ``.name`` attribute.

            Mirrors Calibre's ``PersistentTemporaryFile``: the file is opened in
            binary write mode, is NOT deleted on close, and exposes ``.name`` so
            the decryptors can write their output to that path. Callers use both
            ``handle.name`` and (occasionally) ``handle.write()``/``close()``.
            """
            return tempfile.NamedTemporaryFile(
                mode="w+b", suffix=suffix, dir=work_dir, delete=False
            )

        def load_resources(self, names):
            """Return ``{name: bytes}`` read from the vendored module directory.

            Calibre normally reads these from the plugin zip; here the modules
            sit unpacked under ``vendor_dir``. DeDRM only calls this once on
            Linux to stage helper scripts for optional Wine usage; missing files
            are skipped silently, matching Calibre's lenient behaviour.
            """
            result = {}
            for name in names:
                resource_path = os.path.join(vendor_dir, *name.split("/"))
                try:
                    with open(resource_path, "rb") as handle:
                        result[name] = handle.read()
                except OSError:
                    # A missing optional resource must not abort initialization.
                    continue
            return result

    return FileTypePlugin


def _make_module(name):
    """Create and register a fresh empty module under ``name``."""
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def install(config_dir, vendor_dir, work_dir):
    """Register the fake ``calibre`` package tree in ``sys.modules``.

    Must be called before importing the vendored DeDRM package. ``config_dir``
    becomes Calibre's ``config_dir`` (DeDRM stores prefs at
    ``<config_dir>/plugins/dedrm.json``); ``vendor_dir`` is the unpacked module
    directory; ``work_dir`` is where temporary files are created.
    """
    # The vendored ``standalone.jsonconfig`` provides a Calibre-free JSONConfig
    # implementation; reuse it so prefs read/write stays identical on both the
    # engine side and the Flask ``prefs_store`` side. ``vendor_dir`` must be on
    # ``sys.path`` already (the engine inserts it before calling install()).
    from standalone.jsonconfig import JSONConfig as _VendorJSONConfig

    class JSONConfig(_VendorJSONConfig):
        """JSONConfig whose default base path is our DeDRM config directory.

        DeDRM constructs ``JSONConfig("plugins/dedrm.json")`` with no explicit
        base path, so binding the default here is what lands the prefs file at
        ``<config_dir>/plugins/dedrm.json``.
        """

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
    # Some modules import ``dynamic``; a plain dict is a sufficient stand-in.
    utils_config.dynamic = {}
    calibre.utils = sys.modules["calibre.utils"]

    # calibre.customize
    customize = _make_module("calibre.customize")
    customize.FileTypePlugin = _make_filetype_plugin(vendor_dir, work_dir)

    # calibre.constants
    constants = _make_module("calibre.constants")
    constants.iswindows = sys.platform.startswith("win")
    constants.isosx = sys.platform == "darwin"
    constants.islinux = sys.platform.startswith("linux")

    # calibre_plugins.dedrm package.
    #
    # The vendored modules carry compatibility code that sets
    # ``__package__ = "calibre_plugins.dedrm"`` whenever a ``calibre`` module is
    # importable (which it now is, thanks to the shim). Several modules then use
    # genuine relative imports with NO bare-name fallback, e.g.
    # ``from .utilities import SafeUnbuffered`` in ineptepub.py. For those to
    # resolve we must register ``calibre_plugins.dedrm`` as a real package whose
    # submodule search path points at the vendored directory - exactly how
    # Calibre itself exposes the plugin. With this in place, a top-level
    # ``import ineptepub`` whose ``__package__`` is ``calibre_plugins.dedrm`` can
    # still satisfy ``from .utilities import ...`` from the vendor dir.
    calibre_plugins = _make_module("calibre_plugins")
    calibre_plugins.__path__ = []
    dedrm_pkg = _make_module("calibre_plugins.dedrm")
    dedrm_pkg.__path__ = [vendor_dir]
    calibre_plugins.dedrm = dedrm_pkg

    # calibre.ptempfile
    ptempfile = _make_module("calibre.ptempfile")

    @contextmanager
    def TemporaryFile(suffix=""):
        """Yield a temp file path, removing it on exit (Calibre-compatible)."""
        fd, path = tempfile.mkstemp(suffix=suffix, dir=work_dir)
        os.close(fd)
        try:
            yield path
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    ptempfile.TemporaryFile = TemporaryFile
