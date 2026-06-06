#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Isolated subprocess that runs the vendored DeDRM engine on a single file.

This script is launched by :func:`cps.dedrm.remove_drm` as a separate process,
NOT imported into the Flask worker. Running in a child process is deliberate:

* The ~40 vendored DeDRM modules import each other by bare name (``import
  ineptepub``) and mutate global state (``sys.path``, ``sys.stdout``). Isolating
  them avoids polluting or colliding with the parent's module namespace.
* DeDRM parses untrusted ebook binaries; a crash or hang stays contained.
* All temporary state is discarded when the process exits.

It intentionally does NOT import the ``cps`` package (which would pull in the
whole Flask application). Paths are resolved relative to this file instead.

Invocation::

    python engine.py --input <path> --output-dir <dir> \
        --config-dir <dir> --result-file <path>

The result is written as JSON to ``--result-file`` so the parent never has to
parse DeDRM's verbose stdout::

    {"status": "decrypted", "output": "/abs/path"}   # produced a new file
    {"status": "none"}                                # no DRM / nothing to do
    {"status": "error", "message": "..."}             # failed; keep original
"""

import os
import sys
import json
import shutil
import argparse
import tempfile
import traceback


def _write_result(result_file, payload):
    """Persist the result JSON for the parent process to read."""
    try:
        with open(result_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
    except OSError:
        # If we cannot even write the result file there is nothing more to do;
        # the parent will treat a missing/invalid result as a failure and keep
        # the original file.
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description="Headless DeDRM engine")
    parser.add_argument("--input", required=True, help="Path to the ebook to process")
    parser.add_argument("--output-dir", required=True, help="Directory for the decrypted output")
    parser.add_argument("--config-dir", required=True, help="DeDRM config dir (holds plugins/dedrm.json)")
    parser.add_argument("--result-file", required=True, help="Where to write the JSON result")
    args = parser.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    vendor_dir = os.path.join(here, "_vendor")

    # DeDRM's initialize() does a plain os.mkdir(config_dir/plugins), so the
    # config dir itself must exist first.
    os.makedirs(args.config_dir, exist_ok=True)

    # Private scratch directory for DeDRM's intermediate temp files. Kept inside
    # the output dir so a single cleanup of that tree removes everything.
    work_dir = tempfile.mkdtemp(prefix="dedrm-work-", dir=args.output_dir)

    # Make the shim importable, then make the vendored modules importable by
    # bare name (their own compatibility code expects the package dir on path).
    if here not in sys.path:
        sys.path.insert(0, here)
    if vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

    try:
        import _calibre_shim
        _calibre_shim.install(args.config_dir, vendor_dir, work_dir)

        # Load the DeDRM plugin module straight from its file. Its internal
        # relative imports (``from . import x``) all fall back to bare ``import
        # x``, which resolves via ``vendor_dir`` on sys.path.
        import importlib.util

        init_path = os.path.join(vendor_dir, "__init__.py")
        spec = importlib.util.spec_from_file_location("__init__", init_path)
        dedrm_plugin = importlib.util.module_from_spec(spec)
        # Register the loaded module as the top-level ``__init__`` BEFORE running
        # it. The vendored ``prefs.py`` does ``from __init__ import PLUGIN_NAME``;
        # without this, a bare ``import __init__`` could resolve to the unrelated
        # ``standalone/__init__.py`` (its directory ends up on sys.path via the
        # modules' own compatibility code). Pinning sys.modules makes it
        # deterministic regardless of sys.path ordering.
        sys.modules["__init__"] = dedrm_plugin
        spec.loader.exec_module(dedrm_plugin)

        plugin = dedrm_plugin.DeDRM()
        # ``initialize`` stages optional helper scripts; failures there are not
        # fatal to decryption, so guard it.
        try:
            plugin.initialize()
        except Exception:
            traceback.print_exc()

        input_path = os.path.abspath(args.input)
        output = plugin.run(input_path)

        if not output or os.path.abspath(output) == input_path:
            # DeDRM returns the original path when the file is DRM-free or of an
            # unknown type. That means there was nothing to remove.
            _write_result(args.result_file, {"status": "none"})
            return 0

        # DeDRM produced a new (decrypted) file, possibly with a different
        # extension (e.g. KFX -> .epub, eReader .pdb -> .pmlz). Copy it into the
        # output directory under a stable, collision-free name.
        ext = os.path.splitext(output)[1] or os.path.splitext(input_path)[1]
        base = os.path.splitext(os.path.basename(input_path))[0]
        final_path = os.path.join(args.output_dir, base + ext)
        if os.path.abspath(final_path) != os.path.abspath(output):
            shutil.copy2(output, final_path)

        _write_result(args.result_file, {"status": "decrypted", "output": final_path})
        return 0

    except Exception as exc:  # noqa: BLE001 - report everything to the parent
        traceback.print_exc()
        _write_result(args.result_file, {"status": "error", "message": str(exc)})
        return 1
    finally:
        # Remove the scratch dir; the final output (if any) was already copied
        # to output_dir which is outside work_dir.
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
