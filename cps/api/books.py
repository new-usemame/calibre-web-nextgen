# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalog endpoints for /api/v1."""
from flask import jsonify, request
from flask_babel import get_locale

from . import api_v1
from .serializers import serialize_book_list_item, serialize_book_detail
from .. import calibre_db, config, db, ub, isoLanguages
from ..helper import edit_book_read_status
from ..usermanagement import login_required_if_no_ano

# Stateless sort map — mirrors web.py sort options without calling get_sort_function
# (which writes per-user state and must not be called from a read-only API endpoint).
SORT_MAP = {
    "new": [db.Books.timestamp.desc()],
    "old": [db.Books.timestamp],
    "abc": [db.Books.sort],
    "zyx": [db.Books.sort.desc()],
    "pubnew": [db.Books.pubdate.desc()],
    "pubold": [db.Books.pubdate],
    "authaz": [db.Books.author_sort.asc(), db.Series.name, db.Books.series_index],
    "authza": [db.Books.author_sort.desc(), db.Series.name.desc(), db.Books.series_index.desc()],
}


@api_v1.route("/books")
@login_required_if_no_ano
def list_books():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", config.config_books_per_page, type=int)
    sort = request.args.get("sort", "new")
    order = SORT_MAP.get(sort, SORT_MAP["new"])
    search = request.args.get("search")

    if search:
        offset = (page - 1) * per_page
        join = (
            db.books_series_link,
            db.Books.id == db.books_series_link.c.book,
            db.Series,
        )
        entries, total, _pagination = calibre_db.get_search_results(
            search, config, offset, [order], per_page, *join
        )
        return jsonify({
            "items": [serialize_book_list_item(b) for b in entries],
            "page": page,
            "per_page": per_page,
            "total": total,
        })

    entries, _random, pagination = calibre_db.fill_indexpage(
        page, per_page, db.Books, True, order,
        False, config.config_read_column,
    )
    return jsonify({
        "items": [serialize_book_list_item(b) for b in entries],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total_count,
    })


@api_v1.route("/books/<int:book_id>")
@login_required_if_no_ano
def book_detail(book_id):
    result = calibre_db.get_book_read_archived(
        book_id, config.config_read_column,
        allow_show_archived=True, allow_show_hidden=True,
    )
    if not result:
        return jsonify({"error": {"code": "not_found", "message": "Book not found"}}), 404

    book, read_status, is_archived = result

    # Enrich language objects with display name so serialize_book_detail stays pure
    for lang in getattr(book, "languages", None) or []:
        lang.language_name = isoLanguages.get_language_name(get_locale(), lang.lang_code)

    return jsonify(serialize_book_detail(
        book,
        read=(read_status == ub.ReadBook.STATUS_FINISHED),
        archived=bool(is_archived),
    ))


@api_v1.route("/books/<int:book_id>/read", methods=["POST"])
@login_required_if_no_ano
def toggle_book_read(book_id):
    data = request.get_json(silent=True) or {}
    read = bool(data.get("read", True))
    edit_book_read_status(book_id, read)
    return jsonify({"read": read})
