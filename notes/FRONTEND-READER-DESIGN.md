# In-browser reader (SPA) — design note

Operator flagship: elevate the in-browser reader to enterprise quality, mobile +
desktop, with cross-device progress and (phase 2) annotation/highlight sync.
This note scopes the React reader on `redesign/frontend`.

## Strategy

Reuse the existing storage + file delivery; rebuild only the reading surface in
React so it lives inside the SPA shell with the elevated design system.

- **Book file**: served by the existing `/download/<id>/epub/<name>` route
  (auth-cookied). epub.js opens it directly — no new file endpoint.
- **Progress**: the existing `ub.Bookmark(user_id, book_id, format, bookmark_key)`
  row already stores the epub.js CFI. The legacy reader posts to
  `/ajax/bookmark/<id>/<format>` (form). We add a JSON mirror under `/api/v1`
  that reads/writes the SAME row with the SAME `format` casing (lowercase, e.g.
  `epub`) — so progress is shared between the legacy reader and the SPA reader
  (open in one, resume in the other). Single source of truth = the Bookmark row.

## Phase 1 (this iteration) — epub reader

- Route `/app/read/:id`. Fetches book detail → picks the epub format + its
  `download_url`. (PDF/CBZ link out to the legacy `/read/...` for now; epub is the
  flagship format. Noted as a follow-up.)
- epub.js (`epubjs` npm, bundled — already vendored in legacy static; MIT) renders
  a paginated rendition into the SPA.
- Controls: prev/next (on-screen arrows, ← → keys, swipe/click zones), a TOC
  drawer (epub spine/nav), font-size +/−, and a reading theme (light / sepia /
  dark) independent of the app chrome.
- Progress: on open, GET the saved CFI and `display(cfi)`; on `relocated`,
  debounce-POST the new CFI. A thin progress bar shows percentage via
  `book.locations` (generated lazily).
- States: loading (spinner), error (bad/missing epub), and a clean full-bleed
  reading view that hides the app sidebar/topbar chrome.
- Mobile: tap zones for page turn, drawer TOC, large touch targets; desktop:
  keyboard + centered column with comfortable measure.

## Phase 2 (follow-up, not this iteration)

- Highlights/annotations: epub.js `annotations.add('highlight', cfi)`, persisted
  per-user; reconcile with KOReader/Kobo annotation sync (coordinate with the
  web-reader program + cwasync). Needs its own storage + a merge story.
- pdf.js-based PDF reader in-SPA.
- Per-book reading settings memory (font/theme) and bookmarks (named CFIs).

## API (phase 1)

- `GET /api/v1/books/<id>/bookmark?format=epub` → `{ "bookmark": "<cfi>"|null }`
- `POST /api/v1/books/<id>/bookmark` `{ format, bookmark }` → 204 (empty bookmark
  clears it). Reuses the Bookmark model + lowercase format for legacy interop.

## Verification

- API: container round-trip (save CFI → read back → clear); ACL (anon 401);
  cross-check the row is the same one the legacy `/ajax/bookmark` writes.
- UI (Playwright): open a real epub from the library, page forward, reload →
  resumes at the saved location; TOC navigates; font/theme change; mobile tap
  zones. Console clean.
