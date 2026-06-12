# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Hygiene guard: no stray junk files at the repository root.

A 0-byte file literally named ``None`` was accidentally committed in #440
(almost certainly a shell redirect to an unset variable, e.g. ``> $OUT``
with OUT empty, or a Python ``open(str(path))`` where path was None). Such
names are classic symptoms of a path bug in a build/test script; they ship
in the Docker image and propagate into every branch merged from main.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# File names that only ever appear by accident: stringified non-values from
# Python/JS, or Windows device names that break checkouts there.
STRAY_NAMES = ["None", "null", "undefined", "NaN", "nil", "NUL", "nul", "CON", "PRN"]


@pytest.mark.unit
def test_no_stray_junk_files_at_repo_root():
    present = [n for n in STRAY_NAMES if (REPO_ROOT / n).is_file()]
    assert not present, (
        f"Stray junk file(s) {present} at repo root — a build/test step wrote "
        f"to a bad path (e.g. a shell redirect to an empty variable). Remove "
        f"the file(s) and fix the step that produced them."
    )
