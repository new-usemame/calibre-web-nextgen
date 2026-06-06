# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web-NextGen contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Fork #331 follow-up (@Gusdezup): Kobo sync fails behind reverse proxies
with default buffer sizes. Measured root cause: the x-kobo-synctoken
response header. Our own cursor fields are ~495B, but with Kobo store
proxying enabled the store's 3-part JWT (~2-2.5KB real-world, see
notes/KOBO-PROTOCOL-REFERENCE.md §3.1) is embedded in our JSON and then
base64'd AGAIN (+33% on the largest component) — pushing total response
headers past nginx's 4K default (`proxy_buffer_size`).

Fix: transport-level compression of the token. build_sync_token emits
`z1:` + b64(zlib(json)); from_headers sniffs the prefix and falls back to
the legacy plain-b64 parse for tokens already in the wild. Devices echo
the token opaquely — only this server parses it — so no device migration
exists. The schema VERSION is untouched (compression is transport, not
schema).

Sniff safety: the b64 alphabet (A-Za-z0-9+/=) contains neither ':' nor
'.', so `z1:`-prefixed tokens can't collide with legacy b64 tokens, and
the existing dotted kobo-store-token path ('.' in token) stays reachable.
"""

import json
import zlib
from base64 import b64decode, b64encode
from datetime import datetime

import pytest

from cps.services.SyncToken import SyncToken, to_epoch_timestamp


def _legacy_header(data: dict) -> str:
    """Build a token exactly the way pre-#331 servers did (plain b64 JSON)."""
    return b64encode(json.dumps(
        {"version": "1-4-0", "data": data}).encode()).decode()


def _data(store_token=""):
    now = datetime(2026, 6, 7, 1, 0, 0)
    return {
        "raw_kobo_store_token": store_token,
        "books_last_modified": to_epoch_timestamp(now),
        "books_last_created": to_epoch_timestamp(now),
        "archive_last_modified": to_epoch_timestamp(now),
        "reading_state_last_modified": to_epoch_timestamp(now),
        "tags_last_modified": to_epoch_timestamp(now),
        "books_last_id": 42,
        "magic_shelf_last_id": 7,
        "magic_shelf_membership_at": to_epoch_timestamp(now),
    }


def _fake_store_jwt(size=2400):
    """Synthetic 3-part JWT shaped like the real store token (b64ish text)."""
    part = b64encode(b"x" * (size // 2)).decode()
    return "eyJhbGciOiJSUzI1NiJ9." + part[:size - 60] + ".sig"


@pytest.mark.unit
class TestLegacyTokensStillParse:
    def test_legacy_plain_b64_parses_with_all_fields(self):
        """Tokens already on devices in the wild MUST keep parsing."""
        header = _legacy_header(_data(store_token="abc"))
        tok = SyncToken.from_headers({SyncToken.SYNC_TOKEN_HEADER: header})
        assert tok.books_last_id == 42
        assert tok.magic_shelf_last_id == 7
        assert tok.raw_kobo_store_token == "abc"

    def test_dotted_store_token_passthrough_unchanged(self):
        header = "storepart1.storepart2"
        tok = SyncToken.from_headers({SyncToken.SYNC_TOKEN_HEADER: header})
        assert tok.raw_kobo_store_token == header


@pytest.mark.unit
class TestCompressedTokens:
    def test_round_trip(self):
        src = SyncToken(
            raw_kobo_store_token=_fake_store_jwt(),
            books_last_id=42,
            magic_shelf_last_id=7,
        )
        header = src.build_sync_token()
        assert header.startswith("z1:"), (
            "build_sync_token must emit the compressed transport format"
        )
        out = SyncToken.from_headers({SyncToken.SYNC_TOKEN_HEADER: header})
        assert out.books_last_id == 42
        assert out.magic_shelf_last_id == 7
        assert out.raw_kobo_store_token == src.raw_kobo_store_token

    def test_oversized_store_token_fits_4k_budget(self):
        """The reporter-mirror case: a realistic ~2.4KB store JWT must leave
        the whole header value comfortably inside nginx's 4K default once
        cookies (~300B) + CSP (~140B) + the rest (~400B) are accounted
        for. Budget: token value < 3000 bytes."""
        src = SyncToken(raw_kobo_store_token=_fake_store_jwt(2400))
        header = src.build_sync_token()
        assert len(header) < 3000, (
            f"compressed token is {len(header)}B — must stay under the 3000B "
            "budget so total response headers fit nginx's 4K default"
        )

    def test_compression_beats_legacy_encoding(self):
        src = SyncToken(raw_kobo_store_token=_fake_store_jwt(2400))
        compressed = src.build_sync_token()
        legacy = b64encode(json.dumps(
            {"version": SyncToken.VERSION, "data": _data(_fake_store_jwt(2400))}
        ).encode()).decode()
        assert len(compressed) < len(legacy) * 0.75, (
            "compression must beat the legacy double-b64 encoding by a "
            "meaningful margin"
        )

    def test_garbage_after_marker_degrades_to_fresh_token(self):
        tok = SyncToken.from_headers({SyncToken.SYNC_TOKEN_HEADER: "z1:!!!notb64!!!"})
        assert tok.books_last_id == -1
        assert tok.books_last_modified == datetime.min

    def test_truncated_compressed_token_degrades_cleanly(self):
        """A proxy that truncates the header (the original failure class)
        must yield a fresh token, not a 500."""
        src = SyncToken(raw_kobo_store_token=_fake_store_jwt())
        header = src.build_sync_token()
        tok = SyncToken.from_headers({SyncToken.SYNC_TOKEN_HEADER: header[:len(header) // 2]})
        assert tok.books_last_modified == datetime.min

    def test_schema_version_untouched(self):
        """Compression is transport-level: the inner schema VERSION must
        stay 1-4-0 so version-gated logic is unaffected."""
        assert SyncToken.VERSION == "1-4-0"
        src = SyncToken(books_last_id=1)
        header = src.build_sync_token()
        raw = zlib.decompress(b64decode(header[3:]))
        assert json.loads(raw)["version"] == "1-4-0"
