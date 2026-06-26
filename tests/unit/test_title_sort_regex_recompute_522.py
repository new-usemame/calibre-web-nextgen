# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests for fork issue #522 — changing the "Regular Expression
for Title Sorting" in /admin/viewconfig must re-sort the existing collection.

Root cause: Calibre's ``metadata.db`` stores a per-book ``sort`` column and
only recomputes it when a book's *title* changes (the ``books_update_trg``
trigger fires ``UPDATE books SET sort=title_sort(NEW.title) WHERE OLD.title
<> NEW.title``). UI/OPDS listings ``ORDER BY books.sort``. So after an admin
edits the title-sort regex, every existing row keeps its stale ``sort`` and
the order never changes until each book is individually edited.

Fix: ``CalibreDB.reapply_title_sort()`` runs ``UPDATE books SET sort =
title_sort(title)`` through the registered ``title_sort`` UDF (which reads the
updated regex at call time), and the viewconfig handler calls it when the
regex changes.

These tests build a minimal sqlite mirror of the real schema + trigger + UDF
so they exercise the actual SQL semantics rather than mocking them.
"""

import ast
import os
import re
import sqlite3

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- A faithful mini-Calibre sqlite, matching cps/db.py + metadata.db ---------

# Mutable config the UDF reads at call time, mirroring the production closure in
# cps/db.py::_register_sqlite_udfs (which reads CalibreDB.config.config_title_regex).
_CFG = {"regex": r"^(A|The|An)\s+"}


def _title_sort(title):
    if title is None:
        return ""
    regex = _CFG["regex"]
    try:
        if regex:
            match = re.compile(regex, re.IGNORECASE).search(title)
            if match:
                prep = match.group(0)
                title = title[len(prep):] + ", " + prep.strip()
    except Exception:
        pass
    return title.strip()


def _make_engine():
    engine = create_engine("sqlite://")  # single in-memory connection

    @event.listens_for(engine, "connect")
    def _register(dbapi_connection, _record):
        dbapi_connection.create_function("title_sort", 1, _title_sort)

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, sort TEXT)"))
        # The real metadata.db trigger: recompute sort ONLY when title changes.
        conn.execute(text(
            "CREATE TRIGGER books_update_trg AFTER UPDATE ON books BEGIN "
            "UPDATE books SET sort=title_sort(NEW.title) "
            "WHERE id=NEW.id AND OLD.title <> NEW.title; END"))
        conn.execute(text(
            "CREATE TRIGGER books_insert_trg AFTER INSERT ON books BEGIN "
            "UPDATE books SET sort=title_sort(NEW.title) WHERE id=NEW.id; END"))
    return engine


@pytest.fixture()
def session():
    _CFG["regex"] = r"^(A|The|An)\s+"
    engine = _make_engine()
    Session = sessionmaker(bind=engine)
    s = Session()
    # Insert via the insert trigger so sort is computed like production.
    for i, title in enumerate(["The Time Machine", "An Apple", "Zorro"], start=1):
        s.execute(text("INSERT INTO books (id, title) VALUES (:i, :t)"),
                  {"i": i, "t": title})
    s.commit()
    yield s
    s.close()


def _sort_of(session, book_id):
    return session.execute(
        text("SELECT sort FROM books WHERE id=:i"), {"i": book_id}).scalar()


def test_initial_sort_strips_articles(session):
    # Baseline: insert trigger applied the default regex.
    assert _sort_of(session, 1) == "Time Machine, The"
    assert _sort_of(session, 2) == "Apple, An"
    assert _sort_of(session, 3) == "Zorro"


def test_regex_change_alone_leaves_sort_stale(session):
    """This is the bug: changing the regex does NOT touch existing rows."""
    _CFG["regex"] = r"^(A|An)\s+"  # 'The' no longer stripped
    # Stored sort is unchanged — the trigger never fired (no title edit).
    assert _sort_of(session, 1) == "Time Machine, The"


def test_recompute_reapplies_new_regex_to_all_books(session):
    """The fix: UPDATE books SET sort = title_sort(title) re-derives all rows."""
    _CFG["regex"] = r"^(A|An)\s+"  # 'The' no longer stripped; 'An' still is
    rowcount = session.execute(
        text("UPDATE books SET sort = title_sort(title)")).rowcount
    session.commit()
    assert rowcount == 3
    assert _sort_of(session, 1) == "The Time Machine"   # 'The' kept now
    assert _sort_of(session, 2) == "Apple, An"          # 'An' still stripped
    assert _sort_of(session, 3) == "Zorro"


def test_recompute_does_not_mutate_titles(session):
    """Recompute must touch only sort, never title (else it would re-trigger
    and risk feedback loops / data drift)."""
    _CFG["regex"] = r"^(A|An)\s+"
    session.execute(text("UPDATE books SET sort = title_sort(title)"))
    session.commit()
    titles = session.execute(text("SELECT title FROM books ORDER BY id")).scalars().all()
    assert titles == ["The Time Machine", "An Apple", "Zorro"]


# --- Source-pins so a refactor can't silently drop the wiring -----------------

def test_calibredb_exposes_reapply_title_sort():
    from cps.db import CalibreDB
    assert hasattr(CalibreDB, "reapply_title_sort"), \
        "CalibreDB.reapply_title_sort() recompute method missing"


def test_reapply_uses_title_sort_udf_update():
    """Pin the exact SQL so the recompute keeps going through the UDF."""
    src = open(os.path.join(REPO_ROOT, "cps", "db.py")).read()
    func_src = src.split("def reapply_title_sort", 1)[1].split("\n    def ", 1)[0]
    assert "UPDATE books SET sort = title_sort(title)" in func_src


def test_viewconfig_handler_recomputes_on_regex_change():
    """Pin that update_view_configuration calls reapply_title_sort inside the
    config_title_regex change branch — the user-visible trigger for #522."""
    src = open(os.path.join(REPO_ROOT, "cps", "admin.py")).read()
    tree = ast.parse(src)
    func = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "update_view_configuration")
    # Find the `if _config_string(..., "config_title_regex")` branch.
    regex_if = None
    for node in ast.walk(func):
        if isinstance(node, ast.If):
            branch_src = ast.get_source_segment(src, node.test) or ""
            if "config_title_regex" in branch_src:
                regex_if = node
                break
    assert regex_if is not None, "regex-change branch not found in viewconfig"
    body_src = "\n".join(ast.get_source_segment(src, s) or "" for s in regex_if.body)
    assert "reapply_title_sort" in body_src, \
        "viewconfig must recompute title sort when the regex changes (#522)"
