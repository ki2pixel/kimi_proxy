---
name: kimi-proxy-streaming-debug
description: Expert debugging for streaming errors in Kimi Proxy Dashboard. Use when encountering ReadError, TimeoutException, ConnectError, or SSE streaming issues. Provides systematic troubleshooting for proxy streaming failures, token extraction problems, and WebSocket connection issues.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Streaming Debug

**TL;DR**: The current streaming layer is designed for best effort, not perfect resume. `proxy/stream.py` normalizes known streaming failures, still tries to extract partial usage from buffered SSE data in `finally`, and broadcasts `streaming_error` plus `metric_updated` events when possible.

## Source of Truth

Primary files:

- `src/kimi_proxy/proxy/stream.py`
- `src/kimi_proxy/proxy/client.py`
- `src/kimi_proxy/api/routes/proxy.py`
- `src/kimi_proxy/core/exceptions.py`
- `tests/e2e/test_streaming_errors.py`

## Known Streaming Error Types

`src/kimi_proxy/proxy/stream.py` defines the canonical streaming error map:

```python
STREAMING_ERROR_TYPES = {
    "read_error": "Connexion interrompue par le provider",
    "connect_error": "Impossible de se connecter au provider",
    "timeout_error": "Timeout lors de la lecture du stream",
    "decode_error": "Erreur de décodage des données",
    "unknown": "Erreur streaming inconnue",
}
```

These are the labels that should appear in docs and dashboards.

## What the Current Stream Layer Actually Does

### 1. Iterate the upstream stream

`stream_generator(...)` yields chunks as they arrive.

### 2. Capture known network failures

It handles at least:

- `httpx.ReadError`
- `httpx.ConnectError`
- `httpx.TimeoutException`
- unexpected generic exceptions

### 3. Extract partial usage even after failure

This is a critical current behavior.

```python
usage_data = extract_usage_from_stream(buffer, provider_type)
```

The code does this in `finally`, which means partial buffered SSE data can still update token metrics even if the stream ended badly.

### 4. Broadcast to the dashboard

When enough context is available, the backend can emit:

- `metric_updated`
- `streaming_error`

## WebSocket Error Broadcast

### ✅ Real event shape

```python
await manager.broadcast({
    "type": "streaming_error",
    "session_id": session_id,
    "metric_id": metric_id,
    "error_type": error_type,
    "error_message": STREAMING_ERROR_TYPES.get(error_type, STREAMING_ERROR_TYPES["unknown"]),
    "timestamp": datetime.now().isoformat(),
})
```

If you update frontend or monitoring docs, use this structure.

## Provider Timeouts

The stream layer currently keeps provider-specific timeout labels for chunk reads:

- `gemini`: `60.0`
- `kimi`: `30.0`
- `default`: `30.0`

Important nuance: these values are used by the stream helper for diagnostics and timeout messaging. Effective network behavior also depends on the surrounding HTTPX client configuration in the proxy layer.

## Request-Layer Retry vs Stream-Layer Recovery

### ✅ Real current behavior

- `proxy/client.py` retries request-level `ReadError`, `ConnectError`, and `TimeoutException`
- `proxy/stream.py` performs best-effort extraction and error broadcast after a stream has started

### ❌ Not the current behavior

- full stream resume with chunk replay
- transparent mid-stream reconnection that preserves the exact SSE session

Do not document full resume support unless it is actually added.

## Practical Debug Flow

### Inspect recent stream errors

```bash
./bin/kimi-proxy logs | grep "STREAM_ERROR" | tail -20
```

### Run the focused regression suite

```bash
PYTHONPATH=src python -m pytest tests/e2e/test_streaming_errors.py -q
```

### Check route-level proxy handling

Inspect `src/kimi_proxy/api/routes/proxy.py` for the JSON responses returned on `ReadError` / `TimeoutException` and for additional broadcasted provider-context alerts.

## `StreamingError` Exception

`src/kimi_proxy/core/exceptions.py` defines `StreamingError`, but the dominant runtime behavior currently relies on HTTPX exception handling plus normalized broadcast helpers in `proxy/stream.py`. Document both, but prioritize the actual code path the proxy uses today.

## Golden Rule

**For streaming docs, be explicit about best-effort behavior: partial tokens may still be recovered, errors are normalized, and dashboards are updated via WebSocket when possible.** Avoid promising resume semantics the code does not implement.