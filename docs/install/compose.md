# Install / switch to Calibre-Web-NextGen with `docker compose` (CLI)

This is the baseline path for anyone comfortable on the command line. If you manage
containers through a NAS or GUI instead, use the matching guide in the
[index](README.md) — the idea is the same, the buttons differ.

**Switching is safe and reversible.** Your books, users, settings and Read checkmarks live
in the folders you mount (`/config`, `/calibre-library`, `/cwa-book-ingest`), not in the
image. Nothing is converted or deleted.

## Switch from CWA

In your existing `docker-compose.yml`, change the image line:

```diff
- image: crocodilestick/calibre-web-automated:latest
+ image: ghcr.io/new-usemame/calibre-web-nextgen:latest
```

Then pull and restart:

```bash
docker compose pull && docker compose up -d
```

Switching back is the same one-line change in reverse.

## Fresh install

Create `docker-compose.yml`, adjusting the volume paths and IDs for your host:

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
      - ./config:/config
      - ./library:/calibre-library
      - ./ingest:/cwa-book-ingest
    ports:
      - 8083:8083
    restart: unless-stopped
```

Bring it up:

```bash
docker compose up -d
```

Then open `http://<host>:8083` to finish setup. For the full configuration reference
(Calibre binaries, advanced volumes, reverse proxy), see the main
[README](../../README.md).

## Updating later

```bash
docker compose pull && docker compose up -d
```

`pull` fetches the newest `:latest` image; `up -d` recreates the container with your data
mounted.

---

**Your setup might differ.** If a step doesn't match what you see on screen, or if
sync / auto-ingest isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and a screenshot of the screen you're stuck on, and we'll tell you
the exact buttons to press.
