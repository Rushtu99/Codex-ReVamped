#!/data/data/com.termux/files/usr/bin/python
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit


SCRIPT_DIR = Path(__file__).resolve().parent
TERMUX_HOME = Path("/data/data/com.termux/files/home")
DEFAULT_BUNDLE_PATH = Path.home() / ".codex-revamped" / "accounts.seed.json"
DEFAULT_DB_URL = "sqlite+aiosqlite:///~/.codex-lb/store.db"

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import managed accounts.seed.json into codex-lb sqlite storage.")
    parser.add_argument("--db-url", help="Explicit codex-lb sqlite DB URL override")
    parser.add_argument("--key-file", help="Explicit codex-lb encryption key file override")
    parser.add_argument(
        "--bundle",
        help="Input bundle path (default: ~/.codex-revamped/accounts.seed.json)",
    )
    return parser.parse_args()


def read_kv_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        if not path.exists():
            return values
    except OSError:
        return values
    try:
        raw_text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return values
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def sqlite_path_from_url(db_url: str, lb_dir_hint: Path | None = None) -> Path:
    if not db_url.startswith("sqlite"):
        raise SystemExit(f"Unsupported database URL for importer: {db_url}")
    marker = ":///"
    marker_index = db_url.find(marker)
    if marker_index < 0:
        raise SystemExit(f"Cannot parse sqlite path from URL: {db_url}")
    raw_path = db_url[marker_index + len(marker) :].partition("?")[0].partition("#")[0]
    if raw_path.startswith("/~"):
        raw_path = raw_path[1:]
    if raw_path.startswith("~/.codex-lb/") and lb_dir_hint is not None:
        return lb_dir_hint / raw_path.split("~/.codex-lb/", 1)[1]
    if raw_path == ":memory:":
        raise SystemExit("In-memory sqlite URLs are not supported.")
    return Path(raw_path).expanduser()


def key_path_from_value(value: str, lb_dir_hint: Path | None = None) -> Path:
    if value.startswith("~/.codex-lb/") and lb_dir_hint is not None:
        return lb_dir_hint / value.split("~/.codex-lb/", 1)[1]
    return Path(value).expanduser()


def discover_running_codex_lb_env() -> dict[str, str]:
    proc_dir = Path("/proc")
    if not proc_dir.exists():
        return {}

    candidates: list[int] = []
    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline_raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        if not cmdline_raw:
            continue
        cmdline = [part.decode("utf-8", errors="ignore") for part in cmdline_raw.split(b"\x00") if part]
        if "codex-lb" in " ".join(cmdline).lower():
            candidates.append(int(entry.name))

    for pid in sorted(candidates, reverse=True):
        env_path = proc_dir / str(pid) / "environ"
        try:
            raw = env_path.read_bytes()
        except OSError:
            continue
        env_map: dict[str, str] = {}
        for part in raw.split(b"\x00"):
            if not part or b"=" not in part:
                continue
            key, value = part.split(b"=", 1)
            env_map[key.decode("utf-8", errors="ignore")] = value.decode("utf-8", errors="ignore")
        if "CODEX_LB_DATABASE_URL" in env_map or "CODEX_LB_ENCRYPTION_KEY_FILE" in env_map:
            return env_map
    return {}


def iter_runtime_env_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_path = os.environ.get("CODEX_RUNTIME_ENV")
    if env_path:
        candidates.append(Path(env_path))
    portable_override = os.environ.get("CODEX_PORTABLE_SETUP_DIR")
    if portable_override:
        candidates.append(Path(portable_override) / "runtime.env")
    candidates.append(SCRIPT_DIR / "runtime.env")
    candidates.append(Path.home() / ".codex-revamped" / "runtime.env")
    candidates.append(Path.home() / ".codex-portable-setup" / "runtime.env")
    candidates.append(TERMUX_HOME / ".codex-portable-setup" / "runtime.env")
    candidates.append(TERMUX_HOME / ".suroot" / ".codex-portable-setup" / "runtime.env")

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        deduped.append(candidate)
        seen.add(candidate)
    return deduped


def candidate_lb_dirs(proc_env: dict[str, str] | None = None) -> list[Path]:
    dirs: list[Path] = []
    if proc_env and proc_env.get("HOME"):
        dirs.append(Path(proc_env["HOME"]) / ".codex-lb")

    env_dir = os.environ.get("CODEX_LB_DIR")
    if env_dir:
        dirs.append(Path(env_dir))

    for runtime_env in iter_runtime_env_candidates():
        values = read_kv_env_file(runtime_env)
        runtime_lb_dir = values.get("CODEX_LB_DIR")
        if runtime_lb_dir:
            dirs.append(Path(runtime_lb_dir))

    dirs.append(Path.home() / ".codex-lb")
    dirs.append(TERMUX_HOME / ".codex-lb")
    dirs.append(TERMUX_HOME / ".suroot" / ".codex-lb")

    deduped: list[Path] = []
    seen: set[Path] = set()
    for lb_dir in dirs:
        if lb_dir in seen:
            continue
        deduped.append(lb_dir)
        seen.add(lb_dir)
    return deduped


def resolve_storage_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    db_url: str | None = args.db_url
    key_file: str | None = args.key_file

    if db_url is None and os.environ.get("CODEX_LB_DATABASE_URL"):
        db_url = os.environ["CODEX_LB_DATABASE_URL"]
    if key_file is None and os.environ.get("CODEX_LB_ENCRYPTION_KEY_FILE"):
        key_file = os.environ["CODEX_LB_ENCRYPTION_KEY_FILE"]

    proc_env = discover_running_codex_lb_env()
    if db_url is None and proc_env.get("CODEX_LB_DATABASE_URL"):
        db_url = proc_env["CODEX_LB_DATABASE_URL"]
    if key_file is None and proc_env.get("CODEX_LB_ENCRYPTION_KEY_FILE"):
        key_file = proc_env["CODEX_LB_ENCRYPTION_KEY_FILE"]

    lb_dirs = candidate_lb_dirs(proc_env=proc_env)
    for lb_dir in lb_dirs:
        env_values = read_kv_env_file(lb_dir / ".env")
        if db_url is None and env_values.get("CODEX_LB_DATABASE_URL"):
            db_url = env_values["CODEX_LB_DATABASE_URL"]
        if key_file is None and env_values.get("CODEX_LB_ENCRYPTION_KEY_FILE"):
            key_file = env_values["CODEX_LB_ENCRYPTION_KEY_FILE"]

    if db_url is None:
        db_url = DEFAULT_DB_URL
    if not urlsplit(db_url).scheme.startswith("sqlite"):
        raise SystemExit("Only sqlite backends are supported by import-accounts.py")

    db_path: Path | None = None
    for lb_dir in lb_dirs:
        try:
            db_path = sqlite_path_from_url(db_url, lb_dir_hint=lb_dir)
            if db_path.exists():
                break
        except SystemExit:
            raise
        except Exception:
            continue
    if db_path is None:
        db_path = sqlite_path_from_url(db_url)

    if key_file is None:
        key_path = db_path.parent / "encryption.key"
    else:
        key_path = key_path_from_value(key_file, lb_dir_hint=db_path.parent)

    return db_path, key_path


def decode_account(raw: dict[str, object]) -> dict[str, object]:
    account: dict[str, object] = {}
    for key in ACCOUNT_COLUMNS:
        value = raw.get(key)
        if key in BLOB_FIELDS and value is not None:
            account[key] = base64.b64decode(value)
        else:
            account[key] = value
    return account


def ensure_key(bundle: dict[str, object], key_path: Path) -> None:
    key_bytes = base64.b64decode(bundle["encryption_key_b64"])
    if key_path.exists():
        existing = key_path.read_bytes()
        if existing != key_bytes:
            raise SystemExit(
                f"Existing key at {key_path} does not match accounts.seed.json; "
                "refusing to import incompatible encrypted account blobs."
            )
        return
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key_bytes)


def main() -> None:
    args = parse_args()
    bundle_path = Path(args.bundle).expanduser() if args.bundle else DEFAULT_BUNDLE_PATH
    db_path, key_path = resolve_storage_paths(args)

    if not bundle_path.exists():
        print(f"No account bundle found at {bundle_path}; nothing to import.")
        return

    bundle = json.loads(bundle_path.read_text())
    accounts = bundle.get("accounts", [])
    if not isinstance(accounts, list):
        raise SystemExit("accounts.seed.json is invalid: 'accounts' must be a list.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_key(bundle, key_path)

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(CREATE_ACCOUNTS_SQL)
        imported = 0
        for raw in accounts:
            conn.execute(UPSERT_SQL, decode_account(raw))
            imported += 1
        conn.commit()
    finally:
        conn.close()

    print(f"Imported {imported} account(s) from {bundle_path} into {db_path}")


if __name__ == "__main__":
    main()
