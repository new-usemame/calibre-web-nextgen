# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests for fork issue #536 (@chloeroform) — bulk-action and
drag-merge AJAX calls must build their URLs with the application-root prefix
(``getPath()``) so they work behind a reverse proxy mounted on a sub-path.

The reporter hit 404s behind a proxy on:

  * ``/ajax/view``                   (cover/badge view-settings toggle)
  * ``/shelf/add_selected_to_shelf`` (bulk add-to-shelf)
  * ``/ajax/readselectedbooks``      (bulk mark read/unread)
  * ``/ajax/deleteselectedbooks``    (bulk delete)

all of which flow through ``postJson()`` in ``book_organizer.js``, which
called ``fetch(url, ...)`` on a bare root-absolute path. Auditing for the
same pattern (the reporter's "grepping reveals other problematic calls")
surfaced one sibling: ``drag-drop-merge.js`` POSTed to a bare
``/ajax/mergebooks``. Both 404 behind a sub-path proxy.

The fix routes every one of these through ``getPath()`` (the same helper
``filter_grid.js``/``get_meta.js``/``edit_books.js`` already use). These are
structural pin-checks on the two JS files; the behavioural proof that
``getPath()`` carries the proxy prefix is the codebase convention these match.
``getPath()`` returns ``""`` at root, so the fix is a no-op for non-proxy
deployments.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ORGANIZER_JS = REPO_ROOT / "cps" / "static" / "js" / "book_organizer.js"
MERGE_JS = REPO_ROOT / "cps" / "static" / "js" / "drag-drop-merge.js"


def _norm(text):
    """Collapse whitespace and normalise quotes for tolerant matching."""
    return re.sub(r"\s+", " ", text.replace('"', "'"))


@pytest.mark.unit
class TestBookOrganizerPostJsonProxySafe:
    """``postJson()`` is the single chokepoint for all four bulk endpoints;
    its ``fetch`` must prepend ``getPath()``."""

    def _js(self):
        return ORGANIZER_JS.read_text()

    def test_postjson_fetch_routes_through_getpath(self):
        js = _norm(self._js())
        assert "fetch(getPath() + url" in js, (
            "fork #536: postJson() must call fetch(getPath() + url, ...) so the "
            "four bulk endpoints carry the reverse-proxy sub-path prefix"
        )

    def test_postjson_does_not_fetch_bare_url(self):
        js = _norm(self._js())
        assert "fetch(url," not in js, (
            "fork #536: fetch(url, ...) on the bare root-absolute path 404s "
            "behind a sub-path proxy; it must be fetch(getPath() + url, ...)"
        )

    def test_no_bare_absolute_fetch_in_organizer(self):
        js = self._js()
        bare = re.findall(r"""fetch\(\s*['"]/""", js)
        assert not bare, (
            f"fork #536: bare absolute fetch('/...') bypasses the proxy prefix: {bare}"
        )


@pytest.mark.unit
class TestDragMergeProxySafe:
    """The drag-to-merge POST must also route through ``getPath()``."""

    def _js(self):
        return MERGE_JS.read_text()

    def test_mergebooks_routes_through_getpath(self):
        js = _norm(self._js())
        assert "fetch(getPath() + '/ajax/mergebooks'" in js, (
            "fork #536: the merge POST must be fetch(getPath() + '/ajax/mergebooks', "
            "...) so it works behind a sub-path proxy"
        )

    def test_no_bare_mergebooks_fetch(self):
        js = self._js()
        bare = re.findall(r"""fetch\(\s*['"]/ajax/mergebooks""", js)
        assert not bare, (
            f"fork #536: bare absolute fetch('/ajax/mergebooks') 404s behind a "
            f"sub-path proxy: {bare}"
        )
