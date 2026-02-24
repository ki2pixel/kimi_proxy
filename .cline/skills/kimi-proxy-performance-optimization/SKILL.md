---
name: kimi-proxy-performance-optimization
description: Performance optimization expert for Kimi Proxy Dashboard. Use when optimizing token counting, database queries, WebSocket performance, or reducing latency. Covers async optimization, database indexing, caching strategies, and resource utilization.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Performance Optimization

This skill provides comprehensive performance optimization guidance for Kimi Proxy Dashboard.

## Core Performance Principles

### Async/Await Optimization

**Always use async operations for I/O:**
```python
# ✅ GOOD: Async HTTP calls
import httpx
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        return response.json()

# ❌ BAD: Blocking HTTP calls
import requests  # Synchronous, blocks event loop
def fetch_data(url: str) -> dict:
    response = requests.get(url)
    return response.json()
```

### Connection Pooling

**Reuse connections to avoid overhead:**
```python
# Global client instance
from httpx import AsyncClient

_client = None

async def get_client() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    return _client

# Reuse for all requests
client = await get_client()
response = await client.get(url)
```

### Database Optimization

**Use async database operations:**
```python
# ✅ GOOD: Async SQLite
import aiosqlite

async def get_session(session_id: str):
    async with aiosqlite.connect("sessions.db") as db:
        async with db.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,)
        ) as cursor:
            return await cursor.fetchone()

# ❌ BAD: Synchronous SQLite
import sqlite3

def get_session(session_id: str):
    conn = sqlite3.connect("sessions.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    return cursor.fetchone()
```

## Token Counting Optimization

### Efficient Tokenization

**Cache tokenization results:**
```python
from functools import lru_cache
import tiktoken

@lru_cache(maxsize=1000)
def count_tokens_cached(text: str) -> int:
    """Cache token counts to avoid repeated computation."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

# Use cached version for repeated texts
token_count = count_tokens_cached(message.content)
```

### Streaming Token Counting

**Count tokens incrementally during streaming:**
```python
class StreamingTokenCounter:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.total_tokens = 0
        self.buffer = ""
    
    def add_chunk(self, chunk: str):
        """Add streaming chunk and update token count."""
        self.buffer += chunk
        
        # Process complete tokens
        try:
            tokens = self.encoding.encode(self.buffer)
            self.total_tokens = len(tokens)
            
            # Keep partial token at end of buffer
            # (tiktoken handles this automatically)
            
        except UnicodeDecodeError:
            # Handle incomplete UTF-8 sequences
            pass
    
    def get_total_tokens(self) -> int:
        return self.total_tokens
```

### Memory-Efficient Processing

**Process large texts in chunks:**
```python
def count_tokens_efficient(text: str, chunk_size: int = 8192) -> int:
    """Count tokens in large texts without loading everything into memory."""
    encoding = tiktoken.get_encoding("cl100k_base")
    total_tokens = 0
    
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        tokens = encoding.encode(chunk)
        total_tokens += len(tokens)
    
    return total_tokens
```

## Database Query Optimization

### Indexing Strategy

**Add indexes for frequently queried columns:**
```sql
-- Sessions table indexes
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
CREATE INDEX idx_sessions_status ON sessions(status);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

-- Messages table indexes
CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_token_count ON messages(token_count);
```

### Query Optimization

**Use efficient queries:**
```python
# ✅ GOOD: Single query with JOIN
async def get_session_with_messages(session_id: str):
    async with aiosqlite.connect("sessions.db") as db:
        async with db.execute("""
            SELECT s.*, m.content, m.token_count, m.created_at
            FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            WHERE s.id = ?
            ORDER BY m.created_at
        """, (session_id,)) as cursor:
            rows = await cursor.fetchall()
            return process_session_data(rows)

# ❌ BAD: N+1 queries
async def get_session_bad(session_id: str):
    async with aiosqlite.connect("sessions.db") as db:
        # Get session
        session = await db.execute_fetchone(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        
        # Separate query for messages (N+1 problem)
        messages = await db.execute_fetchall(
            "SELECT * FROM messages WHERE session_id = ?", (session_id,)
        )
        
        return {**session, "messages": messages}
```

### Connection Pooling

**Use connection pooling for high concurrency:**
```python
import aiosqlite

class DatabasePool:
    def __init__(self, database_path: str, max_connections: int = 10):
        self.database_path = database_path
        self.max_connections = max_connections
        self._pool = []
    
    async def get_connection(self):
        if self._pool:
            return self._pool.pop()
        
        if len(self._pool) < self.max_connections:
            conn = await aiosqlite.connect(self.database_path)
            return conn
        
        # Wait for available connection
        while not self._pool:
            await asyncio.sleep(0.01)
        return self._pool.pop()
    
    async def release_connection(self, conn):
        if len(self._pool) < self.max_connections:
            self._pool.append(conn)
        else:
            await conn.close()
```

## WebSocket Performance

### Message Batching

**Batch WebSocket updates:**
```javascript
class WebSocketBatcher {
    constructor(socket, batchDelay = 100) {
        this.socket = socket;
        this.batchDelay = batchDelay;
        this.pendingUpdates = [];
        this.batchTimer = null;
    }
    
    queueUpdate(update) {
        this.pendingUpdates.push(update);
        
        if (!this.batchTimer) {
            this.batchTimer = setTimeout(() => {
                this.flushBatch();
            }, this.batchDelay);
        }
    }
    
    flushBatch() {
        if (this.pendingUpdates.length > 0) {
            const batch = {
                type: 'batch_update',
                updates: this.pendingUpdates,
                timestamp: Date.now()
            };
            
            this.socket.send(JSON.stringify(batch));
            this.pendingUpdates = [];
        }
        
        this.batchTimer = null;
    }
}
```

### Connection Management

**Handle reconnections efficiently:**
```javascript
class ResilientWebSocket {
    constructor(url, options = {}) {
        this.url = url;
        this.maxRetries = options.maxRetries || 5;
        this.baseDelay = options.baseDelay || 1000;
        this.maxDelay = options.maxDelay || 30000;
        this.socket = null;
        this.retryCount = 0;
        this.isReconnecting = false;
    }
    
    async connect() {
        if (this.isReconnecting) return;
        
        try {
            this.socket = new WebSocket(this.url);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.retryCount = 0;
                this.onConnected();
            };
            
            this.socket.onmessage = (event) => {
                this.handleMessage(event.data);
            };
            
            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.attemptReconnect();
            };
            
        } catch (error) {
            this.attemptReconnect();
        }
    }
    
    attemptReconnect() {
        if (this.retryCount >= this.maxRetries) {
            console.error('Max reconnection attempts reached');
            return;
        }
        
        this.isReconnecting = true;
        this.retryCount++;
        
        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.retryCount - 1),
            this.maxDelay
        );
        
        setTimeout(() => {
            console.log(`Attempting reconnect ${this.retryCount}/${this.maxRetries}`);
            this.isReconnecting = false;
            this.connect();
        }, delay);
    }
    
    // Abstract methods to override
    onConnected() {}
    handleMessage(data) {}
}
```

## Caching Strategies

### Multi-Level Caching

**Implement multiple cache levels:**
```python
from functools import lru_cache
import asyncio
from typing import Dict, Any

class MultiLevelCache:
    def __init__(self):
        self.l1_cache = {}  # Fast in-memory
        self.l2_cache = {}  # Larger in-memory with TTL
        self.l3_cache = {}  # Persistent storage
    
    @lru_cache(maxsize=1000)
    def get_l1(self, key: str) -> Any:
        """L1: CPU cache level (function-level caching)"""
        return self.l1_cache.get(key)
    
    async def get_l2(self, key: str) -> Any:
        """L2: Application cache with TTL"""
        if key in self.l2_cache:
            entry = self.l2_cache[key]
            if entry['expires'] > asyncio.get_event_loop().time():
                return entry['value']
            else:
                del self.l2_cache[key]
        return None
    
    async def get_l3(self, key: str) -> Any:
        """L3: Persistent cache (database/file)"""
        # Implement persistent storage logic
        return self.l3_cache.get(key)
    
    async def get(self, key: str) -> Any:
        """Get with cache hierarchy"""
        # Try L1 first
        value = self.get_l1(key)
        if value is not None:
            return value
        
        # Try L2
        value = await self.get_l2(key)
        if value is not None:
            self.l1_cache[key] = value  # Promote to L1
            return value
        
        # Try L3
        value = await self.get_l3(key)
        if value is not None:
            self.l2_cache[key] = {
                'value': value,
                'expires': asyncio.get_event_loop().time() + 3600  # 1 hour TTL
            }
            return value
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set with cache hierarchy"""
        # Always set L1
        self.l1_cache[key] = value
        
        # Set L2 with TTL
        self.l2_cache[key] = {
            'value': value,
            'expires': asyncio.get_event_loop().time() + ttl
        }
        
        # Optionally persist to L3
        self.l3_cache[key] = value
```

### Cache Invalidation

**Implement smart cache invalidation:**
```python
class SmartCache:
    def __init__(self):
        self.cache = {}
        self.dependencies = {}  # Track what depends on what
    
    def invalidate_by_dependency(self, dependency_key: str):
        """Invalidate all cache entries that depend on a key"""
        if dependency_key in self.dependencies:
            dependent_keys = self.dependencies[dependency_key]
            for key in dependent_keys:
                self.invalidate(key)
            del self.dependencies[dependency_key]
    
    def set_with_dependencies(self, key: str, value: Any, depends_on: list = None):
        """Set cache entry with dependency tracking"""
        self.cache[key] = value
        
        if depends_on:
            for dep in depends_on:
                if dep not in self.dependencies:
                    self.dependencies[dep] = []
                self.dependencies[dep].append(key)
    
    def invalidate(self, key: str):
        """Invalidate specific cache entry"""
        if key in self.cache:
            del self.cache[key]
        
        # Also invalidate dependents
        self.invalidate_by_dependency(key)
```

## Resource Utilization

### Memory Management

**Monitor and limit memory usage:**
```python
import psutil
import os

class MemoryManager:
    def __init__(self, max_memory_mb: int = 512):
        self.max_memory_mb = max_memory_mb
        self.process = psutil.Process(os.getpid())
    
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        return self.process.memory_info().rss / 1024 / 1024
    
    def should_gc(self) -> bool:
        """Check if garbage collection should run"""
        return self.get_memory_usage() > self.max_memory_mb * 0.8
    
    def force_gc_if_needed(self):
        """Force garbage collection if memory usage is high"""
        if self.should_gc():
            import gc
            gc.collect()
            print(f"GC triggered. Memory: {self.get_memory_usage():.1f}MB")
    
    async def monitor_memory(self, interval: int = 60):
        """Background memory monitoring"""
        while True:
            usage = self.get_memory_usage()
            if usage > self.max_memory_mb:
                print(f"High memory usage: {usage:.1f}MB / {self.max_memory_mb}MB")
                self.force_gc_if_needed()
            
            await asyncio.sleep(interval)
```

### CPU Optimization

**Optimize CPU-intensive operations:**
```python
import asyncio
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

class CPUOptimizer:
    def __init__(self):
        self.executor = ProcessPoolExecutor(max_workers=multiprocessing.cpu_count())
        self.loop = asyncio.get_event_loop()
    
    async def run_cpu_task(self, func, *args):
        """Run CPU-intensive task in separate process"""
        return await self.loop.run_in_executor(self.executor, func, *args)
    
    def shutdown(self):
        """Clean shutdown of executor"""
        self.executor.shutdown(wait=True)

# Usage example
optimizer = CPUOptimizer()

async def process_large_dataset(data):
    # CPU-intensive processing in separate process
    result = await optimizer.run_cpu_task(heavy_computation, data)
    return result

def heavy_computation(data):
    # CPU-intensive work here
    # This runs in a separate process
    return processed_data
```

## Monitoring and Profiling

### Performance Metrics

**Implement comprehensive monitoring:**
```python
import time
from contextlib import asynccontextmanager

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    @asynccontextmanager
    async def measure_time(self, operation: str):
        """Context manager to measure operation time"""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_metric(f"{operation}_duration", duration)
            print(f"{operation} took {duration:.3f}s")
    
    def record_metric(self, name: str, value: float):
        """Record a performance metric"""
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append({
            'value': value,
            'timestamp': time.time()
        })
        
        # Keep only last 1000 measurements
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
    
    def get_average(self, name: str) -> float:
        """Get average value for a metric"""
        if name not in self.metrics:
            return 0.0
        
        values = [m['value'] for m in self.metrics[name]]
        return sum(values) / len(values) if values else 0.0
    
    def get_percentile(self, name: str, percentile: float) -> float:
        """Get percentile value for a metric"""
        if name not in self.metrics:
            return 0.0
        
        values = sorted([m['value'] for m in self.metrics[name]])
        if not values:
            return 0.0
        
        index = int(len(values) * percentile / 100)
        return values[min(index, len(values) - 1)]

# Usage
monitor = PerformanceMonitor()

async def handle_request(request):
    async with monitor.measure_time("request_processing"):
        # Process request
        result = await process_request(request)
        return result
```

### Profiling Tools

**Use profiling for bottleneck identification:**
```python
import cProfile
import pstats
import io

class Profiler:
    def __init__(self):
        self.profiler = cProfile.Profile()
    
    def start_profiling(self):
        """Start profiling"""
        self.profiler.enable()
    
    def stop_profiling(self, sort_by: str = 'cumulative', max_lines: int = 20):
        """Stop profiling and print results"""
        self.profiler.disable()
        
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats(sort_by)
        ps.print_stats(max_lines)
        
        print("Profile Results:")
        print(s.getvalue())

# Usage
profiler = Profiler()

def slow_function():
    profiler.start_profiling()
    # Your code here
    result = do_slow_operation()
    profiler.stop_profiling()
    return result
```

## Load Testing

### Automated Load Testing

**Implement load testing scripts:**
```python
import asyncio
import aiohttp
import time
from statistics import mean, median

class LoadTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
    
    async def setup(self):
        """Setup HTTP session"""
        self.session = aiohttp.ClientSession()
    
    async def teardown(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
    
    async def make_request(self, endpoint: str, data: dict = None) -> dict:
        """Make a single request"""
        start_time = time.time()
        
        try:
            if data:
                async with self.session.post(f"{self.base_url}{endpoint}", json=data) as resp:
                    response_time = time.time() - start_time
                    return {
                        'status': resp.status,
                        'response_time': response_time,
                        'success': resp.status == 200
                    }
            else:
                async with self.session.get(f"{self.base_url}{endpoint}") as resp:
                    response_time = time.time() - start_time
                    return {
                        'status': resp.status,
                        'response_time': response_time,
                        'success': resp.status == 200
                    }
        except Exception as e:
            response_time = time.time() - start_time
            return {
                'status': 0,
                'response_time': response_time,
                'success': False,
                'error': str(e)
            }
    
    async def run_load_test(self, endpoint: str, num_requests: int, concurrent: int = 10, data: dict = None):
        """Run load test"""
        await self.setup()
        
        print(f"Running load test: {num_requests} requests, {concurrent} concurrent")
        
        results = []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(concurrent)
        
        async def bounded_request():
            async with semaphore:
                return await self.make_request(endpoint, data)
        
        # Run all requests
        start_time = time.time()
        tasks = [bounded_request() for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        await self.teardown()
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        response_times = [r['response_time'] for r in results]
        
        print(f"\nResults:")
        print(f"Total requests: {num_requests}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Requests/sec: {num_requests/total_time:.2f}")
        print(f"Avg response time: {mean(response_times):.3f}s")
        print(f"Median response time: {median(response_times):.3f}s")
        print(f"95th percentile: {sorted(response_times)[int(len(response_times)*0.95)]:.3f}s")
        
        return results

# Usage
async def main():
    tester = LoadTester("http://localhost:8000")
    results = await tester.run_load_test("/api/sessions", 1000, 50)

if __name__ == "__main__":
    asyncio.run(main())
```

This comprehensive performance optimization guide covers the key areas for improving Kimi Proxy Dashboard performance: async operations, database optimization, caching strategies, WebSocket efficiency, and monitoring tools.