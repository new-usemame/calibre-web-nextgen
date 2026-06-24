# Security review — #495 Generic OAuth per-provider default permissions

Manual review (slash-command can't attach to a scratchpad worktree; Greptile
also auto-reviews on push). Role/permission change → security-relevant.

## Surface
- `cps/admin.py` `_selected_generic_oauth_default_role` + save in
  `_configuration_oauth_helper` (admin-only route).
- `cps/oauth_bb.py` `_oauth_effective_default_role`, `_oauth_role_enabled`,
  new-user role assignment, blueprint role booleans.
- `cps/ub.py` nullable `oauth_default_role` column + idempotent migration.

## Findings
1. **No privilege escalation.** The checkbox→bitmask map contains only
   download/viewer/upload/edit/delete/passwd/edit_shelf — never ROLE_ADMIN.
   OAuth default permissions cannot make new users admin (test
   `test_never_grants_admin`). Admin remains governed by the separate group
   logic. PASS.
2. **No role injection.** Role bits come from a fixed allow-list of form keys;
   an unexpected field maps to nothing. Only admin_required callers reach the
   save path. PASS.
3. **No silent downgrade (regression).** Column is NULLABLE;
   `_oauth_effective_default_role` falls back to global `config_default_role`
   when unset. Verified live: NULL provider role + global default
   download|viewer → new users get download|viewer; the config checkboxes
   mirror the effective default. PASS.
4. **Explicit 0 honored.** An admin who unchecks all gets role 0 (their choice),
   not the global default. PASS.
5. **Robustness.** None/garbage guarded in both helpers; SQLAlchemy
   parameterized update; idempotent NULL-default migration (verified on a live
   container, /admin/config renders 200). PASS.

Verdict: no vulnerabilities. Safe to merge.
