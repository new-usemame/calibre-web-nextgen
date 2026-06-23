# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests for the "update available" banner message.

These guard two things at once:

1. The banner message must be built from a STATIC, translatable msgid with
   named placeholders — not an f-string interpolated *before* gettext sees it.
   The old code did ``_(f"... {current} ...")`` which makes the translation key
   the fully-interpolated runtime string, so pybabel extracts nothing usable and
   every non-English user gets the English fallback forever.

2. The banner copy must be free of the ``⚡🚨`` emoji spam (Jellyfin-derived
   human-facing tone policy) and must still show the user both versions.
"""

import inspect
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))

import cps.render_template as rt


def test_format_update_banner_message_builds_translatable_emoji_free_string(monkeypatch):
    """The gettext msgid is static; the rendered string carries both versions, no emoji."""
    captured = {}

    def fake_gettext(msgid):
        captured['msgid'] = msgid
        return msgid

    monkeypatch.setattr(rt, "_", fake_gettext)

    msg = rt._format_update_banner_message("v4.0.169", "v4.0.170")

    # 1) The translatable key must be the STATIC template, not the interpolated
    #    runtime string — named placeholders present, version numbers absent.
    assert "%(latest)s" in captured['msgid']
    assert "%(current)s" in captured['msgid']
    assert "4.0.170" not in captured['msgid']
    assert "4.0.169" not in captured['msgid']

    # 2) The user-visible message still shows both versions.
    assert "v4.0.170" in msg
    assert "v4.0.169" in msg

    # 3) No AI-tell emoji.
    for junk in ("⚡", "🚨"):
        assert junk not in msg


def test_update_notification_drops_fstring_gettext_antipattern():
    """Source-pin: the banner notification no longer ships the un-extractable
    ``_(f"...")`` pattern or the emoji spam, and routes through the helper."""
    src = inspect.getsource(rt.cwa_update_notification)

    assert '_(f"' not in src and "_(f'" not in src, "f-string inside gettext is not extractable"
    assert "⚡" not in src and "🚨" not in src, "emoji spam must be gone from the banner"
    assert "_format_update_banner_message" in src, "must build the message via the translatable helper"


def test_format_translation_missing_message_is_static_translatable(monkeypatch):
    """Same i18n contract as the update banner: the "translations needed" notice
    must build from a STATIC msgid (named placeholders), not interpolate the
    language/count into the gettext key (the old ``_(f"...")``), and be emoji-free."""
    captured = {}

    def fake_gettext(msgid):
        captured["msgid"] = msgid
        return msgid

    monkeypatch.setattr(rt, "_", fake_gettext)

    msg = rt._format_translation_missing_message("German", 42)

    assert "%(language)s" in captured["msgid"]
    assert "%(count)s" in captured["msgid"]
    assert "German" not in captured["msgid"]
    assert "42" not in captured["msgid"]
    assert "German" in msg and "42" in msg
    assert "🌐" not in msg


def test_translations_missing_notification_drops_fstring_antipattern():
    src = inspect.getsource(rt.translations_missing_notification)
    assert '_(f"' not in src and "_(f'" not in src, "f-string inside gettext is not extractable"
    assert "🌐" not in src, "drop the emoji for tone consistency"
    assert "_format_translation_missing_message" in src, "route through the translatable helper"
