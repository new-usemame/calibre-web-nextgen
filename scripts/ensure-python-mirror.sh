#!/usr/bin/env bash
# Ensure our GHCR mirror of the python-build-standalone tarball exists.
#
# WHY THIS EXISTS
#   The GitHub release-asset CDN (objects/release-assets.githubusercontent.com)
#   intermittently 404s the GitHub-Actions egress — sometimes for >10 min at a
#   stretch — which broke EVERY image build (the Dockerfile used to curl Python
#   from there). So we mirror the tarball into our own GHCR image and the
#   Dockerfile COPYs it from there instead. GHCR is the same registry the base
#   images come from, so it's reliable from inside the build.
#
# WHAT THIS DOES (idempotent — safe to run every build)
#   1. Reads PYTHON_VERSION + PYTHON_BUILD_STANDALONE_RELEASE from the Dockerfile
#      (the single source of truth).
#   2. If ghcr.io/new-usemame/pbs-cache:cpython-<ver>-<rel> already exists → done.
#   3. Otherwise downloads both arch tarballs from the release CDN (with retries)
#      and pushes a tiny multi-arch image containing /python.tar.gz.
#
# >>> TO BUMP PYTHON: change ONLY the two ARGs in the Dockerfile. <<<
#   The mirror tag here and the Dockerfile's COPY --from both derive from those
#   ARGs, and CI runs this script before every build, so the new mirror is built
#   automatically the first time. There is no other manual step.
#
# AUTH: set GHCR_TOKEN to a token with write:packages (CI passes secrets.GH_PAT).
#       Only needed when the mirror has to be built; the existence check is anon.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE="${REPO_ROOT}/Dockerfile"
GHCR_USER="${GHCR_USER:-new-usemame}"
MIRROR_PATH="new-usemame/pbs-cache"          # ghcr.io/<this>
MIRROR_REPO="ghcr.io/${MIRROR_PATH}"

read_arg() { grep -E "^ARG ${1}=" "$DOCKERFILE" | head -1 | cut -d= -f2; }
PYTHON_VERSION="$(read_arg PYTHON_VERSION)"
PBS_RELEASE="$(read_arg PYTHON_BUILD_STANDALONE_RELEASE)"
[ -n "$PYTHON_VERSION" ] && [ -n "$PBS_RELEASE" ] || { echo "ERROR: could not read Python pin from $DOCKERFILE"; exit 1; }

TAG="cpython-${PYTHON_VERSION}-${PBS_RELEASE}"
REF="${MIRROR_REPO}:${TAG}"
echo "python-build-standalone mirror target: ${REF}"

# --- 1. Already present? -------------------------------------------------------
# The mirror package is private, so the existence check must be AUTHENTICATED
# (an anonymous token can't see a private manifest and would always report
# "missing", causing a needless rebuild every run). Use GHCR_TOKEN when set;
# fall back to an anonymous token only if it isn't (e.g. ad-hoc local runs).
if [ -n "${GHCR_TOKEN:-}" ]; then
  reg_token="$(curl -s -u "${GHCR_USER}:${GHCR_TOKEN}" "https://ghcr.io/token?scope=repository:${MIRROR_PATH}:pull" \
    | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
else
  reg_token="$(curl -s "https://ghcr.io/token?scope=repository:${MIRROR_PATH}:pull" \
    | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
fi
if curl -sf -o /dev/null \
     -H "Authorization: Bearer ${reg_token}" \
     -H 'Accept: application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json' \
     "https://ghcr.io/v2/${MIRROR_PATH}/manifests/${TAG}"; then
  echo "Mirror already present — nothing to do."
  exit 0
fi
echo "Mirror missing — building and pushing it."

# --- 2. Build + push the mirror ----------------------------------------------
: "${GHCR_TOKEN:?GHCR_TOKEN (token with write:packages, e.g. GH_PAT) required to build the mirror}"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

download() {  # download <pbs-arch-triple> <output-file>
  local url="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}/cpython-${PYTHON_VERSION}+${PBS_RELEASE}-$1-install_only.tar.gz"
  echo "Downloading $1 from ${url}"
  curl -fL --connect-timeout 30 --retry 8 --retry-delay 5 --retry-all-errors -o "$2" "$url"
}
download "x86_64-unknown-linux-gnu"  "${WORK}/python-amd64.tar.gz"
download "aarch64-unknown-linux-gnu" "${WORK}/python-arm64.tar.gz"

cat > "${WORK}/Dockerfile" <<'DF'
# syntax=docker/dockerfile:1
# Holds the python-build-standalone tarball for the building platform at
# /python.tar.gz. Consumed by the app Dockerfile via COPY --from.
FROM scratch
ARG TARGETARCH
COPY python-${TARGETARCH}.tar.gz /python.tar.gz
DF

echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin
docker buildx create --use --name pbs-mirror-builder >/dev/null 2>&1 || docker buildx use pbs-mirror-builder
docker buildx build --platform linux/amd64,linux/arm64 -t "${REF}" --push "${WORK}"
echo "Pushed ${REF}"
