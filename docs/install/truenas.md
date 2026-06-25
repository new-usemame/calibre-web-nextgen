# Install / switch to Calibre-Web-NextGen on TrueNAS SCALE

This works whether you're installing fresh or switching from the standard
Calibre-Web-Automated (CWA) image. **Your books, users, settings and the Read checkmarks
you've set all live in the storage you mount into the container — nothing gets converted
or deleted, and switching is reversible.**

On TrueNAS SCALE, Calibre-Web usually runs as a **Custom App**. The image is one field in
that app's configuration. Labels match SCALE's **Apps** UI (Dragonfish / Electric Eel
generation); older versions are close but may word things slightly differently.

## Switch from CWA

1. **Apps** → click your existing Calibre-Web-Automated app → **Edit**.
2. Find the **Image Repository** field and change it from
   `crocodilestick/calibre-web-automated` to:

   ```
   ghcr.io/new-usemame/calibre-web-nextgen
   ```

   Leave the **Image Tag** as `latest`.
3. Leave **Storage** (the host-path mounts for `/config`, `/calibre-library`,
   `/cwa-book-ingest`) and the environment variables (`PUID`, `PGID`, `TZ`) exactly as
   they are.
4. Click **Save / Update**. SCALE pulls the new image and redeploys the app with your
   same storage mounted. Open the app's WebUI and log in as usual.

> Undo path: note the old repository value before you change it. Switching back is the
> same edit in reverse.

## Fresh install

1. **Apps** → **Discover Apps** → **Custom App** (top right).
2. Set:
   - **Application Name:** `calibre-web-nextgen`
   - **Image Repository:** `ghcr.io/new-usemame/calibre-web-nextgen`
   - **Image Tag:** `latest`
3. **Container Environment Variables** — add `PUID`, `PGID`, `TZ` (e.g. `568`, `568`,
   `Europe/Berlin`; match the user that owns your dataset).
4. **Port Forwarding** — forward a host port (e.g. `8083`) to container port `8083`.
5. **Storage** — add three host-path (or dataset) mounts:
   - mount your config dataset → `/config`
   - mount your Calibre library dataset → `/calibre-library`
   - mount an ingest dataset → `/cwa-book-ingest`
6. Click **Install**. SCALE pulls the image and deploys the app. Open the WebUI to finish
   setup.

## Updating later

1. **Apps** → **Installed**. When a new image is published, the
   `calibre-web-nextgen` app shows an **Update** badge (SCALE re-checks the `:latest` tag
   on its own schedule; you can also hit **Refresh**).
2. Click **Update**. SCALE pulls the newest image and redeploys; your datasets stay
   mounted, so library and settings are untouched.

---

**Your setup might differ.** If a step doesn't match what you see on screen, or if
sync / auto-ingest isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and a screenshot of the screen you're stuck on, and we'll tell you
the exact buttons to press.
