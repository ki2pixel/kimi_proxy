---
name: kimi-proxy-testing-strategies
description: Comprehensive testing strategies for Kimi Proxy Dashboard. Use when writing tests, debugging issues, or ensuring system reliability. Covers unit tests, integration tests, E2E testing, and performance testing with pytest-asyncio.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Testing Strategies

This skill provides comprehensive testing guidance for Kimi Proxy Dashboard.

## Test Architecture

### Test Structure

```
tests/
├── conftest.py              # Pytest configuration and fixtures
├── unit/                    # Isolated unit tests
│   ├── test_tokens.py
│   ├── test_models.py
│   ├── test_database.py
│   └── test_config.py
├── integration/              # Component integration tests
│   ├── test_api_routes.py
│   ├── test_proxy_client.py
│   ├── test_websocket.py
│   └── test_mcp_integration.py
└── e2e/                     # End-to-end tests
    ├── test_full_workflow.py
    ├── test_multi_provider.py
    └── test_regression.py
```

### Pytest Configuration

```python
# conftest.py
import pytest
import asyncio
import tempfile
import os
from pathlib import Path

# Test database fixture
@pytest.fixture(scope="session")
def test_db():
    """In-memory database for testing"""
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    
    # Initialize test database
    from kimi_proxy.core.database import init_database
    init_database(db_path)
    
    yield db_path
    
    # Cleanup
    os.unlink(db_path)

# Async client fixture
@pytest.fixture
async def async_client():
    """Test HTTP client"""
    from httpx import AsyncClient
    async with AsyncClient(base_url="http://testserver") as client:
        yield client

# Mock MCP servers fixture
@pytest.fixture
def mock_mcp_servers():
    """Mock MCP servers for testing"""
    import subprocess
    processes = []
    
    # Start mock servers on different ports
    for port in [8002, 8003, 8004, 8005]:
        proc = subprocess.Popen([
            'python', '-c', f'''
import http.server
import socketserver
import json

class MockHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["content-length"])
        post_data = self.rfile.read(content_length)
        
        response = {{"jsonrpc": "2.0", "result": {{"success": True}}, "id": 1}
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

with socketserver.TCPServer(("", {port}), MockHandler) as httpd:
    httpd.serve_forever()
'''
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(proc)
    
    yield processes
    
    # Cleanup
    for proc in processes:
        proc.terminate()
        proc.wait()
```

## Unit Testing

### Token Counting Tests

```python
# tests/unit/test_tokens.py
import pytest
from kimi_proxy.core.tokens import count_tokens_tiktoken, ENCODING

class TestTokenCounting:
    def test_empty_string(self):
        """Test empty string token count"""
        assert count_tokens_tiktoken("") == 0
    
    def test_simple_text(self):
        """Test basic text tokenization"""
        text = "Hello, world!"
        tokens = count_tokens_tiktoken(text)
        assert tokens > 0
        assert isinstance(tokens, int)
    
    def test_unicode_handling(self):
        """Test Unicode text tokenization"""
        text = "Bonjour le monde! 🚀"
        tokens = count_tokens_tiktoken(text)
        assert tokens > 0
    
    def test_large_text_performance(self):
        """Test performance with large text"""
        text = "word " * 10000  # 50K characters
        
        import time
        start = time.time()
        tokens = count_tokens_tiktoken(text)
        duration = time.time() - start
        
        assert tokens > 0
        assert duration < 1.0  # Should complete in < 1 second
    
    @pytest.mark.parametrize("text,expected", [
        ("Hello", 1),
        ("Hello world", 2),
        ("Hello, world!", 3),
    ])
    def test_known_token_counts(self, text, expected):
        """Test known token counts"""
        assert count_tokens_tiktoken(text) == expected
```

### Database Tests

```python
# tests/unit/test_database.py
import pytest
import sqlite3
from kimi_proxy.core.database import get_db, create_session, get_active_session
from kimi_proxy.core.models import Session

class TestDatabase:
    def test_create_session(self, test_db):
        """Test session creation"""
        with get_db(test_db) as conn:
            session_id = create_session(
                name="Test Session",
                provider="test",
                model="test-model"
            )
            
            assert session_id is not None
            
            # Verify session was created
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            result = cursor.fetchone()
            assert result is not None
            assert result["name"] == "Test Session"
    
    def test_get_active_session(self, test_db):
        """Test active session retrieval"""
        with get_db(test_db) as conn:
            # Create test session
            session_id = create_session("Active Test", "test", "test-model")
            
            # Get active session
            active = get_active_session(test_db)
            assert active is not None
            assert active.id == session_id
            assert active.is_active is True
    
    def test_database_connection_error(self):
        """Test database error handling"""
        with pytest.raises(sqlite3.DatabaseError):
            with get_db("/invalid/path/db.sqlite") as conn:
                conn.execute("SELECT 1")
```

### Configuration Tests

```python
# tests/unit/test_config.py
import pytest
import tempfile
import os
from pathlib import Path
from kimi_proxy.config.loader import get_config

class TestConfiguration:
    def test_load_valid_config(self):
        """Test loading valid configuration"""
        config_content = '''
[models."test-model"]
provider = "test-provider"
model = "test-model"

[providers."test-provider"]
type = "openai-compatible"
base_url = "https://api.test.com/v1"
api_key = "${TEST_API_KEY}"
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            # Mock environment variable
            os.environ['TEST_API_KEY'] = 'test-key-123'
            
            config = get_config(f.name)
            
            assert config.get('models', {}).get('test-model') is not None
            assert config['models']['test-model']['provider'] == 'test-provider'
    
    def test_missing_config_file(self):
        """Test handling of missing config file"""
        with pytest.raises(FileNotFoundError):
            get_config("/nonexistent/config.toml")
    
    def test_invalid_toml_syntax(self):
        """Test invalid TOML syntax"""
        config_content = '''
[invalid-section
missing = "quote"
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            with pytest.raises(ValueError):  # TOML parsing error
                get_config(f.name)
```

## Integration Testing

### API Integration Tests

```python
# tests/integration/test_api_routes.py
import pytest
from httpx import AsyncClient
from kimi_proxy.main import app

class TestAPIRoutes:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, async_client):
        """Test health check endpoint"""
        response = await async_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "opérationnel"
        assert "message" in data
    
    @pytest.mark.asyncio
    async def test_sessions_endpoint(self, async_client):
        """Test sessions API endpoint"""
        # Create test session
        create_response = await async_client.post("/api/sessions", json={
            "name": "Test Session",
            "provider": "test",
            "model": "test-model"
        })
        assert create_response.status_code == 201
        
        # Get sessions list
        list_response = await async_client.get("/api/sessions")
        assert list_response.status_code == 200
        
        sessions = list_response.json()
        assert len(sessions) > 0
        assert any(s["name"] == "Test Session" for s in sessions)
    
    @pytest.mark.asyncio
    async def test_proxy_endpoint(self, async_client):
        """Test proxy endpoint functionality"""
        response = await async_client.post("/chat/completions", json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        })
        
        # Should proxy to test provider
        assert response.status_code in [200, 202]  # Success or streaming
```

### WebSocket Integration Tests

```python
# tests/integration/test_websocket.py
import pytest
import asyncio
import websockets
import json
from kimi_proxy.services.websocket_manager import ConnectionManager

class TestWebSocketIntegration:
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection and message handling"""
        manager = ConnectionManager()
        
        # Mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.messages = []
            
            async def send_json(self, data):
                self.messages.append(data)
            
            async def receive_json(self):
                return {"type": "test", "data": "payload"}
        
        ws = MockWebSocket()
        
        # Test connection
        await manager.connect(ws)
        assert ws in manager.active_connections
        
        # Test broadcasting
        await manager.broadcast({"type": "test", "data": "broadcast"})
        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "test"
        
        # Test disconnection
        await manager.disconnect(ws)
        assert ws not in manager.active_connections
    
    @pytest.mark.asyncio
    async def test_real_time_updates(self):
        """Test real-time metric updates"""
        manager = ConnectionManager()
        
        updates_received = []
        
        async def collect_updates(data):
            updates_received.append(data)
        
        # Mock WebSocket
        ws = type('MockWS', (), {
            'send_json': lambda self, data: updates_received.append(data)
        })()
        
        await manager.connect(ws)
        
        # Send multiple updates
        for i in range(5):
            await manager.broadcast({
                "type": "metric",
                "data": {"tokens": i * 10}
            })
            await asyncio.sleep(0.01)
        
        assert len(updates_received) == 5
        assert all(update["type"] == "metric" for update in updates_received)
```

### MCP Integration Tests

```python
# tests/integration/test_mcp_integration.py
import pytest
from kimi_proxy.features.mcp.client import get_mcp_client, MCPConnectionError

class TestMCPIntegration:
    @pytest.mark.asyncio
    async def test_task_master_connection(self, mock_mcp_servers):
        """Test Task Master MCP server connection"""
        client = get_mcp_client("task_master")
        
        # Test initialization
        result = await client.call("initialize", {
            "projectRoot": "/tmp/test-project",
            "yes": True
        })
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_sequential_thinking(self, mock_mcp_servers):
        """Test Sequential Thinking MCP"""
        client = get_mcp_client("sequential_thinking")
        
        result = await client.call("sequentialthinking_tools", {
            "available_mcp_tools": ["task-master"],
            "thought": "Test reasoning process",
            "next_thought_needed": False,
            "thought_number": 1,
            "total_thoughts": 1
        })
        
        assert "result" in result
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_filesystem_operations(self, mock_mcp_servers):
        """Test Fast Filesystem MCP"""
        client = get_mcp_client("fast_filesystem")
        
        # Test file reading
        result = await client.call("read_file", {
            "path": "/tmp/test.txt"
        })
        
        assert result["success"] is True
        assert "content" in result
    
    @pytest.mark.asyncio
    async def test_json_query(self, mock_mcp_servers):
        """Test JSON Query MCP"""
        client = get_mcp_client("json_query")
        
        # Create test JSON file
        import json
        test_data = {"key": "value", "nested": {"inner": "data"}}
        with open("/tmp/test.json", "w") as f:
            json.dump(test_data, f)
        
        # Test JSONPath query
        result = await client.call("json_query_jsonpath", {
            "file_path": "/tmp/test.json",
            "jsonpath": "$.nested.inner"
        })
        
        assert result["success"] is True
        assert result["data"] == "data"
```

## End-to-End Testing

### Full Workflow Tests

```python
# tests/e2e/test_full_workflow.py
import pytest
import asyncio
from httpx import AsyncClient

class TestFullWorkflow:
    @pytest.mark.asyncio
    async def test_complete_session_workflow(self):
        """Test complete session lifecycle"""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            # 1. Create session
            session_response = await client.post("/api/sessions", json={
                "name": "E2E Test Session",
                "provider": "test",
                "model": "test-model"
            })
            assert session_response.status_code == 201
            session_data = session_response.json()
            session_id = session_data["id"]
            
            # 2. Send chat completion request
            chat_response = await client.post("/chat/completions", json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello, test!"}],
                "stream": False
            })
            assert chat_response.status_code == 200
            
            # 3. Check metrics were recorded
            metrics_response = await client.get(f"/api/sessions/{session_id}/memory")
            assert metrics_response.status_code == 200
            metrics = metrics_response.json()
            assert len(metrics) > 0
            
            # 4. Export session data
            export_response = await client.get(f"/api/export/csv?session_id={session_id}")
            assert export_response.status_code == 200
            assert "text/csv" in export_response.headers["content-type"]
    
    @pytest.mark.asyncio
    async def test_multi_provider_routing(self):
        """Test provider routing functionality"""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            # Test with different providers
            providers = ["kimi", "nvidia", "mistral"]
            
            for provider in providers:
                response = await client.post("/chat/completions", json={
                    "model": f"{provider}/test-model",
                    "messages": [{"role": "user", "content": f"Test {provider}"}],
                    "stream": False
                })
                
                # Should route to correct provider
                assert response.status_code in [200, 202]
                
                # Check provider was used (via logs or metrics)
                # This would require additional test infrastructure
```

### Regression Tests

```python
# tests/e2e/test_regression.py
import pytest
from kimi_proxy.core.tokens import count_tokens_tiktoken

class TestRegression:
    def test_token_counting_regression(self):
        """Regression test for token counting"""
        # Known cases from previous versions
        test_cases = [
            ("Hello", 1),
            ("Hello world", 2),
            ("The quick brown fox", 4),
            ("Bonjour le monde!", 4),
        ]
        
        for text, expected in test_cases:
            actual = count_tokens_tiktoken(text)
            assert actual == expected, f"Token count regression for '{text}': expected {expected}, got {actual}"
    
    def test_performance_regression(self):
        """Regression test for performance"""
        import time
        
        # Test large text processing
        large_text = "word " * 1000
        start_time = time.time()
        
        tokens = count_tokens_tiktoken(large_text)
        
        duration = time.time() - start_time
        
        # Should complete within reasonable time
        assert duration < 0.5, f"Performance regression: took {duration:.3f}s for large text"
        assert tokens > 0
    
    @pytest.mark.asyncio
    async def test_api_compatibility_regression(self):
        """Test API compatibility regression"""
        from kimi_proxy.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Test essential endpoints still work
        response = client.get("/health")
        assert response.status_code == 200
        
        response = client.get("/models")
        assert response.status_code == 200
        
        models = response.json()
        assert "data" in models
        assert len(models["data"]) > 0
```

## Performance Testing

### Load Testing

```python
# tests/e2e/test_load.py
import pytest
import asyncio
import time
from httpx import AsyncClient

class TestLoad:
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test concurrent request handling"""
        async with AsyncClient(base_url="http://localhost:8000") as client:
            # Send 50 concurrent requests
            tasks = []
            for i in range(50):
                task = client.post("/chat/completions", json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": f"Test message {i}"}],
                    "stream": False
                })
                tasks.append(task)
            
            start_time = time.time()
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time
            
            # Check success rate
            successful = sum(1 for r in responses if hasattr(r, 'status_code') and r.status_code == 200)
            success_rate = successful / len(responses)
            
            assert success_rate > 0.95, f"Success rate: {success_rate:.2%}"
            assert duration < 30, f"Duration: {duration:.2f}s"
    
    @pytest.mark.asyncio
    async def test_websocket_load(self):
        """Test WebSocket connection limits"""
        connections = []
        
        async def create_connection(i):
            import websockets
            ws = await websockets.connect("ws://localhost:8000/ws")
            connections.append(ws)
            
            # Send test message
            await ws.send(json.dumps({"type": "test", "data": i}))
            
            # Wait for response
            response = await ws.recv()
            return response
        
        # Create 20 concurrent WebSocket connections
        tasks = [create_connection(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check connection success rate
        successful = sum(1 for r in results if not isinstance(r, Exception))
        success_rate = successful / len(results)
        
        assert success_rate > 0.9, f"WebSocket success rate: {success_rate:.2%}"
        
        # Cleanup
        for ws in connections:
            await ws.close()
```

## Test Execution

### Running Tests

```bash
# Run all tests
PYTHONPATH=src python -m pytest tests/ -v

# Run specific test categories
PYTHONPATH=src python -m pytest tests/unit/ -v
PYTHONPATH=src python -m pytest tests/integration/ -v
PYTHONPATH=src python -m pytest tests/e2e/ -v

# Run with coverage
PYTHONPATH=src python -m pytest tests/ --cov=src/kimi_proxy --cov-report=html

# Run performance tests
PYTHONPATH=src python -m pytest tests/e2e/test_load.py -v -s

# Run regression tests
PYTHONPATH=src python -m pytest tests/e2e/test_regression.py -v
```

### Test Configuration

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --asyncio-mode=auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests
    unit: marks tests as unit tests
```

### CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests
      run: |
        PYTHONPATH=src python -m pytest tests/unit/ -v --cov=src/kimi_proxy
    
    - name: Run integration tests
      run: |
        PYTHONPATH=src python -m pytest tests/integration/ -v
    
    - name: Run E2E tests
      run: |
        PYTHONPATH=src python -m pytest tests/e2e/ -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```
