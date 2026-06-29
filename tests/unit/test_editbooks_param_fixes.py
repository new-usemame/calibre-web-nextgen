# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression pins for two edit_book_param bugs surfaced by the SPA edit form
(they also affect the legacy inline books-table editor):

1. Clearing a book's description 500'd — the comments branch did
   ``book.comments[0].text`` unconditionally, which IndexErrors when the comment
   was just cleared (book.comments empty).
2. An invalid language input ERASED the book's existing languages —
   edit_book_languages mutates book.languages before flagging invalid entries,
   and edit_book_param committed that mutation even on the error path.
"""
import inspect
from pathlib import Path
import pytest

import cps.editbooks as editbooks

SRC = inspect.getsource(editbooks.edit_book_param)


@pytest.mark.unit
def test_comments_branch_guards_empty_list():
    # The [0] access must be guarded so clearing the description doesn't IndexError.
    assert 'book.comments[0].text if book.comments else ""' in SRC, (
        "comments branch must guard book.comments[0] for the empty/cleared case"
    )
    # And the raw unguarded access must be gone.
    assert "'newValue':  book.comments[0].text" not in SRC


@pytest.mark.unit
def test_invalid_languages_rolls_back_and_returns():
    # Invalid languages must roll back the (already-applied) mutation and return
    # without reaching the unconditional commit — otherwise the cleared language
    # set is persisted (data loss).
    lang_block = SRC.split("elif param == 'languages':", 1)[1].split("elif param ==", 1)[0]
    assert "calibre_db.session.rollback()" in lang_block, (
        "invalid-language path must roll back the mutation"
    )
    assert "return Response(" in lang_block, (
        "invalid-language path must early-return before the shared commit"
    )
