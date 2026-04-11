from __future__ import annotations

import asyncio
import difflib
import json
import secrets
import shutil
import sqlite3
import subprocess
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from app.core.config.settings import get_settings
from app.core.exceptions import DashboardBadRequestError, DashboardConflictError, DashboardNotFoundError
from app.modules.sessions.schemas import (
    SessionActionResponse,
    SessionAttachResponse,
    SessionControlState,
    SessionDetailResponse,
    SessionForkResponse,
    SessionListItem,
    SessionListResponse,
    SessionTimelineEvent,
    SessionsCapabilitiesResponse,
)

_CLIENT_NAME = "codex_lb_dashboard"
_CLIENT_TITLE = "CodexLB Dashboard"
_CLIENT_VERSION = "0.1.0"
_MAX_LIST_LIMIT = 100
_APP_SERVER_STDIO_LIMIT = 16 * 1024 * 1024


@dataclass(slots=True)
class _SessionArtifact:
    id: str
    title: str
    preview: str | None
    cwd: str | None
    updated_at: datetime | None
    created_at: datetime | None
    source: str | None
    model_provider: str | None
    model: str | None
    reasoning_effort: str | None
    archived: bool
    rollout_path: Path | None = None
    latest_event_at: datetime | None = None


@dataclass(slots=True)
class _Lease:
    attachment_id: str
    session_id: str
    owner_session_id: str
    stream_token: str
    lease_expires_at: datetime
    current_turn_id: str | None = None
    queues: set[asyncio.Queue[dict[str, Any]]] = field(default_factory=set)

    def expired(self) -> bool:
        return datetime.now(UTC) >= self.lease_expires_at


class _CodexAppServerBridge:
    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._notification_handlers: set[callable] = set()
        self._last_used_at: datetime | None = None

    async def start(self) -> None:
        if self._process and self._process.returncode is None:
            self._last_used_at = datetime.now(UTC)
            return

        settings = get_settings()
        codex_bin = settings.sessions_codex_cli_bin
        if not shutil.which(codex_bin):
            raise DashboardBadRequestError("Codex CLI binary not found.", code="codex_missing")

        self._process = await asyncio.create_subprocess_exec(
            codex_bin,
            "app-server",
            stdout=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # Some threads resume with multi-megabyte JSON payloads. asyncio's default
        # StreamReader line limit is too small for those single-line responses.
        for stream_name in ("stdout", "stderr"):
            stream = getattr(self._process, stream_name, None)
            if stream is not None and hasattr(stream, "_limit"):
                stream._limit = max(getattr(stream, "_limit", 0), _APP_SERVER_STDIO_LIMIT)
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._drain_stderr())
        self._last_used_at = datetime.now(UTC)
        await self.request(
            "initialize",
            {
                "clientInfo": {
                    "name": _CLIENT_NAME,
                    "title": _CLIENT_TITLE,
                    "version": _CLIENT_VERSION,
                },
                "capabilities": {"experimentalApi": True},
            },
        )
        await self.notify("initialized", {})

    async def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            with suppress(Exception):
                await asyncio.wait_for(process.wait(), timeout=2)
        for task in (self._reader_task, self._stderr_task):
            if task is not None:
                task.cancel()
                with suppress(Exception):
                    await task
        self._reader_task = None
        self._stderr_task = None

    async def maybe_stop_for_idle(self) -> None:
        if self._process is None or self._process.returncode is not None:
            return
        if self._last_used_at is None:
            return
        idle_ttl = timedelta(seconds=get_settings().sessions_app_server_idle_ttl_seconds)
        if datetime.now(UTC) - self._last_used_at >= idle_ttl:
            await self.stop()

    def register_notification_handler(self, handler: callable) -> None:
        self._notification_handlers.add(handler)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self.start()
        payload: dict[str, Any] = {"method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        await self.start()
        async with self._lock:
            self._request_id += 1
            request_id = self._request_id
            loop = asyncio.get_running_loop()
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._pending[request_id] = future
            payload: dict[str, Any] = {"id": request_id, "method": method}
            if params is not None:
                payload["params"] = params
            await self._send(payload)
        try:
            result = await asyncio.wait_for(future, timeout=30)
        except TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise DashboardBadRequestError(f"{method} timed out.", code="interactive_timeout") from exc
        self._last_used_at = datetime.now(UTC)
        return result

    async def _send(self, payload: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise DashboardBadRequestError("Codex app-server is unavailable.", code="interactive_unavailable")
        process.stdin.write((json.dumps(payload, ensure_ascii=True) + "\n").encode("utf-8"))
        await process.stdin.drain()

    async def _read_stdout(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            try:
                payload = json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                continue
            if "id" in payload:
                future = self._pending.pop(int(payload["id"]), None)
                if future is None or future.done():
                    continue
                if "error" in payload:
                    message = payload["error"].get("message", "Interactive request failed.")
                    future.set_exception(DashboardBadRequestError(message, code="interactive_failed"))
                else:
                    future.set_result(payload.get("result", {}))
                continue
            if "method" in payload:
                for handler in list(self._notification_handlers):
                    with suppress(Exception):
                        handler(payload)

    async def _drain_stderr(self) -> None:
        if self._process is None or self._process.stderr is None:
            return
        while True:
            line = await self._process.stderr.readline()
            if not line:
                return


class SessionsService:
    def __init__(self) -> None:
        self._bridge = _CodexAppServerBridge()
        self._leases_by_attachment: dict[str, _Lease] = {}
        self._leases_by_session: dict[str, _Lease] = {}
        self._bridge.register_notification_handler(self._handle_notification)

    @classmethod
    def for_app(cls, app: object) -> "SessionsService":
        state = getattr(app, "state", None)
        service = getattr(state, "sessions_service", None)
        if not isinstance(service, cls):
            service = cls()
            setattr(state, "sessions_service", service)
        return service

    async def get_capabilities(self, *, interactive_session_allowed: bool) -> SessionsCapabilitiesResponse:
        settings = get_settings()
        enabled = settings.sessions_enabled
        interactive_enabled = enabled and settings.sessions_interactive_enabled and interactive_session_allowed
        reason = None
        if not enabled:
            reason = "Sessions feature is disabled."
        elif not settings.sessions_interactive_enabled:
            reason = "Interactive continuation is disabled."
        elif not interactive_session_allowed:
            reason = "Interactive continuation requires a fully verified dashboard session."
        elif not shutil.which(settings.sessions_codex_cli_bin):
            interactive_enabled = False
            reason = "Codex CLI is unavailable on this host."
        return SessionsCapabilitiesResponse(
            enabled=enabled,
            interactive_available=interactive_enabled,
            read_only=enabled and not interactive_enabled,
            beta=True,
            restriction_reason=reason,
            codex_home=str(settings.sessions_codex_home),
        )

    def ensure_enabled(self) -> None:
        if not get_settings().sessions_enabled:
            raise DashboardNotFoundError("Sessions feature is disabled.", code="sessions_disabled")

    async def list_sessions(
        self,
        *,
        query: str | None,
        cursor: str | None,
        limit: int,
    ) -> SessionListResponse:
        self.ensure_enabled()
        limit = max(1, min(limit, _MAX_LIST_LIMIT))
        artifacts = sorted(
            self._load_artifacts().values(),
            key=lambda artifact: artifact.updated_at or datetime.fromtimestamp(0, UTC),
            reverse=True,
        )
        if query:
            lowered = query.lower()
            artifacts = [
                artifact
                for artifact in artifacts
                if lowered in artifact.title.lower()
                or lowered in (artifact.preview or "").lower()
                or lowered in (artifact.cwd or "").lower()
            ]
        start = int(cursor or "0")
        page = artifacts[start : start + limit]
        next_cursor = str(start + limit) if start + limit < len(artifacts) else None
        return SessionListResponse(
            data=[self._to_list_item(artifact) for artifact in page],
            next_cursor=next_cursor,
        )

    async def get_session_detail(self, session_id: str, *, interactive_session_allowed: bool) -> SessionDetailResponse:
        self.ensure_enabled()
        artifacts = self._load_artifacts()
        artifact = artifacts.get(session_id)
        if artifact is None:
            raise DashboardNotFoundError("Session not found.", code="session_not_found")
        events = self._read_session_events(artifact.rollout_path)
        lease = self._active_lease_for_session(session_id)
        capabilities = await self.get_capabilities(interactive_session_allowed=interactive_session_allowed)
        return SessionDetailResponse(
            session=self._to_list_item(artifact),
            events=events,
            interactive_available=capabilities.interactive_available,
            controller_attachment_id=lease.attachment_id if lease is not None else None,
            restriction_reason=capabilities.restriction_reason,
        )

    async def attach_session(self, session_id: str, *, owner_session_id: str) -> SessionAttachResponse:
        self.ensure_enabled()
        await self._ensure_interactive_allowed()
        artifact = self._require_session(session_id)
        lease = self._active_lease_for_session(session_id)
        if lease is not None and lease.owner_session_id != owner_session_id:
            raise DashboardConflictError("Session is already controlled by another dashboard session.", code="controller_conflict")

        result = await self._bridge.request(
            "thread/resume",
            {
                "threadId": session_id,
                "personality": "pragmatic",
                # Required by the current app-server protocol when resuming from thread id.
                "persistExtendedHistory": True,
            },
        )
        thread = result.get("thread", {})
        now = datetime.now(UTC)
        refreshed = _Lease(
            attachment_id=lease.attachment_id if lease is not None else uuid.uuid4().hex,
            session_id=session_id,
            owner_session_id=owner_session_id,
            stream_token=secrets.token_urlsafe(24),
            lease_expires_at=now + timedelta(seconds=get_settings().sessions_app_server_idle_ttl_seconds),
            current_turn_id=lease.current_turn_id if lease is not None else None,
        )
        self._leases_by_attachment[refreshed.attachment_id] = refreshed
        self._leases_by_session[session_id] = refreshed
        artifact.title = thread.get("preview") or artifact.title
        return SessionAttachResponse(
            attachment_id=refreshed.attachment_id,
            stream_token=refreshed.stream_token,
            lease_expires_at=refreshed.lease_expires_at,
            session=self._to_list_item(artifact, control_state="attached"),
        )

    async def fork_session(self, session_id: str) -> SessionForkResponse:
        self.ensure_enabled()
        await self._ensure_interactive_allowed()
        result = await self._bridge.request(
            "thread/fork",
            {
                "threadId": session_id,
                "persistExtendedHistory": True,
            },
        )
        thread = result.get("thread", {})
        session = SessionListItem(
            id=thread.get("id", ""),
            title=thread.get("preview") or "Forked session",
            preview=thread.get("preview"),
            cwd=thread.get("cwd"),
            updated_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            source="codex-app-server",
            model_provider=thread.get("modelProvider"),
            model=thread.get("model"),
            reasoning_effort=thread.get("reasoningEffort"),
            archived=False,
            status="idle",
            control_state="detached",
            latest_event_at=datetime.now(UTC),
        )
        return SessionForkResponse(session=session)

    async def start_turn(self, session_id: str, *, attachment_id: str, prompt: str, owner_session_id: str) -> SessionActionResponse:
        self.ensure_enabled()
        await self._ensure_interactive_allowed()
        prompt = prompt.strip()
        if not prompt:
            raise DashboardBadRequestError("Prompt is required.", code="invalid_prompt")
        if len(prompt) > get_settings().sessions_max_prompt_chars:
            raise DashboardBadRequestError("Prompt is too large.", code="prompt_too_large")
        lease = self._require_owned_lease(session_id, attachment_id, owner_session_id)
        result = await self._bridge.request(
            "turn/start",
            {
                "threadId": session_id,
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
            },
        )
        turn = result.get("turn", {})
        lease.current_turn_id = turn.get("id")
        lease.lease_expires_at = datetime.now(UTC) + timedelta(seconds=get_settings().sessions_app_server_idle_ttl_seconds)
        return SessionActionResponse(status="ok", turn_id=lease.current_turn_id)

    async def interrupt_turn(self, session_id: str, *, attachment_id: str, owner_session_id: str) -> SessionActionResponse:
        self.ensure_enabled()
        await self._ensure_interactive_allowed()
        lease = self._require_owned_lease(session_id, attachment_id, owner_session_id)
        if not lease.current_turn_id:
            raise DashboardBadRequestError("No active turn to interrupt.", code="no_active_turn")
        await self._bridge.request("turn/interrupt", {"threadId": session_id, "turnId": lease.current_turn_id})
        return SessionActionResponse(status="ok", turn_id=lease.current_turn_id)

    async def open_stream(
        self,
        *,
        attachment_id: str,
        token: str,
        owner_session_id: str,
    ) -> tuple[_Lease, asyncio.Queue[dict[str, Any]]]:
        lease = self._leases_by_attachment.get(attachment_id)
        if lease is None or lease.expired():
            raise DashboardBadRequestError("Attachment lease is no longer valid.", code="attachment_expired")
        if lease.owner_session_id != owner_session_id:
            raise DashboardBadRequestError("Attachment owner mismatch.", code="attachment_owner_mismatch")
        if token != lease.stream_token:
            raise DashboardBadRequestError("Invalid stream token.", code="invalid_stream_token")
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        lease.queues.add(queue)
        queue.put_nowait(
            {
                "type": "session.attached",
                "sessionId": lease.session_id,
                "attachmentId": lease.attachment_id,
                "leaseExpiresAt": lease.lease_expires_at.isoformat().replace("+00:00", "Z"),
            }
        )
        return lease, queue

    def close_stream(self, *, attachment_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        lease = self._leases_by_attachment.get(attachment_id)
        if lease is None:
            return
        lease.queues.discard(queue)
        if not lease.queues:
            self._leases_by_attachment.pop(attachment_id, None)
            self._leases_by_session.pop(lease.session_id, None)

    async def send_queue_events(self, websocket: WebSocket, queue: asyncio.Queue[dict[str, Any]]) -> None:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)

    async def shutdown(self) -> None:
        await self._bridge.stop()

    def _handle_notification(self, payload: dict[str, Any]) -> None:
        method = str(payload.get("method") or "")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        thread_id = self._notification_thread_id(params)
        if not thread_id:
            return
        lease = self._active_lease_for_session(thread_id)
        if lease is None:
            return
        if method in {"turn/completed", "thread/closed"}:
            lease.current_turn_id = None
        elif method == "turn/started" and isinstance(params.get("turn"), dict):
            lease.current_turn_id = params["turn"].get("id")
        normalized = self._normalize_notification(method, params)
        if normalized is None:
            return
        for queue in list(lease.queues):
            with suppress(asyncio.QueueFull):
                queue.put_nowait(normalized)

    def _notification_thread_id(self, params: dict[str, Any]) -> str | None:
        if isinstance(params.get("threadId"), str):
            return params["threadId"]
        thread = params.get("thread")
        if isinstance(thread, dict) and isinstance(thread.get("id"), str):
            return thread["id"]
        return None

    def _normalize_notification(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        payload: dict[str, Any] = {
            "type": method.replace("/", "."),
            "sessionId": self._notification_thread_id(params),
            "turnId": params.get("turnId"),
            "itemId": params.get("itemId"),
        }
        if "delta" in params:
            payload["text"] = params["delta"]
        elif isinstance(params.get("turn"), dict):
            payload["status"] = params["turn"].get("status")
        elif isinstance(params.get("status"), dict):
            payload["status"] = params["status"].get("type")
        if isinstance(params.get("error"), dict):
            payload["error"] = params["error"].get("message")
        return payload

    async def _ensure_interactive_allowed(self) -> None:
        settings = get_settings()
        if not settings.sessions_interactive_enabled:
            raise DashboardBadRequestError("Interactive continuation is disabled.", code="interactive_unavailable")
        await self._bridge.start()

    def _require_owned_lease(self, session_id: str, attachment_id: str, owner_session_id: str) -> _Lease:
        lease = self._leases_by_attachment.get(attachment_id)
        if lease is None or lease.expired():
            raise DashboardBadRequestError("Attachment lease is no longer valid.", code="attachment_expired")
        if lease.session_id != session_id:
            raise DashboardBadRequestError("Attachment does not match session.", code="attachment_session_mismatch")
        if lease.owner_session_id != owner_session_id:
            raise DashboardBadRequestError("Attachment owner mismatch.", code="attachment_owner_mismatch")
        return lease

    def _active_lease_for_session(self, session_id: str) -> _Lease | None:
        lease = self._leases_by_session.get(session_id)
        if lease is None:
            return None
        if lease.expired():
            self._leases_by_attachment.pop(lease.attachment_id, None)
            self._leases_by_session.pop(session_id, None)
            return None
        return lease

    def _require_session(self, session_id: str) -> _SessionArtifact:
        artifact = self._load_artifacts().get(session_id)
        if artifact is None:
            raise DashboardNotFoundError("Session not found.", code="session_not_found")
        return artifact

    def _load_artifacts(self) -> dict[str, _SessionArtifact]:
        settings = get_settings()
        codex_home = settings.sessions_codex_home.resolve()
        artifacts = self._load_sqlite_threads(codex_home)
        index_entries = self._load_session_index(codex_home)
        for session_id, entry in index_entries.items():
            artifact = artifacts.get(session_id)
            if artifact is None:
                artifacts[session_id] = _SessionArtifact(
                    id=session_id,
                    title=entry["title"],
                    preview=entry["title"],
                    cwd=None,
                    updated_at=entry["updated_at"],
                    created_at=None,
                    source="cli",
                    model_provider=None,
                    model=None,
                    reasoning_effort=None,
                    archived=False,
                    rollout_path=self._find_rollout_file(codex_home, session_id),
                    latest_event_at=entry["updated_at"],
                )
                continue
            if entry["updated_at"] and (artifact.updated_at is None or entry["updated_at"] > artifact.updated_at):
                artifact.updated_at = entry["updated_at"]
            if entry["title"] and not artifact.title:
                artifact.title = entry["title"]
        return artifacts

    def _load_sqlite_threads(self, codex_home: Path) -> dict[str, _SessionArtifact]:
        state_path = codex_home / "state_5.sqlite"
        if not state_path.is_file():
            return {}
        query = """
        SELECT id, title, cwd, updated_at, created_at, source, model_provider, archived,
               rollout_path, model, reasoning_effort
        FROM threads
        """
        connection = sqlite3.connect(state_path)
        try:
            rows = connection.execute(query).fetchall()
        finally:
            connection.close()
        artifacts: dict[str, _SessionArtifact] = {}
        for row in rows:
            rollout_path = Path(row[8]) if row[8] else None
            latest_event_at = self._rollout_timestamp(rollout_path)
            artifacts[row[0]] = _SessionArtifact(
                id=row[0],
                title=row[1] or row[0],
                preview=row[1],
                cwd=row[2],
                updated_at=_from_unix(row[3]),
                created_at=_from_unix(row[4]),
                source=row[5],
                model_provider=row[6],
                model=row[9],
                reasoning_effort=row[10],
                archived=bool(row[7]),
                rollout_path=rollout_path,
                latest_event_at=latest_event_at,
            )
        return artifacts

    def _load_session_index(self, codex_home: Path) -> dict[str, dict[str, Any]]:
        path = codex_home / "session_index.jsonl"
        if not path.is_file():
            return {}
        entries: dict[str, dict[str, Any]] = {}
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                with suppress(json.JSONDecodeError):
                    payload = json.loads(line)
                    session_id = payload.get("id")
                    if not isinstance(session_id, str):
                        continue
                    entries[session_id] = {
                        "title": payload.get("thread_name") or session_id,
                        "updated_at": _parse_dt(payload.get("updated_at")),
                    }
        return entries

    def _find_rollout_file(self, codex_home: Path, session_id: str) -> Path | None:
        sessions_dir = codex_home / "sessions"
        if not sessions_dir.is_dir():
            return None
        for path in sessions_dir.rglob(f"*{session_id}.jsonl"):
            return path
        return None

    def _rollout_timestamp(self, rollout_path: Path | None) -> datetime | None:
        if rollout_path is None or not rollout_path.is_file():
            return None
        with suppress(OSError):
            return datetime.fromtimestamp(rollout_path.stat().st_mtime, UTC)
        return None

    def _read_session_events(self, rollout_path: Path | None) -> list[SessionTimelineEvent]:
        if rollout_path is None or not rollout_path.is_file():
            return []
        settings = get_settings()
        limit = settings.sessions_recent_event_limit
        with rollout_path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()[-limit:]
        events: list[SessionTimelineEvent] = []
        message_turn_markers: list[int] = []
        previous_text_by_role: dict[str, str] = {}
        for idx, raw_line in enumerate(lines):
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            timestamp = _parse_dt(payload.get("timestamp"))
            event_type = str(payload.get("type") or "unknown")
            content = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
            if event_type == "response_item" and content.get("type") == "message":
                role = content.get("role")
                if isinstance(role, str):
                    message_turn_markers.append(len(events))
                text = _extract_message_text(content)
                previous_text = previous_text_by_role.get(role) if isinstance(role, str) else None
                text = _optimize_event_text(text, previous_text=previous_text, settings=settings)
                if isinstance(role, str) and isinstance(text, str):
                    previous_text_by_role[role] = text
                events.append(
                    SessionTimelineEvent(
                        id=f"{rollout_path.name}:{idx}",
                        type="message",
                        role=role,
                        text=text,
                        timestamp=timestamp,
                    )
                )
                continue
            if event_type == "event_msg":
                text = content.get("message") or content.get("type")
                if isinstance(text, str):
                    text = _optimize_event_text(text, previous_text=None, settings=settings)
                events.append(
                    SessionTimelineEvent(
                        id=f"{rollout_path.name}:{idx}",
                        type=str(content.get("type") or "event"),
                        text=str(text) if text is not None else None,
                        turn_id=content.get("turn_id"),
                        timestamp=timestamp,
                    )
                )
        window_turns = settings.sessions_context_window_turns
        if window_turns > 0 and len(message_turn_markers) > window_turns:
            cutoff = message_turn_markers[-window_turns]
            events = events[cutoff:]
        return events

    def _to_list_item(
        self,
        artifact: _SessionArtifact,
        *,
        control_state: SessionControlState | None = None,
    ) -> SessionListItem:
        lease = self._active_lease_for_session(artifact.id)
        state = control_state or ("attached" if lease is not None else "detached")
        status = "archived" if artifact.archived else ("active" if lease is not None and lease.current_turn_id else "idle")
        return SessionListItem(
            id=artifact.id,
            title=artifact.title,
            preview=artifact.preview,
            cwd=artifact.cwd,
            updated_at=artifact.updated_at,
            created_at=artifact.created_at,
            source=artifact.source,
            model_provider=artifact.model_provider,
            model=artifact.model,
            reasoning_effort=artifact.reasoning_effort,
            archived=artifact.archived,
            status=status,
            control_state=state,
            latest_event_at=artifact.latest_event_at,
        )


def _extract_message_text(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            parts.append(text)
    if not parts:
        return None
    return "\n".join(parts)


def _optimize_event_text(text: str | None, *, previous_text: str | None, settings: Any) -> str | None:
    if not isinstance(text, str):
        return text
    optimized = text
    if getattr(settings, "sessions_distill_enabled", False) and len(optimized) >= settings.sessions_distill_min_chars:
        optimized = _distill_text(optimized, settings=settings)

    if (
        getattr(settings, "sessions_diff_enabled", False)
        and isinstance(previous_text, str)
        and previous_text
        and optimized
    ):
        diff_text = _render_diff(previous_text, optimized)
        if diff_text is not None:
            ratio = len(diff_text) / max(1, len(optimized))
            if ratio <= settings.sessions_diff_fallback_ratio:
                optimized = diff_text

    return optimized


def _distill_text(text: str, *, settings: Any) -> str:
    provider = getattr(settings, "sessions_distill_provider", "internal")
    if provider == "distill_cli":
        distilled = _distill_with_cli(text, settings=settings)
        if distilled:
            return distilled
    return _distill_internal(text, target_chars=settings.sessions_distill_target_chars)


def _distill_with_cli(text: str, *, settings: Any) -> str | None:
    try:
        process = subprocess.run(
            [settings.sessions_distill_cli_bin],
            input=text,
            text=True,
            capture_output=True,
            timeout=settings.sessions_distill_timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if process.returncode != 0:
        return None
    output = process.stdout.strip()
    return output or None


def _distill_internal(text: str, *, target_chars: int) -> str:
    if len(text) <= target_chars:
        return text
    half = max(200, target_chars // 2)
    head = text[:half].rstrip()
    tail = text[-half:].lstrip()
    omitted = len(text) - len(head) - len(tail)
    return f"{head}\n\n[distilled: omitted {omitted} chars]\n\n{tail}"


def _render_diff(previous_text: str, current_text: str) -> str | None:
    if previous_text == current_text:
        return None
    diff = difflib.unified_diff(
        previous_text.splitlines(),
        current_text.splitlines(),
        fromfile="previous",
        tofile="current",
        lineterm="",
    )
    rendered = "\n".join(diff).strip()
    if not rendered:
        return None
    return f"[diff-only update]\n{rendered}"


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = value.replace("Z", "+00:00")
    with suppress(ValueError):
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _from_unix(value: Any) -> datetime | None:
    if value is None:
        return None
    with suppress(TypeError, ValueError, OSError):
        return datetime.fromtimestamp(float(value), UTC)
    return None
