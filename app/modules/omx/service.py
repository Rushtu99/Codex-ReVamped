from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.exceptions import DashboardBadRequestError
from app.modules.omx.schemas import (
    OmxAction,
    OmxCommandResultResponse,
    OmxDashboardResponse,
    OmxDashboardSession,
    OmxDashboardWorker,
    OmxOverviewResponse,
    OmxQuickRef,
    OmxReasoningLevel,
    OmxSessionTokenUsage,
    OmxTokenUsage,
    OmxWorkerTokenUsage,
)

_DEFAULT_TIMEOUT_SECONDS = 20
_OUTPUT_LIMIT_CHARS = 120_000
_REASONING_REGEX = re.compile(r"model_reasoning_effort:\s*(low|medium|high|xhigh)", re.IGNORECASE)
_WHITESPACE_REGEX = re.compile(r"\s+")
_SESSION_HISTORY_LIMIT = 60
_TEAM_JOB_HISTORY_LIMIT = 60

_ACTION_COMMANDS: dict[OmxAction, tuple[str, ...]] = {
    "version": ("version",),
    "status": ("status",),
    "doctor": ("doctor",),
    "doctor_team": ("doctor", "--team"),
    "cleanup": ("cleanup",),
    "cleanup_dry_run": ("cleanup", "--dry-run"),
    "cancel": ("cancel",),
    "reasoning_get": ("reasoning",),
}

_QUICK_REFS: tuple[tuple[str, str, str, str], ...] = (
    (
        "ralplan",
        "Consensus Plan",
        '$ralplan "describe the change"',
        "Build a consensus plan before execution.",
    ),
    (
        "team",
        "Team Mode",
        '$team 3 "implement the approved plan"',
        "Start a coordinated multi-worker implementation run.",
    ),
    (
        "ultrawork",
        "Ultrawork (ult)",
        '$ultrawork 3 "parallel bounded tasks"',
        "Run high-throughput parallel execution lanes (alias: ult).",
    ),
    (
        "team_status",
        "Team Status",
        "omx team status <team-name>",
        "Inspect current worker states and task progress.",
    ),
)


def _truncate(text: str) -> str:
    if len(text) <= _OUTPUT_LIMIT_CHARS:
        return text
    return f"{text[:_OUTPUT_LIMIT_CHARS]}\n\n... output truncated ..."


def _runtime_env_candidates() -> list[Path]:
    env_override = os.getenv("CODEX_RUNTIME_ENV")
    candidates: list[Path] = []
    if env_override:
        candidates.append(Path(env_override))
    home = Path.home()
    candidates.append(home / ".codex-revamped" / "runtime.env")
    candidates.append(home / ".codex-portable-setup" / "runtime.env")
    return candidates


def _read_runtime_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    except OSError:
        return {}
    return values


def _resolve_runtime_env() -> tuple[Path | None, dict[str, str]]:
    for candidate in _runtime_env_candidates():
        if candidate.is_file():
            return candidate, _read_runtime_values(candidate)
    return None, {}


def _resolve_omx_bin(runtime_values: dict[str, str]) -> str | None:
    runtime_bin = runtime_values.get("CODEX_OMX_BIN")
    if runtime_bin and Path(runtime_bin).is_file() and os.access(runtime_bin, os.X_OK):
        return runtime_bin
    discovered = shutil.which("omx")
    if discovered:
        return discovered
    return None


def _extract_reasoning(stdout: str) -> OmxReasoningLevel | None:
    match = _REASONING_REGEX.search(stdout)
    if not match:
        return None
    value = match.group(1).lower()
    if value not in {"low", "medium", "high", "xhigh"}:
        return None
    return value  # type: ignore[return-value]


def _resolve_omx_state_dir(runtime_values: dict[str, str]) -> Path:
    candidates: list[Path] = []

    env_override = os.getenv("CODEX_OMX_STATE_DIR")
    if env_override:
        candidates.append(Path(env_override).expanduser())

    runtime_root = runtime_values.get("CODEX_PORTABLE_DIR")
    if runtime_root:
        root = Path(runtime_root).expanduser()
        candidates.extend([root / ".omx", root])

    candidates.append(Path.home() / ".omx")

    for candidate in candidates:
        if candidate.name == ".omx" and candidate.is_dir():
            return candidate
        nested = candidate / ".omx"
        if nested.is_dir():
            return nested

    for candidate in candidates:
        if candidate.name == ".omx":
            return candidate

    return Path.home() / ".omx"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_json_dict(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def _iter_jsonl_dicts(path: Path) -> Iterable[dict[str, Any]]:
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()

    items: list[dict[str, Any]] = []
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _one_line(value: str | None, *, fallback: str = "--", max_len: int = 160) -> str:
    if not value:
        return fallback
    normalized = _WHITESPACE_REGEX.sub(" ", value).strip()
    if not normalized:
        return fallback
    if len(normalized) <= max_len:
        return normalized
    return f"{normalized[: max_len - 3]}..."


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return _parse_datetime(int(raw))
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    return None


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            return None
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            return None
    return None


def _read_token_value(mapping: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        if key in mapping:
            parsed = _coerce_int(mapping.get(key))
            if parsed is not None:
                return parsed
    return None


def _extract_tokens_from_sources(*sources: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def apply_source(source: dict[str, Any]) -> None:
        nonlocal input_tokens, output_tokens, total_tokens
        if input_tokens is None:
            input_tokens = _read_token_value(source, "input_tokens", "inputTokens")
        if output_tokens is None:
            output_tokens = _read_token_value(source, "output_tokens", "outputTokens")
        if total_tokens is None:
            total_tokens = _read_token_value(source, "total_tokens", "totalTokens")

    for source in sources:
        if not source:
            continue
        apply_source(source)
        tokens = source.get("tokens")
        if isinstance(tokens, dict):
            apply_source(tokens)
        usage = source.get("usage")
        if isinstance(usage, dict):
            apply_source(usage)

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return input_tokens, output_tokens, total_tokens


def _build_quick_refs() -> list[OmxQuickRef]:
    return [
        OmxQuickRef(key=key, label=label, command=command, description=description)
        for key, label, command, description in _QUICK_REFS
    ]


def _session_sort_key(session: OmxDashboardSession) -> float:
    timestamp = session.last_activity_at or session.started_at
    return timestamp.timestamp() if timestamp else 0.0


class OmxService:
    async def get_overview(self) -> OmxOverviewResponse:
        runtime_env_path, runtime_values = _resolve_runtime_env()
        omx_bin = _resolve_omx_bin(runtime_values)
        warnings: list[str] = []

        if runtime_env_path is None:
            warnings.append("Codex-ReVamped runtime.env was not found.")
        if not omx_bin:
            warnings.append("OMX binary was not found in runtime metadata or PATH.")

        version_result = await self._run_command("version", runtime_values, suppress_error=True)
        status_result = await self._run_command("status", runtime_values, suppress_error=True)
        reasoning_result = await self._run_command("reasoning_get", runtime_values, suppress_error=True)
        doctor_result = await self._run_command("doctor", runtime_values, suppress_error=True)

        if version_result and version_result.exit_code != 0:
            warnings.append("`omx version` failed. Check OMX installation.")
        if status_result and status_result.exit_code != 0:
            warnings.append("`omx status` failed. OMX runtime state may be unavailable.")

        return OmxOverviewResponse(
            available=bool(omx_bin),
            binary_path=omx_bin,
            runtime_env_path=str(runtime_env_path) if runtime_env_path else None,
            runtime_dir=runtime_values.get("CODEX_PORTABLE_DIR"),
            version=(version_result.stdout.splitlines()[0].strip() if version_result and version_result.stdout else None),
            reasoning=_extract_reasoning(reasoning_result.stdout) if reasoning_result else None,
            status_summary=(status_result.stdout.strip() if status_result and status_result.stdout else None),
            doctor_summary=(doctor_result.stdout.strip() if doctor_result and doctor_result.stdout else None),
            warnings=warnings,
            last_checked_at=datetime.now(UTC),
        )

    async def get_dashboard(self) -> OmxDashboardResponse:
        runtime_env_path, runtime_values = _resolve_runtime_env()
        state_dir = _resolve_omx_state_dir(runtime_values)
        warnings: list[str] = []
        notes: list[str] = []

        if runtime_env_path is None:
            warnings.append("Codex-ReVamped runtime.env was not found.")
        if not state_dir.is_dir():
            warnings.append(f"OMX runtime state directory not found at `{state_dir}`.")

        metrics = _read_json_dict(state_dir / "metrics.json")
        active_session_data = _read_json_dict(state_dir / "state" / "session.json")
        hud_state_data = _read_json_dict(state_dir / "state" / "hud-state.json")

        sessions_by_id: dict[str, OmxDashboardSession] = {}
        session_tokens_by_id: dict[str, OmxSessionTokenUsage] = {}
        workers: list[OmxDashboardWorker] = []
        worker_tokens: list[OmxWorkerTokenUsage] = []

        active_session_id = _as_text(active_session_data.get("session_id"))
        if active_session_id:
            started_at = _parse_datetime(active_session_data.get("started_at"))
            last_activity_at = _parse_datetime(metrics.get("last_activity")) or _parse_datetime(
                hud_state_data.get("last_turn_at")
            )
            cwd = _as_text(active_session_data.get("cwd"))
            pid = _as_text(active_session_data.get("pid"))
            context_parts = [part for part in (f"cwd {cwd}" if cwd else None, f"pid {pid}" if pid else None) if part]

            sessions_by_id[active_session_id] = OmxDashboardSession(
                id=active_session_id,
                status="running",
                context_line=_one_line(" · ".join(context_parts), fallback="Active OMX session."),
                started_at=started_at,
                last_activity_at=last_activity_at or started_at,
                cwd=cwd,
                source="state",
            )

            session_input = _coerce_int(metrics.get("session_input_tokens"))
            session_output = _coerce_int(metrics.get("session_output_tokens"))
            session_total = _coerce_int(metrics.get("session_total_tokens"))
            if session_total is None and session_input is not None and session_output is not None:
                session_total = session_input + session_output
            if any(value is not None for value in (session_input, session_output, session_total)):
                session_tokens_by_id[active_session_id] = OmxSessionTokenUsage(
                    session_id=active_session_id,
                    input_tokens=session_input,
                    output_tokens=session_output,
                    total_tokens=session_total,
                    exact=True,
                )

        logs_dir = state_dir / "logs"
        historical_count = 0
        if logs_dir.is_dir():
            for log_path in sorted(logs_dir.glob("omx-*.jsonl"), reverse=True):
                for event in _iter_jsonl_dicts(log_path):
                    if historical_count >= _SESSION_HISTORY_LIMIT:
                        break
                    if _as_text(event.get("event")) != "session_start":
                        continue
                    session_id = _as_text(event.get("session_id"))
                    if not session_id or session_id in sessions_by_id:
                        continue
                    timestamp = _parse_datetime(event.get("timestamp")) or _parse_datetime(event.get("_ts"))
                    sessions_by_id[session_id] = OmxDashboardSession(
                        id=session_id,
                        status="historical",
                        context_line="Session start captured in OMX log.",
                        started_at=timestamp,
                        last_activity_at=timestamp,
                        cwd=None,
                        source="logs",
                    )
                    historical_count += 1
                if historical_count >= _SESSION_HISTORY_LIMIT:
                    break

        team_jobs_dir = state_dir / "team-jobs"
        team_jobs_count = 0
        if team_jobs_dir.is_dir():
            for job_path in sorted(team_jobs_dir.glob("*.json"), reverse=True):
                if team_jobs_count >= _TEAM_JOB_HISTORY_LIMIT:
                    break
                payload = _read_json_dict(job_path)
                if not payload:
                    continue
                team_jobs_count += 1

                job_id = job_path.stem
                session_id = f"team-job:{job_id}"
                if session_id in sessions_by_id:
                    continue

                team_name = _as_text(payload.get("teamName"))
                status = _as_text(payload.get("status")) or "unknown"
                started_at = _parse_datetime(payload.get("startedAt"))
                stderr_line = _one_line(_as_text(payload.get("stderr")), fallback="", max_len=180)
                stdout_line = _one_line(_as_text(payload.get("stdout")), fallback="", max_len=180)
                context_fragments = [
                    fragment
                    for fragment in (f"team {team_name}" if team_name else None, stderr_line, stdout_line)
                    if fragment
                ]
                context_line = _one_line(" · ".join(context_fragments), fallback="Team job snapshot available.", max_len=180)

                sessions_by_id[session_id] = OmxDashboardSession(
                    id=session_id,
                    status=status,
                    context_line=context_line,
                    started_at=started_at,
                    last_activity_at=started_at,
                    cwd=_as_text(payload.get("cwd")),
                    source="team-jobs",
                )

        team_state_root = state_dir / "state" / "team"
        if team_state_root.is_dir():
            team_dirs = sorted(
                (path for path in team_state_root.iterdir() if path.is_dir()),
                key=lambda item: item.name,
            )
            for team_dir in team_dirs:
                workers_root = team_dir / "workers"
                if not workers_root.is_dir():
                    continue
                for worker_dir in sorted(
                    (path for path in workers_root.iterdir() if path.is_dir()),
                    key=lambda item: item.name,
                ):
                    status_data = _read_json_dict(worker_dir / "status.json")
                    heartbeat_data = _read_json_dict(worker_dir / "heartbeat.json")
                    identity_data = _read_json_dict(worker_dir / "identity.json")

                    worker_status = _as_text(status_data.get("state")) or "unknown"
                    job_line = _one_line(
                        _as_text(status_data.get("job_line"))
                        or _as_text(status_data.get("task_summary"))
                        or _as_text(status_data.get("task"))
                        or _as_text(status_data.get("current_task"))
                        or _as_text(status_data.get("message"))
                        or _as_text(identity_data.get("task"))
                        or _as_text(identity_data.get("description")),
                        fallback="No job detail available.",
                    )
                    last_heartbeat_at = _parse_datetime(heartbeat_data.get("timestamp")) or _parse_datetime(
                        heartbeat_data.get("updated_at")
                    )
                    role = _as_text(identity_data.get("role"))
                    session_id = _as_text(identity_data.get("session_id"))

                    workers.append(
                        OmxDashboardWorker(
                            team=team_dir.name,
                            worker_id=worker_dir.name,
                            status=worker_status,
                            job_line=job_line,
                            role=role,
                            last_heartbeat_at=last_heartbeat_at,
                            session_id=session_id,
                        )
                    )

                    worker_input, worker_output, worker_total = _extract_tokens_from_sources(
                        status_data,
                        heartbeat_data,
                        identity_data,
                    )
                    worker_exact = any(token is not None for token in (worker_input, worker_output, worker_total))
                    worker_tokens.append(
                        OmxWorkerTokenUsage(
                            team=team_dir.name,
                            worker_id=worker_dir.name,
                            input_tokens=worker_input,
                            output_tokens=worker_output,
                            total_tokens=worker_total,
                            exact=worker_exact,
                        )
                    )

        sessions = sorted(sessions_by_id.values(), key=_session_sort_key, reverse=True)
        for session in sessions:
            session_tokens_by_id.setdefault(
                session.id,
                OmxSessionTokenUsage(session_id=session.id, exact=False),
            )

        session_tokens = [session_tokens_by_id[session.id] for session in sessions]
        workers = sorted(workers, key=lambda item: (item.team, item.worker_id))
        worker_tokens = sorted(worker_tokens, key=lambda item: (item.team, item.worker_id))

        if not sessions:
            notes.append("No OMX session records were discovered in state, logs, or team jobs.")
        if sessions and not any(entry.exact for entry in session_tokens):
            notes.append("Session token metrics are unavailable; values are marked as N/A.")
        if workers and not any(entry.exact for entry in worker_tokens):
            notes.append("Worker token metrics are unavailable from OMX worker state; values are marked as N/A.")

        return OmxDashboardResponse(
            quick_refs=_build_quick_refs(),
            sessions=sessions,
            workers=workers,
            token_usage=OmxTokenUsage(
                sessions=session_tokens,
                workers=worker_tokens,
                notes=notes,
            ),
            warnings=warnings,
            updated_at=datetime.now(UTC),
        )

    async def run_action(self, action: OmxAction, level: OmxReasoningLevel | None = None) -> OmxCommandResultResponse:
        _, runtime_values = _resolve_runtime_env()
        if action == "reasoning_set":
            if level is None:
                raise DashboardBadRequestError("`level` is required for reasoning_set.", code="invalid_payload")
            return await self._run_command(action, runtime_values, level=level)
        return await self._run_command(action, runtime_values)

    async def _run_command(
        self,
        action: OmxAction,
        runtime_values: dict[str, str],
        level: OmxReasoningLevel | None = None,
        suppress_error: bool = False,
    ) -> OmxCommandResultResponse:
        omx_bin = _resolve_omx_bin(runtime_values)
        if not omx_bin:
            if suppress_error:
                now = datetime.now(UTC)
                return OmxCommandResultResponse(
                    action=action,
                    command=["omx"],
                    exit_code=127,
                    stdout="",
                    stderr="omx binary not found",
                    started_at=now,
                    finished_at=now,
                    timed_out=False,
                )
            raise DashboardBadRequestError("OMX binary not found.", code="omx_missing")

        if action == "reasoning_set":
            if level is None:
                raise DashboardBadRequestError("`level` is required for reasoning_set.", code="invalid_payload")
            args = ("reasoning", level)
        else:
            args = _ACTION_COMMANDS.get(action)
            if args is None:
                raise DashboardBadRequestError(f"Unsupported OMX action: {action}", code="invalid_payload")

        command = [omx_bin, *args]
        env = os.environ.copy()
        if runtime_values.get("CODEX_RUNTIME_ENV"):
            env["CODEX_RUNTIME_ENV"] = runtime_values["CODEX_RUNTIME_ENV"]
        if runtime_values.get("CODEX_PORTABLE_DIR"):
            env["CODEX_PORTABLE_SETUP_DIR"] = runtime_values["CODEX_PORTABLE_DIR"]

        started_at = datetime.now(UTC)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        timed_out = False
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=_DEFAULT_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            timed_out = True
            process.kill()
            stdout_bytes, stderr_bytes = await process.communicate()
        finished_at = datetime.now(UTC)
        exit_code = process.returncode if process.returncode is not None else 124

        return OmxCommandResultResponse(
            action=action,
            command=command,
            exit_code=exit_code,
            stdout=_truncate(stdout_bytes.decode("utf-8", errors="replace")),
            stderr=_truncate(stderr_bytes.decode("utf-8", errors="replace")),
            started_at=started_at,
            finished_at=finished_at,
            timed_out=timed_out,
        )
