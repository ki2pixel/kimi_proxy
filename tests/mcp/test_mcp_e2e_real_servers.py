"""
Tests E2E avec serveurs MCP réels.

Ces tests vérifient le système complet avec:
- Qdrant MCP lancé sur port 6333
- Compression MCP lancé sur port 8001
- Task Master MCP lancé sur port 8002
- Sequential Thinking MCP lancé sur port 8003
- Fast Filesystem MCP lancé sur port 8004
- JSON Query MCP lancé sur port 8005

PRÉREQUIS:
./scripts/start-mcp-servers.sh start

ATTENTION: Ces tests modifient les serveurs MCP réels!
"""
import pytest
import pytest_asyncio
import asyncio
import json
import tempfile
import os
from datetime import datetime

from kimi_proxy.features.mcp.client import get_mcp_client, reset_mcp_client
from kimi_proxy.features.mcp.base.config import MCPClientConfig


# Fixtures E2E
@pytest.fixture(scope="module")
def real_mcp_config():
    """Config pour serveurs MCP réels."""
    config = MCPClientConfig()
    # Configuration pour tests E2E avec serveurs locaux
    config.qdrant_url = "http://localhost:6333"
    config.compression_url = "http://localhost:8001"
    config.task_master_url = "http://localhost:8002"
    config.sequential_thinking_url = "http://localhost:8003"
    config.fast_filesystem_url = "http://localhost:8004"
    config.json_query_url = "http://localhost:8005"
    return config


@pytest.fixture(scope="module")
async def real_mcp_client(real_mcp_config):
    """Client MCP configuré pour serveurs réels."""
    # Reset pour s'assurer d'un état propre
    reset_mcp_client()
    
    # Configurer avec URLs réels
    client = get_mcp_client()
    client.config = real_mcp_config
    
    yield client
    
    # Cleanup après tests
    reset_mcp_client()


# Fonctions helper pour vérifier disponibilité serveurs
def is_qdrant_available():
    """Vérifie si Qdrant est disponible."""
    try:
        import httpx
        response = httpx.get("http://localhost:6333/health", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def is_compression_available():
    """Vérifie si Compression MCP est disponible."""
    try:
        import httpx
        response = httpx.get("http://localhost:8001/health", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def is_task_master_available():
    """Vérifie si Task Master MCP est disponible."""
    try:
        import httpx
        response = httpx.get("http://localhost:8002/health", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def is_sequential_thinking_available():
    """Vérifie si Sequential Thinking MCP est disponible."""
    try:
        import httpx
        response = httpx.get("http://localhost:8003/health", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def is_fast_filesystem_available():
    """Vérifie si Fast Filesystem MCP est disponible."""
    try:
        import httpx
        response = httpx.get("http://localhost:8004/health", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def is_json_query_available():
    """Vérifie si JSON Query MCP est disponible."""
    try:
        import httpx
        response = httpx.get("http://localhost:8005/health", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def all_servers_available():
    """Vérifie si tous les serveurs MCP sont disponibles."""
    return all([
        is_qdrant_available(),
        is_compression_available(),
        is_task_master_available(),
        is_sequential_thinking_available(),
        is_fast_filesystem_available(),
        is_json_query_available()
    ])


def docker_available():
    """Vérifie si Docker est disponible."""
    try:
        import subprocess
        subprocess.check_output(["docker", "--version"], text=True)
        return True
    except:
        return False


@pytest.mark.asyncio
@pytest.mark.skipif(not is_qdrant_available(), reason="Qdrant non disponible")
async def test_e2e_compression_to_qdrant_workflow(real_mcp_client):
    """Workflow E2E: compresser → stocker → rechercher similaire."""
    client = real_mcp_client
    
    # Étape 1: compresser documentation
    doc_content = "# Documentation Kimi Proxy\n\n## Features\n* Token counting\n* Stream compression\n* MCP integration\n## API Usage\n```bash\ncurl http://localhost:8000/chat/completions\n```"
    
    compressed = await client.compress_content(doc_content)
    print(f"📦 Compression: {compressed.original_tokens} → {compressed.compressed_tokens} tokens (ratio: {compressed.compression_ratio:.1%})")
    assert compressed.compression_ratio > 0
    
    # Étape 2: stocker dans Qdrant
    vector_id = await client.store_memory_vector(
        doc_content,
        memory_type="semantic",
        metadata={
            "type": "documentation",
            "version": "2.4.0",
            "timestamp": datetime.now().isoformat()
        }
    )
    assert vector_id is not None
    print(f"✅ Vecteur stocké: {vector_id}")
    
    # Étape 3: recherche sémantique
    similar_results = await client.search_similar(
        "Kimi proxy API compression and tokens",
        limit=3,
        score_threshold=0.6
    )
    print(f"🔍 Found {len(similar_results)} results (seuil 0.6)")
    
    for r in similar_results:
        print(f"  → {r.id}: score={r.score:.2f}, preview={r.content_preview[:60]}...")
        assert r.score >= 0.6
    
    assert len(similar_results) >= 1


@pytest.mark.asyncio
@pytest.mark.skipif(not is_task_master_available(), reason="Task Master indisponible")
async def test_e2e_task_master_workflow(real_mcp_client):
    """Workflow E2E: analyse PRD → expansion → stats."""
    client = real_mcp_client
    
    # Créer un PRD temporaire
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        prd_content = """Kimi Proxy Dashboard v2.5 Requirements

Functional Requirements:
- Add semantic search overlay in dashboard
- Implement automatic context compaction trigger when 70% full
- Add MCP tool call monitoring (latency, success rate)
- Export tasks to CSV/JSON from dashboard
- Add dark mode toggle
- Implement workspace restrictions for MCP servers

Technical Requirements:
- FastAPI backend with WebSocket real-time updates
- Qdrant vector store for semantic memory
- React frontend with modular components
- SQLite for session persistence

Non-Functional:
- Latency < 100ms for search operations
- 99% uptime for MCP servers
- GDPR compliant data handling
"""
        f.write(prd_content)
        prd_file = f.name
    
    try:
        # Étape 1: Parser PRD
        print(f"📄 Parsing PRD: {prd_file}")
        parse_result = await client.call_task_master_tool("parse_prd", {
            "input": prd_file,
            "numTasks": 8,
            "research": True
        })
        
        assert "success" in parse_result
        print(f"✅ PRD parsed, tasks created: {parse_result.get('tasks_created', '?')}")
        
        # Étape 2: Récupérer tâches
        tasks = await client.get_task_master_tasks()
        print(f"📋 Loaded {len(tasks)} tasks")
        
        if len(tasks) > 0:
            # Étape 3: Expansion première tâche
            first_task = tasks[0]
            expanded = await client.expand_task(
                task_id=first_task.id,
                num_subtasks=5,
                prompt="Focus on FastAPI implementation with MCP"
            )
            print(f"🔧 Expanded task {first_task.id}")
            
            # Étape 4: Stats
            stats = await client.get_task_master_stats()
            print(f"📊 Stats: total={stats.total_tasks}, pending={stats.pending}, in-progress={stats.in_progress}")
            
            assert stats.total_tasks >= 0
            
    finally:
        os.unlink(prd_file)


@pytest.mark.asyncio
@pytest.mark.skipif(not is_fast_filesystem_available(), reason="Fast Filesystem indisponible")
async def test_e2e_filesystem_cran_paths(real_mcp_client):
    """Test CRAN avec Fast Filesystem: Create → Read → Append → Navigate."""
    client = real_mcp_client
    test_dir = tempfile.mkdtemp(prefix="kimi_test_")
    test_file = os.path.join(test_dir, "test_cran.txt")
    
    try:
        # Create
        write_result = await client.fast_write_file(test_file, "Initial content\n")
        assert write_result.success is True
        print(f"✅ Created {test_file}")
        
        # Read
        read_result = await client.fast_read_file(test_file)
        assert read_result.success is True
        assert "Initial content" in read_result.content
        print(f"✅ Read: {read_result.content.strip()}")
        
        # Append
        append_result = await client.fast_write_file(test_file, "Append line\n", append=True)
        assert append_result.success is True
        
        # Verify append
        read_result2 = await client.fast_read_file(test_file)
        assert "Append line" in read_result2.content
        print(f"✅ Append verified")
        
        # Navigate (list directory)
        list_result = await client.fast_list_directory(test_dir)
        assert list_result.success is True
        print(f"✅ Listed {len(list_result.files_affected)} files")
        
    finally:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.asyncio
@pytest.mark.skipif(not is_json_query_available(), reason="JSON Query indisponible")
async def test_e2e_json_query_config_analysis(real_mcp_client):
    """Test JSON Query avec configuration réelle."""
    client = real_mcp_client
    
    # Créer fichier config JSON
    config_data = {
        "mcp": {
            "qdrant": {"url": "http://localhost:6333", "api_key": "key123"},
            "compression": {"url": "http://localhost:8001"},
            "task_master": {"url": "http://localhost:8002"},
            "sequential_thinking": {"url": "http://localhost:8003"},
            "fast_filesystem": {"url": "http://localhost:8004"},
            "json_query": {"url": "http://localhost:8005"}
        },
        "proxy": {
            "stream_timeout": 120.0,
            "max_retries": 2
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config_data, f, indent=2)
        config_file = f.name
    
    try:
        # Recherche clés "url"
        keys_result = await client.search_json_keys(config_file, "url")
        assert keys_result.success is True
        print(f"🔑 Found {len(keys_result.results)} keys 'url'")
        
        # Recherche valeurs "localhost"
        values_result = await client.search_json_values(config_file, "localhost")
        assert values_result.success is True
        print(f"🌐 Found {len(values_result.results)} occurrences of 'localhost'")
        
        # JSONPath: extraire tous les URLs
        jp_result = await client.jsonpath_query(config_file, "$.mcp.*.url")
        assert jp_result.success is True
        urls = [r for r in jp_result.results if isinstance(r, str)]
        print(f"🔗 Extracted {len(urls)} URLs via JSONPath")
        assert len(urls) >= 5  # Au moins 5 URLs
        
        # Vérifier une URL spécifique
        assert "http://localhost:6333" in urls
        
    finally:
        os.unlink(config_file)


@pytest.mark.asyncio
@pytest.mark.skipif(not all_servers_available(), reason="Tous les serveurs MCP nécessaires")
async def test_e2e_sequential_thinking_with_mcp(real_mcp_client):
    """Test Sequential Thinking utilisant les outils MCP disponibles."""
    client = real_mcp_client
    
    # Obtenir la liste des outils disponibles
    tools_list = []
    
    if await client.check_qdrant_status():
        tools_list.append("qdrant_mcp")
    if await client.check_compression_status():
        tools_list.append("compression_mcp")
    if await client.check_task_master_status():
        tools_list.append("task_master")
    if await client.check_fast_filesystem_status():
        tools_list.append("fast_filesystem")
    if await client.check_json_query_status():
        tools_list.append("json_query")
    
    print(f"🛠️ Available MCP tools: {tools_list}")
    
    # Raisonnement séquentiel avec outils
    step1 = await client.call_sequential_thinking(
        thought="I need to debug a performance issue in my FastAPI app",
        thought_number=1,
        total_thoughts=3,
        available_mcp_tools=tools_list
    )
    
    print(f"Step 1: {step1.thought}")
    assert step1.next_thought_needed is True
    
    if step1.next_thought_needed:
        step2 = await client.call_sequential_thinking(
            thought="Let me check the code and logs to find bottlenecks",
            thought_number=2,
            total_thoughts=3,
            available_mcp_tools=tools_list
        )
        
        print(f"Step 2: {step2.thought}")
        assert step2.step_number == 2


@pytest.mark.asyncio
@pytest.mark.skipif(not docker_available(), reason="Docker needed for Qdrant")
async def test_e2e_setup_qdrant_with_docker():
    """Test configuration Qdrant via Docker si disponible."""
    import subprocess
    
    try:
        # Vérifier si Qdrant tourne déjà
        subprocess.check_output(["docker", "ps"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("Docker non disponible")
    
    # Pourrait lancer Qdrant: docker run -d -p 6333:6333 qdrant/qdrant
    print("🐳 Docker Qdrant validation skipped (manual setup required)")


# Tests performance
@pytest.mark.asyncio
async def test_e2e_performance_latency(real_mcp_client):
    """Benchmark latence serveurs MCP."""
    client = real_mcp_client
    latencies = {}
    
    # Test Qdrant health
    if await client.check_qdrant_status():
        start = datetime.now()
        await client.check_qdrant_status()
        latencies["qdrant"] = (datetime.now() - start).total_seconds() * 1000
    
    # Test Compression health
    if await client.check_compression_status():
        start = datetime.now()
        await client.check_compression_status()
        latencies["compression"] = (datetime.now() - start).total_seconds() * 1000
    
    # Test Task Master simple call
    if await client.check_task_master_status():
        start = datetime.now()
        await client.call_task_master_tool("get_tasks", {})
        latencies["task_master"] = (datetime.now() - start).total_seconds() * 1000
    
    # Imprimer résultat
    print("⚡ Latencies:")
    for server, latency_ms in latencies.items():
        status = "✅" if latency_ms < 100 else "⚠️" if latency_ms < 500 else "❌"
        print(f"  {status} {server}: {latency_ms:.1f}ms")
    
    assert all(l < 1000 for l in latencies.values()), "Un serveur a une latence >1s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
