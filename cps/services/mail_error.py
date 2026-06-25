# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Turn an :mod:`smtplib` exception into a human-readable message.

The background mail task surfaces this string to the user when a
"Send to eReader" send fails. ``smtplib`` exceptions carry their payload in
several shapes:

* a bytes ``smtp_error`` (``SMTPResponseException`` and friends),
* a ``message`` string,
* the structured ``recipients`` dict of :class:`smtplib.SMTPRecipientsRefused`
  (``{address: (code, reason_bytes)}``), or
* arbitrary ``args`` that may hold bytes or non-string objects.

The historical handler joined ``args`` blindly with ``'\\n'.join(e.args)``.
When the exception was ``SMTPRecipientsRefused`` — whose single arg is the
recipients *dict* — that raised
``TypeError: sequence item 0: expected str instance, dict found`` *inside the
error handler itself*, so the user saw the secondary crash instead of the real
SMTP rejection (CWA #1406, reported by @kurtlieber). This helper decodes or
stringifies every shape so the underlying error always survives.

Pure function, stdlib-only — unit-testable without the Flask app.
"""

import smtplib


def _decode(value):
    """Decode bytes to str (lossy, never raising); pass other values to ``str``."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def compose_smtp_error_text(exc):
    """Build a readable message from an smtplib exception.

    Preserves the original handler's precedence (``smtp_error`` → ``message``
    → ``args``) and inserts a dedicated branch for
    :class:`smtplib.SMTPRecipientsRefused`, which has neither ``smtp_error``
    nor ``message`` and so historically fell through to the unsafe ``args``
    join. Always returns a ``str``; never raises on byte/dict/object payloads.
    """
    smtp_error = getattr(exc, "smtp_error", None)
    if smtp_error:
        return _decode(smtp_error).replace("\n", ". ")

    message = getattr(exc, "message", None)
    if message:
        return _decode(message)

    if isinstance(exc, smtplib.SMTPRecipientsRefused) and exc.recipients:
        refused = []
        for recipient, status in exc.recipients.items():
            try:
                code, reason = status
            except (TypeError, ValueError):
                refused.append("{}: {}".format(recipient, _decode(status)))
                continue
            refused.append("{}: {} {}".format(recipient, code, _decode(reason)))
        return ", ".join(refused)

    args = getattr(exc, "args", None)
    if args:
        return "\n".join(_decode(arg) for arg in args)

    return ""
