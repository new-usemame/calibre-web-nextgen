# Phase 2 — KoboReader.sqlite provider verified against a REAL device DB

Date: 2026-05-25. Operator supplied a real `KoboReader.sqlite` (1,771 Bookmark
rows, 1,722 highlights) so the provider's SQL could be checked against the
genuine Kobo schema without the device.

## Bug found + fixed (the real schema caught what the doc didn't)

The real `Bookmark` table has **`EndContainerChildIndex` as NOT NULL with no
default** — `KOBO-PROTOCOL-REFERENCE.md` §10.1 only documented
`StartContainerChildIndex`. `kobo_sqlite_provider.buildBookmarkRow` set the
start sentinel but not the end one, and the INSERT omitted the column — so
**every device insert would have failed with a NOT NULL constraint violation**
on real hardware. This is exactly the class of bug the device gate exists to
catch; the real DB caught it pre-hardware.

Fix: `buildBookmarkRow` now sets `EndContainerChildIndex = -99`; the INSERT
column list + bind include it (17 cols). Pinned by a busted assertion. Also
captured `ChapterProgress` in `readAll`/`bookmarkRowToPortable` (real highlights
populate it) so device→web carries progress.

## Verified against the real schema (copy; original never touched)

`/tmp/kobo_insert_verify.py` ran the provider's **exact** INSERT + `readAll`
SELECT column lists against a copy of the real DB:

- INSERT satisfies all 9 NOT-NULL-no-default columns (BookmarkID, VolumeID,
  ContentID, Start/EndContainerPath, Start/EndContainerChildIndex,
  Start/EndOffset). Inserts a web highlight cleanly (Color=2, `-99` sentinels).
- `INSERT OR IGNORE` idempotent — double insert → 1 row, no error.
- `readAll` SELECT valid against the real schema; reads our row back (the test
  volume went 577 → 578 highlights).
- All my INSERT/SELECT column **names** exist in the real schema (0 unknown).

## What still needs the physical device (tonight)

Only the part that is irreducibly device-side: open the book in **stock Nickel**
and confirm the inserted highlight **renders** there, plus the live KOReader I/O
path (the plugin actually opening KoboReader.sqlite via its sqlite FFI + the
backup file). The SQL correctness + idempotency + schema-fit are now proven.
Run `notes/feat-annotation-koreader-bridge-device-verification.md`.
