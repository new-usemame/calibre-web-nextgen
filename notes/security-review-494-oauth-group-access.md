# Security review — #494 Generic OAuth group-based access control

Manual review (the /security-review slash-command can't attach to a scratchpad
worktree; Greptile also auto-reviews on push). Auth/authorization change.

## Surface
- `cps/oauth_bb.py` `register_user_from_generic_oauth`: new pre-provision
  authorization gate `_oauth_group_access_denied`; configurable group claim.
- `cps/ub.py`: 3 new `oauthProvider` columns + idempotent migration.
- `cps/admin.py`: admin save of the 3 fields.

## Findings
1. **Authorization gate — fail closed.** require_group + empty allow-list denies
   everyone (tested), not admit-all. require off = unchanged behavior. PASS.
2. **Gate ordering.** Runs before `ub.User()` AND for existing users (before the
   `if not user` branch), so a rejected identity never auto-provisions and an
   existing user dropped from the group is rejected on next login. Source-pinned.
   PASS.
3. **Matching semantics.** Exact-string, case-insensitive set membership (not
   substring) — no widening bypass. PASS.
4. **Trust model.** `user_groups` come from the IdP token already validated by
   the OAuth flow; no new trust assumption introduced. PASS.
5. **Info leak.** End user sees a generic "not allowed" flash; required groups
   are only logged server-side. PASS.
6. **Injection.** group_claim is a dict key into userinfo; saves go through
   SQLAlchemy parameterized update. No SQLi/template injection. PASS.
7. **Regression / DoS.** `oauth_require_group` defaults OFF (existing installs
   unaffected); claim parsing is linear in token size. PASS.

## Residual
- Misconfiguration footgun: requiring groups with the wrong claim name locks
  users out (fail-closed direction — safe). Mitigated by help text. Accept.

Verdict: no vulnerabilities. Safe to merge.
