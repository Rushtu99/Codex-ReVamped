#!/data/data/com.termux/files/usr/bin/python
from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path


HOME = Path.home()
PORTABLE_DIR = HOME / ".codex-portable-setup"
LB_DIR = HOME / ".codex-lb"
BUNDLE_PATH = PORTABLE_DIR / "accounts.seed.json"
DB_PATH = LB_DIR / "store.db"
KEY_PATH = LB_DIR / "encryption.key"

BLOB_FIELDS = {
    "access_token_encrypted",
    "refresh_token_encrypted",
    "id_token_encrypted",
}

ACCOUNT_COLUMNS = [
    "id",
    "chatgpt_account_id",
    "email",
    "plan_type",
    "access_token_encrypted",
    "refresh_token_encrypted",
    "id_token_encrypted",
    "last_refresh",
    "created_at",
    "status",
    "deactivation_reason",
    "reset_at",
]

CREATE_ACCOUNTS_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
  id VARCHAR PRIMARY KEY NOT NULL,
  chatgpt_account_id VARCHAR,
  email VARCHAR NOT NULL,
  plan_type VARCHAR NOT NULL,
  access_token_encrypted BLOB NOT NULL,
  refresh_token_encrypted BLOB NOT NULL,
  id_token_encrypted BLOB NOT NULL,
  last_refresh DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(14) NOT NULL,
  deactivation_reason TEXT,
  reset_at INTEGER
)
"""

UPSERT_SQL = """
INSERT INTO accounts (
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
) VALUES (
  :id,
  :chatgpt_account_id,
  :email,
  :plan_type,
  :access_token_encrypted,
  :refresh_token_encrypted,
  :id_token_encrypted,
  :last_refresh,
  :created_at,
  :status,
  :deactivation_reason,
  :reset_at
)
ON CONFLICT(id) DO UPDATE SET
  chatgpt_account_id = excluded.chatgpt_account_id,
  email = excluded.email,
  plan_type = excluded.plan_type,
  access_token_encrypted = excluded.access_token_encrypted,
  refresh_token_encrypted = excluded.refresh_token_encrypted,
  id_token_encrypted = excluded.id_token_encrypted,
  last_refresh = excluded.last_refresh,
  created_at = excluded.created_at,
  status = excluded.status,
  deactivation_reason = excluded.deactivation_reason,
  reset_at = excluded.reset_at
"""


def decode_account(raw: dict[str, object]) -> dict[str, object]:
    account: dict[str, object] = {}
    for key in ACCOUNT_COLUMNS:
        value = raw.get(key)
        if key in BLOB_FIELDS and value is not None:
            account[key] = base64.b64decode(value)
        else:
            account[key] = value
    return account


def ensure_key(bundle: dict[str, object]) -> None:
    key_bytes = base64.b64decode(bundle["encryption_key_b64"])
    if KEY_PATH.exists():
        existing = KEY_PATH.read_bytes()
        if existing != key_bytes:
            raise SystemExit(
                "Existing ~/.codex-lb/encryption.key does not match accounts.seed.json; "
                "refusing to import incompatible encrypted account blobs."
            )
        return
    KEY_PATH.write_bytes(key_bytes)


def main() -> None:
    if not BUNDLE_PATH.exists():
        print(f"No account bundle found at {BUNDLE_PATH}; nothing to import.")
        return

    bundle = json.loads(BUNDLE_PATH.read_text())
    accounts = bundle.get("accounts", [])
    if not isinstance(accounts, list):
        raise SystemExit("accounts.seed.json is invalid: 'accounts' must be a list.")

    LB_DIR.mkdir(parents=True, exist_ok=True)
    ensure_key(bundle)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(CREATE_ACCOUNTS_SQL)
        imported = 0
        for raw in accounts:
            conn.execute(UPSERT_SQL, decode_account(raw))
            imported += 1
        conn.commit()
    finally:
        conn.close()

    print(f"Imported {imported} account(s) from {BUNDLE_PATH}")


if __name__ == "__main__":
    main()
