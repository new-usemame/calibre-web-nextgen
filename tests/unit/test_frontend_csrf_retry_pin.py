# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Source-pin: the SPA's apiPost CSRF retry must not replay validation 400s.

There is no JS test runner in this repo, so we guard the invariant the same way
we guard Python ones — by inspecting the source. The bug this prevents: apiPost
used to refresh the CSRF token and re-POST on ANY 400, silently double-submitting
every legitimately-rejected request (doubled bcrypt on failed password changes,
doubled audit entries). A stale CSRF token surfaces as a *non-JSON* (HTML) 400;
our own validation errors are JSON — so the retry must discriminate on
content-type, never on a bare status === 400.
"""
from pathlib import Path
import re
import pytest

API_TS = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "api.ts").read_text()


@pytest.mark.unit
def test_apipost_csrf_retry_checks_content_type():
    # The retry guard must reference content-type so JSON 400s aren't replayed.
    assert "content-type" in API_TS.lower(), (
        "apiPost CSRF retry must discriminate CSRF (HTML) 400s from validation "
        "(JSON) 400s via content-type"
    )


@pytest.mark.unit
def test_apipost_has_no_bare_400_retry():
    """A bare `if (res.status === 400) { ... doPost }` retry (no content-type
    guard in the same block) is the regression — fail if it reappears."""
    # Find the retry block and assert it is gated, not bare.
    assert "isJson400" in API_TS, "expected the content-type-gated retry sentinel isJson400"
    # The clearCsrf()-then-replay must be guarded by `!isJson400`, never a bare 400.
    m = re.search(r"if\s*\(res\.status === 400 && !isJson400\)", API_TS)
    assert m, "CSRF retry must be gated on `res.status === 400 && !isJson400`"
