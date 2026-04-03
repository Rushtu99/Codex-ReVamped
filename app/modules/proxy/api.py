from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import cast

from fastapi import APIRouter, Body, Depends, File, Form, Request, Response, Security, UploadFile, WebSocket
from fastapi.responses import JSONResponse, StreamingResponse
import httpx
from pydantic import ValidationError

from app.core.auth.dependencies import (
    set_openai_error_format,
    validate_codex_usage_identity,
    validate_proxy_api_key,
    validate_proxy_api_key_authorization,
)
from app.core.clients.proxy import ProxyResponseError
from app.core.config.settings import get_settings
from app.core.errors import OpenAIErrorEnvelope, openai_error
from app.core.exceptions import ProxyAuthError, ProxyRateLimitError
from app.core.middleware.api_firewall import _parse_trusted_proxy_networks, resolve_connection_client_ip
from app.core.openai.chat_requests import ChatCompletionsRequest
from app.core.openai.chat_responses import ChatCompletionResult, collect_chat_completion, stream_chat_chunks
from app.core.openai.exceptions import ClientPayloadError
from app.core.openai.model_registry import UpstreamModel, get_model_registry, is_public_model
from app.core.openai.models import (
    CompactResponseResult,
    OpenAIError,
    OpenAIResponsePayload,
    OpenAIResponseResult,
)
from app.core.openai.models import (
    OpenAIErrorEnvelope as OpenAIErrorEnvelopeModel,
)
from app.core.openai.parsing import parse_response_payload
from app.core.openai.requests import ResponsesCompactRequest, ResponsesRequest
from app.core.openai.v1_requests import V1ResponsesCompactRequest, V1ResponsesRequest
from app.core.runtime_logging import log_error_response
from app.core.types import JsonValue
from app.core.utils.json_guards import is_json_mapping
from app.core.utils.request_id import ensure_request_id
from app.core.utils.sse import format_sse_event, parse_sse_data_json
from app.db.session import get_background_session
from app.dependencies import ProxyContext, get_proxy_context, get_proxy_websocket_context
from app.modules.api_keys.repository import ApiKeysRepository
from app.modules.api_keys.service import (
    ApiKeyData,
    ApiKeyInvalidError,
    ApiKeyRateLimitExceededError,
    ApiKeysService,
    ApiKeyUsageReservationData,
)
from app.modules.firewall.repository import FirewallRepository
from app.modules.firewall.service import FirewallRepositoryPort, FirewallService
from app.modules.proxy import service as proxy_service_module
from app.modules.proxy.request_policy import (
    apply_api_key_enforcement,
    openai_invalid_payload_error,
    openai_validation_error,
    validate_model_access,
)
from app.modules.proxy.schemas import (
    ModelListItem,
    ModelListResponse,
    ModelMetadata,
    RateLimitStatusPayload,
    ReasoningLevelSchema,
)
from app.modules.request_logs.repository import RequestLogsRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/backend-api/codex",
    tags=["proxy"],
    dependencies=[Security(validate_proxy_api_key), Depends(set_openai_error_format)],
)
ws_router = APIRouter(
    prefix="/backend-api/codex",
    tags=["proxy"],
)
v1_router = APIRouter(
    prefix="/v1",
    tags=["proxy"],
    dependencies=[Security(validate_proxy_api_key), Depends(set_openai_error_format)],
)
v1_ws_router = APIRouter(
    prefix="/v1",
    tags=["proxy"],
)
usage_router = APIRouter(
    tags=["proxy"],
    dependencies=[Depends(validate_codex_usage_identity), Depends(set_openai_error_format)],
)
transcribe_router = APIRouter(
    prefix="/backend-api",
    tags=["proxy"],
    dependencies=[Security(validate_proxy_api_key), Depends(set_openai_error_format)],
)

_TRANSCRIPTION_MODEL = "gpt-4o-transcribe"
_UNAVAILABLE_SELECTION_ERROR_CODES = {
    "no_accounts",
    "no_plan_support_for_model",
    "additional_quota_data_unavailable",
    "no_additional_quota_eligible_accounts",
}
_LOCAL_MODEL_PREFIXES = ("ollama/", "local/")
_LOCAL_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
_LOCAL_OLLAMA_TIMEOUT_SECONDS = 120.0


@dataclass(slots=True)
class _LocalResponseExecution:
    lines: list[str]
    response_payload: OpenAIResponsePayload | None
    error_payload: OpenAIErrorEnvelopeModel | None
    status_code: int


@router.post(
    "/responses",
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
async def responses(
    request: Request,
    payload: ResponsesRequest = Body(...),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> Response:
    return await _stream_responses(
        request,
        payload,
        context,
        api_key,
        codex_session_affinity=True,
        openai_cache_affinity=True,
        prefer_http_bridge=True,
    )


@ws_router.websocket("/responses")
async def responses_websocket(
    websocket: WebSocket,
    context: ProxyContext = Depends(get_proxy_websocket_context),
) -> None:
    api_key, denial = await _validate_proxy_websocket_request(websocket)
    if denial is not None:
        await websocket.send_denial_response(denial)
        return
    turn_state = proxy_service_module.ensure_downstream_turn_state(websocket.headers)
    await websocket.accept(headers=proxy_service_module.build_downstream_turn_state_accept_headers(turn_state))
    forwarded_headers = dict(websocket.headers)
    forwarded_headers.setdefault("x-codex-turn-state", turn_state)
    await context.service.proxy_responses_websocket(
        websocket,
        forwarded_headers,
        codex_session_affinity=True,
        openai_cache_affinity=True,
        api_key=api_key,
    )


@v1_router.post(
    "/responses",
    response_model=OpenAIResponseResult,
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
async def v1_responses(
    request: Request,
    payload: V1ResponsesRequest = Body(...),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> Response:
    try:
        responses_payload = payload.to_responses_request()
    except ClientPayloadError as exc:
        error = openai_invalid_payload_error(exc.param)
        return _logged_error_json_response(request, 400, error)
    except ValidationError as exc:
        error = openai_validation_error(exc)
        return _logged_error_json_response(request, 400, error)
    if responses_payload.stream:
        return await _stream_responses(
            request,
            responses_payload,
            context,
            api_key,
            codex_session_affinity=False,
            openai_cache_affinity=True,
            prefer_http_bridge=True,
        )
    return await _collect_responses(
        request,
        responses_payload,
        context,
        api_key,
        codex_session_affinity=False,
        openai_cache_affinity=True,
        prefer_http_bridge=True,
    )


@v1_ws_router.websocket("/responses")
async def v1_responses_websocket(
    websocket: WebSocket,
    context: ProxyContext = Depends(get_proxy_websocket_context),
) -> None:
    api_key, denial = await _validate_proxy_websocket_request(websocket)
    if denial is not None:
        await websocket.send_denial_response(denial)
        return
    turn_state = proxy_service_module.ensure_downstream_turn_state(websocket.headers)
    await websocket.accept(headers=proxy_service_module.build_downstream_turn_state_accept_headers(turn_state))
    forwarded_headers = dict(websocket.headers)
    forwarded_headers.setdefault("x-codex-turn-state", turn_state)
    await context.service.proxy_responses_websocket(
        websocket,
        forwarded_headers,
        codex_session_affinity=False,
        openai_cache_affinity=True,
        api_key=api_key,
    )


@router.get("/models", response_model=ModelListResponse)
async def models(
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> Response:
    return await _build_models_response(api_key)


@v1_router.get("/models", response_model=ModelListResponse)
async def v1_models(
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> Response:
    return await _build_models_response(api_key)


@transcribe_router.post("/transcribe")
async def backend_transcribe(
    request: Request,
    file: UploadFile = File(...),
    prompt: str | None = Form(None),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> JSONResponse:
    return await _transcribe_request(
        request=request,
        file=file,
        prompt=prompt,
        context=context,
        api_key=api_key,
    )


@v1_router.post("/audio/transcriptions")
async def v1_audio_transcriptions(
    request: Request,
    model: str = Form(...),
    file: UploadFile = File(...),
    prompt: str | None = Form(None),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> JSONResponse:
    if model != _TRANSCRIPTION_MODEL:
        return _logged_error_json_response(
            request,
            status_code=400,
            content=_openai_invalid_transcription_model_error(model),
        )
    return await _transcribe_request(
        request=request,
        file=file,
        prompt=prompt,
        context=context,
        api_key=api_key,
    )


async def _build_models_response(api_key: ApiKeyData | None) -> Response:
    reservation = await _enforce_request_limits(
        api_key,
        request_model=None,
        request_service_tier=None,
    )

    allowed_models = set(api_key.allowed_models) if api_key and api_key.allowed_models else None
    if api_key and api_key.enforced_model:
        forced = {api_key.enforced_model}
        allowed_models = forced if allowed_models is None else (allowed_models & forced)
    created = int(time.time())

    registry = get_model_registry()
    snapshot = registry.get_snapshot()

    if snapshot is None:
        await _release_reservation(reservation)
        return JSONResponse(content=ModelListResponse(data=[]).model_dump(mode="json"))

    items: list[ModelListItem] = []
    for slug, model in snapshot.models.items():
        if not is_public_model(model, allowed_models):
            continue
        items.append(
            ModelListItem(
                id=slug,
                created=created,
                owned_by="codex-lb",
                metadata=_to_model_metadata(model),
            )
        )
    await _release_reservation(reservation)
    return JSONResponse(content=ModelListResponse(data=items).model_dump(mode="json"))


def _to_model_metadata(model: UpstreamModel) -> ModelMetadata:
    return ModelMetadata(
        display_name=model.display_name,
        description=model.description,
        context_window=model.context_window,
        input_modalities=list(model.input_modalities),
        supported_reasoning_levels=[
            ReasoningLevelSchema(effort=rl.effort, description=rl.description)
            for rl in model.supported_reasoning_levels
        ],
        default_reasoning_level=model.default_reasoning_level,
        supports_reasoning_summaries=model.supports_reasoning_summaries,
        support_verbosity=model.support_verbosity,
        default_verbosity=model.default_verbosity,
        prefer_websockets=model.prefer_websockets,
        supports_parallel_tool_calls=model.supports_parallel_tool_calls,
        supported_in_api=model.supported_in_api,
        minimal_client_version=model.minimal_client_version,
        priority=model.priority,
    )


@v1_router.post(
    "/chat/completions",
    response_model=ChatCompletionResult,
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"},
                }
            }
        }
    },
)
async def v1_chat_completions(
    request: Request,
    payload: ChatCompletionsRequest = Body(...),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> Response:
    effective_model = _effective_model_for_api_key(api_key, payload.model)
    validate_model_access(api_key, effective_model)

    rate_limit_headers = await context.service.rate_limit_headers()
    try:
        responses_payload = payload.to_responses_request()
    except ClientPayloadError as exc:
        error = openai_invalid_payload_error(exc.param)
        return _logged_error_json_response(request, 400, error, headers=rate_limit_headers)
    except ValidationError as exc:
        error = openai_validation_error(exc)
        return _logged_error_json_response(request, 400, error, headers=rate_limit_headers)
    reservation = await _enforce_request_limits(
        api_key,
        request_model=effective_model,
        request_service_tier=responses_payload.service_tier,
    )
    local_execution = await _execute_local_response(
        responses_payload,
        api_key=api_key,
        reservation=reservation,
        request_transport="http",
    )
    if local_execution is not None:
        if local_execution.error_payload is not None:
            return _logged_error_json_response(
                request,
                local_execution.status_code,
                local_execution.error_payload.model_dump(mode="json", exclude_none=True),
                headers=rate_limit_headers,
            )
        local_stream = _stream_local_lines(local_execution.lines)
        if payload.stream:
            stream_options = payload.stream_options
            include_usage = bool(stream_options and stream_options.include_usage)
            return StreamingResponse(
                stream_chat_chunks(local_stream, model=responses_payload.model, include_usage=include_usage),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", **rate_limit_headers},
            )
        result = await collect_chat_completion(local_stream, model=responses_payload.model)
        if isinstance(result, OpenAIErrorEnvelopeModel):
            error = result.error
            code = error.code if error else None
            status_code = 503 if code in _UNAVAILABLE_SELECTION_ERROR_CODES else 502
            return _logged_error_json_response(
                request,
                status_code,
                content=result.model_dump(mode="json", exclude_none=True),
                headers=rate_limit_headers,
            )
        return JSONResponse(
            content=result.model_dump(mode="json", exclude_none=True),
            status_code=200,
            headers=rate_limit_headers,
        )

    responses_payload.stream = True
    apply_api_key_enforcement(responses_payload, api_key)
    stream = context.service.stream_responses(
        responses_payload,
        request.headers,
        codex_session_affinity=False,
        propagate_http_errors=True,
        openai_cache_affinity=True,
        api_key=api_key,
        api_key_reservation=reservation,
        suppress_text_done_events=True,
    )
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        first = None
    except ProxyResponseError as exc:
        return _logged_error_json_response(request, exc.status_code, exc.payload, headers=rate_limit_headers)

    stream_with_first = _prepend_first(first, stream)
    if payload.stream:
        stream_options = payload.stream_options
        include_usage = bool(stream_options and stream_options.include_usage)
        return StreamingResponse(
            stream_chat_chunks(stream_with_first, model=responses_payload.model, include_usage=include_usage),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", **rate_limit_headers},
        )

    result = await collect_chat_completion(stream_with_first, model=responses_payload.model)
    if isinstance(result, OpenAIErrorEnvelopeModel):
        error = result.error
        code = error.code if error else None
        status_code = 503 if code in _UNAVAILABLE_SELECTION_ERROR_CODES else 502
        return _logged_error_json_response(
            request,
            status_code,
            content=result.model_dump(mode="json", exclude_none=True),
            headers=rate_limit_headers,
        )
    return JSONResponse(
        content=result.model_dump(mode="json", exclude_none=True),
        status_code=200,
        headers=rate_limit_headers,
    )


async def _stream_responses(
    request: Request,
    payload: ResponsesRequest,
    context: ProxyContext,
    api_key: ApiKeyData | None,
    *,
    codex_session_affinity: bool = False,
    openai_cache_affinity: bool = False,
    suppress_text_done_events: bool = False,
    prefer_http_bridge: bool = False,
) -> Response:
    apply_api_key_enforcement(payload, api_key)
    validate_model_access(api_key, payload.model)
    reservation = await _enforce_request_limits(
        api_key,
        request_model=payload.model,
        request_service_tier=payload.service_tier,
    )

    rate_limit_headers = await context.service.rate_limit_headers()
    bridge_active = prefer_http_bridge and proxy_service_module.get_settings().http_responses_session_bridge_enabled
    downstream_turn_state = (
        proxy_service_module.ensure_http_downstream_turn_state(request.headers) if bridge_active else None
    )
    turn_state_headers = (
        proxy_service_module.build_downstream_turn_state_response_headers(downstream_turn_state)
        if downstream_turn_state is not None
        else {}
    )
    local_execution = await _execute_local_response(
        payload,
        api_key=api_key,
        reservation=reservation,
        request_transport="http",
    )
    if local_execution is not None:
        if local_execution.error_payload is not None:
            return _logged_error_json_response(
                request,
                local_execution.status_code,
                local_execution.error_payload.model_dump(mode="json", exclude_none=True),
                headers={**turn_state_headers, **rate_limit_headers},
            )
        return StreamingResponse(
            _stream_local_lines(local_execution.lines),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", **turn_state_headers, **rate_limit_headers},
        )

    payload.stream = True
    if prefer_http_bridge:
        stream = context.service.stream_http_responses(
            payload,
            request.headers,
            codex_session_affinity=codex_session_affinity,
            propagate_http_errors=True,
            openai_cache_affinity=openai_cache_affinity,
            api_key=api_key,
            api_key_reservation=reservation,
            suppress_text_done_events=suppress_text_done_events,
            downstream_turn_state=downstream_turn_state,
        )
    else:
        stream = context.service.stream_responses(
            payload,
            request.headers,
            codex_session_affinity=codex_session_affinity,
            propagate_http_errors=True,
            openai_cache_affinity=openai_cache_affinity,
            api_key=api_key,
            api_key_reservation=reservation,
            suppress_text_done_events=suppress_text_done_events,
        )
    try:
        first = await stream.__anext__()
    except StopAsyncIteration:
        return StreamingResponse(
            _prepend_first(None, stream),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", **rate_limit_headers},
        )
    except ProxyResponseError as exc:
        await _release_reservation(reservation)
        return _logged_error_json_response(
            request,
            exc.status_code,
            exc.payload,
            headers=rate_limit_headers,
        )
    return StreamingResponse(
        _prepend_first(first, stream),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", **turn_state_headers, **rate_limit_headers},
    )


async def _collect_responses(
    request: Request,
    payload: ResponsesRequest,
    context: ProxyContext,
    api_key: ApiKeyData | None,
    *,
    codex_session_affinity: bool = False,
    openai_cache_affinity: bool = False,
    suppress_text_done_events: bool = False,
    prefer_http_bridge: bool = False,
) -> Response:
    apply_api_key_enforcement(payload, api_key)
    validate_model_access(api_key, payload.model)
    reservation = await _enforce_request_limits(
        api_key,
        request_model=payload.model,
        request_service_tier=payload.service_tier,
    )

    rate_limit_headers = await context.service.rate_limit_headers()
    bridge_active = prefer_http_bridge and proxy_service_module.get_settings().http_responses_session_bridge_enabled
    downstream_turn_state = (
        proxy_service_module.ensure_http_downstream_turn_state(request.headers) if bridge_active else None
    )
    turn_state_headers = (
        proxy_service_module.build_downstream_turn_state_response_headers(downstream_turn_state)
        if downstream_turn_state is not None
        else {}
    )
    local_execution = await _execute_local_response(
        payload,
        api_key=api_key,
        reservation=reservation,
        request_transport="http",
    )
    if local_execution is not None:
        if local_execution.error_payload is not None:
            return _logged_error_json_response(
                request,
                local_execution.status_code,
                local_execution.error_payload.model_dump(mode="json", exclude_none=True),
                headers={**turn_state_headers, **rate_limit_headers},
            )
        if local_execution.response_payload is None:
            return _logged_error_json_response(
                request,
                502,
                _default_error_envelope().model_dump(mode="json", exclude_none=True),
                headers={**turn_state_headers, **rate_limit_headers},
            )
        return JSONResponse(
            content=local_execution.response_payload.model_dump(mode="json", exclude_none=True),
            headers={**turn_state_headers, **rate_limit_headers},
        )

    payload.stream = True
    if prefer_http_bridge:
        stream = context.service.stream_http_responses(
            payload,
            request.headers,
            codex_session_affinity=codex_session_affinity,
            propagate_http_errors=True,
            openai_cache_affinity=openai_cache_affinity,
            api_key=api_key,
            api_key_reservation=reservation,
            suppress_text_done_events=suppress_text_done_events,
            downstream_turn_state=downstream_turn_state,
        )
    else:
        stream = context.service.stream_responses(
            payload,
            request.headers,
            codex_session_affinity=codex_session_affinity,
            propagate_http_errors=True,
            openai_cache_affinity=openai_cache_affinity,
            api_key=api_key,
            api_key_reservation=reservation,
            suppress_text_done_events=suppress_text_done_events,
        )
    try:
        response_payload = await _collect_responses_payload(stream)
    except ProxyResponseError as exc:
        await _release_reservation(reservation)
        error = _parse_error_envelope(exc.payload)
        return _logged_error_json_response(
            request,
            exc.status_code,
            error.model_dump(mode="json", exclude_none=True),
            headers=rate_limit_headers,
        )
    if isinstance(response_payload, OpenAIResponsePayload):
        if response_payload.status == "failed":
            error_payload = _error_envelope_from_response(response_payload.error)
            status_code = _status_for_error(error_payload.error)
            return _logged_error_json_response(
                request,
                status_code,
                error_payload.model_dump(mode="json", exclude_none=True),
                headers={**turn_state_headers, **rate_limit_headers},
            )
        return JSONResponse(
            content=response_payload.model_dump(mode="json", exclude_none=True),
            headers={**turn_state_headers, **rate_limit_headers},
        )
    status_code = _status_for_error(response_payload.error)
    return _logged_error_json_response(
        request,
        status_code,
        response_payload.model_dump(mode="json", exclude_none=True),
        headers={**turn_state_headers, **rate_limit_headers},
    )


@router.post("/responses/compact", response_model=CompactResponseResult)
async def responses_compact(
    request: Request,
    payload: ResponsesCompactRequest = Body(...),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> JSONResponse:
    return await _compact_responses(
        request, payload, context, api_key, codex_session_affinity=True, openai_cache_affinity=True
    )


@v1_router.post("/responses/compact", response_model=CompactResponseResult)
async def v1_responses_compact(
    request: Request,
    payload: V1ResponsesCompactRequest = Body(...),
    context: ProxyContext = Depends(get_proxy_context),
    api_key: ApiKeyData | None = Security(validate_proxy_api_key),
) -> JSONResponse:
    try:
        compact_payload = payload.to_compact_request()
    except ClientPayloadError as exc:
        error = openai_invalid_payload_error(exc.param)
        return _logged_error_json_response(request, 400, error)
    except ValidationError as exc:
        error = openai_validation_error(exc)
        return _logged_error_json_response(request, 400, error)
    return await _compact_responses(
        request,
        compact_payload,
        context,
        api_key,
        codex_session_affinity=False,
        openai_cache_affinity=True,
    )


async def _compact_responses(
    request: Request,
    payload: ResponsesCompactRequest,
    context: ProxyContext,
    api_key: ApiKeyData | None,
    codex_session_affinity: bool = False,
    openai_cache_affinity: bool = False,
) -> JSONResponse:
    apply_api_key_enforcement(payload, api_key)
    validate_model_access(api_key, payload.model)
    reservation = await _enforce_request_limits(
        api_key,
        request_model=payload.model,
        request_service_tier=_compact_request_service_tier(payload),
    )

    rate_limit_headers = await context.service.rate_limit_headers()
    try:
        result = await context.service.compact_responses(
            payload,
            request.headers,
            codex_session_affinity=codex_session_affinity,
            openai_cache_affinity=openai_cache_affinity,
            api_key=api_key,
            api_key_reservation=reservation,
        )
    except NotImplementedError:
        error = OpenAIErrorEnvelopeModel(
            error=OpenAIError(
                message="responses/compact is not implemented",
                type="server_error",
                code="not_implemented",
            )
        )
        return _logged_error_json_response(
            request,
            501,
            error.model_dump(mode="json", exclude_none=True),
            headers=rate_limit_headers,
        )
    except ProxyResponseError as exc:
        error = _parse_error_envelope(exc.payload)
        return _logged_error_json_response(
            request,
            exc.status_code,
            error.model_dump(mode="json", exclude_none=True),
            headers=rate_limit_headers,
        )
    finally:
        await _release_reservation(reservation)
    return JSONResponse(
        content=result.model_dump(mode="json", exclude_none=True),
        headers=rate_limit_headers,
    )


async def _transcribe_request(
    *,
    request: Request,
    file: UploadFile,
    prompt: str | None,
    context: ProxyContext,
    api_key: ApiKeyData | None,
) -> JSONResponse:
    validate_model_access(api_key, _TRANSCRIPTION_MODEL)
    reservation = await _enforce_request_limits(
        api_key,
        request_model=_TRANSCRIPTION_MODEL,
        request_service_tier=None,
    )
    rate_limit_headers = await context.service.rate_limit_headers()
    try:
        audio_bytes = await file.read()
        result = await context.service.transcribe(
            audio_bytes=audio_bytes,
            filename=file.filename or "audio.wav",
            content_type=file.content_type,
            prompt=prompt,
            headers=request.headers,
            api_key=api_key,
        )
    except ProxyResponseError as exc:
        error = _parse_error_envelope(exc.payload)
        return _logged_error_json_response(
            request,
            exc.status_code,
            error.model_dump(mode="json", exclude_none=True),
            headers=rate_limit_headers,
        )
    finally:
        await _release_reservation(reservation)
    return JSONResponse(content=result, headers=rate_limit_headers)


@usage_router.get("/api/codex/usage", response_model=RateLimitStatusPayload)
@usage_router.get("/api/codex/usage/", response_model=RateLimitStatusPayload, include_in_schema=False)
async def codex_usage(
    context: ProxyContext = Depends(get_proxy_context),
) -> RateLimitStatusPayload:
    payload = await context.service.get_rate_limit_payload()
    return RateLimitStatusPayload.from_data(payload)


async def _prepend_first(first: str | None, stream: AsyncIterator[str]) -> AsyncIterator[str]:
    if first is not None:
        yield first
    async for line in stream:
        yield line


def _parse_sse_payload(line: str) -> dict[str, JsonValue] | None:
    return parse_sse_data_json(line)


async def _stream_local_lines(lines: list[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


def _is_local_model(model: str) -> bool:
    normalized = model.strip().lower()
    return any(normalized.startswith(prefix) for prefix in _LOCAL_MODEL_PREFIXES)


def _resolve_local_model_name(model: str) -> str:
    normalized = model.strip()
    for prefix in _LOCAL_MODEL_PREFIXES:
        if normalized.lower().startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def _ollama_base_url() -> str:
    return os.getenv("CODEX_LB_LOCAL_OLLAMA_BASE_URL", _LOCAL_OLLAMA_BASE_URL).rstrip("/")


def _ollama_timeout_seconds() -> float:
    raw = os.getenv("CODEX_LB_LOCAL_OLLAMA_TIMEOUT_SECONDS")
    if not raw:
        return _LOCAL_OLLAMA_TIMEOUT_SECONDS
    try:
        parsed = float(raw)
    except ValueError:
        return _LOCAL_OLLAMA_TIMEOUT_SECONDS
    return parsed if parsed > 0 else _LOCAL_OLLAMA_TIMEOUT_SECONDS


def _extract_prompt_text(input_value: JsonValue) -> str:
    if isinstance(input_value, str):
        return input_value.strip()

    fragments: list[str] = []

    def visit(value: JsonValue) -> None:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                fragments.append(stripped)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return

        text_value = value.get("text")
        if isinstance(text_value, str):
            stripped = text_value.strip()
            if stripped:
                fragments.append(stripped)

        content_value = value.get("content")
        if content_value is not None:
            visit(content_value)

        input_field = value.get("input")
        if input_field is not None:
            visit(input_field)

    visit(input_value)
    deduped: list[str] = []
    seen: set[str] = set()
    for fragment in fragments:
        if fragment in seen:
            continue
        deduped.append(fragment)
        seen.add(fragment)
    return "\n".join(deduped).strip()


def _build_local_prompt(payload: ResponsesRequest) -> str:
    parts: list[str] = []
    instructions = payload.instructions.strip()
    if instructions:
        parts.append(instructions)
    extracted = _extract_prompt_text(payload.input)
    if extracted:
        parts.append(extracted)
    return "\n\n".join(parts).strip() or "Continue."


async def _finalize_local_reservation(
    reservation: ApiKeyUsageReservationData | None,
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    service_tier: str | None,
) -> None:
    if reservation is None:
        return
    async with get_background_session() as session:
        service = ApiKeysService(ApiKeysRepository(session))
        try:
            await service.finalize_usage_reservation(
                reservation.reservation_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=0,
                service_tier=service_tier,
            )
        except Exception:
            logger.warning("Failed to finalize local API key reservation id=%s", reservation.reservation_id, exc_info=True)
            await service.release_usage_reservation(reservation.reservation_id)


async def _write_local_request_log(
    *,
    request_id: str,
    model: str,
    api_key: ApiKeyData | None,
    status: str,
    error_code: str | None,
    error_message: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    latency_ms: int | None,
    reasoning_effort: str | None,
    service_tier: str | None,
    transport: str,
) -> None:
    async with get_background_session() as session:
        repository = RequestLogsRepository(session)
        await repository.add_log(
            account_id=None,
            api_key_id=api_key.id if api_key else None,
            request_id=request_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
            error_message=error_message,
            cached_input_tokens=0,
            reasoning_tokens=None,
            reasoning_effort=reasoning_effort,
            service_tier=service_tier,
            requested_service_tier=service_tier,
            actual_service_tier=service_tier if status == "success" else None,
            transport=transport,
            requested_at=None,
        )


def _local_response_payload(
    *,
    response_id: str,
    model: str,
    text: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, JsonValue]:
    total_tokens = max(0, input_tokens) + max(0, output_tokens)
    return {
        "id": response_id,
        "status": "completed",
        "model": model,
        "output": [
            {
                "id": f"msg_{response_id}",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text,
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


def _local_error_execution(
    *,
    response_id: str,
    status_code: int,
    error_payload: OpenAIErrorEnvelopeModel,
) -> _LocalResponseExecution:
    error = error_payload.error.model_dump(mode="json", exclude_none=True) if error_payload.error else {}
    failed_event = {
        "type": "response.failed",
        "response": {
            "id": response_id,
            "status": "failed",
            "error": error,
        },
    }
    return _LocalResponseExecution(
        lines=[format_sse_event(failed_event)],
        response_payload=None,
        error_payload=error_payload,
        status_code=status_code,
    )


async def _execute_local_response(
    payload: ResponsesRequest,
    *,
    api_key: ApiKeyData | None,
    reservation: ApiKeyUsageReservationData | None,
    request_transport: str,
) -> _LocalResponseExecution | None:
    if not _is_local_model(payload.model):
        return None

    request_id = ensure_request_id()
    response_id = f"resp_local_{request_id}"
    model = payload.model
    ollama_model = _resolve_local_model_name(model)
    prompt = _build_local_prompt(payload)
    started = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=_ollama_timeout_seconds()) as client:
            response = await client.post(
                f"{_ollama_base_url()}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            raw_payload = response.json()
    except httpx.HTTPStatusError as exc:
        message = f"Local model request failed ({exc.response.status_code})"
        try:
            parsed = exc.response.json()
            if isinstance(parsed, dict):
                maybe_error = parsed.get("error")
                if isinstance(maybe_error, str) and maybe_error.strip():
                    message = maybe_error.strip()
        except Exception:
            pass
        code = "local_model_not_found" if exc.response.status_code == 404 else "local_model_error"
        status_code = 503 if exc.response.status_code in {404, 429, 500, 502, 503, 504} else 502
        envelope = OpenAIErrorEnvelopeModel(
            error=OpenAIError(
                message=message,
                type="server_error",
                code=code,
            )
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        await _write_local_request_log(
            request_id=request_id,
            model=model,
            api_key=api_key,
            status="error",
            error_code=code,
            error_message=message,
            input_tokens=None,
            output_tokens=None,
            latency_ms=latency_ms,
            reasoning_effort=payload.reasoning.effort if payload.reasoning else None,
            service_tier=payload.service_tier,
            transport=request_transport,
        )
        await _release_reservation(reservation)
        return _local_error_execution(response_id=response_id, status_code=status_code, error_payload=envelope)
    except Exception as exc:
        message = str(exc) or "Local model unavailable"
        envelope = OpenAIErrorEnvelopeModel(
            error=OpenAIError(
                message=message,
                type="server_error",
                code="local_model_unavailable",
            )
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        await _write_local_request_log(
            request_id=request_id,
            model=model,
            api_key=api_key,
            status="error",
            error_code="local_model_unavailable",
            error_message=message,
            input_tokens=None,
            output_tokens=None,
            latency_ms=latency_ms,
            reasoning_effort=payload.reasoning.effort if payload.reasoning else None,
            service_tier=payload.service_tier,
            transport=request_transport,
        )
        await _release_reservation(reservation)
        return _local_error_execution(response_id=response_id, status_code=503, error_payload=envelope)

    if not isinstance(raw_payload, dict):
        raw_payload = {}
    text = raw_payload.get("response")
    response_text = text if isinstance(text, str) else ""
    input_tokens = int(raw_payload.get("prompt_eval_count") or 0)
    output_tokens = int(raw_payload.get("eval_count") or 0)
    response_payload_raw = _local_response_payload(
        response_id=response_id,
        model=model,
        text=response_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    parsed_payload = parse_response_payload(response_payload_raw)
    if parsed_payload is None:
        parsed_payload = OpenAIResponsePayload.model_validate(response_payload_raw)

    lines: list[str] = []
    if response_text:
        lines.append(format_sse_event({"type": "response.output_text.delta", "delta": response_text}))
    lines.append(format_sse_event({"type": "response.completed", "response": response_payload_raw}))

    latency_ms = int((time.monotonic() - started) * 1000)
    await _write_local_request_log(
        request_id=request_id,
        model=model,
        api_key=api_key,
        status="success",
        error_code=None,
        error_message=None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        reasoning_effort=payload.reasoning.effort if payload.reasoning else None,
        service_tier=payload.service_tier,
        transport=request_transport,
    )
    await _finalize_local_reservation(
        reservation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        service_tier=payload.service_tier,
    )

    return _LocalResponseExecution(
        lines=lines,
        response_payload=parsed_payload,
        error_payload=None,
        status_code=200,
    )


def _logged_error_json_response(
    request: Request,
    status_code: int,
    content: Mapping[str, JsonValue] | OpenAIErrorEnvelopeModel | OpenAIErrorEnvelope,
    *,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    code, message = _error_details_from_content(content)
    log_error_response(
        logger,
        request,
        status_code,
        code,
        message,
        category="proxy_error_response",
    )
    return JSONResponse(status_code=status_code, content=content, headers=headers)


def _error_details_from_content(
    content: Mapping[str, JsonValue] | OpenAIErrorEnvelopeModel | OpenAIErrorEnvelope,
) -> tuple[str | None, str | None]:
    if isinstance(content, OpenAIErrorEnvelopeModel):
        error = content.error
        if error is None:
            return None, None
        return error.code, error.message
    if not isinstance(content, Mapping):
        return None, None
    error = content.get("error")
    if not is_json_mapping(error):
        return None, None
    error_mapping = cast(Mapping[str, JsonValue], error)
    code = error_mapping.get("code")
    message = error_mapping.get("message")
    return code if isinstance(code, str) else None, message if isinstance(message, str) else None


async def _validate_proxy_websocket_request(
    websocket: WebSocket,
) -> tuple[ApiKeyData | None, JSONResponse | None]:
    denial = await _websocket_firewall_denial_response(websocket)
    if denial is not None:
        return None, denial
    try:
        api_key = await validate_proxy_api_key_authorization(websocket.headers.get("authorization"))
    except ProxyAuthError as exc:
        return None, JSONResponse(
            status_code=exc.status_code,
            content=openai_error(exc.code, exc.message, error_type=exc.error_type),
        )
    return api_key, None


async def _websocket_firewall_denial_response(websocket: WebSocket) -> JSONResponse | None:
    settings = get_settings()
    client_ip = resolve_connection_client_ip(
        websocket.headers,
        websocket.client.host if websocket.client else None,
        trust_proxy_headers=settings.firewall_trust_proxy_headers,
        trusted_proxy_networks=_parse_trusted_proxy_networks(settings.firewall_trusted_proxy_cidrs),
    )
    async with get_background_session() as session:
        repository = cast(FirewallRepositoryPort, FirewallRepository(session))
        service = FirewallService(repository)
        if await service.is_ip_allowed(client_ip):
            return None
    return JSONResponse(
        status_code=403,
        content=openai_error("ip_forbidden", "Access denied for client IP", error_type="access_error"),
    )


async def _enforce_request_limits(
    api_key: ApiKeyData | None,
    *,
    request_model: str | None,
    request_service_tier: str | None,
) -> ApiKeyUsageReservationData | None:
    if api_key is None:
        return None

    async with get_background_session() as session:
        service = ApiKeysService(ApiKeysRepository(session))
        try:
            return await service.enforce_limits_for_request(
                api_key.id,
                request_model=request_model,
                request_service_tier=request_service_tier,
            )
        except ApiKeyRateLimitExceededError as exc:
            message = f"{exc}. Usage resets at {exc.reset_at.isoformat()}Z."
            raise ProxyRateLimitError(message) from exc
        except ApiKeyInvalidError as exc:
            raise ProxyAuthError(str(exc)) from exc


async def _release_reservation(reservation: ApiKeyUsageReservationData | None) -> None:
    if reservation is None:
        return
    async with get_background_session() as session:
        service = ApiKeysService(ApiKeysRepository(session))
        await service.release_usage_reservation(reservation.reservation_id)


def _effective_model_for_api_key(api_key: ApiKeyData | None, requested_model: str) -> str:
    if api_key is None or api_key.enforced_model is None:
        return requested_model
    return api_key.enforced_model


def _compact_request_service_tier(payload: ResponsesCompactRequest) -> str | None:
    if not payload.model_extra:
        return None
    value = payload.model_extra.get("service_tier")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


async def _collect_responses_payload(stream: AsyncIterator[str]) -> OpenAIResponseResult:
    output_items: dict[int, dict[str, JsonValue]] = {}
    terminal_result: OpenAIResponseResult | None = None
    async for line in stream:
        payload = _parse_sse_payload(line)
        if not payload:
            continue
        event_type = payload.get("type")
        _collect_output_item_event(payload, output_items)
        if terminal_result is not None:
            continue
        if event_type == "error":
            terminal_result = _parse_event_error_envelope(payload)
            continue
        if event_type == "response.failed":
            response = payload.get("response")
            if isinstance(response, dict):
                error_value = response.get("error")
                if isinstance(error_value, dict):
                    try:
                        terminal_result = OpenAIErrorEnvelopeModel.model_validate({"error": error_value})
                        continue
                    except ValidationError:
                        terminal_result = _default_error_envelope()
                        continue
                parsed = parse_response_payload(response)
                if parsed is not None and parsed.error is not None:
                    terminal_result = _error_envelope_from_response(parsed.error)
                    continue
            terminal_result = _default_error_envelope()
            continue
        if event_type in ("response.completed", "response.incomplete"):
            response = payload.get("response")
            if isinstance(response, dict):
                parsed = parse_response_payload(_merge_collected_output_items(response, output_items))
                if parsed is not None:
                    terminal_result = parsed
                    continue
            terminal_result = _default_error_envelope()

    if terminal_result is not None:
        return terminal_result
    return _default_error_envelope()


def _collect_output_item_event(
    payload: dict[str, JsonValue],
    output_items: dict[int, dict[str, JsonValue]],
) -> None:
    event_type = payload.get("type")
    if event_type not in ("response.output_item.added", "response.output_item.done"):
        return
    output_index = payload.get("output_index")
    item = payload.get("item")
    if not isinstance(output_index, int) or not isinstance(item, dict):
        return
    output_items[output_index] = dict(item)


def _merge_collected_output_items(
    response: Mapping[str, JsonValue],
    output_items: dict[int, dict[str, JsonValue]],
) -> dict[str, JsonValue]:
    merged = dict(response)
    if not output_items:
        return merged

    existing_output = response.get("output")
    if isinstance(existing_output, list) and existing_output:
        return merged

    merged["output"] = [item for _, item in sorted(output_items.items())]
    return merged


def _parse_event_error_envelope(payload: dict[str, JsonValue]) -> OpenAIErrorEnvelopeModel:
    error_value = payload.get("error")
    if isinstance(error_value, dict):
        try:
            return OpenAIErrorEnvelopeModel.model_validate({"error": error_value})
        except ValidationError:
            return _default_error_envelope()
    return _default_error_envelope()


def _default_error_envelope() -> OpenAIErrorEnvelopeModel:
    return OpenAIErrorEnvelopeModel(
        error=OpenAIError(
            message="Upstream error",
            type="server_error",
            code="upstream_error",
        )
    )


def _parse_error_envelope(payload: JsonValue | OpenAIErrorEnvelope) -> OpenAIErrorEnvelopeModel:
    if not isinstance(payload, dict):
        return _default_error_envelope()
    try:
        return OpenAIErrorEnvelopeModel.model_validate(payload)
    except ValidationError:
        return _default_error_envelope()


def _openai_invalid_transcription_model_error(model: str) -> OpenAIErrorEnvelope:
    error = openai_error(
        "invalid_request_error",
        f"Unsupported transcription model '{model}'. Only '{_TRANSCRIPTION_MODEL}' is supported.",
        error_type="invalid_request_error",
    )
    error["error"]["param"] = "model"
    return error


def _error_envelope_from_response(error_value: OpenAIError | None) -> OpenAIErrorEnvelopeModel:
    if error_value is None:
        return _default_error_envelope()
    return OpenAIErrorEnvelopeModel(error=error_value)


def _status_for_error(error_value: OpenAIError | None) -> int:
    if error_value and error_value.code == "previous_response_not_found":
        return 400
    if error_value and error_value.code in _UNAVAILABLE_SELECTION_ERROR_CODES:
        return 503
    return 502
