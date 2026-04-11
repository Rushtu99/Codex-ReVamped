from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.config.settings import get_settings
from app.modules.sessions.service import SessionsService, _CodexAppServerBridge, _Lease


def _write_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                title TEXT,
                cwd TEXT,
                updated_at INTEGER,
                created_at INTEGER,
                source TEXT,
                model_provider TEXT,
                archived INTEGER,
                rollout_path TEXT,
                model TEXT,
                reasoning_effort TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO threads (
                id, title, cwd, updated_at, created_at, source, model_provider, archived,
                rollout_path, model, reasoning_effort
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "thr_123",
                "Implement sessions tab",
                "/repo",
                1775435680,
                1775435600,
                "cli",
                "codex-lb",
                0,
                str(path.parent / "sessions" / "2026" / "04" / "06" / "rollout-thr_123.jsonl"),
                "gpt-5.4",
                "high",
            ),
        )
        connection.commit()
    finally:
        connection.close()


@pytest.mark.asyncio
async def test_sessions_service_reads_native_codex_artifacts(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "06"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-thr_123.jsonl"
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:09:33.774Z",
                        "type": "session_meta",
                        "payload": {"id": "thr_123", "cwd": "/repo", "model_provider": "codex-lb"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:10:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "Continue the implementation"}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "thr_123",
                "thread_name": "Implement sessions tab",
                "updated_at": "2026-04-06T00:10:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sqlite(codex_home / "state_5.sqlite")

    monkeypatch.setenv("CODEX_LB_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_CODEX_HOME", str(codex_home))
    get_settings.cache_clear()

    service = SessionsService()
    listing = await service.list_sessions(query=None, cursor=None, limit=20)
    assert len(listing.data) == 1
    assert listing.data[0].id == "thr_123"
    assert listing.data[0].title == "Implement sessions tab"
    assert listing.data[0].cwd == "/repo"
    assert listing.data[0].model == "gpt-5.4"

    detail = await service.get_session_detail("thr_123", interactive_session_allowed=False)
    assert detail.session.id == "thr_123"
    assert detail.events[0].text == "Continue the implementation"


@pytest.mark.asyncio
async def test_attach_session_sends_required_resume_fields(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "06"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-thr_123.jsonl"
    rollout_path.write_text("", encoding="utf-8")
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "thr_123",
                "thread_name": "Implement sessions tab",
                "updated_at": "2026-04-06T00:10:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sqlite(codex_home / "state_5.sqlite")

    monkeypatch.setenv("CODEX_LB_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_INTERACTIVE_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_CODEX_HOME", str(codex_home))
    get_settings.cache_clear()

    service = SessionsService()
    calls: list[tuple[str, dict[str, object] | None]] = []

    async def fake_start() -> None:
        return None

    async def fake_request(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        calls.append((method, params))
        return {"thread": {"id": "thr_123", "preview": "Implement sessions tab"}}

    service._bridge.start = fake_start  # type: ignore[method-assign]
    service._bridge.request = fake_request  # type: ignore[method-assign]

    response = await service.attach_session("thr_123", owner_session_id="owner-1")

    assert response.session.id == "thr_123"
    assert response.session.control_state == "attached"
    assert calls == [
        (
            "thread/resume",
            {
                "threadId": "thr_123",
                "personality": "pragmatic",
                "persistExtendedHistory": True,
            },
        )
    ]


@pytest.mark.asyncio
async def test_start_turn_sends_text_elements(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "06"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-thr_123.jsonl"
    rollout_path.write_text("", encoding="utf-8")
    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "thr_123",
                "thread_name": "Implement sessions tab",
                "updated_at": "2026-04-06T00:10:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write_sqlite(codex_home / "state_5.sqlite")

    monkeypatch.setenv("CODEX_LB_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_INTERACTIVE_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_CODEX_HOME", str(codex_home))
    get_settings.cache_clear()

    service = SessionsService()
    service._leases_by_attachment["attach-1"] = _Lease(
        attachment_id="attach-1",
        session_id="thr_123",
        owner_session_id="owner-1",
        stream_token="token-1",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        current_turn_id=None,
    )

    calls: list[tuple[str, dict[str, object] | None]] = []

    async def fake_start() -> None:
        return None

    async def fake_request(method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        calls.append((method, params))
        return {"turn": {"id": "turn-1"}}

    service._bridge.start = fake_start  # type: ignore[method-assign]
    service._bridge.request = fake_request  # type: ignore[method-assign]

    response = await service.start_turn(
        "thr_123",
        attachment_id="attach-1",
        prompt="continue",
        owner_session_id="owner-1",
    )

    assert response.turn_id == "turn-1"
    assert calls == [
        (
            "turn/start",
            {
                "threadId": "thr_123",
                "input": [{"type": "text", "text": "continue", "text_elements": []}],
            },
        )
    ]


@pytest.mark.asyncio
async def test_bridge_start_raises_stdio_limit(monkeypatch):
    class FakeStream:
        def __init__(self) -> None:
            self._limit = 65536

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = FakeStream()
            self.stderr = FakeStream()
            self.stdin = object()
            self.returncode = None

    process = FakeProcess()

    async def fake_subprocess_exec(*args, **kwargs):
        return process

    async def fake_request(self, method: str, params: dict[str, object] | None = None) -> dict[str, object]:
        return {"userAgent": "test", "codexHome": "/tmp/.codex", "platformFamily": "unix", "platformOs": "linux"}

    async def fake_notify(self, method: str, params: dict[str, object] | None = None) -> None:
        return None

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess_exec)
    monkeypatch.setattr(_CodexAppServerBridge, "request", fake_request)
    monkeypatch.setattr(_CodexAppServerBridge, "notify", fake_notify)

    bridge = _CodexAppServerBridge()
    await bridge.start()

    assert process.stdout._limit >= 16 * 1024 * 1024
    assert process.stderr._limit >= 16 * 1024 * 1024


@pytest.mark.asyncio
async def test_session_detail_applies_sliding_window(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "06"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-thr_123.jsonl"
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:10:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "old turn"}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:11:00.000Z",
                        "type": "event_msg",
                        "payload": {"type": "turn_started", "message": "old event"},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:12:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"type": "input_text", "text": "new turn"}],
                        },
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    (codex_home / "session_index.jsonl").write_text(
        json.dumps({"id": "thr_123", "thread_name": "Window test", "updated_at": "2026-04-06T00:12:00Z"}) + "\n",
        encoding="utf-8",
    )
    _write_sqlite(codex_home / "state_5.sqlite")

    monkeypatch.setenv("CODEX_LB_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CODEX_LB_SESSIONS_CONTEXT_WINDOW_TURNS", "1")
    monkeypatch.setenv("CODEX_LB_SESSIONS_DISTILL_ENABLED", "false")
    get_settings.cache_clear()

    service = SessionsService()
    detail = await service.get_session_detail("thr_123", interactive_session_allowed=False)

    assert len(detail.events) == 1
    assert detail.events[0].text == "new turn"


@pytest.mark.asyncio
async def test_session_detail_distills_large_event_text(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "06"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-thr_123.jsonl"
    large_text = "A" * 200
    rollout_path.write_text(
        json.dumps(
            {
                "timestamp": "2026-04-06T00:10:00.000Z",
                "type": "event_msg",
                "payload": {"type": "log", "message": large_text},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (codex_home / "session_index.jsonl").write_text(
        json.dumps({"id": "thr_123", "thread_name": "Distill test", "updated_at": "2026-04-06T00:12:00Z"}) + "\n",
        encoding="utf-8",
    )
    _write_sqlite(codex_home / "state_5.sqlite")

    monkeypatch.setenv("CODEX_LB_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CODEX_LB_SESSIONS_DISTILL_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_DISTILL_PROVIDER", "internal")
    monkeypatch.setenv("CODEX_LB_SESSIONS_DISTILL_MIN_CHARS", "50")
    monkeypatch.setenv("CODEX_LB_SESSIONS_DISTILL_TARGET_CHARS", "40")
    get_settings.cache_clear()

    service = SessionsService()
    detail = await service.get_session_detail("thr_123", interactive_session_allowed=False)

    assert len(detail.events) == 1
    assert detail.events[0].text is not None
    assert "[distilled: omitted" in detail.events[0].text


@pytest.mark.asyncio
async def test_session_detail_prefers_diff_when_smaller(tmp_path, monkeypatch):
    codex_home = tmp_path / ".codex"
    rollout_dir = codex_home / "sessions" / "2026" / "04" / "06"
    rollout_dir.mkdir(parents=True)
    rollout_path = rollout_dir / "rollout-thr_123.jsonl"
    base_text = "\n".join([f"line {i}" for i in range(1, 20)])
    updated_text = base_text.replace("line 12", "line 12 changed")
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:10:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": base_text}],
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-06T00:11:00.000Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": updated_text}],
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (codex_home / "session_index.jsonl").write_text(
        json.dumps({"id": "thr_123", "thread_name": "Diff test", "updated_at": "2026-04-06T00:12:00Z"}) + "\n",
        encoding="utf-8",
    )
    _write_sqlite(codex_home / "state_5.sqlite")

    monkeypatch.setenv("CODEX_LB_SESSIONS_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CODEX_LB_SESSIONS_DISTILL_ENABLED", "false")
    monkeypatch.setenv("CODEX_LB_SESSIONS_DIFF_ENABLED", "true")
    monkeypatch.setenv("CODEX_LB_SESSIONS_DIFF_FALLBACK_RATIO", "1.0")
    get_settings.cache_clear()

    service = SessionsService()
    detail = await service.get_session_detail("thr_123", interactive_session_allowed=False)

    assert len(detail.events) == 2
    assert detail.events[1].text is not None
    assert detail.events[1].text.startswith("[diff-only update]")
