---
name: kimi-proxy-streaming-debug
description: Expert debugging for streaming errors in Kimi Proxy Dashboard. Use when encountering ReadError, TimeoutException, ConnectError, or SSE streaming issues. Provides systematic troubleshooting for proxy streaming failures, token extraction problems, and WebSocket connection issues.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Streaming Debug

This skill provides expert debugging guidance for streaming errors in Kimi Proxy Dashboard.

## Streaming Error Types

### ReadError
**Symptom**: Connection closed unexpectedly during streaming
```python
httpx.ReadError: [Errno 104] Connection reset by peer
```

**Common Causes**:
- Provider rate limiting
- Network instability
- Server-side connection timeout
- Proxy configuration issues

**Debug Steps**:
```python
# 1. Check provider status
curl -H "Authorization: Bearer $KIMI_API_KEY" \
     https://api.kimi.com/coding/v1/models

# 2. Test connection stability
for i in {1..5}; do
    curl -s -w "%{http_code}\n" \
         -H "Authorization: Bearer $KIMI_API_KEY" \
         https://api.kimi.com/coding/v1/chat/completions \
         -d '{"model":"kimi-for-coding","messages":[{"role":"user","content":"test"}]}' \
         -o /dev/null
    sleep 1
done

# 3. Check proxy logs
tail -f logs/proxy.log | grep -i "readerror\|connection\|reset"
```

### TimeoutException
**Symptom**: Request exceeds timeout limit
```python
httpx.TimeoutException: Request timed out
```

**Common Causes**:
- Slow provider response
- Network latency
- Insufficient timeout configuration
- Large context windows

**Debug Steps**:
```python
# 1. Check current timeout settings
grep -r "timeout" config.toml src/kimi_proxy/

# 2. Test provider response time
time curl -H "Authorization: Bearer $KIMI_API_KEY" \
          https://api.kimi.com/coding/v1/chat/completions \
          -d '{"model":"kimi-for-coding","messages":[{"role":"user","content":"test"}]}'

# 3. Monitor network latency
ping -c 10 api.kimi.com

# 4. Check token count vs timeout
python -c "
from src.kimi_proxy.core.tokens import count_tokens
text = open('large_context.txt').read()
tokens = count_tokens(text)
print(f'Tokens: {tokens}, Estimated time: {tokens/1000*30}s')
"
```

### ConnectError
**Symptom**: Cannot establish connection to provider
```python
httpx.ConnectError: [Errno 110] Connection timed out
```

**Common Causes**:
- DNS resolution issues
- Firewall blocking
- Provider service down
- Network configuration

**Debug Steps**:
```bash
# 1. Test DNS resolution
nslookup api.kimi.com

# 2. Test connectivity
telnet api.kimi.com 443

# 3. Check firewall rules
sudo iptables -L | grep 443

# 4. Test with different network
curl --interface eth0 -I https://api.kimi.com

# 5. Check provider status page
curl -s https://status.kimi.com | grep -i "operational\|incident"
```

## SSE Streaming Issues

### Incomplete Streams
**Symptom**: Stream cuts off mid-response
```javascript
// Client-side: stream ends prematurely
const response = await fetch('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, stream: true })
});

const reader = response.body.getReader();
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Process chunk
}
```

**Debug Steps**:
```python
# 1. Monitor SSE headers
curl -H "Accept: text/event-stream" \
     -H "Authorization: Bearer $PROXY_KEY" \
     -X POST http://localhost:8000/api/chat \
     -d '{"message":"test","stream":true}' \
     -v

# 2. Check for proper SSE format
curl -H "Accept: text/event-stream" \
     -H "Authorization: Bearer $PROXY_KEY" \
     -X POST http://localhost:8000/api/chat \
     -d '{"message":"test","stream":true}' \
     | head -20

# Expected format:
# data: {"chunk": "Hello"}
#
# data: {"chunk": " world"}
#
# data: [DONE]
```

### Token Extraction Problems
**Symptom**: Tokens not counted correctly during streaming
```python
# Incomplete token counting
async def process_stream(response):
    total_tokens = 0
    async for chunk in response.aiter_text():
        # BUG: Only counts visible text, misses partial tokens
        total_tokens += count_tokens(chunk)
    return total_tokens
```

**Debug Steps**:
```python
# 1. Test token counting accuracy
from src.kimi_proxy.core.tokens import count_tokens

test_text = "Hello world, this is a test message for token counting."
tokens = count_tokens(test_text)
print(f"Text: {len(test_text)} chars, Tokens: {tokens}")

# 2. Test streaming token extraction
async def debug_stream_tokens(response):
    chunks = []
    async for chunk in response.aiter_text():
        chunks.append(chunk)
        partial_tokens = count_tokens(''.join(chunks))
        print(f"Chunk {len(chunks)}: {len(chunk)} chars, Running total: {partial_tokens}")
    
    final_text = ''.join(chunks)
    final_tokens = count_tokens(final_text)
    print(f"Final: {len(final_text)} chars, {final_tokens} tokens")

# 3. Compare with non-streaming
response_text = await response.text()
streaming_tokens = await debug_stream_tokens(response)
direct_tokens = count_tokens(response_text)
print(f"Streaming: {streaming_tokens}, Direct: {direct_tokens}")
```

## WebSocket Connection Issues

### Connection Drops
**Symptom**: WebSocket disconnects unexpectedly
```javascript
// Client-side connection handling
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onclose = (event) => {
    console.log('WebSocket closed:', event.code, event.reason);
    // Code 1006 = Abnormal closure
};
```

**Debug Steps**:
```python
# 1. Monitor WebSocket connections
netstat -tlnp | grep :8000

# 2. Check server logs
tail -f logs/proxy.log | grep -i "websocket\|ws\|connection"

# 3. Test WebSocket handshake
websocat ws://localhost:8000/ws --text
# Send: {"type": "ping"}
# Should receive: {"type": "pong"}

# 4. Monitor connection count
watch -n 1 'netstat -tlnp | grep :8000 | wc -l'
```

### Message Corruption
**Symptom**: WebSocket messages arrive corrupted
```javascript
ws.onmessage = (event) => {
    try {
        const data = JSON.parse(event.data);
        // Handle data
    } catch (error) {
        console.error('Invalid JSON received:', event.data);
    }
};
```

**Debug Steps**:
```python
# 1. Enable WebSocket debugging
import logging
logging.getLogger('websockets').setLevel(logging.DEBUG)

# 2. Monitor message flow
# Server-side: Add logging
async def websocket_handler(websocket, path):
    async for message in websocket:
        logger.debug(f"Received: {message[:100]}...")
        try:
            data = json.loads(message)
            logger.debug(f"Parsed: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")

# 3. Test message integrity
# Client-side: Add checksums
function sendMessage(data) {
    const message = JSON.stringify(data);
    const checksum = btoa(message).slice(0, 10);
    ws.send(JSON.stringify({
        checksum,
        data: message
    }));
}
```

## Systematic Debugging Process

### Phase 1: Isolate the Problem

```python
# 1. Reproduce consistently
async def reproduce_error():
    for attempt in range(5):
        try:
            await make_streaming_request()
            print(f"Attempt {attempt + 1}: SUCCESS")
        except Exception as e:
            print(f"Attempt {attempt + 1}: FAILED - {e}")
            await asyncio.sleep(1)

# 2. Test with minimal payload
minimal_request = {
    "model": "kimi-for-coding",
    "messages": [{"role": "user", "content": "test"}],
    "stream": True,
    "max_tokens": 10
}

# 3. Test different providers
providers_to_test = ["kimi", "nvidia", "mistral"]
for provider in providers_to_test:
    try:
        await test_provider_streaming(provider, minimal_request)
        print(f"{provider}: SUCCESS")
    except Exception as e:
        print(f"{provider}: FAILED - {e}")
```

### Phase 2: Network Diagnostics

```bash
# 1. Test basic connectivity
ping -c 5 api.kimi.com

# 2. Test SSL/TLS
openssl s_client -connect api.kimi.com:443 -servername api.kimi.com < /dev/null

# 3. Test with different DNS
dig api.kimi.com
nslookup api.kimi.com 8.8.8.8

# 4. Check MTU issues
ping -M do -s 1472 api.kimi.com  # Test large packets

# 5. Test with proxy settings
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
curl -I https://api.kimi.com
```

### Phase 3: Application Diagnostics

```python
# 1. Enable detailed logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add to proxy configuration
logging.getLogger('httpx').setLevel(logging.DEBUG)
logging.getLogger('websockets').setLevel(logging.DEBUG)

# 2. Monitor resource usage
import psutil
import os

def monitor_resources():
    process = psutil.Process(os.getpid())
    memory = process.memory_info().rss / 1024 / 1024
    cpu = process.cpu_percent(interval=1)
    connections = len(process.connections())
    
    print(f"Memory: {memory:.1f}MB, CPU: {cpu:.1f}%, Connections: {connections}")

# 3. Profile streaming performance
import cProfile
profiler = cProfile.Profile()
profiler.enable()

await streaming_request()

profiler.disable()
profiler.print_stats(sort='cumulative')
```

### Phase 4: Provider-Specific Issues

```python
# Test each provider's streaming endpoint
provider_configs = {
    "kimi": {
        "base_url": "https://api.kimi.com/coding/v1",
        "model": "kimi-for-coding"
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/kimi-k2.5"
    },
    "mistral": {
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-large-latest"
    }
}

async def test_provider_streaming(provider_name, config):
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv(f'{provider_name.upper()}_API_KEY')}",
        "Content-Type": "application/json"
    }
    data = {
        "model": config["model"],
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
        "max_tokens": 50
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        async with client.stream("POST", url, headers=headers, json=data) as response:
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            chunk_count = 0
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk_count += 1
                    if chunk_count > 10:  # Test first 10 chunks
                        break
            
            return f"Received {chunk_count} chunks successfully"
```

## Error Recovery Patterns

### Automatic Retry Logic

```python
class StreamingRetryClient:
    def __init__(self, max_retries=3, base_delay=1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    async def stream_with_retry(self, url, headers, data):
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream("POST", url, headers=headers, json=data) as response:
                        if response.status_code != 200:
                            raise Exception(f"HTTP {response.status_code}: {response.text}")
                        
                        # Yield chunks as they arrive
                        async for line in response.aiter_lines():
                            yield line
                return  # Success
                
            except (httpx.ReadError, httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    print(f"All {self.max_retries + 1} attempts failed")
                    raise last_exception
```

### Graceful Degradation

```python
class GracefulStreamingClient:
    def __init__(self):
        self.fallback_providers = ["kimi", "nvidia", "mistral"]
    
    async def stream_with_fallback(self, message, preferred_provider=None):
        providers_to_try = [preferred_provider] + self.fallback_providers
        providers_to_try = [p for p in providers_to_try if p]  # Remove None
        
        for provider in providers_to_try:
            try:
                print(f"Trying provider: {provider}")
                async for chunk in self.stream_from_provider(provider, message):
                    yield chunk
                return  # Success
                
            except Exception as e:
                print(f"Provider {provider} failed: {e}")
                continue
        
        raise Exception("All providers failed")
    
    async def stream_from_provider(self, provider, message):
        # Implementation per provider
        config = self.get_provider_config(provider)
        # ... streaming logic
```

## Monitoring and Alerting

### Stream Health Monitoring

```python
class StreamHealthMonitor:
    def __init__(self):
        self.metrics = {
            'total_streams': 0,
            'successful_streams': 0,
            'failed_streams': 0,
            'average_chunks_per_stream': 0,
            'error_types': {}
        }
    
    def record_stream_start(self):
        self.metrics['total_streams'] += 1
    
    def record_stream_success(self, chunk_count):
        self.metrics['successful_streams'] += 1
        self.update_average_chunks(chunk_count)
    
    def record_stream_failure(self, error_type):
        self.metrics['failed_streams'] += 1
        self.metrics['error_types'][error_type] = self.metrics['error_types'].get(error_type, 0) + 1
    
    def update_average_chunks(self, chunk_count):
        total = self.metrics['successful_streams']
        current_avg = self.metrics['average_chunks_per_stream']
        self.metrics['average_chunks_per_stream'] = (current_avg * (total - 1) + chunk_count) / total
    
    def get_health_report(self):
        success_rate = (self.metrics['successful_streams'] / self.metrics['total_streams']) * 100
        return {
            'success_rate': f"{success_rate:.1f}%",
            'total_streams': self.metrics['total_streams'],
            'average_chunks': f"{self.metrics['average_chunks_per_stream']:.1f}",
            'top_errors': sorted(self.metrics['error_types'].items(), key=lambda x: x[1], reverse=True)[:3]
        }
```

### Automated Alerts

```python
class StreamingAlertManager:
    def __init__(self, monitor, thresholds=None):
        self.monitor = monitor
        self.thresholds = thresholds or {
            'min_success_rate': 95.0,  # Alert if below 95%
            'max_consecutive_failures': 5,
            'min_chunks_per_stream': 3
        }
        self.consecutive_failures = 0
    
    def check_alerts(self):
        report = self.monitor.get_health_report()
        alerts = []
        
        # Success rate alert
        success_rate = float(report['success_rate'].rstrip('%'))
        if success_rate < self.thresholds['min_success_rate']:
            alerts.append(f"Low success rate: {success_rate}% (threshold: {self.thresholds['min_success_rate']}%)")
        
        # Consecutive failures alert
        if self.consecutive_failures >= self.thresholds['max_consecutive_failures']:
            alerts.append(f"High consecutive failures: {self.consecutive_failures}")
        
        # Average chunks alert
        avg_chunks = float(report['average_chunks'])
        if avg_chunks < self.thresholds['min_chunks_per_stream']:
            alerts.append(f"Low average chunks per stream: {avg_chunks}")
        
        return alerts
    
    def record_result(self, success, chunk_count=None):
        if success:
            self.consecutive_failures = 0
            if chunk_count is not None:
                self.monitor.record_stream_success(chunk_count)
        else:
            self.consecutive_failures += 1
            self.monitor.record_stream_failure("unknown")
```

This comprehensive debugging guide covers the most common streaming issues in Kimi Proxy Dashboard and provides systematic approaches to identify, diagnose, and resolve them.