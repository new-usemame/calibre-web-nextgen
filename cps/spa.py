# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Serves the SPA shell at /app, gated by env CWNG_SPA. Replaced by the Vite build in Plan 02."""
import os
from flask import Blueprint, send_from_directory, abort

from . import logger

log = logger.create()

spa = Blueprint("spa", __name__)

_SPA_DIR = os.path.join(os.path.dirname(__file__), "static", "app")


def _spa_enabled():
    return os.environ.get("CWNG_SPA", "").strip().lower() in ("1", "true", "yes")


@spa.route("/app")
@spa.route("/app/<path:path>")
def spa_shell(path=""):
    if not _spa_enabled():
        abort(404)
    index_path = os.path.join(_SPA_DIR, "index.html")
    if not os.path.isfile(index_path):
        log.warning("SPA shell requested but build artifact not found: %s — run the Vite build "
                    "or set CWNG_SPA=0 to suppress this warning", index_path)
        abort(404)
    return send_from_directory(_SPA_DIR, "index.html")
