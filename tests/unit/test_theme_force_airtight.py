# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Theme enforcement must be airtight: the deprecated default theme must never
reach a user.

The light/default theme is deprecated; caliBlur (dark) is the only supported
theme. ``cps.admin.before_request`` (an ``@admi.before_app_request`` handler,
so it runs for every request) forces ``g.current_theme = 1`` and templates gate
their caliBlur ``<link>`` tags on ``{% if g.current_theme == 1 %}``.

The escape this guards against: ``g.current_theme`` is set partway through a
handler that does *unguarded* work first (``config.*`` reads, a DB
autoconfig/recovery block) — and two other ``@app.before_request`` handlers in
``cps/__init__.py`` run *before* this one. If any of them raises, the theme is
never set, ``g.current_theme`` is undefined, and ``{% if g.current_theme == 1 %}``
evaluates False — so the page (typically the standalone ``http_error.html``)
renders the deprecated default theme. That is the root cause behind the class of
"default-theme-only" display bugs, e.g. #320's oversized shelf-reorder covers,
which a caliBlur-only repro could not see.

Two invariants make it airtight:
  1. The force is the FIRST thing ``before_request`` does (before any unguarded
     work), and is a single unconditional assignment — so a later exception in
     the handler body still leaves caliBlur forced on whatever page renders.
  2. ``http_error.html`` (standalone — it does not extend ``layout.html``, and
     renders on exactly the failures where the before_request chain may not have
     completed) defaults an undefined ``g.current_theme`` to caliBlur.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
ADMIN_SRC = (REPO_ROOT / "cps" / "admin.py").read_text()
HTTP_ERROR_HTML = (REPO_ROOT / "cps" / "templates" / "http_error.html").read_text()


def _before_request_src() -> str:
    """Slice the body of admin.before_request() out of the file text (no import,
    matching the file-based source-pin style of the other UI regression tests)."""
    lines = ADMIN_SRC.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith("def before_request():")),
        None,
    )
    assert start is not None, "def before_request(): not found in cps/admin.py"
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^(@|def |class )", lines[j]):
            end = j
            break
    return "\n".join(lines[start:end])


class TestThemeForcedFirstAndUnconditional:
    def test_force_precedes_any_unguarded_config_access(self):
        src = _before_request_src()
        force_idx = src.find("g.current_theme = 1")
        assert force_idx != -1, "before_request must force g.current_theme = 1"
        cfg_idx = src.find("config.config_")
        assert cfg_idx != -1, "expected a config.config_* access in before_request"
        assert force_idx < cfg_idx, (
            "g.current_theme = 1 must be forced BEFORE the unguarded config.* "
            "accesses (and the DB autoconfig block) — otherwise an exception "
            "there skips the theme and the rendered (error) page falls back to "
            "the deprecated default theme. This is the #320 default-theme escape."
        )

    def test_single_unconditional_theme_assignment(self):
        src = _before_request_src()
        # `=(?!=)` counts assignments only, not `==` comparisons (the comment
        # documenting the template check contains a literal g.current_theme == 1).
        n = len(re.findall(r"g\.current_theme\s*=(?!=)", src))
        assert n == 1, (
            f"expected exactly one g.current_theme assignment in before_request "
            f"(single source of truth), found {n}. The old per-user/config "
            f"compute that the force immediately discarded is dead code."
        )

    def test_force_is_body_level_not_nested(self):
        src = _before_request_src()
        for line in src.splitlines():
            if re.match(r"\s*g\.current_theme\s*=\s*1\b", line):
                indent = len(line) - len(line.lstrip())
                assert indent == 4, (
                    f"the theme force must be unconditional at function-body "
                    f"indent (4), not nested under a try/if that could skip it; "
                    f"got indent={indent}"
                )
                return
        pytest.fail("no 'g.current_theme = 1' assignment found in before_request")


class TestErrorPageThemeResilient:
    def test_http_error_defaults_undefined_theme_to_caliblur(self):
        assert (
            "g.get('current_theme', 1)" in HTTP_ERROR_HTML
            or 'g.get("current_theme", 1)' in HTTP_ERROR_HTML
        ), (
            "http_error.html must use g.get('current_theme', 1) so the standalone "
            "error page renders caliBlur even when before_request never set the "
            "theme — it renders on exactly those failures."
        )

    def test_http_error_has_no_bare_nonresilient_check(self):
        assert "g.current_theme == 1" not in HTTP_ERROR_HTML, (
            "http_error.html still has a bare g.current_theme == 1 check, which "
            "falls back to the deprecated default theme when the theme is unset."
        )
