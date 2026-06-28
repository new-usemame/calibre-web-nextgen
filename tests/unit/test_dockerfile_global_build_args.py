# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pin the version-defining build ARGs to GLOBAL scope (before the first FROM).

A Dockerfile `ARG FOO` re-declared inside a build stage only inherits a
default value when FOO is a *global* arg — one declared before the first
`FROM`. If the defaulted declaration sits inside an earlier stage, the
re-declaration in a later stage resolves to the empty string.

That is exactly what broke every :dev image build on 2026-06-28: commit
c1cd7b462 prepended a `FROM node:22-slim AS frontend-build` stage above the
ARG block, which had been global until then. CALIBRE_RELEASE / KEPUBIFY_RELEASE
/ PYTHON_VERSION / PYTHON_BUILD_STANDALONE_RELEASE became scoped to
frontend-build, so the `dependencies` stage re-declared them empty. The Python
install step then built the URL

    https://github.com/astral-sh/python-build-standalone/releases/download//cpython-+-x86_64-unknown-linux-gnu-install_only.tar.gz

(note the `download//cpython-+-` — empty release + empty version), which 404s.
Bumping the pin (#544), adding retries (#545) and authenticating the download
(#546) all chased the wrong layer because the URL itself was malformed.

These tests fail on the broken layout (defaults trapped after the first FROM)
and pass once the defaults are hoisted above every FROM. They also guard
against a future stage being prepended above the ARG block again.
"""

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "Dockerfile"

# ARGs whose value feeds a download URL in a later stage. Each MUST carry its
# default in global scope so every stage that re-declares it inherits a value.
VERSION_ARGS = (
    "CALIBRE_RELEASE",
    "KEPUBIFY_RELEASE",
    "PYTHON_BUILD_STANDALONE_RELEASE",
    "PYTHON_VERSION",
)


@pytest.fixture(scope="module")
def dockerfile_text() -> str:
    return DOCKERFILE.read_text()


@pytest.fixture(scope="module")
def first_from_offset(dockerfile_text: str) -> int:
    """Character offset of the first `FROM` instruction."""
    match = re.search(r"^FROM\b", dockerfile_text, re.MULTILINE)
    assert match, "Dockerfile must contain at least one FROM"
    return match.start()


@pytest.mark.parametrize("arg", VERSION_ARGS)
def test_version_arg_default_is_global(arg: str, dockerfile_text: str, first_from_offset: int) -> None:
    """The defaulted declaration (`ARG NAME=value`) must appear before the
    first FROM, i.e. in global scope, so later-stage re-declarations inherit it."""
    match = re.search(rf"^ARG {re.escape(arg)}=\S", dockerfile_text, re.MULTILINE)
    assert match, f"Dockerfile must declare a default for ARG {arg} (e.g. `ARG {arg}=...`)"
    assert match.start() < first_from_offset, (
        f"ARG {arg}=... carries its default AFTER the first FROM, so it is scoped "
        f"to that stage and the `dependencies` stage re-declares it empty — which "
        f"produces malformed download URLs (404). Move the defaulted declaration "
        f"above the first FROM (global scope)."
    )


def test_no_defaulted_version_arg_trapped_inside_a_stage(dockerfile_text: str, first_from_offset: int) -> None:
    """Defense in depth: NO defaulted version-arg declaration may live after the
    first FROM. A duplicate `ARG NAME=value` inside a stage re-introduces the
    two-places-to-bump trap that hid the original regression (#544 bumped the
    trapped copy and had no effect)."""
    post_from = dockerfile_text[first_from_offset:]
    for arg in VERSION_ARGS:
        assert not re.search(rf"^ARG {re.escape(arg)}=\S", post_from, re.MULTILINE), (
            f"A defaulted `ARG {arg}=...` appears after the first FROM. Keep the "
            f"single source of truth in the global block; stages should re-declare "
            f"with a bare `ARG {arg}` (no value) so they inherit the global default."
        )


def test_python_url_components_are_substituted(dockerfile_text: str) -> None:
    """The Python download line must reference both version vars, and the global
    defaults must be non-empty — together these guarantee the rendered URL is
    `download/<release>/cpython-<version>+<release>-...` and never the empty-var
    `download//cpython-+-...` that 404s."""
    assert re.search(
        r"releases/download/\$\{PYTHON_BUILD_STANDALONE_RELEASE\}/"
        r"cpython-\$\{PYTHON_VERSION\}\+\$\{PYTHON_BUILD_STANDALONE_RELEASE\}",
        dockerfile_text,
    ), "Python download URL must interpolate PYTHON_BUILD_STANDALONE_RELEASE and PYTHON_VERSION"
    for arg in ("PYTHON_BUILD_STANDALONE_RELEASE", "PYTHON_VERSION"):
        match = re.search(rf"^ARG {re.escape(arg)}=(\S+)", dockerfile_text, re.MULTILINE)
        assert match and match.group(1), f"Global default for {arg} must be non-empty"
