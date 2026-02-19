---
name: kimi-proxy-streaming-debug
description: Expert debugging for streaming errors in Kimi Proxy Dashboard. Use when encountering ReadError, TimeoutException, ConnectError, or SSE streaming issues. Provides systematic troubleshooting for proxy streaming failures, token extraction problems, and WebSocket connection issues.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Streaming Debug

This skill provides systematic debugging for streaming-related issues in Kimi Proxy Dashboard.

## Quick Diagnosis

### Common Streaming Errors

**ReadError**: Connection interrupted by provider
```bash
# Check provider status
./bin/kimi-proxy logs | grep "STREAM_ERROR"

# Verify timeouts in config.toml
[proxy.timeouts]
kimi = 120.0
nvidia = 150.0
```

**TimeoutException**: Response taking too long
```python
# Check current timeout configuration
from kimi_proxy.config.loader import get_config
config = get_config()
timeouts = config.get("proxy", {}).get("timeouts", {})
```

**ConnectError**: Cannot reach provider
```bash
# Test provider connectivity
curl -I https://api.kimi.com/coding/v1/models
curl -I https://integrate.api.nvidia.com/v1/models
```

## Systematic Troubleshooting

### Step 1: Identify the Error Pattern

Check logs for error patterns:
```bash
# Recent streaming errors
./bin/kimi-proxy logs | tail -50 | grep -E "(ReadError|Timeout|ConnectError|STREAM_ERROR)"

# Provider-specific issues
./bin/kimi-proxy logs | grep -E "(kimi|nvidia|mistral)" | tail -20
```

### Step 2: Verify Configuration

Check timeout settings:
```python
# In config.toml
[proxy]
stream_timeout = 120.0
max_retries = 2
retry_delay = 1.0

[proxy.timeouts]
gemini = 180.0  # Slower provider
kimi = 120.0
nvidia = 150.0
cerebras = 60.0
groq = 60.0
```

### Step 3: Test Individual Providers

```bash
# Test each provider independently
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "kimi-code/kimi-for-coding", "messages": [{"role": "user", "content": "test"}], "stream": true}'
```

### Step 4: Check Token Extraction

Verify token counting works:
```python
# Test token extraction
from kimi_proxy.core.tokens import count_tokens_tiktoken
tokens = count_tokens_tiktoken("Test message")
print(f"Token count: {tokens}")
```

## Advanced Debugging

### WebSocket Issues

Check WebSocket connections:
```javascript
// In browser console
ws = new WebSocket('ws://localhost:8000/ws');
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

### Database Corruption

Reset database if needed:
```bash
# Backup first
./scripts/backup.sh

# Reset database
rm sessions.db && ./bin/kimi-proxy start
```

### Memory Leaks

Check for memory issues:
```bash
# Monitor memory usage
ps aux | grep kimi-proxy

# Check for growing session count
./bin/kimi-proxy status
```

## Prevention Strategies

### Optimize Timeouts

Adjust timeouts based on provider characteristics:
```toml
[proxy.timeouts]
# Fast providers
groq = 30.0
cerebras = 30.0

# Medium providers  
kimi = 120.0
nvidia = 150.0

# Slow providers
gemini = 180.0
```

### Monitor Health

Set up health monitoring:
```bash
# Continuous health check
watch -n 5 curl http://localhost:8000/health

# Monitor active sessions
watch -n 10 curl http://localhost:8000/api/sessions/active
```

### Rate Limiting

Configure rate limiting to prevent overwhelming providers:
```toml
[rate_limiting]
enabled = true
requests_per_minute = 60
burst_size = 10
```

## Recovery Procedures

### Automatic Recovery

The proxy automatically retries on network errors:
- 4xx errors: No retry (client error)
- 5xx errors: Retry with exponential backoff
- Network errors: Retry up to 2 times

### Manual Recovery

```bash
# Restart proxy service
./bin/kimi-proxy restart

# Clear stuck sessions
curl -X DELETE http://localhost:8000/api/sessions/stale

# Reset MCP servers if needed
./scripts/start-mcp-servers.sh restart
```

## Performance Monitoring

### Key Metrics to Watch

- **Stream latency**: Time to first chunk
- **Token extraction accuracy**: Tokens counted vs actual
- **Error rate**: Percentage of failed streams
- **Recovery time**: Time to recover from errors

### Monitoring Commands

```bash
# Stream performance
./bin/kimi-proxy logs | grep "stream_latency" | tail -20

# Token accuracy
curl http://localhost:8000/api/sessions/active | jq '.token_accuracy'

# Error rates
./bin/kimi-proxy logs | grep -c "STREAM_ERROR"
```
