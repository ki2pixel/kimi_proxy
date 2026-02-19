---
name: kimi-proxy-performance-optimization
description: Performance optimization expert for Kimi Proxy Dashboard. Use when optimizing token counting, database queries, WebSocket performance, or reducing latency. Covers async optimization, database indexing, caching strategies, and resource utilization.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Performance Optimization

This skill provides comprehensive performance optimization for Kimi Proxy Dashboard.

## Token Counting Optimization

### Efficient Tokenization

```python
# Batch token counting for multiple messages
from kimi_proxy.core.tokens import count_tokens_tiktoken
import asyncio

async def batch_count_tokens(messages: list[dict]) -> int:
    """Count tokens for multiple messages efficiently"""
    tasks = []
    for msg in messages:
        if isinstance(msg.get('content'), str):
            tasks.append(asyncio.create_task(
                asyncio.to_thread(count_tokens_tiktoken, msg['content'])
            ))
    results = await asyncio.gather(*tasks)
    return sum(results)
```

### Token Caching

```python
# Cache token counts to avoid recomputation
from functools import lru_cache
import hashlib

@lru_cache(maxsize=10000)
def cached_token_count(text: str) -> int:
    """Cache token counts by content hash"""
    return count_tokens_tiktoken(text)

def get_content_hash(content: str) -> str:
    """Generate hash for content-based caching"""
    return hashlib.md5(content.encode()).hexdigest()

# Usage in proxy
content_hash = get_content_hash(message['content'])
token_count = cached_token_count(content_hash + message['content'])
```

### Streaming Token Counting

```python
# Incremental token counting during streaming
class StreamingTokenCounter:
    def __init__(self):
        self.total_tokens = 0
        self.buffer = ""
    
    def process_chunk(self, chunk: str) -> int:
        """Process streaming chunk and return new tokens"""
        self.buffer += chunk
        new_tokens = count_tokens_tiktoken(self.buffer)
        delta = new_tokens - self.total_tokens
        self.total_tokens = new_tokens
        return delta
```

## Database Optimization

### Query Optimization

```python
# Use indexes for common queries
# In database.py
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_metrics_session_id ON metrics(session_id);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);

# Optimized session retrieval
async def get_active_session_optimized() -> Optional[Session]:
    """Get active session with indexed query"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sessions 
            WHERE is_active = 1 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        return cursor.fetchone()
```

### Connection Pooling

```python
# Implement connection pooling for SQLite
import aiosqlite
from contextlib import asynccontextmanager

class DatabasePool:
    def __init__(self, max_connections: int = 10):
        self.pool = asyncio.Queue(maxsize=max_connections)
        self.connections = []
    
    @asynccontextmanager
    async def get_connection(self):
        """Get connection from pool"""
        try:
            conn = self.pool.get_nowait()
        except asyncio.QueueEmpty:
            conn = await aiosqlite.connect(DATABASE_FILE)
        try:
            yield conn
        finally:
            if self.pool.qsize() < self.pool.maxsize:
                self.pool.put_nowait(conn)
            else:
                await conn.close()
```

### Batch Database Operations

```python
# Batch insert metrics for performance
async def batch_insert_metrics(metrics: list[Metric]) -> None:
    """Insert multiple metrics in single transaction"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO metrics (session_id, timestamp, prompt_tokens, completion_tokens, total_tokens, source, provider)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [(m.session_id, m.timestamp, m.prompt_tokens, m.completion_tokens, 
                m.total_tokens, m.source, m.provider) for m in metrics])
        conn.commit()
```

## WebSocket Performance

### Efficient Broadcasting

```python
# Optimize WebSocket broadcasting
from kimi_proxy.services.websocket_manager import ConnectionManager

class OptimizedConnectionManager(ConnectionManager):
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.message_queue = asyncio.Queue()
        self._broadcast_task = None
    
    async def start_broadcast_worker(self):
        """Background worker for broadcasting"""
        while True:
            message = await self.message_queue.get()
            if self.connections:
                await asyncio.gather(
                    *[conn.send_json(message) for conn in self.connections],
                    return_exceptions=True
                )
    
    async def broadcast(self, message: dict) -> None:
        """Queue message for broadcasting"""
        await self.message_queue.put(message)
```

### Message Compression

```python
# Compress WebSocket messages for large payloads
import json
import gzip
import base64

async def send_compressed(websocket: WebSocket, data: dict) -> None:
    """Send compressed message if large"""
    json_str = json.dumps(data)
    if len(json_str) > 1024:  # Compress if > 1KB
        compressed = gzip.compress(json_str.encode())
        encoded = base64.b64encode(compressed).decode()
        await websocket.send_json({"compressed": True, "data": encoded})
    else:
        await websocket.send_json(data)
```

## HTTP Client Optimization

### Connection Reuse

```python
# Use HTTPX with connection pooling
import httpx

class OptimizedProxyClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            ),
            timeout=httpx.Timeout(60.0, connect=5.0)
        )
    
    async def request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Request with exponential backoff"""
        for attempt in range(3):
            try:
                return await self.client.request(method, url, **kwargs)
            except httpx.RequestError as e:
                if attempt == 2:
                    raise
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
```

### Request Streaming Optimization

```python
# Optimize streaming response processing
async def optimized_stream_generator(
    response: httpx.Response,
    chunk_size: int = 8192
) -> AsyncGenerator[str, None]:
    """Optimized streaming with larger chunks"""
    buffer = ""
    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
        buffer += chunk.decode('utf-8', errors='ignore')
        while '\n' in buffer:
            line, buffer = buffer.split('\n', 1)
            if line.strip():
                yield line
```

## Memory Management

### Memory Profiling

```python
# Monitor memory usage
import psutil
import tracemalloc

class MemoryProfiler:
    def __init__(self):
        self.process = psutil.Process()
    
    def get_memory_usage(self) -> dict:
        """Get current memory usage"""
        memory_info = self.process.memory_info()
        return {
            'rss': memory_info.rss / 1024 / 1024,  # MB
            'vms': memory_info.vms / 1024 / 1024,   # MB
            'percent': self.process.memory_percent()
        }
    
    def start_tracing(self):
        """Start memory tracing"""
        tracemalloc.start()
    
    def get_traced_usage(self) -> dict:
        """Get traced memory usage"""
        current, peak = tracemalloc.get_traced_memory()
        return {
            'current': current / 1024 / 1024,  # MB
            'peak': peak / 1024 / 1024       # MB
        }
```

### Garbage Collection Optimization

```python
# Optimize garbage collection
import gc
import weakref

class OptimizedSessionManager:
    def __init__(self):
        self.sessions = weakref.WeakValueDictionary()
        self._last_gc = time.time()
    
    def cleanup_old_sessions(self, max_age_seconds: int = 3600):
        """Clean up old sessions and force GC"""
        current_time = time.time()
        if current_time - self._last_gc > 300:  # GC every 5 minutes
            old_sessions = [
                sid for sid, session in self.sessions.items()
                if current_time - session.last_activity > max_age_seconds
            ]
            for sid in old_sessions:
                del self.sessions[sid]
            gc.collect()
            self._last_gc = current_time
```

## Caching Strategies

### Redis-like Caching

```python
# In-memory cache with TTL
import time
from typing import Any, Optional

class TTLCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key not in self.cache:
            return None
        
        if time.time() - self.timestamps[key] > self.ttl:
            del self.cache[key]
            del self.timestamps[key]
            return None
        
        return self.cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """Set item in cache"""
        if len(self.cache) >= self.max_size:
            # Remove oldest item
            oldest_key = min(self.timestamps.keys(), key=self.timestamps.get)
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
```

### Provider Response Caching

```python
# Cache provider responses for identical requests
async def cached_provider_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    cache_key: str,
    ttl_seconds: int = 60
) -> dict:
    """Cache provider responses"""
    cache = TTLCache(max_size=1000, ttl_seconds=ttl_seconds)
    
    # Check cache first
    cached_response = cache.get(cache_key)
    if cached_response:
        return cached_response
    
    # Make request
    response = await client.request(method, url)
    result = response.json()
    
    # Cache result
    cache.set(cache_key, result)
    return result
```

## Performance Monitoring

### Key Metrics

```python
# Performance metrics collection
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'request_latency': [],
            'token_counting_time': [],
            'database_query_time': [],
            'websocket_broadcast_time': [],
            'memory_usage': []
        }
    
    def record_latency(self, operation: str, duration_ms: float) -> None:
        """Record operation latency"""
        if operation not in self.metrics:
            self.metrics[operation] = []
        self.metrics[operation].append(duration_ms)
    
    def get_stats(self, operation: str) -> dict:
        """Get performance statistics"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {'mean': 0, 'p95': 0, 'p99': 0}
        
        values = self.metrics[operation]
        return {
            'mean': sum(values) / len(values),
            'p95': sorted(values)[int(len(values) * 0.95)],
            'p99': sorted(values)[int(len(values) * 0.99)],
            'count': len(values)
        }
```

### Performance Alerts

```python
# Alert on performance degradation
async def check_performance_alerts() -> None:
    """Check for performance issues"""
    monitor = PerformanceMonitor()
    
    # Check request latency
    stats = monitor.get_stats('request_latency')
    if stats['p95'] > 5000:  # 5 seconds
        await send_alert("High request latency detected", {
            'p95_latency_ms': stats['p95']
        })
    
    # Check memory usage
    profiler = MemoryProfiler()
    memory = profiler.get_memory_usage()
    if memory['percent'] > 80:
        await send_alert("High memory usage", {
            'memory_percent': memory['percent']
        })
```

## Optimization Commands

### Performance Testing

```bash
# Load testing the proxy
ab -n 1000 -c 10 -p postfile.txt http://localhost:8000/chat/completions

# WebSocket performance test
python -c "
import asyncio
import websockets
import time

async def test_websocket():
    start = time.time()
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        await ws.send('test')
        response = await ws.recv()
        print(f'WebSocket latency: {time.time() - start:.3f}s')

asyncio.run(test_websocket())
"
```

### Database Performance

```bash
# Analyze database performance
sqlite3 sessions.db 'EXPLAIN QUERY PLAN SELECT * FROM metrics WHERE session_id = 1 ORDER BY timestamp DESC LIMIT 100;'

# Check database size
du -h sessions.db

# Optimize database
sqlite3 sessions.db 'VACUUM;'
sqlite3 sessions.db 'ANALYZE;'
```

### Memory Profiling

```bash
# Profile memory usage
python -m memory_profiler src/kimi_proxy/main.py

# Check for memory leaks
python -c "
import time
import psutil
import gc

process = psutil.Process()
for i in range(60):  # Monitor for 1 minute
    memory = process.memory_info().rss / 1024 / 1024
    print(f'Memory: {memory:.1f}MB')
    time.sleep(1)
    if i % 10 == 0:
        gc.collect()
"
```
