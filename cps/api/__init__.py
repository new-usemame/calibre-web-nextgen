# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned JSON API for the NextGen SPA frontend. See notes/FRONTEND-REBUILD-DESIGN.md."""
import traceback

from flask import Blueprint, jsonify
from werkzeug.exceptions import HTTPException

from .. import logger

log = logger.create()

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@api_v1.errorhandler(HTTPException)
def handle_http_exception(exc):
    """Return JSON instead of HTML for all HTTPExceptions raised inside the API blueprint."""
    return jsonify({"error": {"code": exc.name.lower().replace(" ", "_"),
                              "message": exc.description}}), exc.code


@api_v1.errorhandler(Exception)
def handle_generic_exception(exc):
    """Return a JSON 500 and log the full traceback; never silently swallow."""
    log.error("Unhandled exception in api_v1: %s", traceback.format_exc())
    return jsonify({"error": {"code": "internal_server_error",
                              "message": "An unexpected error occurred"}}), 500


@api_v1.route("/health")
def health():
    return jsonify({"status": "ok", "api": "v1"})


# Route modules attach their views to api_v1 on import; import LAST so api_v1 exists.
from . import auth   # noqa: E402,F401
from . import books  # noqa: E402,F401
