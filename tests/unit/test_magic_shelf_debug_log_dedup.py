# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2026 Calibre-Web contributors
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Regression tests: the _cwa_ensure_db_session before_request hook
logged two DEBUG lines on EVERY authenticated request, flooding docker
logs whenever the log level is DEBUG and a UI tab is polling. Fixed by
routing one merged message through _log_magic_shelf_counts, deduped per
user per count change (same pattern as _AUTHOR_SORT_DRIFT_WARNED, fork
#108). cps.log is patched directly; caplog is flaky with cps's handlers.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

CPS_INIT = Path(__file__).resolve().parents[2] / "cps" / "__init__.py"


@pytest.mark.unit
class TestMagicShelfDebugLogDedup:
    def test_unconditional_per_request_debug_lines_removed(self):
        src = CPS_INIT.read_text()
        assert "magic shelves for user {current_user.id} before filtering" not in src
        assert "Filtered to {len(filtered_shelves)} visible magic shelves" not in src

    def test_steady_state_polling_logs_once(self):
        import cps
        cps._MAGIC_SHELF_COUNTS_LOGGED.clear()
        with patch.object(cps, "log", MagicMock(spec=logging.Logger)) as fake_log:
            for _ in range(50):  # user 3, 5 shelves visible, polled every ~3s
                cps._log_magic_shelf_counts(3, 5, 5)
        assert fake_log.debug.call_count == 1
        assert cps._MAGIC_SHELF_COUNTS_LOGGED == {3: (5, 5)}

    def test_count_change_logs_exactly_once_more(self):
        import cps
        cps._MAGIC_SHELF_COUNTS_LOGGED.clear()
        with patch.object(cps, "log", MagicMock(spec=logging.Logger)) as fake_log:
            for _ in range(10):
                cps._log_magic_shelf_counts(3, 5, 5)
            for _ in range(10):
                cps._log_magic_shelf_counts(3, 5, 4)  # one shelf hidden
        assert fake_log.debug.call_count == 2
        assert cps._MAGIC_SHELF_COUNTS_LOGGED == {3: (5, 4)}

    def test_per_user_isolation(self):
        import cps
        cps._MAGIC_SHELF_COUNTS_LOGGED.clear()
        with patch.object(cps, "log", MagicMock(spec=logging.Logger)) as fake_log:
            for uid in (3, 7, 3, 7):
                cps._log_magic_shelf_counts(uid, 5, 5)
        assert fake_log.debug.call_count == 2
        assert cps._MAGIC_SHELF_COUNTS_LOGGED == {3: (5, 5), 7: (5, 5)}
