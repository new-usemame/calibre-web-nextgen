# Install / switch to Calibre-Web-NextGen

These guides walk you through installing Calibre-Web-NextGen, or switching to it from
the standard Calibre-Web-Automated (CWA) image, using the tool you already manage your
containers with — no command line needed unless your platform is built around one.

**Switching is safe and reversible.** Your books, users, settings, and the Read
checkmarks you've set all live in the folders you mount into the container
(`/config`, `/calibre-library`, `/cwa-book-ingest`), not inside the image. Nothing is
converted or deleted, and you can switch back by pointing at the old image again.

The image name is always:

```
ghcr.io/new-usemame/calibre-web-nextgen:latest
```

Keep the same volume folders and the same `PUID` / `PGID` / `TZ` you already had.

## Pick your platform

| Platform | Guide |
|---|---|
| Synology (Container Manager, DSM 7.2+) | [synology.md](synology.md) |
| Unraid (Docker tab) | [unraid.md](unraid.md) |
| Portainer (Stacks) | [portainer.md](portainer.md) |
| TrueNAS SCALE (Apps → Custom App) | [truenas.md](truenas.md) |
| Plain `docker compose` (CLI) | [compose.md](compose.md) |

QNAP Container Station and Dockge guides are on the way. If you're on one of those and
want a hand before they land, open an issue or ask on Discord (links at the bottom of
every guide) and we'll walk you through it.

---

**Your setup might differ.** If a step doesn't match what you see on screen, or if
sync / auto-ingest isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and a screenshot of the screen you're stuck on, and we'll tell you
the exact buttons to press.
