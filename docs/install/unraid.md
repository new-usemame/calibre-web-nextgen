# Install / switch to Calibre-Web-NextGen on Unraid

This works whether you're installing fresh or switching from the standard
Calibre-Web-Automated (CWA) image. **Your books, users, settings and the Read checkmarks
you've set all live in the folders mapped into the container — nothing gets converted or
deleted, and switching is reversible.**

On Unraid the only thing that changes is the **Repository** (image) line. Every path
mapping and variable stays the same.

## Switch from CWA (the one-field change)

1. **Docker** tab → click your existing Calibre-Web-Automated container → **Edit**.
2. Change the **Repository** field from
   `crocodilestick/calibre-web-automated:latest` to:

   ```
   ghcr.io/new-usemame/calibre-web-nextgen:latest
   ```

3. Leave every **Path** (`/config`, `/calibre-library`, `/cwa-book-ingest`) and every
   variable (`PUID`, `PGID`, `TZ`) exactly as they are.
4. Click **Apply**. Unraid pulls the new image and recreates the container with your same
   data mounted. Open the WebUI and log in as usual.

> Want a clean rollback path? Before editing, you can clone the container template
> (Docker tab → **Add Container** → pick your CWA template) so the old image line is saved
> as a separate, stopped entry.

## Fresh install

1. **Docker** tab → **Add Container**.
2. Fill in:
   - **Name:** `calibre-web-nextgen`
   - **Repository:** `ghcr.io/new-usemame/calibre-web-nextgen:latest`
   - **WebUI port:** map host `8083` → container `8083`
   - **Path mappings** (Add another Path for each):
     - `/config` → e.g. `/mnt/user/appdata/calibre-web-nextgen`
     - `/calibre-library` → your Calibre library share
     - `/cwa-book-ingest` → an ingest folder you'll drop books into
   - **Variables:** `PUID` (usually `99`), `PGID` (usually `100`), `TZ` (e.g.
     `Europe/Berlin`)
3. Click **Apply**. Unraid pulls the image and starts it. Open the WebUI to finish setup.

## Updating later

Unraid makes this easy — no manual image deletion needed:

1. **Docker** tab → toggle **Advanced View** (top right) if you don't see version info.
2. Click **Check for Updates**. The `calibre-web-nextgen` row will show *update ready*
   when a new image is published.
3. Click **apply update** (or **Update** in the container's context menu). Unraid pulls
   the new image and recreates the container with your data intact.

---

**Your setup might differ.** If a step doesn't match what you see on screen, or if
sync / auto-ingest isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and a screenshot of the screen you're stuck on, and we'll tell you
the exact buttons to press.
