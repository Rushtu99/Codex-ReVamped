#!/data/data/com.termux/files/usr/bin/python
from __future__ import annotations

import base64
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


HOME = Path.home()
LB_DIR = HOME / ".codex-lb"
DB_PATH = LB_DIR / "store.db"
KEY_PATH = LB_DIR / "encryption.key"
BUNDLE_PATH = HOME / ".codex-portable-setup" / "accounts.seed.json"

BLOB_FIELDS = {
    "access_token_encrypted",
    "refresh_token_encrypted",
    "id_token_encrypted",
}


def encode_value(key: str, value: object) -> object:
    if value is None:
        return None
    if key in BLOB_FIELDS:
        return base64.b64encode(value).decode("ascii")
    return value


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Account database not found: {DB_PATH}")
    if not KEY_PATH.exists():
        raise SystemExit(f"Encryption key not found: {KEY_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
              id,
              chatgpt_account_id,
              email,
              plan_type,
              access_token_encrypted,
              refresh_token_encrypted,
              id_token_encrypted,
              last_refresh,
              created_at,
              status,
              deactivation_reason,
              reset_at
            FROM accounts
            ORDER BY created_at, email
            """
        ).fetchall()
    finally:
        conn.close()

    bundle = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        # Account token blobs are only portable when the matching key is restored.
        "encryption_key_b64": base64.b64encode(KEY_PATH.read_bytes()).decode("ascii"),
        "accounts": [
            {key: encode_value(key, row[key]) for key in row.keys()}
            for row in rows
        ],
    }

    BUNDLE_PATH.write_text(json.dumps(bundle, indent=2) + "\n")
    print(f"Wrote {len(bundle['accounts'])} account(s) to {BUNDLE_PATH}")


if __name__ == "__main__":
    main()
