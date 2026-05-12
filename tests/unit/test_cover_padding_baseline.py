# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.
"""Baseline snapshot of cover_padding output before the cover_preview rename.

This test runs against the CURRENT module name (`cover_padding`). After the
rename it will be deleted — its job is to prove the rename was behavior-
preserving by passing both before and (with the import patched) after the
move.
"""
import hashlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def sample_cover_bytes():
    p = Path(__file__).parent / "fixtures" / "sample_cover_4x3.jpg"
    if not p.is_file():
        pytest.skip("sample cover fixture missing")
    return p.read_bytes()


@pytest.mark.skipif(
    os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true",
    reason="local rename-equivalence pin; runs locally only",
)
def test_pad_blob_kobo_libra_color_edge_mirror_is_stable(sample_cover_bytes):
    from cps.services import cover_padding

    if not cover_padding.use_IM:
        pytest.skip("Wand/ImageMagick not available")

    settings = cover_padding.PaddingSettings(
        enabled=True,
        target_aspect="kobo_libra_color",
        fill_mode="edge_mirror",
        manual_color="",
    )
    out = cover_padding.pad_blob(sample_cover_bytes, settings)
    digest = hashlib.sha256(out).hexdigest()
    assert len(out) > 1024, "padded blob should be non-trivial JPEG"
    assert out[:2] == b"\xff\xd8", "must be JPEG SOI"
    # Captured on local-dev container (Wand 0.6.x, ImageMagick 6.9.x).
    # Compared against the same environment after the rename — see
    # Phase 1 / Task 10 of notes/COVER-NORMALIZATION-PHASE-1-PLAN.md.
    assert digest == "8cf966e78a22069043736c610af24a574d3e82724c79da44e6cae8a7b8c26cf8", (
        f"actual sha256={digest}"
    )
