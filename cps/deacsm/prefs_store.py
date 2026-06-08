# -*- coding: utf-8 -*-

"""Calibre-free persistence + paths for the vendored DeACSM (ACSM Input) plugin.

Like ``cps.dedrm.prefs_store``, this is a lightweight layer shared by the Flask
app and the ingest worker. It never imports the vendored DeACSM modules. The
DeACSM engine subprocess points Calibre's ``config_dir`` at :data:`DEACSM_DIR`,
so the plugin's own ``ACSMInput_Prefs`` reads/writes the same JSON this module
manages.

Activation state is NOT a JSON flag — it is the presence of the Adobe device
files (``device.xml`` + ``activation.xml``) in the account folder, so
:func:`is_activated` checks those directly.
"""

import os
import json
import errno
import tempfile
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None

# Resolve config directory the same way the ingest worker's get_app_db_path()
# does — cannot rely on cps.constants.CONFIG_DIR because CALIBRE_DBPATH is
# only exported for the Flask process (svc-calibre-web-automated/run) and
# not for the ingest-service subprocess, so BASE_DIR would be picked up
# there instead of /config.
CONFIG_DIR = os.environ.get("CALIBRE_DBPATH", "/config")

# Everything DeACSM-related for this install lives here.
DEACSM_DIR = os.path.join(CONFIG_DIR, "deacsm")

# DeACSM's own layout under config_dir: prefs JSON and the Adobe account folder.
PLUGIN_DIR = os.path.join(DEACSM_DIR, "plugins", "ACSMInput")
PREFS_PATH = os.path.join(PLUGIN_DIR, "ACSMInput.json")
ACCOUNT_DIR = os.path.join(PLUGIN_DIR, "account")

# Adobe activation artefacts that prove the account is set up.
DEVICE_XML = os.path.join(ACCOUNT_DIR, "device.xml")
ACTIVATION_XML = os.path.join(ACCOUNT_DIR, "activation.xml")
DEVICE_KEY = os.path.join(ACCOUNT_DIR, "devicesalt")

_DIR_MODE = 0o700

# Default preferences, mirroring DeACSM's ``ACSMInput_Prefs`` defaults.
DEFAULTS = {
    "configured": False,
    "notify_fulfillment": True,
    "detailed_logging": False,
    "delete_acsm_after_fulfill": False,
    "list_of_rented_books": [],
    "path_to_account_data": ACCOUNT_DIR,
    # App-private cache (not read by DeACSM) populated at activation time so the
    # admin page can show the account without spawning the engine.
    "account_uuid": None,
    "account_type": None,
    "account_email": None,
}


def _ensure_dir(path, mode=_DIR_MODE):
    try:
        os.makedirs(path, mode=mode)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise


def ensure_dirs():
    """Create the plugin + account directories DeACSM expects."""
    _ensure_dir(ACCOUNT_DIR)


@contextmanager
def _locked(lock_path, exclusive):
    if fcntl is None:  # pragma: no cover
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
    """Return the full preferences dict with defaults filled in."""
    prefs = {}
    for key, value in DEFAULTS.items():
        prefs[key] = list(value) if isinstance(value, list) else value

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
            pass
    # The account path is install-specific; always force our canonical location.
    prefs["path_to_account_data"] = ACCOUNT_DIR
    return prefs


def save_prefs(prefs):
    """Atomically persist ``prefs`` to :data:`PREFS_PATH`."""
    _ensure_dir(os.path.dirname(PREFS_PATH))
    with _locked(_lock_path(), exclusive=True):
        fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(PREFS_PATH), prefix=".acsm-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(prefs, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, PREFS_PATH)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def is_activated():
    """Return ``True`` when an Adobe account/device has been activated.

    The signal is the presence of the Adobe device files, not a JSON flag.
    """
    return os.path.exists(DEVICE_XML) and os.path.exists(ACTIVATION_XML)
