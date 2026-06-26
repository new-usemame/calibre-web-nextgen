# Install / switch with `docker compose` (command line)

The baseline path, on any machine with Docker installed. **Your books, users, settings and
Read checkmarks live in the volumes you mount — not in the image — so switching keeps
everything and is reversible.**

## Fresh install

1. Create a folder and a `docker-compose.yml` in it:

   ```yaml
   services:
     calibre-web-nextgen:
       image: ghcr.io/new-usemame/calibre-web-nextgen:latest
       container_name: calibre-web-nextgen
       environment:
         - PUID=1000
         - PGID=1000
         - TZ=America/New_York
       volumes:
         - ./config:/config
         - ./library:/calibre-library
         - ./ingest:/cwa-book-ingest
       ports:
         - 8083:8083
       restart: unless-stopped
   ```

   Adjust the volume paths, `PUID`/`PGID` (run `id` to see yours), and `TZ`.
2. Start it:

   ```bash
   docker compose up -d
   ```
3. Open `http://<host>:8083` and log in.

## Switching from stock CWA

In your existing `docker-compose.yml`, change only the image line:

```diff
- image: crocodilestick/calibre-web-automated:latest
+ image: ghcr.io/new-usemame/calibre-web-nextgen:latest
```

Keep the same `volumes` (so `/config` and `/calibre-library` point at your existing data),
then:

```bash
docker compose pull
docker compose up -d
```

Your library, users and Read checkmarks carry over untouched. To roll back, change the image
line back and run the same two commands.

## Updating later

```bash
docker compose pull && docker compose up -d
```

`pull` fetches the newest `:latest` image; `up -d` recreates the container with your data
intact. (`restart` alone does **not** pull a new image.)

---

**Your setup might differ.** If a step doesn't match what you see, or if sync / auto-ingest
isn't working after you switch, we'll help you through it:

- **Open an issue** (best for tracking): https://github.com/new-usemame/Calibre-Web-NextGen/issues
- **Ask on Discord** (faster back-and-forth): https://discord.gg/B8NXZmcp32

Include your platform and what you ran, and we'll help you sort it out.
