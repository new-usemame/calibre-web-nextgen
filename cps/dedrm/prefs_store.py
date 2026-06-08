# -*- coding: utf-8 -*-

"""Calibre-free persistence layer for the DeDRM preferences file.

The vendored DeDRM code stores its configuration (keys, serials, PIDs,
passphrases and a handful of flags) in a JSON file that Calibre's own
``JSONConfig`` would normally manage. Calibre-Web-NextGen needs to read and
write that very same file from TWO different processes:

* the Flask web application (the admin UI that manages the keys), and
* the standalone ingest worker (``scripts/ingest_processor.py``), which only
  reads it to decide whether DRM removal is configured.

To keep both processes consistent we treat a single on-disk JSON file as the
source of truth. This module deliberately does NOT import any vendored DeDRM
module: it must stay lightweight and import-safe inside the long-lived Flask
worker. The vendored ``DeDRM_Prefs`` class (used only inside the isolated
engine subprocess) reads/writes the exact same path, because the engine points
Calibre's ``config_dir`` at :data:`DEDRM_DIR`.

All writes are atomic (write to a temp file, then ``os.replace``) and guarded
by an advisory file lock so a concurrent admin save and ingest read never see a
half-written file.
"""

import os
import json
import errno
import tempfile
from contextlib import contextmanager

try:
    # POSIX advisory locking. The production target is Linux (Docker), so this
    # is always available there; on platforms without fcntl we degrade to a
    # no-op lock (atomic replace alone still prevents torn reads).
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

# Resolve config directory the same way the ingest worker's get_app_db_path()
# does — cannot rely on cps.constants.CONFIG_DIR because CALIBRE_DBPATH is
# only exported for the Flask process (svc-calibre-web-automated/run) and
# not for the ingest-service subprocess, so BASE_DIR would be picked up
# there instead of /config.
CONFIG_DIR = os.environ.get("CALIBRE_DBPATH", "/config")

# Directory that holds everything DeDRM-related for this install.
DEDRM_DIR = os.path.join(CONFIG_DIR, "dedrm")

# Canonical preferences file. The nested ``plugins/dedrm.json`` layout is what
# DeDRM's own prefs code produces when ``config_dir == DEDRM_DIR``; we match it
# so the engine subprocess and this module operate on the same file.
PREFS_PATH = os.path.join(DEDRM_DIR, "plugins", "dedrm.json")

# Directory for uploaded key files that the schema references by path
# (currently only ``kindleextrakeyfile``). Keys for every other slot are stored
# inline (hex/base64) inside the JSON itself.
KEYFILES_DIR = os.path.join(DEDRM_DIR, "keyfiles")

# Restrictive permissions: these files contain decryption secrets.
_DIR_MODE = 0o700

# Default preference values, mirroring DeDRM's ``DeDRM_Prefs`` defaults so a
# brand-new install behaves exactly like the desktop plugin would.
DEFAULTS = {
    "configured": False,
    "deobfuscate_fonts": True,
    "remove_watermarks": True,
    # Named-key stores: ``{display_name: key_material}``.
    "bandnkeys": {},
    "adeptkeys": {},
    "ereaderkeys": {},
    "kindlekeys": {},
    "androidkeys": {},
    # Flat value lists.
    "pids": [],
    "serials": [],
    "lcp_passphrases": [],
    "adobe_pdf_passphrases": [],
    # Advanced / rarely used on a headless server.
    "adobewineprefix": "",
    "kindlewineprefix": "",
    "kindleextrakeyfile": "",
    # App-private (NOT read by DeDRM): optional human labels for entries that
    # DeDRM stores without a name, e.g. mapping a Kindle serial number to a
    # friendly device name. Shape: ``{store: {value: label}}``. DeDRM only reads
    # the stores above, so this extra key is ignored by the decryption engine.
    "cwa_labels": {},
}

# Keys whose value is a ``{name: value}`` mapping.
NAMED_KEY_STORES = ("bandnkeys", "adeptkeys", "ereaderkeys", "kindlekeys", "androidkeys")

# Keys whose value is a flat list.
LIST_STORES = ("pids", "serials", "lcp_passphrases", "adobe_pdf_passphrases")


def _ensure_dir(path, mode=_DIR_MODE):
    """Create ``path`` (and parents) if missing, ignoring races."""
    try:
        os.makedirs(path, mode=mode)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


@contextmanager
def _locked(lock_path, exclusive):
    """Advisory file lock around a critical section.

    ``exclusive`` selects a write lock (``LOCK_EX``) vs a shared read lock
    (``LOCK_SH``). The lock file lives next to the prefs file and is created on
    demand. On platforms without ``fcntl`` this is a no-op.
    """
    if fcntl is None:  # pragma: no cover - non-POSIX fallback
        yield
        return
    _ensure_dir(os.path.dirname(lock_path))
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _lock_path():
    return PREFS_PATH + ".lock"


def get_prefs():
    """Return the full preferences dict with defaults filled in.

    Missing or unreadable files yield a copy of :data:`DEFAULTS`. The returned
    dict is always a standalone copy; mutating it does not touch disk until
    :func:`save_prefs` is called.
    """
    prefs = {}
    # Start from defaults (deep-ish copy so nested dicts/lists are independent).
    for key, value in DEFAULTS.items():
        prefs[key] = dict(value) if isinstance(value, dict) else (list(value) if isinstance(value, list) else value)

    with _locked(_lock_path(), exclusive=False):
        try:
            with open(PREFS_PATH, "rb") as handle:
                raw = handle.read()
            if raw.strip():
                stored = json.loads(raw)
                if isinstance(stored, dict):
                    prefs.update(stored)
        except FileNotFoundError:
            pass
        except (ValueError, OSError):
            # Corrupt or unreadable prefs must not crash the app; fall back to
            # defaults. The admin UI will let the user re-create the config.
            pass
    return prefs


def save_prefs(prefs):
    """Atomically persist ``prefs`` to :data:`PREFS_PATH`.

    Writes to a temp file in the same directory and ``os.replace``s it into
    place, so a concurrent reader sees either the old or the new file, never a
    partial one. The whole operation is guarded by an exclusive lock.
    """
    target_dir = os.path.dirname(PREFS_PATH)
    _ensure_dir(target_dir)

    with _locked(_lock_path(), exclusive=True):
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".dedrm-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(prefs, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, PREFS_PATH)
        except BaseException:
            # Clean up the temp file on any failure so we do not leak it.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def is_configured(prefs=None):
    """Return ``True`` when DeDRM has enough configuration to attempt removal.

    DeDRM is considered configured if the user explicitly flagged it
    (``configured == True``) OR if any key store / value list is non-empty.
    When this returns ``False`` callers must skip DRM removal entirely.
    """
    if prefs is None:
        prefs = get_prefs()
    if prefs.get("configured") is True:
        return True
    for store in NAMED_KEY_STORES:
        if prefs.get(store):
            return True
    for store in LIST_STORES:
        if prefs.get(store):
            return True
    return False


def add_named_key(prefs, store, name, value):
    """Add ``value`` under a unique ``name`` to a named-key store.

    Mirrors DeDRM's ``addnamedvaluetoprefs``: duplicate values are ignored and
    name collisions get a numeric suffix. Mutates and returns ``prefs`` plus the
    resolved name (or ``None`` when the value already existed).
    """
    if store not in NAMED_KEY_STORES:
        raise ValueError("Unknown named-key store: %s" % store)
    bucket = prefs.setdefault(store, {})
    if value in bucket.values():
        return prefs, None
    resolved = name
    counter = 1
    while resolved in bucket:
        counter += 1
        resolved = "{0}_{1}".format(name, counter)
    bucket[resolved] = value
    return prefs, resolved


def delete_named_key(prefs, store, name):
    """Remove ``name`` from a named-key store if present."""
    if store in NAMED_KEY_STORES:
        prefs.get(store, {}).pop(name, None)
    return prefs


def add_list_value(prefs, store, value):
    """Append ``value`` to a list store, skipping duplicates."""
    if store not in LIST_STORES:
        raise ValueError("Unknown list store: %s" % store)
    bucket = prefs.setdefault(store, [])
    if value not in bucket:
        bucket.append(value)
    return prefs


def delete_list_value(prefs, store, value):
    """Remove ``value`` from a list store if present (and any label for it)."""
    if store in LIST_STORES:
        bucket = prefs.get(store, [])
        if value in bucket:
            bucket.remove(value)
        delete_label(prefs, store, value)
    return prefs


def set_label(prefs, store, value, label):
    """Attach an optional human label to a stored value (app-private).

    Used so a Kindle serial number can carry a friendly device name. Stored in
    ``cwa_labels`` which DeDRM ignores; an empty label clears any existing one.
    """
    labels = prefs.setdefault("cwa_labels", {})
    bucket = labels.setdefault(store, {})
    if label:
        bucket[value] = label
    else:
        bucket.pop(value, None)
    return prefs


def get_labels(prefs, store):
    """Return the ``{value: label}`` map for a store (possibly empty)."""
    return prefs.get("cwa_labels", {}).get(store, {})


def delete_label(prefs, store, value):
    """Remove any label attached to ``value`` in ``store``."""
    prefs.get("cwa_labels", {}).get(store, {}).pop(value, None)
    return prefs


def merge_imported_prefs(prefs, imported):
    """Additively merge an imported ``dedrm.json`` dict into ``prefs``.

    Used to bring a whole DeDRM configuration over from desktop Calibre. Keys
    and list values are added (deduplicated; existing entries are kept), the
    post-processing flags are taken from the import when present, and
    ``configured`` is enabled if the import had any configuration. Unknown keys
    in the import are ignored. Returns ``(prefs, added_count)``.
    """
    if not isinstance(imported, dict):
        return prefs, 0
    added = 0
    for store in NAMED_KEY_STORES:
        bucket = imported.get(store)
        if isinstance(bucket, dict):
            for name, value in bucket.items():
                _, resolved = add_named_key(prefs, store, str(name), value)
                if resolved is not None:
                    added += 1
    for store in LIST_STORES:
        values = imported.get(store)
        if isinstance(values, list):
            for value in values:
                before = len(prefs.get(store, []))
                add_list_value(prefs, store, value)
                if len(prefs.get(store, [])) > before:
                    added += 1
    for flag in ("deobfuscate_fonts", "remove_watermarks"):
        if flag in imported:
            prefs[flag] = bool(imported[flag])
    if imported.get("configured") or added:
        prefs["configured"] = True
    # Carry over any friendly labels for matching values.
    labels = imported.get("cwa_labels")
    if isinstance(labels, dict):
        for store, mapping in labels.items():
            if isinstance(mapping, dict):
                for value, label in mapping.items():
                    set_label(prefs, store, value, label)
    return prefs, added
