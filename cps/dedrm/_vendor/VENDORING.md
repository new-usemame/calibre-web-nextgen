# Vendored DeDRM plugin — provenance & re-sync instructions

The Python modules in this directory are vendored verbatim from the **DeDRM
plugin** of the actively-maintained fork:

- **Upstream:** https://github.com/Satsuoni/DeDRM_tools
- **Source path in upstream:** `DeDRM_plugin/`
- **Plugin version:** `10.0.20` (see `__version.py`)
- **Vendored from commit:** `31f200058ee3f9e535d5a170f5ba44a706fa66d0`
  ("added gitattributes to hopefully avoid script breakage", 2026-05-24)

This fork merges many open upstream PRs and adds bugfixes/features on top of
`noDRM/DeDRM_tools`. Its device-side key-extraction tools (KFX extractor,
Frida scripts, C/C++ helpers under the repo's `Other_Tools/`) are **not**
vendored — they run on the user's Kindle/PC to obtain keys, which are then
entered into the Calibre-Web DeDRM admin page. Only the file-decryption plugin
code lives here.

## How these files were produced

Upstream ships each `.py` with a one-line placeholder `#@@CALIBRE_COMPAT_CODE@@`
that its `make_release.py` build step expands into the real Calibre-compat
block (from `DeDRM_plugin/__calibre_compat_code.py`). We reproduce exactly that
build step so the vendored files are the *built* form the plugin actually runs
as — the expanded block sets `__package__ = "calibre_plugins.dedrm"` and the
`sys.path` entries our headless engine relies on.

Transformations applied when vendoring:
1. Run the upstream `patch_file` expansion on every `.py` (replace the
   `#@@CALIBRE_COMPAT_CODE@@` line with the compat block).
2. Normalize all line endings to LF.
3. **Exclude** files we do not use:
   - `config.py` — the PyQt5 configuration widget (replaced by our native web
     UI under `cps/templates/config_dedrm.html`).
   - `__main__.py`, `scriptinterface.py` — CLI entry points we do not call.
   - `standalone/__init__.py`, `standalone/passhash.py`,
     `standalone/remove_drm.py` — the upstream "standalone" CLI (explicitly
     marked unfinished upstream). Only `standalone/jsonconfig.py` is kept (a
     Calibre-free `JSONConfig`); `standalone/__init__.py` here is our own empty
     package stub.

## Re-syncing to a newer upstream commit

```sh
git clone --depth 1 https://github.com/Satsuoni/DeDRM_tools.git
# then re-run the vendoring transform (see the repo's scripts / commit history
# for the helper that applied steps 1-3 above) targeting cps/dedrm/_vendor/,
# keeping the standalone/__init__.py stub.
```

After re-syncing, re-run `tests/unit/test_dedrm_slice1.py` (engine passthrough
+ import isolation) to confirm the shim still loads the modules cleanly.

Do **not** hand-edit the vendored `.py` files; keep changes upstream so a
re-sync stays a clean overwrite. App-specific glue lives in the parent package
(`cps/dedrm/__init__.py`, `engine.py`, `_calibre_shim.py`, `prefs_store.py`).
