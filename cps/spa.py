# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Serves the SPA shell at /app. Opt-OUT via env CWNG_SPA (default: enabled)."""
import os
from flask import Blueprint, send_from_directory, abort

from . import logger, constants

log = logger.create()

spa = Blueprint("spa", __name__)

_SPA_DIR = os.path.join(os.path.dirname(__file__), "static", "app")

_DISABLE_VALUES = ("0", "false", "no", "off")


def _spa_enabled():
    """SPA availability — OPT-OUT (enabled by default).

    Every updated instance should surface the new UI on its own so users can opt
    in, without the operator having to set anything (rollout goal: show the
    'Try the new UI' nudge to everyone, then eventually make it the default). Set
    CWNG_SPA to a falsey value (0/false/no/off) to turn the new UI off entirely."""
    return (os.environ.get("CWNG_SPA") or "").strip().lower() not in _DISABLE_VALUES


def _spa_bundle_present():
    """The compiled SPA must actually be on disk; a source checkout that never ran
    the Vite build has no bundle, so the nudge would lead to a 404."""
    return os.path.isfile(os.path.join(_SPA_DIR, "index.html"))


@spa.app_context_processor
def _inject_spa_flag():
    """Expose to ALL Jinja templates whether the new SPA is available (so the
    legacy layout shows the 'Switch to New UI' nudge only when /app will actually
    load) plus the running version (so the nudge banner can reset its dismissal
    on each update). app_context_processor = app-wide, not just this blueprint."""
    return {
        "cwng_spa_enabled": _spa_enabled() and _spa_bundle_present(),
        "cwng_app_version": constants.INSTALLED_VERSION,
    }


@spa.route("/app")
@spa.route("/app/")
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
