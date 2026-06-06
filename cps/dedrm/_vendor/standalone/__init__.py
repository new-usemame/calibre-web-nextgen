# -*- coding: utf-8 -*-

# Package stub for the vendored DeDRM "standalone" helpers.
#
# Upstream DeDRM ships a `standalone/` package whose __init__ implements an
# (explicitly unfinished) command-line interface. Calibre-Web-NextGen does not
# use that CLI, so the original __init__ is intentionally NOT vendored. We keep
# this empty package marker only so that `standalone.jsonconfig` remains
# importable as a submodule (DeDRM's prefs.py falls back to it when Calibre is
# not available).
