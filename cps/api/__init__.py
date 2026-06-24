# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Versioned JSON API for the NextGen SPA frontend. See notes/FRONTEND-REBUILD-DESIGN.md."""
from flask import Blueprint, jsonify

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@api_v1.route("/health")
def health():
    return jsonify({"status": "ok", "api": "v1"})


# Route modules attach their views to api_v1 on import; import LAST so api_v1 exists.
# from . import auth   # enabled in Task 3
# from . import books  # enabled in Task 5
