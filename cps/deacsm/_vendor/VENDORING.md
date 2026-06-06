# Vendored DeACSM (ACSM Input) plugin — provenance & re-sync

The Python modules here are vendored from the **ACSM Input** plugin:

- **Upstream:** https://github.com/Leseratte10/acsm-calibre-plugin
- **Source path:** `calibre-plugin/`
- **Plugin version:** `0.1.0`
- **Vendored from commit:** `fb288afb3a83156f0e534eb1e0ec1cbc45a3e675` (2025-10-07)

DeACSM redeems Adobe `.acsm` fulfillment tokens against Adobe's servers and
downloads the actual (still Adobe-DRM) EPUB/PDF. The account's encryption key is
also what DeDRM needs to decrypt Adobe DRM, so activation auto-bridges that key
into `cps/dedrm` (see `cps/deacsm/__init__.py`).

## Bundled cryptography (important)

DeACSM needs `oscrypto`, which the official 1.3.0 release does NOT support on
OpenSSL 3. We therefore bundle the **forked oscrypto** and `asn1crypto` exactly
as upstream's `package_modules.sh` does:

- `oscrypto/`   — from `oscrypto_1.3.0_fork_2023-12-19.zip`
  (https://github.com/Leseratte10/acsm-calibre-plugin/releases/download/config/oscrypto_1.3.0_fork_2023-12-19.zip)
- `asn1crypto/` — from `asn1crypto_1.5.1.zip`
  (https://github.com/Leseratte10/acsm-calibre-plugin/releases/download/config/asn1crypto_1.5.1.zip)

`oscrypto` loads `libcrypto` via ctypes. Autodetection works on the project's
Debian/Ubuntu image (validated against OpenSSL 3.5.6). On unusual images the
`ACSM_LIBCRYPTO` / `ACSM_LIBSSL` env vars override the library paths (the engine
honours them, mirroring upstream).

## How these files were produced

1. Run upstream's compat-code expansion on every `.py` (replace the
   `#@@CALIBRE_COMPAT_CODE@@` line with `__calibre_compat_code.py`), same as the
   DeDRM vendoring (see `cps/dedrm/_vendor/VENDORING.md`).
2. Normalize line endings to LF.
3. Vendor only the headless core. **Excluded:** `config.py` / `gui_main*.py`
   (PyQt), `getEncryptionKeyWindows.py` / `exportPluginAuthToWindowsADE.py`
   (Windows), `register_ADE_account.py` / `fulfill.py` (CLIs),
   `keyextractDecryptor.py` + `keyextract/` + `*.exe` (Windows key tools).
   `standalone/jsonconfig.py` is copied from the DeDRM vendoring to provide a
   Calibre-free `JSONConfig`.

## Re-syncing

```sh
git clone --depth 1 https://github.com/Leseratte10/acsm-calibre-plugin.git
# re-download the bundled oscrypto fork + asn1crypto (see package_modules.sh),
# then re-apply the compat-code expansion + LF normalization into this dir,
# keeping standalone/__init__.py (our stub) and standalone/jsonconfig.py.
```

After re-syncing, re-run the DeACSM engine `status` command headless to confirm
oscrypto still loads against the image's OpenSSL. Do NOT hand-edit the vendored
files; app glue lives in the parent package (`__init__.py`, `engine.py`,
`_calibre_shim.py`, `prefs_store.py`).
