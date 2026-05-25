# Manual device verification — KOReader annotation bridge (Phase 2)

Run this once on real hardware before Phase 2 is considered complete. It
verifies the one thing CI cannot: the `KoboReader.sqlite` ↔ Nickel round-trip.
Everything else (server pull/push, diff/merge, field mapping) is automated +
green; this gate covers the device write.

Design: `notes/2026-05-25-annotation-two-way-phase1-phase2-DESIGN.md` §4.
Until this passes, keep the plugin's "Sync highlights" toggle default **off**.

## Prerequisites

- A physical Kobo running **KOReader** with the `cwasync.koplugin` from this
  branch installed (copy `koreader/plugins/cwasync.koplugin/` to the device's
  `koreader/plugins/`).
- The Kobo also has a CW-synced **kepub** of a test book (so it has KoboSpans +
  a `Bookmark`-compatible VolumeID).
- CWNG (`cwn-local` or teenyverse) reachable from the device, with **KOReader
  sync enabled** (`cwa_settings.koreader_sync_enabled = 1`).
- In the plugin: Set NextGen Server, Login, then enable **Sync highlights
  (experimental, Kobo only)**.

## Test 1 — web → device (the headline: server highlight reaches Nickel)

1. In the CWNG **web reader**, open the test book, select a sentence, save a
   highlight (e.g. green, note "bridge-test-1").
2. On the Kobo, open the book in **KOReader** → plugin menu → **Sync highlights
   now**. Expect an info message "Highlights synced: N to device, …".
3. On the host, inspect the device DB (or pull it):
   ```
   sqlite3 KoboReader.sqlite \
     "SELECT BookmarkID, Color, Text, substr(StartContainerPath,1,20) \
      FROM Bookmark WHERE Text LIKE '%bridge-test-1%' OR Annotation='bridge-test-1';"
   ```
   ✅ A row exists; `BookmarkID` is the server's `cwn-web-…` id; `Color=2`
      (green); `StartContainerPath` is `span#kobo\.x\.y`.
4. **Close KOReader and open the book in stock Nickel.** Navigate to the
   highlighted passage.
   ✅ The highlight shows in the stock reader. *(This is the whole point of the
      bridge — a web-created highlight on a stock Kobo.)*

## Test 2 — device → web (reverse direction)

5. In KOReader (or Nickel), create a highlight on a different sentence
   ("bridge-test-2"). Sync highlights now.
6. In the CWNG web reader, reload the book.
   ✅ "bridge-test-2" appears as an overlay; the `/annotations/<book>` page
      lists it with `source: kobo` (read out of KoboReader.sqlite) or
      `koreader`.

## Test 3 — safety: backup + integrity

7. On the device, confirm a backup was made before the first write:
   ```
   ls -la .kobo/KoboReader.sqlite.cwn-bak-*
   ```
   ✅ At least one backup file exists.
8. Integrity check the live DB:
   ```
   sqlite3 KoboReader.sqlite "PRAGMA integrity_check;"
   ```
   ✅ `ok`. No corruption from our writes.

## Test 4 — idempotency / no feedback loop

9. Run **Sync highlights now** twice in a row without changing anything.
   ✅ Second run reports "0 to device, 0 to server" (or only genuinely-new
      rows). No duplicate `Bookmark` rows for the same passage:
   ```
   sqlite3 KoboReader.sqlite \
     "SELECT BookmarkID, COUNT(*) FROM Bookmark GROUP BY BookmarkID HAVING COUNT(*)>1;"
   ```
   ✅ Empty (INSERT OR IGNORE held; no dupes).

## On failure

Capture and open a GitHub issue with:
```
cp .kobo/KoboReader.sqlite /tmp/koboreader-fail.sqlite
# KOReader log: koreader/crash.log or the plugin's logger.dbg output
```
Note the failing step number. Do **not** flip the toggle default to on until
all four tests pass.

## Sign-off

- [ ] Test 1 (web → Nickel) passed
- [ ] Test 2 (device → web) passed
- [ ] Test 3 (backup present + integrity ok) passed
- [ ] Test 4 (idempotent, no dupes) passed

Once all four pass, the device-write default may be flipped on in a follow-up.
