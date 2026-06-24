# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for per-provider default permissions for new Generic OAuth users
(PR #495, @lduesing).

The feature lets an admin pick the exact permission bitmask new Generic OAuth
users receive, instead of inheriting the single global default role. These
tests pin both the feature and the **no-regression contract** that was the one
real risk in the original PR:

The original code assigned ``user.role = int(generic.get('oauth_default_role')
or 0)`` while the new column defaulted to 0/NULL. On an existing deployment
that had never configured a per-provider role, every *new* OAuth sign-up would
then land with role 0 (no downloads, no viewer, nothing) — a silent downgrade.

The fix: the column is nullable and ``_oauth_effective_default_role`` falls
back to the global ``config_default_role`` when the per-provider role is unset
(None). An explicitly configured value — including 0 — is honored. So:

* never configured (NULL)  → global default  (no regression)
* configured to a bitmask  → that bitmask
* configured to 0          → 0 (the admin's explicit "no extra permissions")
"""

import inspect
import os
import tempfile

import pytest
from sqlalchemy import create_engine, inspect as sa_inspect, text

from cps import oauth_bb, ub, admin
from cps import constants

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# _selected_generic_oauth_default_role — checkbox form -> role bitmask
# ---------------------------------------------------------------------------
class TestSelectedDefaultRole:
    def test_each_checkbox_maps_to_its_bit(self):
        cases = {
            "config_generic_oauth_default_download_role": constants.ROLE_DOWNLOAD,
            "config_generic_oauth_default_viewer_role": constants.ROLE_VIEWER,
            "config_generic_oauth_default_upload_role": constants.ROLE_UPLOAD,
            "config_generic_oauth_default_edit_role": constants.ROLE_EDIT,
            "config_generic_oauth_default_delete_role": constants.ROLE_DELETE_BOOKS,
            "config_generic_oauth_default_passwd_role": constants.ROLE_PASSWD,
            "config_generic_oauth_default_edit_shelf_role": constants.ROLE_EDIT_SHELFS,
        }
        for field, bit in cases.items():
            assert admin._selected_generic_oauth_default_role({field: "on"}) == bit

    def test_multiple_checkboxes_combine(self):
        to_save = {
            "config_generic_oauth_default_download_role": "on",
            "config_generic_oauth_default_viewer_role": "on",
        }
        assert admin._selected_generic_oauth_default_role(to_save) == (
            constants.ROLE_DOWNLOAD | constants.ROLE_VIEWER)

    def test_no_checkboxes_is_zero(self):
        assert admin._selected_generic_oauth_default_role({}) == 0

    def test_ignores_unrelated_and_global_role_keys(self):
        # Must NOT pick up the *global* default-role checkboxes (download_role,
        # etc.) that live on the same settings page — only its own prefixed
        # fields. A collision there would couple the two unrelated controls.
        to_save = {"download_role": "on", "admin_role": "on", "something": "x"}
        assert admin._selected_generic_oauth_default_role(to_save) == 0

    def test_never_grants_admin(self):
        # No prefixed field maps to ROLE_ADMIN — OAuth default permissions can
        # never silently make every new user an admin.
        to_save = {f: "on" for f in [
            "config_generic_oauth_default_download_role",
            "config_generic_oauth_default_viewer_role",
            "config_generic_oauth_default_upload_role",
            "config_generic_oauth_default_edit_role",
            "config_generic_oauth_default_delete_role",
            "config_generic_oauth_default_passwd_role",
            "config_generic_oauth_default_edit_shelf_role",
        ]}
        role = admin._selected_generic_oauth_default_role(to_save)
        assert not constants.has_flag(role, constants.ROLE_ADMIN)


# ---------------------------------------------------------------------------
# _oauth_role_enabled — bitmask membership with a None/garbage guard
# ---------------------------------------------------------------------------
class TestRoleEnabled:
    def test_flag_set(self):
        role = constants.ROLE_DOWNLOAD | constants.ROLE_VIEWER
        assert oauth_bb._oauth_role_enabled(role, constants.ROLE_DOWNLOAD) is True
        assert oauth_bb._oauth_role_enabled(role, constants.ROLE_VIEWER) is True

    def test_flag_unset(self):
        assert oauth_bb._oauth_role_enabled(constants.ROLE_DOWNLOAD, constants.ROLE_UPLOAD) is False

    def test_none_and_garbage_are_false(self):
        assert oauth_bb._oauth_role_enabled(None, constants.ROLE_DOWNLOAD) is False
        assert oauth_bb._oauth_role_enabled("oops", constants.ROLE_DOWNLOAD) is False
        assert oauth_bb._oauth_role_enabled(0, constants.ROLE_DOWNLOAD) is False


# ---------------------------------------------------------------------------
# _oauth_effective_default_role — THE no-regression contract
# ---------------------------------------------------------------------------
class TestEffectiveDefaultRole:
    def test_unconfigured_falls_back_to_global(self):
        global_default = constants.ROLE_DOWNLOAD | constants.ROLE_VIEWER
        # NULL provider role MUST inherit the global default — this is the line
        # that prevents the silent permission-strip the original PR introduced.
        assert oauth_bb._oauth_effective_default_role(None, global_default) == global_default

    def test_configured_value_is_honored(self):
        provider = constants.ROLE_DOWNLOAD
        assert oauth_bb._oauth_effective_default_role(provider, constants.ROLE_VIEWER) == provider

    def test_explicit_zero_is_honored_not_treated_as_unset(self):
        # An admin who unchecks everything explicitly wants role 0; that must be
        # respected, not overridden by the global default.
        assert oauth_bb._oauth_effective_default_role(0, constants.ROLE_DOWNLOAD) == 0

    def test_garbage_falls_back_to_global(self):
        assert oauth_bb._oauth_effective_default_role("x", constants.ROLE_VIEWER) == constants.ROLE_VIEWER


# ---------------------------------------------------------------------------
# Source-pin: the regression pattern is gone
# ---------------------------------------------------------------------------
class TestNoRegressionSourcePin:
    def test_register_user_uses_effective_role_helper(self):
        src = inspect.getsource(oauth_bb.register_user_from_generic_oauth)
        assert "_oauth_effective_default_role(" in src, (
            "new-user role assignment must route through the fallback helper")

    def test_register_user_drops_the_bare_or_zero_pattern(self):
        """The original ``int(generic.get('oauth_default_role') or 0)`` collapses
        an unconfigured (None) provider role to 0 — the silent downgrade. It must
        not be the role assignment any more."""
        src = inspect.getsource(oauth_bb.register_user_from_generic_oauth)
        assert "int(generic.get('oauth_default_role') or 0)" not in src


# ---------------------------------------------------------------------------
# Migration: oauth_default_role column, idempotent, NULL default
# ---------------------------------------------------------------------------
PRIOR_MANAGED = [
    "oauth_base_url", "oauth_authorize_url", "oauth_token_url", "oauth_userinfo_url",
    "oauth_admin_group", "oauth_group_claim", "oauth_allowed_groups", "oauth_require_group",
    "metadata_url", "scope", "username_mapper", "email_mapper", "login_button",
]


def _make_db_without_default_role():
    fd, path = tempfile.mkstemp(suffix="-app.db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    col_defs = [
        "id INTEGER PRIMARY KEY", "provider_name VARCHAR", "oauth_client_id VARCHAR",
        "oauth_client_secret VARCHAR", "active BOOLEAN",
    ] + [f"'{c}' VARCHAR DEFAULT NULL" for c in PRIOR_MANAGED]
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE oauthProvider ({', '.join(col_defs)})"))
    return engine, path


def _columns(engine):
    return {c["name"] for c in sa_inspect(engine).get_columns("oauthProvider")}


class TestDefaultRoleMigration:
    def test_column_added_and_idempotent(self):
        engine, path = _make_db_without_default_role()
        try:
            assert "oauth_default_role" not in _columns(engine)
            ub.migrate_oauth_provider_table(engine, None)
            assert "oauth_default_role" in _columns(engine)
            ub.migrate_oauth_provider_table(engine, None)  # idempotent
            assert "oauth_default_role" in _columns(engine)
        finally:
            engine.dispose()
            os.unlink(path)

    def test_default_is_null_so_existing_rows_fall_back(self):
        engine, path = _make_db_without_default_role()
        try:
            ub.migrate_oauth_provider_table(engine, None)
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO oauthProvider (provider_name) VALUES ('generic')"))
                value = conn.execute(text(
                    "SELECT oauth_default_role FROM oauthProvider")).fetchone()[0]
            # NULL is the sentinel that routes to the global default at runtime.
            assert value is None
        finally:
            engine.dispose()
            os.unlink(path)
