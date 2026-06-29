# Tutorial tooltips (coach marks) — SPA, skill-driven, single-source design

**Status:** QUEUED (design captured 2026-06-28; not yet built). Operator-requested.
**Owner surface:** new React UI (`/app`) only.

## The intent (operator's words, distilled)
Add gentle, in-context tutorial tooltips ("coach marks") that teach features. They must:
- be created with **frontend-design** quality and a **single, consistent style**;
- be **scalable + AI-iterable** — a skill can add new tooltips without bespoke code each
  time;
- be **unobtrusive and non-invasive** — NOT bound into feature/functional code, NOT
  blocking the UI, easy to ignore;
- be **disableable AND resettable in Settings**, clearly and easily (operator is
  emphatic: "I do not want people to get annoyed with this");
- carry copy with the **same humanization standard as What's New** (benefit-led,
  problem→solution, plain language, no AI tells);
- have **one design definition** — change it in one place and every tooltip changes.
  See [[whats-new-feature]] for the sibling copy standard.

## Architecture (decoupling is the whole point)
A **registry-driven overlay**, not props threaded through feature components.

1. **Registry** — `frontend/src/tutorial/tooltips.ts`: a flat list of tooltip defs.
   ```ts
   export interface TooltipDef {
     id: string;              // stable, e.g. 'discover-shuffle'
     anchor: string;          // CSS selector OR data-attr the overlay finds at runtime
     title: string;           // benefit-led, t()-wrapped
     body: string;            // 1–2 sentences: what + why + how (tone rules below)
     placement?: 'top'|'bottom'|'left'|'right';
     route?: string;          // only show on this /app route (optional)
     order?: number;          // sequencing within a guided tour (optional)
     version?: string;        // release it was introduced (for "only show new ones")
   }
   export const TOOLTIPS: TooltipDef[] = [ ... ];
   ```
   Features opt in **non-invasively** by adding a `data-tip="discover-shuffle"` attribute
   to the element they want anchored — that's the ONLY touch to feature code. The overlay
   reads the attribute/selector at runtime; the feature has no logic, no imports, no
   coupling. Removing a tooltip = delete the registry row (+ the stray data-attr).

2. **Overlay engine** — `frontend/src/tutorial/TutorialOverlay.tsx` mounted once at the
   app root (alongside the router, NOT inside any page). It:
   - finds the anchor element, positions a single shared `<TutorialTip>` component near it;
   - shows tips per the user's mode (see "Modes"); never traps focus or blocks clicks on
     unrelated UI (dim/highlight is optional + light, dismissable with Esc/click-away);
   - is fully keyboard accessible (focusable, Esc to dismiss, "Next/Got it" buttons),
     respects `prefers-reduced-motion`.

3. **Single design source** — `frontend/src/tutorial/TutorialTip.tsx` +
   `TutorialTip.module.css` is the ONE visual definition (bubble, arrow, typography,
   colors, motion). Built with the **frontend-design** skill, using the existing design
   tokens (amber accent `--accent:#cc7b19`, dark surface, CSS Modules). **Every tooltip
   renders through this component — no per-feature styling.** If the look changes, it
   changes here and everywhere at once. This is a hard rule: do not inline tooltip styles
   anywhere else.

## Modes / behavior (anti-annoyance)
- **Default:** show a tooltip at most once per `id` per user, the first time the user is
  on the screen where its anchor exists. Persist "seen" set in `localStorage`
  (e.g. `cwng_tips_seen`). Quiet by default — one tip at a time, never a wall.
- Optionally a **"Take a tour"** action (Help menu or Settings) that walks the ordered
  tips for the current area on demand.
- **"What's new" tie-in (optional):** when a release adds tooltips, only surface tips
  whose `version` is newer than the user's last-seen version, so updates teach just the
  new things. Reuse the version-keyed pattern from the What's New unread dot.

## Settings (clear + easy — required)
Add to the SPA account/settings screen (`frontend/src/pages/Account*`), a clearly
labeled control group:
- **"Show tutorial tips"** — master on/off toggle (off = overlay never shows anything).
- **"Reset tutorial tips"** — button that clears the `seen` set so all tips show again.
- Persist via a small typed `localStorage` helper (reuse/extend `usePersistentBool`,
  the same one Discover uses: `frontend/src/lib/usePersistentBool.ts`). If we later want
  it server-synced per user, route through the account API — but localStorage is the
  acceptable v1 (matches Discover/banners).
- Copy must make it obvious how to turn off/reset, so nobody feels stuck with them.

## Tone / humanization (copy standard — same as What's New)
- Benefit-led title; 1–2 sentence body covering **what it is, why it helps, how to use**.
- Plain language for smart non-technical readers. No jargon, no AI tells, no fluff.
- Each tip earns its place — if it's obvious, don't tip it. Respect the user's intelligence.

## Make it a skill (scalable + AI-iterable)
Create `~/.claude/skills/add-tutorial-tip/SKILL.md` so any session can add tooltips
**consistently**:
1. Identify the feature element; add a single `data-tip="<id>"` attribute (the only
   feature-code touch).
2. Append a `TooltipDef` to the registry with tone-compliant copy + correct anchor +
   placement + route + version.
3. **Always render via the shared `TutorialTip` component — never introduce new tooltip
   styling.** The skill must explicitly check for and reuse the existing design; if a
   design change is wanted, it changes `TutorialTip.module.css` once (and the skill notes
   that all tips inherit it).
4. Verify placement on desktop + mobile (Playwright), and that the master toggle hides it
   and reset re-shows it.

## Verification (per Enterprise standard, when built)
- Playwright desktop + mobile (390px): tip appears on first visit, positions correctly,
  dismisses, doesn't reappear; doesn't block underlying controls.
- Settings: master toggle suppresses all tips; reset restores them.
- Accessibility: keyboard reachable, Esc dismiss, reduced-motion honored.
- Consistency guard: every tip routes through `TutorialTip` (grep for stray tooltip CSS).
