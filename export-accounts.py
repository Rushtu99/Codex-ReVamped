#!/data/data/com.termux/files/usr/bin/python
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import SplitResult, urlsplit, urlunsplit


SCRIPT_DIR = Path(__file__).resolve().parent
TERMUX_HOME = Path("/data/data/com.termux/files/home")
DEFAULT_BUNDLE_PATH = Path.home() / ".codex-revamped" / "accounts.seed.json"
DEFAULT_DB_URL = "sqlite+aiosqlite:///~/.codex-lb/store.db"
DEFAULT_KEY_FILE = "~/.codex-lb/encryption.key"

BLOB_FIELDS = {
    "access_token_encrypted",
    "refresh_token_encrypted",
    "id_token_encrypted",
}


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


def redact_db_url(db_url: str) -> str:
    parsed = urlsplit(db_url)
    if "@" not in parsed.netloc or ":" not in parsed.netloc:
        return db_url
    userinfo, hostinfo = parsed.netloc.rsplit("@", 1)
    username = userinfo.split(":", 1)[0]
    redacted = f"{username}:***@{hostinfo}"
    replaced = SplitResult(parsed.scheme, redacted, parsed.path, parsed.query, parsed.fragment)
    return urlunsplit(replaced)


def normalize_backend(db_url: str) -> str:
    lowered = db_url.lower()
    if lowered.startswith("sqlite+aiosqlite:///") or lowered.startswith("sqlite:///"):
        return "sqlite"
    raise SystemExit(f"Unsupported database URL scheme for exporter: {db_url}")


def sqlite_path_from_url(db_url: str, lb_dir_hint: Path | None = None) -> Path:
    if not db_url.startswith("sqlite"):
        raise SystemExit(f"Not a sqlite URL: {db_url}")
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


def discover_running_codex_lb_env() -> dict[str, str]:
    proc_dir = Path("/proc")
    if not proc_dir.exists():
        return {}

    candidates: list[int] = []
    for entry in proc_dir.iterdir():
        if not entry.name.isdigit():
            continue
        cmdline_path = entry / "cmdline"
        try:
            cmdline_raw = cmdline_path.read_bytes()
        except OSError:
            continue
        if not cmdline_raw:
            continue
        cmdline = [part.decode("utf-8", errors="ignore") for part in cmdline_raw.split(b"\x00") if part]
        joined = " ".join(cmdline).lower()
        if "codex-lb" in joined:
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


def resolve_storage_paths(args: argparse.Namespace) -> tuple[str, Path, Path]:
    db_url: str | None = None
    key_file: str | None = None

    if args.db_url:
        db_url = args.db_url
    if args.key_file:
        key_file = args.key_file

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
    backend = normalize_backend(db_url)
    if backend != "sqlite":
        raise SystemExit("Only sqlite backends are supported by export-accounts.py")

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

    return db_url, db_path, key_path


def encode_value(key: str, value: object) -> object:
    if value is None:
        return None
    if key in BLOB_FIELDS:
        return base64.b64encode(value).decode("ascii")
    return value


def decode_value(key: str, value: object) -> object:
    if value is None:
        return None
    if key in BLOB_FIELDS and isinstance(value, str):
        return base64.b64decode(value)
    return value


def load_existing_bundle(bundle_path: Path) -> dict[str, object] | None:
    if not bundle_path.exists():
        return None

    try:
        bundle = json.loads(bundle_path.read_text())
    except json.JSONDecodeError:
        return None

    if not isinstance(bundle, dict):
        return None

    return bundle


def merge_existing_accounts(existing_bundle: dict[str, object] | None) -> dict[str, dict[str, object]]:
    merged: dict[str, dict[str, object]] = {}
    if not existing_bundle:
        return merged

    accounts = existing_bundle.get("accounts", [])
    if not isinstance(accounts, list):
        return merged

    for raw in accounts:
        if not isinstance(raw, dict):
            continue
        account_id = raw.get("id")
        if not isinstance(account_id, str) or not account_id:
            continue
        merged[account_id] = {
            key: decode_value(key, raw.get(key))
            for key in (
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
            )
        }

    return merged


def write_bundle(args: argparse.Namespace) -> None:
    db_url, db_path, key_path = resolve_storage_paths(args)
    bundle_path = Path(args.bundle).expanduser() if args.bundle else DEFAULT_BUNDLE_PATH

    if not db_path.exists():
        raise SystemExit(f"Account database not found: {db_path}")
    if not key_path.exists():
        raise SystemExit(f"Encryption key not found: {key_path}")

    existing_bundle = load_existing_bundle(bundle_path)
    if existing_bundle is not None:
        existing_key = existing_bundle.get("encryption_key_b64")
        current_key = base64.b64encode(key_path.read_bytes()).decode("ascii")
        if existing_key is not None and existing_key != current_key:
            raise SystemExit(
                "Existing accounts.seed.json uses a different encryption key; "
                "refusing to merge incompatible account blobs."
            )

    conn = sqlite3.connect(db_path)
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

    merged_accounts = merge_existing_accounts(existing_bundle)
    for row in rows:
        merged_accounts[row["id"]] = {
            key: row[key] for key in row.keys()
        }

    ordered_accounts = sorted(
        merged_accounts.values(),
        key=lambda account: (
            account.get("created_at") or "",
            account.get("email") or "",
            account.get("id") or "",
        ),
    )

    bundle = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        # Account token blobs are only portable when the matching key is restored.
        "encryption_key_b64": base64.b64encode(key_path.read_bytes()).decode("ascii"),
        "accounts": [
            {
                key: encode_value(key, account.get(key))
                for key in (
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
                )
            }
            for account in ordered_accounts
        ],
    }

    prior_owner: tuple[int, int, int] | None = None
    if bundle_path.exists():
        stat_result = bundle_path.stat()
        prior_owner = (
            stat_result.st_uid,
            stat_result.st_gid,
            stat_result.st_mode & 0o777,
        )

    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = bundle_path.with_name(f"{bundle_path.name}.tmp")
    tmp_path.write_text(json.dumps(bundle, indent=2) + "\n")
    tmp_path.replace(bundle_path)
    if prior_owner is not None:
        uid, gid, mode = prior_owner
        try:
            os.chown(bundle_path, uid, gid)
        except OSError:
            pass
        try:
            os.chmod(bundle_path, mode)
        except OSError:
            pass
    print(f"Export source: {redact_db_url(db_url)}")
    print(f"Resolved DB: {db_path}")
    print(f"Resolved key: {key_path}")
    print(f"Wrote {len(bundle['accounts'])} account(s) to {bundle_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export codex-lb accounts to the managed bundle.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="retained for compatibility; exporter always merges when keys match",
    )
    parser.add_argument("--db-url", help="Explicit codex-lb sqlite DB URL override")
    parser.add_argument("--key-file", help="Explicit codex-lb encryption key file override")
    parser.add_argument(
        "--bundle",
        help="Output bundle path (default: ~/.codex-revamped/accounts.seed.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_bundle(args)


if __name__ == "__main__":
    main()
