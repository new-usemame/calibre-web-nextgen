# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure (context-free) JSON serializers for the /api/v1 surface."""


def serialize_user(user):
    return {
        "id": user.id,
        "name": user.name,
        "locale": user.locale,
        "theme": user.theme,
        "role": {
            "admin": user.role_admin(),
            "upload": user.role_upload(),
            "edit": user.role_edit(),
            "download": user.role_download(),
            "delete_books": user.role_delete_books(),
            "edit_shelfs": user.role_edit_shelfs(),
            "viewer": user.role_viewer(),
            "passwd": user.role_passwd(),
        },
    }


def serialize_book_list_item(book):
    series = book.series[0].name if getattr(book, "series", None) else None
    return {
        "id": book.id,
        "title": book.title,
        "authors": [a.name for a in book.authors] if getattr(book, "authors", None) else [],
        "series": series,
        "series_index": book.series_index,
        "cover_url": f"/cover/{book.id}/sm" if getattr(book, "has_cover", 0) else None,
        "formats": [d.format for d in book.data] if getattr(book, "data", None) else [],
    }


def serialize_book_detail(book, read=False, archived=False):
    """Full detail serializer — pure, no Flask/DB imports.

    Callers must enrich each language object with a ``.language_name`` attribute
    before calling (``l.language_name = isoLanguages.get_language_name(...)``).
    Falls back to ``l.lang_code`` via ``getattr`` so the function stays testable
    without that enrichment.
    """
    bid = book.id

    # Series (first entry only)
    series_list = getattr(book, "series", None) or []
    series_name = series_list[0].name if series_list else None

    # Cover
    cover_url = f"/cover/{bid}/og" if getattr(book, "has_cover", 0) else None

    # Pubdate — sentinel year <= 101 → null
    pubdate_raw = getattr(book, "pubdate", None)
    if pubdate_raw is not None and getattr(pubdate_raw, "year", 0) > 101:
        pubdate_str = pubdate_raw.date().isoformat()
    else:
        pubdate_str = None

    # Description
    comments = getattr(book, "comments", None) or []
    description_html = comments[0].text if comments else None

    # Tags
    tags = [t.name for t in (getattr(book, "tags", None) or [])]

    # Languages — display name enriched by caller, fallback to lang_code
    languages = [
        getattr(l, "language_name", None) or l.lang_code
        for l in (getattr(book, "languages", None) or [])
    ]

    # Publishers
    publishers = [p.name for p in (getattr(book, "publishers", None) or [])]

    # Identifiers
    identifiers = [
        {"type": i.type, "val": i.val}
        for i in (getattr(book, "identifiers", None) or [])
    ]

    # Formats
    formats = []
    for d in (getattr(book, "data", None) or []):
        fmt = d.format
        formats.append({
            "format": fmt,
            "size_bytes": d.uncompressed_size,
            "download_url": f"/download/{bid}/{fmt.lower()}/{d.name}",
            "read_url": f"/read/{bid}/{fmt.lower()}",
        })

    return {
        "id": bid,
        "title": book.title,
        "authors": [a.name for a in (getattr(book, "authors", None) or [])],
        "series": series_name,
        "series_index": book.series_index,
        "cover_url": cover_url,
        "pubdate": pubdate_str,
        "description_html": description_html,
        "tags": tags,
        "languages": languages,
        "publishers": publishers,
        "identifiers": identifiers,
        "formats": formats,
        "read": bool(read),
        "archived": bool(archived),
    }
