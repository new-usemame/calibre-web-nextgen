# Install / switch to Calibre-Web-NextGen on Synology (Container Manager)

This works whether you're installing fresh or switching from the standard
Calibre-Web-Automated (CWA) image. **Your books, users, settings and the Read checkmarks
you've set all live in the folders mapped into the container — nothing gets converted or
deleted, and you can undo the whole thing in one click.**

DSM is often localized; this guide notes the German labels alongside the English ones
where they're known (e.g. *Speicherplatz / Volume*).

## If you're switching from CWA — note your current setup first

1. **Container Manager → Container** (*Behälter*), click your existing container (often
   called `CMA` or `calibre-web-automated`) → **Details**.
2. On the **Speicherplatz / Volume** tab, note which Synology folder maps to each of
   `/config`, `/calibre-library`, and `/cwa-book-ingest`.
3. On the **Umgebung / Environment** tab, note `PUID`, `PGID`, `TZ`.
4. Back in **Container**, select it → **Aktion → Anhalten** (Action → Stop).
   **Leave it — don't delete it.** A stopped CWA container is your instant undo.

## Create the NextGen project

5. **Container Manager → Projekt → Erstellen** (Project → Create).
   - **Projektname:** `calibre-web-nextgen`
   - **Quelle:** choose *"docker-compose.yml erstellen"* (Create docker-compose.yml) and
     paste this, replacing the three `/volume1/...` paths and the `PUID` / `PGID` / `TZ`
     with the values you noted above (fresh install: use your own folders and IDs):

   ```yaml
   services:
     calibre-web-nextgen:
       image: ghcr.io/new-usemame/calibre-web-nextgen:latest
       container_name: calibre-web-nextgen
       environment:
         - PUID=1026
         - PGID=100
         - TZ=Europe/Berlin
       volumes:
         - /volume1/docker/calibre/config:/config
         - /volume1/docker/calibre/library:/calibre-library
         - /volume1/docker/calibre/ingest:/cwa-book-ingest
       ports:
         - 8083:8083
       restart: unless-stopped
   ```

6. Click through (**Weiter / Fertig** — Next / Done). Container Manager pulls the image
   from ghcr.io on its own — no registry setup needed — and starts it.
7. Open the same web address you always use and log in with your usual account. Your
   library, users, and Read checkmarks are all there.

## Updating later — important, and not the way standard Calibre-Web does it

With a standalone Calibre-Web container, DSM shows an update under **Image** and you click
it. A **Project** is different: the project keeps the image in use, so DSM refuses to
delete or replace it while the container exists — you have to free it first by removing
the container. Your data is safe through all of this because it lives in the mounted
folders, not the container.

1. **Container Manager → Projekt** → your `calibre-web-nextgen` project →
   **Aktion → Anhalten** (Action → Stop).
2. **Container Manager → Container** → select the stopped `calibre-web-nextgen` container
   → **Aktion → Löschen** (Action → Delete). This removes only the container; it's
   recreated in step 4, and your library/settings stay in the mounted folders.
3. **Container Manager → Image** → click the
   `ghcr.io/new-usemame/calibre-web-nextgen:latest` row → **Aktion → Löschen** (Delete).
   Now that no container is using it, this succeeds. It only clears the cached image.
4. **Container Manager → Projekt** → your project → **Aktion → Erstellen / Build**. With
   the cached image gone, Container Manager pulls the newest one fresh and recreates the
   container. Wait ~30 seconds and reload.

> If deleting the image in step 3 still shows an "in use" error, the container in step 2
> wasn't fully removed yet — refresh the **Container** tab and confirm it's gone, then
> retry step 3.

---

**Your setup might differ.** If a step doesn't match what you see on screen, or if
sync / auto-ingest isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and a screenshot of the screen you're stuck on, and we'll tell you
the exact buttons to press.
