# -*- coding: utf-8 -*-

"""Public, import-light DeDRM facade for Calibre-Web-NextGen.

This package vendors the DeDRM plugin source under ``_vendor/`` and exposes a
small, Calibre-free API the rest of the app uses:

* :func:`is_configured` / :func:`get_prefs` / :func:`save_prefs` - prefs access
  (delegated to :mod:`cps.dedrm.prefs_store`).
* :func:`remove_drm` - run the decryptor on a single file.

Importing this module must stay cheap: it deliberately does NOT import any
``_vendor`` module. The heavy, namespace-polluting decryption code runs only in
the isolated :mod:`cps.dedrm.engine` subprocess, which :func:`remove_drm`
launches. This keeps the long-lived Flask worker clean and crash-isolated.
"""

import os
import sys
import json
import tempfile
import subprocess

from cps import logger
from .prefs_store import (
    DEDRM_DIR,
    PREFS_PATH,
    KEYFILES_DIR,
    get_prefs,
    save_prefs,
    is_configured,
    add_named_key,
    delete_named_key,
    add_list_value,
    delete_list_value,
)

log = logger.create()

# Absolute path to the isolated engine script (run as a standalone process).
_ENGINE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.py")

# Extensions DeDRM knows how to process; callers can pre-filter to avoid
# spawning the engine for files it would just pass through unchanged. Mirrors
# the ``file_types`` set declared by the vendored DeDRM plugin.
SUPPORTED_EXTENSIONS = frozenset(
    ["epub", "pdf", "pdb", "prc", "mobi", "pobi", "azw", "azw1",
     "azw3", "azw4", "azw8", "tpz", "kfx", "kfx-zip"]
)

# Safety cap so a pathological file cannot hang ingest forever.
_ENGINE_TIMEOUT = 600


def get_dedrm_dir():
    """Return the base directory holding all DeDRM state for this install."""
    return DEDRM_DIR


def is_supported(path):
    """Return ``True`` if ``path``'s extension is one DeDRM can process."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    return ext in SUPPORTED_EXTENSIONS


def remove_drm(input_path, output_dir):
    """Attempt to strip DRM from ``input_path``, writing the result to ``output_dir``.

    Returns the path to the decrypted file on success, or ``None`` when DeDRM is
    not configured, the file type is unsupported, the file has no DRM, or
    removal failed. Callers treat ``None`` as "keep the original untouched".

    The actual decryption happens in the isolated :mod:`cps.dedrm.engine`
    subprocess. This function never raises for an ordinary decryption failure;
    it logs and returns ``None`` so an ingest pipeline can carry on.
    """
    if not is_configured():
        # Per project policy: do nothing at all when DeDRM is unconfigured.
        return None
    if not is_supported(input_path):
        return None

    os.makedirs(output_dir, exist_ok=True)

    # The engine reports its outcome through a small JSON file rather than via
    # stdout, which DeDRM floods with progress messages.
    result_fd, result_file = tempfile.mkstemp(prefix="dedrm-result-", suffix=".json", dir=output_dir)
    os.close(result_fd)

    try:
        completed = subprocess.run(
            [
                sys.executable,
                _ENGINE_PATH,
                "--input", input_path,
                "--output-dir", output_dir,
                "--config-dir", DEDRM_DIR,
                "--result-file", result_file,
            ],
            capture_output=True,
            text=True,
            timeout=_ENGINE_TIMEOUT,
        )

        # Forward the engine's diagnostics to our logger for troubleshooting.
        if completed.stdout:
            log.debug("DeDRM engine output for %s:\n%s", os.path.basename(input_path), completed.stdout.strip())
        if completed.returncode != 0 and completed.stderr:
            log.warning("DeDRM engine stderr for %s:\n%s", os.path.basename(input_path), completed.stderr.strip())

        try:
            with open(result_file, "r", encoding="utf-8") as handle:
                result = json.load(handle)
        except (OSError, ValueError):
            log.warning("DeDRM engine produced no readable result for %s; keeping original",
                        os.path.basename(input_path))
            return None

        status = result.get("status")
        if status == "decrypted":
            output = result.get("output")
            if output and os.path.exists(output):
                log.info("DeDRM removed DRM from %s", os.path.basename(input_path))
                return output
            log.warning("DeDRM reported success but output is missing for %s", os.path.basename(input_path))
            return None
        if status == "none":
            # No DRM found / unsupported in practice: nothing to swap in.
            return None

        # status == "error" or anything unexpected.
        log.warning("DeDRM could not process %s: %s", os.path.basename(input_path), result.get("message", "unknown error"))
        return None

    except subprocess.TimeoutExpired:
        log.error("DeDRM engine timed out after %ss on %s", _ENGINE_TIMEOUT, os.path.basename(input_path))
        return None
    except Exception as exc:  # noqa: BLE001 - never let DRM removal break ingest
        log.error("DeDRM engine failed to launch for %s: %s", os.path.basename(input_path), exc)
        return None
    finally:
        try:
            os.unlink(result_file)
        except OSError:
            pass


__all__ = [
    "DEDRM_DIR",
    "PREFS_PATH",
    "KEYFILES_DIR",
    "SUPPORTED_EXTENSIONS",
    "get_dedrm_dir",
    "get_prefs",
    "save_prefs",
    "is_configured",
    "is_supported",
    "remove_drm",
    "add_named_key",
    "delete_named_key",
    "add_list_value",
    "delete_list_value",
]
