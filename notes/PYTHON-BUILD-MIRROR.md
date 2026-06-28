# Python (python-build-standalone) is installed from our GHCR mirror

## TL;DR for the next person (or agent)
The Docker image installs Python 3.13 by `COPY`ing a tarball from our own GHCR
image **`ghcr.io/new-usemame/pbs-cache`**, NOT by downloading from GitHub's
release CDN. **To bump Python, change only these two `ARG`s in `Dockerfile`:**

```
ARG PYTHON_BUILD_STANDALONE_RELEASE=20260623
ARG PYTHON_VERSION=3.13.14
```

Everything else follows automatically. Don't touch the workflows or the script.

## Why this exists
GitHub's release-asset CDN intermittently returns **404 to the GitHub-Actions
egress** — sometimes for >10 minutes straight (proven 2026-06-28). The Dockerfile
used to `curl` Python from there, so every image build (dev + release) failed at
random. Pulling from GHCR — the same registry the base images come from — is
reliable, so we mirror the tarball there once and `COPY` it in.

## How it works (3 pieces, all driven by the two ARGs above)
1. **`Dockerfile`** — `ARG PBS_CACHE_REF=ghcr.io/new-usemame/pbs-cache:cpython-${PYTHON_VERSION}-${PYTHON_BUILD_STANDALONE_RELEASE}`
   then `COPY --from=${PBS_CACHE_REF} /python.tar.gz ...`. The tag is derived
   from the two ARGs, so it can never drift from the pin.
2. **`scripts/ensure-python-mirror.sh`** — idempotent: reads the two ARGs, and if
   `pbs-cache:cpython-<ver>-<rel>` isn't already on GHCR, downloads both arch
   tarballs (with retries) and pushes a tiny multi-arch `scratch` image holding
   `/python.tar.gz`. A no-op once the mirror exists.
3. **CI** — both image-build workflows (`docker-image-build-dev.yml`,
   `docker-image-build-release.yml`) run an `ensure-mirror` job (which runs the
   script) **before** the build job, so a freshly-bumped Python is mirrored
   automatically on the first build. No manual step.

So a Python bump = edit two ARGs → next CI run builds the mirror (downloads from
the release CDN that one time, with retries) → all subsequent builds just `COPY`
from GHCR. Regular builds never touch the release CDN.

## Auth note
The `pbs-cache` package is **private**, so builds log in to GHCR with `GH_PAT`
(read:packages) to `COPY --from` it, and the ensure script uses `GH_PAT`
(write:packages) to push it. If you ever make the package **public** in the GHCR
UI, you can drop the `GH_PAT` logins back to `GITHUB_TOKEN` and simplify — purely
optional.

## Manual mirror build (rare; e.g. CDN down during a bump)
```
GHCR_TOKEN="<a PAT with write:packages>" bash scripts/ensure-python-mirror.sh
```
Run from a machine whose network can reach the release CDN.
