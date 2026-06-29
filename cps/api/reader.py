# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Reader progress (bookmark) endpoints for /api/v1.

Reads/writes the SAME ub.Bookmark row the legacy reader uses
(/ajax/bookmark/<id>/<format>), with the SAME lowercase format key — so reading
progress is shared between the legacy reader and the SPA reader: open a book in
one, resume in the other. The bookmark_key is the epub.js CFI string.
"""
from flask import jsonify, request
from sqlalchemy import and_

from . import api_v1
from .. import ub
from ..cw_login import current_user
from ..usermanagement import login_required_if_no_ano


def _err(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _require_real_user():
    if not current_user.is_authenticated or current_user.is_anonymous:
        return _err("unauthorized", "You must be signed in", 401)
    return None


def _bookmark_filter(book_id, fmt):
    return and_(
        ub.Bookmark.user_id == int(current_user.id),
        ub.Bookmark.book_id == book_id,
        ub.Bookmark.format == fmt,
    )


@api_v1.route("/books/<int:book_id>/bookmark")
@login_required_if_no_ano
def get_bookmark(book_id):
    """Return the saved reading position (epub.js CFI) for this user/book/format."""
    guard = _require_real_user()
    if guard:
        return guard
    fmt = (request.args.get("format") or "epub").lower()
    row = ub.session.query(ub.Bookmark).filter(_bookmark_filter(book_id, fmt)).first()
    return jsonify({"bookmark": row.bookmark_key if row else None})


@api_v1.route("/books/<int:book_id>/bookmark", methods=["POST"])
@login_required_if_no_ano
def save_bookmark(book_id):
    """Persist (or, with an empty bookmark, clear) the reading position. Mirrors
    the legacy set_bookmark write so the two readers share one row."""
    guard = _require_real_user()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    fmt = (data.get("format") or "epub").lower()
    bookmark_key = data.get("bookmark") or ""

    # Replace-on-write: one bookmark per (user, book, format), like the legacy route.
    ub.session.query(ub.Bookmark).filter(_bookmark_filter(book_id, fmt)).delete()
    if bookmark_key:
        ub.session.merge(ub.Bookmark(
            user_id=current_user.id,
            book_id=book_id,
            format=fmt,
            bookmark_key=bookmark_key,
        ))
    ub.session_commit("Bookmark for user {} in book {} via api".format(current_user.id, book_id))
    return "", 204
