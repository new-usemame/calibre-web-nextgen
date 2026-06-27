# SPA native deep admin security config — design + security note

Status: **implemented on the SPA branch, behind `CWNG_SPA`. NOT yet merged.**
Requires `/security-review` + operator merge before shipping (CLAUDE.md hard-rule
3c — writes auth/session/secret config and adds new routes). Must NOT be
admin-auto-merged.

## What this is

The last legacy link-out remaining in the SPA admin page was the deep
authentication/security config (login type, LDAP, OAuth/OIDC, server SSL,
reverse-proxy header login, remote magic-link login). The operator's directive is
native-everything, no hybrid link-outs. This rebuilds that surface natively:

- **API:** `cps/api/admin_security.py` — `GET/POST /api/v1/admin/security`.
- **UI:** `SecurityConfigForm` in `frontend/src/pages/Admin.tsx` (+ types/hooks in
  `frontend/src/lib/queries.ts`, styles in `Admin.module.css`).

## Single source of truth (the important part)

The security-critical validation is **NOT reimplemented**. The POST handler builds
the same form-shaped `to_save` dict the legacy `config_edit.html` posts and calls
the existing helpers directly:

- `cps.admin._configuration_ldap_helper(to_save)` — LDAP filter `%s`/parenthesis
  checks, service-account/password requirement by auth level, client-cert file
  existence, write-only bind password (`config_ldap_serv_password_e`, set only if
  non-empty).
- `cps.admin._configuration_oauth_helper(to_save)` — OIDC metadata auto-discovery,
  manual-endpoint fallback, `active` flag, write-only `oauth_client_secret`.
- `cps.admin._config_int/_config_string/_config_checkbox` (→
  `config.set_from_dictionary`, apply-if-present) for the scalar SSL / reverse-proxy
  / login-type / remote-login fields, mirroring the slice of
  `_configuration_update_helper` that handles them.

Because the same helpers run, the SPA enforces byte-for-byte identical rules and
returns the **same** validation messages the legacy form flashes (verified live:
posting a bad LDAP user filter returns `LDAP User Object Filter needs to Have One
"%s" Format Identifier`).

## Secrets are write-only

`GET` never returns a secret. `config_ldap_serv_password_e` and the OAuth
`oauth_client_secret` are reduced to `has_password` / `has_secret` booleans. A
secret is overwritten only when the client sends a non-empty replacement; the
OAuth secret is re-sent as the current DB value when blank so the helper sees
"unchanged" and preserves it. Regression-guarded by
`tests/unit/test_api_v1_admin_security.py::test_get_security_never_leaks_secrets`.

## Deliberate divergence from legacy: restart handling

The legacy form calls `web_server.stop(True)` itself to restart after a
login/LDAP/OAuth change. This endpoint does **not** tear down the worker from
within the request — it returns `reboot_required: true` and the SPA shows a
"restart the server for the login changes to take effect" banner, so the admin
restarts deliberately via the existing control. Rationale: a config endpoint
nuking its own server mid-response is a footgun, and an explicit restart is more
predictable. If `/security-review` prefers exact parity (auto-restart), wiring
`web_server.stop(True)` here is a one-line change.

Pre-existing legacy quirk preserved (not fixed here, to avoid changing legacy
behaviour): the LDAP helper calls `config.save()` *before* its validation block,
so an invalid LDAP payload persists the bad values while returning the error. The
native path inherits this exactly; fixing it should be a separate change against
both surfaces.

## Field coverage

LDAP (provider/port/encryption/auth/service-account+password/DN/user+member+group
filters/group name/openldap/auto-create/CA+cert+key paths), OAuth generic provider
(redirect host/client id+secret/metadata url/issuer/authorize/token/userinfo
urls/scopes/username+email mappers/admin group/login button/disable-standard-login/
group-admin-management), SSL (use_https/certfile/keyfile), reverse-proxy
(enabled/header name/auto-create + the cross-field validation), remote login.

## Verification done

- Backend live (curl, authenticated admin session): GET strips secrets; POST
  scalar save; reverse-proxy cross-field 400; LDAP validation reuse returns the
  exact legacy message; valid LDAP save returns `reboot_required`; login-type
  revert to standard.
- Frontend: `tsc -b` + `vite build` clean; Playwright — login-method dropdown
  reveals the LDAP and OAuth fieldsets, all field labels present, no console
  errors.
- Unit: 6 tests (gating 403/401, secret-strip invariant ×2, legacy-error parse ×2).

## Security-review checklist for the reviewer

- [ ] Confirm no secret reaches the client on GET (test asserts; eyeball the
      payload too).
- [ ] Confirm `_require_admin` gates both GET and POST (anon→401, non-admin→403).
- [ ] Confirm CSRF protection applies to the POST (same global setup as the other
      `/api/v1/admin/*` POSTs).
- [ ] Decide restart parity (banner vs auto-`stop(True)`).
- [ ] Confirm the reverse-proxy header-login toggle can't be set in a way that
      bypasses auth unexpectedly (cross-field validation mirrors legacy).
