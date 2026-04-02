#!/data/data/com.termux/files/usr/bin/python
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


HOME = Path.home()
TERMUX_HOME = Path("/data/data/com.termux/files/home")


def path_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def read_kv_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path_exists(path):
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


def runtime_env_candidates() -> list[Path]:
    candidates: list[Path] = []
    runtime_env = os.environ.get("CODEX_RUNTIME_ENV")
    if runtime_env:
        candidates.append(Path(runtime_env))
    portable_override = os.environ.get("CODEX_PORTABLE_SETUP_DIR")
    if portable_override:
        candidates.append(Path(portable_override) / "runtime.env")
    candidates.append(HOME / ".codex-revamped" / "runtime.env")
    candidates.append(HOME / ".codex-portable-setup" / "runtime.env")
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


def resolve_portable_dir(runtime_values: dict[str, str]) -> Path:
    candidates: list[Path] = []
    if os.environ.get("CODEX_PORTABLE_SETUP_DIR"):
        candidates.append(Path(os.environ["CODEX_PORTABLE_SETUP_DIR"]))
    if runtime_values.get("CODEX_PORTABLE_DIR"):
        candidates.append(Path(runtime_values["CODEX_PORTABLE_DIR"]))
    if os.environ.get("CODEX_RUNTIME_ENV"):
        candidates.append(Path(os.environ["CODEX_RUNTIME_ENV"]).expanduser().resolve().parent)
    candidates.append(HOME / ".codex-revamped")
    candidates.append(HOME / ".codex-portable-setup")
    candidates.append(TERMUX_HOME / ".codex-portable-setup")
    candidates.append(TERMUX_HOME / ".suroot" / ".codex-portable-setup")

    for candidate in candidates:
        export_script = candidate / "export-accounts.py"
        if path_exists(export_script):
            return candidate
    return candidates[0]


def sqlite_path_from_url(db_url: str, lb_dir_hint: Path | None = None) -> Path:
    marker = ":///"
    marker_index = db_url.find(marker)
    if marker_index < 0:
        raise ValueError(f"Cannot parse sqlite path from URL: {db_url}")
    raw_path = db_url[marker_index + len(marker) :].partition("?")[0].partition("#")[0]
    if raw_path.startswith("/~"):
        raw_path = raw_path[1:]
    if raw_path.startswith("~/.codex-lb/") and lb_dir_hint is not None:
        return lb_dir_hint / raw_path.split("~/.codex-lb/", 1)[1]
    return Path(raw_path).expanduser()


def resolve_lb_dir(runtime_values: dict[str, str]) -> Path:
    candidates: list[Path] = []
    if os.environ.get("CODEX_LB_DIR"):
        candidates.append(Path(os.environ["CODEX_LB_DIR"]))
    if runtime_values.get("CODEX_LB_DIR"):
        candidates.append(Path(runtime_values["CODEX_LB_DIR"]))
    candidates.append(HOME / ".codex-lb")
    candidates.append(TERMUX_HOME / ".codex-lb")
    candidates.append(TERMUX_HOME / ".suroot" / ".codex-lb")

    for candidate in candidates:
        if path_exists(candidate / "store.db") or path_exists(candidate / ".env"):
            return candidate
    return candidates[0]


def resolve_db_and_key(lb_dir: Path, runtime_values: dict[str, str]) -> tuple[str, Path, Path]:
    db_url = os.environ.get("CODEX_LB_DATABASE_URL")
    key_value = os.environ.get("CODEX_LB_ENCRYPTION_KEY_FILE")

    env_file = Path(
        os.environ.get("CODEX_LB_ENV_FILE")
        or runtime_values.get("CODEX_LB_ENV_FILE")
        or lb_dir / ".env"
    )
    env_values = read_kv_env_file(env_file)
    if db_url is None and env_values.get("CODEX_LB_DATABASE_URL"):
        db_url = env_values["CODEX_LB_DATABASE_URL"]
    if key_value is None and env_values.get("CODEX_LB_ENCRYPTION_KEY_FILE"):
        key_value = env_values["CODEX_LB_ENCRYPTION_KEY_FILE"]

    if db_url is None:
        db_url = f"sqlite+aiosqlite:////{(lb_dir / 'store.db').as_posix().lstrip('/')}"
    if not urlsplit(db_url).scheme.startswith("sqlite"):
        raise SystemExit(f"Unsupported backend for account sync helper: {db_url}")

    db_path = sqlite_path_from_url(db_url, lb_dir_hint=lb_dir)
    if key_value is None:
        key_path = lb_dir / "encryption.key"
    elif key_value.startswith("~/.codex-lb/"):
        key_path = lb_dir / key_value.split("~/.codex-lb/", 1)[1]
    else:
        key_path = Path(key_value).expanduser()

    return db_url, db_path, key_path


def watched_paths(db_path: Path, key_path: Path) -> list[Path]:
    return [
        db_path,
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
        key_path,
    ]


def snapshot(paths: list[Path]) -> tuple[tuple[str, int | None, int | None], ...]:
    state: list[tuple[str, int | None, int | None]] = []
    for path in paths:
        try:
            if path.exists():
                stat = path.stat()
                state.append((str(path), stat.st_mtime_ns, stat.st_size))
                continue
        except OSError:
            pass
        state.append((str(path), None, None))
    return tuple(state)


def export_accounts(export_script: Path, db_url: str, key_path: Path) -> None:
    if not path_exists(export_script):
        raise SystemExit(f"Export script not found: {export_script}")

    subprocess.run(
        [
            sys.executable,
            str(export_script),
            "--db-url",
            db_url,
            "--key-file",
            str(key_path),
        ],
        check=True,
    )


def main() -> None:
    runtime_values: dict[str, str] = {}
    for candidate in runtime_env_candidates():
        values = read_kv_env_file(candidate)
        if values:
            runtime_values = values
            break

    portable_dir = resolve_portable_dir(runtime_values)
    lb_dir = resolve_lb_dir(runtime_values)
    db_url, db_path, key_path = resolve_db_and_key(lb_dir, runtime_values)
    export_script = portable_dir / "export-accounts.py"
    watch_paths = watched_paths(db_path, key_path)

    os.chdir(portable_dir)
    last_state: tuple[tuple[str, int | None, int | None], ...] | None = None

    while True:
        current_state = snapshot(watch_paths)
        if current_state != last_state:
            if path_exists(db_path) and path_exists(key_path):
                try:
                    export_accounts(export_script, db_url, key_path)
                except subprocess.CalledProcessError as exc:
                    print(f"account sync failed: {exc}", file=sys.stderr)
            last_state = current_state
        time.sleep(2)


if __name__ == "__main__":
    main()
