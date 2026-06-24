# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests for CWA #1406 (@kurtlieber): "Send to eReader" fails with
``TypeError: sequence item 0: expected str instance, dict found``.

Root cause: the background mail task's error handler ran ``'\\n'.join(e.args)``
over every smtplib exception. ``smtplib.SMTPRecipientsRefused`` carries its
payload as a single *dict* arg (``{address: (code, reason)}``), so the join
crashed *inside the error handler* and the user saw the secondary TypeError
instead of the real recipient rejection.

The fix extracts a pure helper, ``compose_smtp_error_text``, that decodes or
stringifies every smtplib payload shape. We pin the helper's behaviour and
source-pin that the mail task delegates to it (so a refactor can't reintroduce
the raw join).
"""

from __future__ import annotations

import importlib.util
import re
import smtplib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_mail_error():
    """Load cps/services/mail_error.py directly (stdlib-only, no cps side effects)."""
    module_path = REPO_ROOT / "cps" / "services" / "mail_error.py"
    spec = importlib.util.spec_from_file_location("mail_error_under_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mail_error = _load_mail_error()
compose_smtp_error_text = mail_error.compose_smtp_error_text


def test_old_inline_join_crashed_on_recipients_dict():
    """Documents the exact #1406 trap: joining a SMTPRecipientsRefused's args
    raises the reported TypeError. Stays green to prove the helper is needed."""
    exc = smtplib.SMTPRecipientsRefused({"a@b.com": (550, b"User unknown")})
    with pytest.raises(TypeError):
        "\n".join(exc.args)  # the historical handler — would crash the error path


def test_recipients_refused_renders_readable_string():
    """The reported crash case now yields a human-readable rejection summary."""
    exc = smtplib.SMTPRecipientsRefused({"kid@home.net": (550, b"User unknown")})
    text = compose_smtp_error_text(exc)
    assert isinstance(text, str)
    assert "kid@home.net" in text
    assert "550" in text
    assert "User unknown" in text


def test_recipients_refused_multiple_addresses():
    exc = smtplib.SMTPRecipientsRefused(
        {
            "a@home.net": (550, b"User unknown"),
            "b@home.net": (552, b"Mailbox full"),
        }
    )
    text = compose_smtp_error_text(exc)
    assert "a@home.net: 550 User unknown" in text
    assert "b@home.net: 552 Mailbox full" in text


def test_recipients_refused_malformed_status_does_not_crash():
    """A non (code, reason) status value must degrade, not raise."""
    exc = smtplib.SMTPRecipientsRefused({"a@home.net": "weird"})
    text = compose_smtp_error_text(exc)
    assert "a@home.net" in text
    assert isinstance(text, str)


def test_smtp_response_exception_uses_smtp_error_bytes():
    exc = smtplib.SMTPDataError(554, b"Transaction failed\nspam detected")
    text = compose_smtp_error_text(exc)
    # bytes decoded, newlines flattened to ". " as the original handler did
    assert text == "Transaction failed. spam detected"


def test_message_attribute_takes_precedence_after_smtp_error():
    class WithMessage(smtplib.SMTPException):
        smtp_error = None
        message = "human readable message"

    assert compose_smtp_error_text(WithMessage()) == "human readable message"


def test_string_args_are_joined_like_before():
    exc = smtplib.SMTPException("first line", "second line")
    assert compose_smtp_error_text(exc) == "first line\nsecond line"


def test_bytes_in_args_are_decoded_not_crashed():
    exc = smtplib.SMTPException(b"byte payload")
    assert compose_smtp_error_text(exc) == "byte payload"


def test_no_payload_returns_empty_string():
    assert compose_smtp_error_text(smtplib.SMTPException()) == ""


def test_always_returns_str_never_raises():
    """Property: every smtplib exception shape produces a str, no exception."""
    cases = [
        smtplib.SMTPRecipientsRefused({"x@y.z": (550, b"no")}),
        smtplib.SMTPDataError(554, b"bad"),
        smtplib.SMTPException("plain"),
        smtplib.SMTPException(b"bytes"),
        smtplib.SMTPException(),
        smtplib.SMTPServerDisconnected("gone"),
    ]
    for exc in cases:
        assert isinstance(compose_smtp_error_text(exc), str)


# ---- source-pin: the mail task must delegate, never re-inline the raw join ----

MAIL_PY = (REPO_ROOT / "cps" / "tasks" / "mail.py").read_text(encoding="utf-8")


def test_mail_task_delegates_to_helper():
    assert "compose_smtp_error_text(e)" in MAIL_PY
    assert "from cps.services.mail_error import compose_smtp_error_text" in MAIL_PY


def test_mail_task_no_longer_does_raw_args_join():
    """If a future edit reintroduces the unsafe join, this fails (the #1406 guard)."""
    assert not re.search(r"['\"]\\n['\"]\s*\.join\(\s*e\.args\s*\)", MAIL_PY)
