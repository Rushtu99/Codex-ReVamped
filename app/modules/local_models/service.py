from __future__ import annotations

import os
from typing import Any

import httpx

from app.modules.local_models.schemas import (
    LocalModelEntry,
    LocalModelListResponse,
    LocalModelMetricsResponse,
    LocalModelStatusResponse,
)


class LocalModelsService:
    def __init__(self, bridge_url: str | None = None, timeout_seconds: float = 3.0) -> None:
        self._bridge_url = (bridge_url or os.getenv("CODEX_LB_LOCAL_MODELS_BRIDGE_URL") or "http://127.0.0.1:17654").rstrip(
            "/"
        )
        self._timeout = timeout_seconds

    async def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self._bridge_url}{path}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        if isinstance(payload, dict):
            return payload
        return {}

    async def status(self) -> LocalModelStatusResponse:
        try:
            payload = await self._get_json("/status")
        except Exception:
            return LocalModelStatusResponse(
                bridge_running=False,
                ollama_running=False,
                endpoint=self._bridge_url,
                loaded_count=0,
            )

        return LocalModelStatusResponse(
            bridge_running=bool(payload.get("bridgeRunning", True)),
            ollama_running=bool(payload.get("ollamaRunning", False)),
            endpoint=str(payload.get("endpoint") or self._bridge_url),
            loaded_count=int(payload.get("loadedCount") or 0),
        )

    async def models(self) -> LocalModelListResponse:
        try:
            payload = await self._get_json("/models")
            raw_models = payload.get("models", [])
        except Exception:
            raw_models = []

        models: list[LocalModelEntry] = []
        if isinstance(raw_models, list):
            for raw in raw_models:
                if not isinstance(raw, dict):
                    continue
                models.append(
                    LocalModelEntry(
                        name=str(raw.get("name") or ""),
                        digest=str(raw.get("digest")) if raw.get("digest") else None,
                        size_bytes=int(raw.get("sizeBytes") or 0),
                        modified_at=raw.get("modifiedAt"),
                        loaded=bool(raw.get("loaded", False)),
                        loaded_size_bytes=int(raw.get("loadedSizeBytes") or 0),
                        last_used_at=raw.get("lastUsedAt"),
                    )
                )
        return LocalModelListResponse(models=models)

    async def metrics(self) -> LocalModelMetricsResponse:
        try:
            payload = await self._get_json("/metrics")
        except Exception:
            payload = {}

        return LocalModelMetricsResponse(
            local_tps=float(payload.get("localTps") or 0.0),
            request_count=int(payload.get("requestCount") or 0),
            queue_depth=int(payload.get("queueDepth") or 0),
            quota_saved_tokens=int(payload.get("quotaSavedTokens") or 0),
            quota_saved_percent=float(payload.get("quotaSavedPercent") or 0.0),
        )
