# Install / switch to Calibre-Web-NextGen on Portainer (Stacks)

This works whether you're installing fresh or switching from the standard
Calibre-Web-Automated (CWA) image. **Your books, users, settings and the Read checkmarks
you've set all live in the folders mapped into the container — nothing gets converted or
deleted, and switching is reversible.**

Portainer runs Calibre-Web from a **Stack** (a compose file it stores for you). Switching
is a one-line edit to that stack.

## Switch from CWA

1. **Stacks** → click the stack that runs your Calibre-Web-Automated container → **Editor**.
2. Find the `image:` line and change it from
   `crocodilestick/calibre-web-automated:latest` to:

   ```yaml
   image: ghcr.io/new-usemame/calibre-web-nextgen:latest
   ```

3. Leave the `volumes:` (`/config`, `/calibre-library`, `/cwa-book-ingest`) and the
   `environment:` (`PUID`, `PGID`, `TZ`) exactly as they are.
4. Scroll down and tick **Re-pull image and redeploy**, then click **Update the stack**.
   Portainer pulls the new image and recreates the container with your same data mounted.
5. Open the WebUI and log in as usual.

> One-click undo: keep a copy of the old `image:` line. Switching back is the same edit in
> reverse plus another **Update the stack**.

## Fresh install

1. **Stacks** → **Add stack**.
2. **Name:** `calibre-web-nextgen`. Paste this into the **Web editor**, adjusting the
   volume paths and IDs for your host:

   ```yaml
   services:
     calibre-web-nextgen:
       image: ghcr.io/new-usemame/calibre-web-nextgen:latest
       container_name: calibre-web-nextgen
       environment:
         - PUID=1000
         - PGID=1000
         - TZ=Europe/Berlin
       volumes:
         - /path/to/config:/config
         - /path/to/library:/calibre-library
         - /path/to/ingest:/cwa-book-ingest
       ports:
         - 8083:8083
       restart: unless-stopped
   ```

3. Click **Deploy the stack**. Portainer pulls the image and starts it. Open the WebUI to
   finish setup.

## Updating later

1. **Stacks** → your `calibre-web-nextgen` stack → **Editor**.
2. Tick **Re-pull image and redeploy** and click **Update the stack**. Because the tag is
   `:latest`, this pulls the newest published image and recreates the container; your data
   stays in the mounted folders.

---

**Your setup might differ.** If a step doesn't match what you see on screen, or if
sync / auto-ingest isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and a screenshot of the screen you're stuck on, and we'll tell you
the exact buttons to press.
