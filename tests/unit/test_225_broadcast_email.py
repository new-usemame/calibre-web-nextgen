# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Acceptance tests for fork issue #225 (@froggybottomboys) phase 2: the
admin EMAIL BROADCAST — the reporter's actual ask (reach users
proactively), on top of the v4.0.118 login banner.

Design note: notes/feat-225-broadcast-email-DESIGN.md. Operator decisions
(2026-06-25): recipient picker (all + individuals), no opt-out, HTML body
with plain-text fallback (multipart/alternative), dedicated compose page
with prefill-from-banner.

These pin, RED on main / GREEN on the branch:

1. TaskEmail grows an optional `html=` kwarg → multipart/alternative with
   BOTH text/plain and text/html; no html kwarg → single text/plain
   (backward-compat for every existing caller).
2. html_to_text derives a readable plain-text fallback (tags stripped,
   entities unescaped, block breaks preserved).
3. build_broadcast_html wraps the body in an email-safe skeleton.
4. send_broadcast_email enqueues one TaskEmail per VALID recipient, skips
   empty/invalid/duplicate addresses, returns (queued, skipped), and each
   task carries the wrapped html + text fallback + subject + recipient.
5. Route source-pins: both routes admin-gated; POST hard-gates on
   get_mail_server_configured, resolves recipient emails SERVER-SIDE from
   posted user ids (never trusts posted email strings), and routes the
   test button to the current admin only.
6. Template pins for the compose page.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# 1. TaskEmail HTML alternative
# --------------------------------------------------------------------------- #

def _make_task(html=None):
    from cps.tasks.mail import TaskEmail
    settings = {"mail_from": "Library <lib@example.com>", "mail_server_type": 0}
    return TaskEmail(
        subject="Hello",
        filepath=None,
        attachment=None,
        settings=settings,
        recipient="reader@example.com",
        task_message="msg",
        text="Plain body",
        html=html,
    )


class TestTaskEmailHtmlAlternative:
    def test_html_kwarg_produces_multipart_alternative(self):
        task = _make_task(html="<p>Rich <b>body</b></p>")
        msg = task.prepare_message()
        assert msg.get_content_type() == "multipart/alternative"
        subtypes = {p.get_content_type() for p in msg.iter_parts()}
        assert "text/plain" in subtypes
        assert "text/html" in subtypes
        # Inspect each part's decoded payload (the text/plain part is base64 on
        # the wire — existing CWNG behaviour — so don't grep the flat string).
        html_part = msg.get_body(preferencelist=("html",))
        plain_part = msg.get_body(preferencelist=("plain",))
        assert "Rich" in html_part.get_payload(decode=True).decode("utf-8")
        assert "Plain body" in plain_part.get_payload(decode=True).decode("utf-8")

    def test_text_part_is_the_fallback_text(self):
        task = _make_task(html="<p>Rich</p>")
        msg = task.prepare_message()
        plain = msg.get_body(preferencelist=("plain",))
        assert plain is not None
        payload = plain.get_payload(decode=True).decode("utf-8")
        assert "Plain body" in payload

    def test_no_html_is_single_text_plain_backward_compat(self):
        task = _make_task(html=None)
        msg = task.prepare_message()
        assert msg.get_content_type() == "text/plain"
        assert not msg.is_multipart()

    def test_html_kwarg_defaults_to_none(self):
        """The new parameter must be OPTIONAL so every existing caller
        (send-to-eReader, registration, test mail) is untouched."""
        from cps.tasks.mail import TaskEmail
        sig = inspect.signature(TaskEmail.__init__)
        assert "html" in sig.parameters
        assert sig.parameters["html"].default is None


# --------------------------------------------------------------------------- #
# 2 & 3. html_to_text / build_broadcast_html
# --------------------------------------------------------------------------- #

class TestHtmlToText:
    def test_strips_tags_and_unescapes(self):
        from cps.helper import html_to_text
        out = html_to_text("<p>Hello &amp; welcome <b>friends</b></p>")
        assert "Hello & welcome friends" in out
        assert "<" not in out and ">" not in out

    def test_preserves_block_and_line_breaks(self):
        from cps.helper import html_to_text
        out = html_to_text("Line one<br>Line two</p><p>Para two")
        assert "Line one" in out and "Line two" in out and "Para two" in out
        assert "\n" in out

    def test_empty_is_empty(self):
        from cps.helper import html_to_text
        assert html_to_text("") == ""
        assert html_to_text(None) == ""

    def test_collapses_runaway_blank_lines(self):
        from cps.helper import html_to_text
        out = html_to_text("A</p></p></p></p>B")
        assert "\n\n\n" not in out


class TestBuildBroadcastHtml:
    def test_wraps_and_preserves_body(self):
        from cps.helper import build_broadcast_html
        out = build_broadcast_html("<p>Keep me</p>")
        assert out.lower().startswith("<!doctype html>")
        assert "<body" in out and "Keep me" in out

    def test_empty_body_still_valid_skeleton(self):
        from cps.helper import build_broadcast_html
        out = build_broadcast_html("")
        assert out.lower().startswith("<!doctype html>") and "</html>" in out


# --------------------------------------------------------------------------- #
# 4. send_broadcast_email enqueue behaviour
# --------------------------------------------------------------------------- #

class TestSendBroadcastEmail:
    @pytest.fixture
    def captured(self, monkeypatch):
        import cps.helper as helper
        tasks = []
        monkeypatch.setattr(helper.config, "get_mail_settings",
                            lambda: {"mail_from": "Library <lib@example.com>", "mail_server_type": 0},
                            raising=False)
        monkeypatch.setattr(helper.WorkerThread, "add",
                            classmethod(lambda cls, user, task, hidden=False: tasks.append((user, task))))
        return tasks

    def test_one_task_per_valid_recipient(self, captured):
        from cps.helper import send_broadcast_email
        queued, skipped = send_broadcast_email(
            "Subject", "<p>Body</p>",
            ["a@b.com", "c@d.com"], "admin")
        assert queued == 2 and skipped == 0
        assert len(captured) == 2
        recips = {t.recipient for _, t in captured}
        assert recips == {"a@b.com", "c@d.com"}

    def test_skips_empty_invalid_and_duplicate(self, captured):
        from cps.helper import send_broadcast_email
        queued, skipped = send_broadcast_email(
            "Subject", "<p>Body</p>",
            ["a@b.com", "", "not-an-email", "a@b.com", "c@d.com"], "admin")
        assert queued == 2
        assert skipped == 3
        recips = {t.recipient for _, t in captured}
        assert recips == {"a@b.com", "c@d.com"}

    def test_each_task_carries_html_text_subject(self, captured):
        from cps.helper import send_broadcast_email
        send_broadcast_email("My Subject", "<p>Hello &amp; hi</p>", ["a@b.com"], "admin")
        _, task = captured[0]
        assert task.subject == "My Subject"
        assert task.html and task.html.lower().startswith("<!doctype html>")
        assert "Hello" in task.html
        # text fallback present and tag-free
        assert "Hello & hi" in task.text
        assert "<p>" not in task.text

    def test_returns_zero_when_no_valid_recipients(self, captured):
        from cps.helper import send_broadcast_email
        queued, skipped = send_broadcast_email("S", "<p>B</p>", ["", "bad"], "admin")
        assert queued == 0 and skipped == 2
        assert captured == []


# --------------------------------------------------------------------------- #
# 5. Route source-pins (admin gate, mail gate, server-side recipient resolve)
# --------------------------------------------------------------------------- #

class TestBroadcastRoutes:
    def test_routes_exist_and_are_admin_gated(self):
        from cps import admin
        get_src = inspect.getsource(admin.broadcast_email)
        post_src = inspect.getsource(admin.send_broadcast)
        # decorators sit just above each function in the module source
        mod_src = inspect.getsource(admin)
        assert '@admi.route("/admin/broadcast", methods=["GET"])' in mod_src
        assert '@admi.route("/admin/broadcast", methods=["POST"])' in mod_src
        # both functions are wrapped by admin_required
        for fn_name in ("broadcast_email", "send_broadcast"):
            idx = mod_src.index("def {}(".format(fn_name))
            preamble = mod_src[max(0, idx - 200):idx]
            assert "@admin_required" in preamble, fn_name
        assert get_src and post_src  # silence unused

    def test_post_hard_gates_on_mail_configured(self):
        from cps import admin
        src = inspect.getsource(admin.send_broadcast)
        assert "get_mail_server_configured()" in src

    def test_recipients_resolved_server_side_not_from_posted_emails(self):
        """Defense in depth: the handler must map posted user IDS to emails
        from the DB, never accept an email address straight off the form."""
        from cps import admin
        src = inspect.getsource(admin.send_broadcast)
        assert 'getlist("recipients")' in src
        assert "_broadcast_recipient_users()" in src
        # must NOT pull a raw email field off the request for the send list
        assert 'request.form.get("email"' not in src
        assert 'request.form.getlist("emails")' not in src

    def test_test_button_targets_current_admin_only(self):
        from cps import admin
        src = inspect.getsource(admin.send_broadcast)
        assert "current_user.email" in src
        # the test branch builds its recipient list from the admin's own email
        assert 'request.form.get("test")' in src

    def test_helper_excludes_anonymous_and_empty_email(self):
        from cps import admin
        src = inspect.getsource(admin._broadcast_recipient_users)
        assert "role_anonymous()" in src
        assert "ub.User.email" in src


# --------------------------------------------------------------------------- #
# 6. Template pins
# --------------------------------------------------------------------------- #

class TestBroadcastTemplate:
    @pytest.fixture(scope="class")
    def tpl(self):
        path = REPO_ROOT / "cps" / "templates" / "broadcast_email.html"
        return path.read_text(encoding="utf-8")

    def test_has_subject_and_body_fields(self, tpl):
        assert 'name="subject"' in tpl
        assert 'name="body"' in tpl

    def test_has_recipient_picker(self, tpl):
        assert 'name="select_all"' in tpl
        assert 'name="recipients"' in tpl
        assert "for u in recipients" in tpl

    def test_has_prefill_test_and_confirm(self, tpl):
        assert "prefill_announcement" in tpl
        assert 'name="test"' in tpl
        assert "confirm(" in tpl  # confirm-before-send

    def test_warns_when_mail_unconfigured(self, tpl):
        assert "not mail_configured" in tpl
        assert "edit_mailsettings" in tpl
