"""
Tests pour MCP Phase 3 - Optimisations Avancées.

Couverture:
- Client MCP externe (Qdrant, Compression)
- Mémoire standardisée (frequent/episodic)
- Routage provider optimisé
- API endpoints Phase 3
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.kimi_proxy.features.mcp.client import (
    MCPExternalClient,
    MCPClientConfig,
    MCPClientError,
    MCPConnectionError,
    get_mcp_client,
    reset_mcp_client
)
from src.kimi_proxy.features.mcp.memory import (
    MemoryManager,
    get_memory_manager,
    reset_memory_manager,
    FREQUENT_ACCESS_THRESHOLD
)
from src.kimi_proxy.proxy.router import (
    find_optimal_provider,
    get_provider_capacities,
    calculate_routing_score,
    get_routing_recommendation,
    ProviderCapacity
)
from src.kimi_proxy.core.models import (
    MCPMemoryEntry,
    MCPCompressionResult,
    QdrantSearchResult,
    ProviderRoutingDecision
)


# ============================================================================
# Tests Client MCP Externe
# ============================================================================

class TestMCPExternalClient:
    """Tests du client MCP externe."""
    
    @pytest.fixture
    def client(self):
        """Fixture client MCP."""
        reset_mcp_client()
        config = MCPClientConfig(
            qdrant_url="http://localhost:6333",
            compression_url="http://localhost:8001"
        )
        return MCPExternalClient(config)
    
    @pytest.mark.asyncio
    async def test_check_qdrant_status_success(self, client):
        """Test vérification statut Qdrant succès."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            status = await client.check_qdrant_status()
            
            assert status.connected is True
            assert status.name == "qdrant-mcp"
            assert "semantic_search" in status.capabilities
    
    @pytest.mark.asyncio
    async def test_check_qdrant_status_failure(self, client):
        """Test vérification statut Qdrant échec."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            
            status = await client.check_qdrant_status()
            
            assert status.connected is False
            assert status.error_count == 1
    
    @pytest.mark.asyncio
    async def test_search_similar_fallback_empty(self, client):
        """Test recherche sémantique fallback vide."""
        with patch.object(client, '_make_rpc_call') as mock_call:
            mock_call.side_effect = Exception("Qdrant unavailable")
            
            results = await client.search_similar("test query")
            
            assert results == []
    
    @pytest.mark.asyncio
    async def test_compress_content_success(self, client):
        """Test compression succès."""
        with patch.object(client, '_make_rpc_call') as mock_call:
            mock_call.return_value = {
                "compressed": "compressed content here",
                "quality_score": 0.85
            }
            
            result = await client.compress_content(
                content="This is a test content for compression",
                algorithm="context_aware"
            )
            
            assert result is not None
            assert result.algorithm == "context_aware"
            assert result.quality_score == 0.85
    
    @pytest.mark.asyncio
    async def test_compress_content_fallback_zlib(self, client):
        """Test compression fallback vers zlib."""
        with patch.object(client, '_make_rpc_call') as mock_call:
            mock_call.side_effect = Exception("Compression server down")
            
            result = await client.compress_content(
                content="This is a test content for compression fallback",
                algorithm="context_aware"
            )
            
            assert result is not None
            assert result.algorithm == "zlib_fallback"
    
    @pytest.mark.asyncio
    async def test_find_redundant_memories(self, client):
        """Test détection mémoires redondantes."""
        with patch.object(client, 'search_similar') as mock_search:
            mock_search.return_value = [
                QdrantSearchResult(id="mem_1", score=0.92),
                QdrantSearchResult(id="mem_2", score=0.88),
            ]
            
            redundant = await client.find_redundant_memories(
                content="Test content",
                similarity_threshold=0.85
            )
            
            assert len(redundant) == 1
            assert redundant[0] == "mem_1"


# ============================================================================
# Tests Memory Manager
# ============================================================================

class TestMemoryManager:
    """Tests du gestionnaire de mémoire."""
    
    @pytest.fixture
    def manager(self):
        """Fixture memory manager."""
        reset_memory_manager()
        mock_client = Mock()
        mock_client.is_qdrant_available.return_value = False
        return MemoryManager(mock_client)
    
    def test_generate_content_hash(self, manager):
        """Test génération hash unique."""
        hash1 = manager._generate_content_hash("Test content")
        hash2 = manager._generate_content_hash("Test content")
        hash3 = manager._generate_content_hash("Different content")
        
        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 16
    
    @pytest.mark.asyncio
    async def test_store_memory_episodic(self, manager):
        """Test stockage mémoire épisodique."""
        with patch('src.kimi_proxy.features.mcp.memory.get_db') as mock_get_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.lastrowid = 123
            mock_conn.cursor.return_value = mock_cursor
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            entry = await manager.store_memory(
                session_id=1,
                content="Test episodic memory content",
                memory_type="episodic"
            )
            
            assert entry is not None
            assert entry.session_id == 1
            assert entry.memory_type == "episodic"
            assert entry.id == 123
    
    @pytest.mark.asyncio
    async def test_store_memory_empty_content(self, manager):
        """Test stockage contenu vide refusé."""
        entry = await manager.store_memory(
            session_id=1,
            content="",
            memory_type="episodic"
        )
        
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_find_similar_memories_fallback(self, manager):
        """Test recherche similaire avec fallback textuel."""
        with patch('src.kimi_proxy.features.mcp.memory.get_db') as mock_get_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                (1, 1, "episodic", "hash1", "Preview 1", "Content 1", 100, 5, None, None, None, None),
                (2, 1, "frequent", "hash2", "Preview 2", "Content 2", 200, 10, None, None, None, None),
            ]
            mock_conn.cursor.return_value = mock_cursor
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            results = await manager.find_similar_memories("test query", session_id=1)
            
            assert len(results) == 2
            assert all(isinstance(r, MCPMemoryEntry) for r in results)
    
    @pytest.mark.asyncio
    async def test_detect_and_promote_frequent_patterns(self, manager):
        """Test détection et promotion patterns fréquents."""
        with patch('src.kimi_proxy.features.mcp.memory.get_db') as mock_get_db:
            mock_conn = Mock()
            mock_cursor = Mock()
            # 3 candidats avec plus de 3 accès
            mock_cursor.fetchall.return_value = [
                (1, 5),
                (2, 8),
                (3, 4),
            ]
            mock_cursor.rowcount = 3
            mock_conn.cursor.return_value = mock_cursor
            mock_get_db.return_value.__enter__ = Mock(return_value=mock_conn)
            mock_get_db.return_value.__exit__ = Mock(return_value=False)
            
            promoted = await manager.detect_and_promote_frequent_patterns(session_id=1)
            
            assert promoted == 3


# ============================================================================
# Tests Routage Provider Optimisé
# ============================================================================

class TestProviderRouting:
    """Tests du routage provider optimisé."""
    
    @pytest.fixture
    def sample_models(self):
        """Fixture modèles de test."""
        return {
            "kimi-code/kimi-for-coding": {
                "provider": "managed:kimi-code",
                "max_context_size": 262144,
                "capabilities": ["thinking"]
            },
            "nvidia/kimi-k2.5": {
                "provider": "nvidia",
                "max_context_size": 262144,
                "capabilities": ["thinking"]
            },
            "groq/compound": {
                "provider": "groq",
                "max_context_size": 131072,
                "capabilities": ["tool_use"]
            },
            "gemini/gemini-2.5-pro": {
                "provider": "gemini",
                "max_context_size": 1048576,
                "capabilities": ["multimodal"]
            },
        }
    
    @pytest.fixture
    def sample_providers(self):
        """Fixture providers de test."""
        return {
            "managed:kimi-code": {"type": "kimi"},
            "nvidia": {"type": "openai"},
            "groq": {"type": "openai"},
            "gemini": {"type": "gemini"},
        }
    
    def test_get_provider_capacities(self, sample_models, sample_providers):
        """Test calcul des capacités providers."""
        capacities = get_provider_capacities(
            current_tokens=50000,
            models=sample_models,
            providers=sample_providers
        )
        
        assert len(capacities) == 4
        # Trie par contexte restant décroissant
        assert capacities[0].max_context >= capacities[1].max_context
        # Vérifie les calculs
        assert capacities[0].context_remaining == capacities[0].max_context - 50000
    
    def test_calculate_routing_score_sufficient(self):
        """Test calcul score avec capacité suffisante."""
        capacity = ProviderCapacity(
            provider_key="test",
            model_key="test-model",
            max_context=262144,
            current_usage=50000,
            context_remaining=212144,
            usage_percentage=19.0,
            cost_factor=1.0,
            latency_score=1.0,
            capabilities=[]
        )
        
        score = calculate_routing_score(capacity, required_tokens=10000)
        
        assert score > 0.5  # Bon score
        assert score <= 1.0
    
    def test_calculate_routing_score_insufficient(self):
        """Test calcul score avec capacité insuffisante."""
        capacity = ProviderCapacity(
            provider_key="test",
            model_key="test-model",
            max_context=100000,
            current_usage=95000,
            context_remaining=5000,
            usage_percentage=95.0,
            cost_factor=1.0,
            latency_score=1.0,
            capabilities=[]
        )
        
        score = calculate_routing_score(capacity, required_tokens=10000)
        
        assert score == 0.0  # Rejeté
    
    def test_find_optimal_provider_preferred_viable(self, sample_models, sample_providers):
        """Test trouve provider optimal - préféré viable."""
        decision = find_optimal_provider(
            current_tokens=50000,
            required_tokens=10000,
            preferred_provider="managed:kimi-code",
            models=sample_models,
            providers=sample_providers
        )
        
        assert isinstance(decision, ProviderRoutingDecision)
        assert decision.fallback_triggered is False
        assert decision.original_provider == "managed:kimi-code"
        assert decision.selected_provider == "managed:kimi-code"
    
    def test_find_optimal_provider_fallback_needed(self, sample_models, sample_providers):
        """Test trouve provider optimal - fallback nécessaire."""
        decision = find_optimal_provider(
            current_tokens=240000,  # Presque plein
            required_tokens=30000,  # Besoin de plus d'espace
            preferred_provider="groq",  # groq a 131K seulement
            models=sample_models,
            providers=sample_providers
        )
        
        assert decision.fallback_triggered is True
        assert decision.selected_provider != "groq"
        # Devrait choisir gemini avec 1M contexte
        assert decision.selected_provider == "gemini"
    
    def test_find_optimal_provider_no_viable(self, sample_models, sample_providers):
        """Test trouve provider optimal - aucun viable."""
        decision = find_optimal_provider(
            current_tokens=250000,  # Presque plein partout
            required_tokens=500000,  # Besoin énorme
            preferred_provider="managed:kimi-code",
            models=sample_models,
            providers=sample_providers
        )
        
        assert decision.fallback_triggered is True
        assert decision.confidence_score < 0.5
    
    def test_get_routing_recommendation_no_session(self, sample_models, sample_providers):
        """Test recommandation sans session."""
        recommendation = get_routing_recommendation(
            session=None,
            prompt_tokens=10000,
            models=sample_models,
            providers=sample_providers
        )
        
        assert recommendation["recommendation"] == "use_default"
        assert recommendation["provider"] == "managed:kimi-code"
    
    def test_get_routing_recommendation_with_session(self, sample_models, sample_providers):
        """Test recommandation avec session active."""
        session = {
            "provider": "managed:kimi-code",
            "estimated_tokens": 50000
        }
        
        recommendation = get_routing_recommendation(
            session=session,
            prompt_tokens=10000,
            models=sample_models,
            providers=sample_providers
        )
        
        assert "decision" in recommendation
        assert "context_safety" in recommendation


# ============================================================================
# Tests Modèles de Données
# ============================================================================

class TestMCPModels:
    """Tests des modèles de données MCP Phase 3."""
    
    def test_mcp_memory_entry_to_dict(self):
        """Test sérialisation MCPMemoryEntry."""
        entry = MCPMemoryEntry(
            id=1,
            session_id=2,
            memory_type="frequent",
            content_hash="abc123",
            content_preview="Preview...",
            full_content="Full content here",
            token_count=100,
            access_count=5,
            similarity_score=0.85
        )
        
        # Sans contenu complet
        dict_without = entry.to_dict(include_content=False)
        assert "full_content" not in dict_without
        assert dict_without["similarity_score"] == 0.85
        
        # Avec contenu complet
        dict_with = entry.to_dict(include_content=True)
        assert dict_with["full_content"] == "Full content here"
    
    def test_mcp_compression_result_to_dict(self):
        """Test sérialisation MCPCompressionResult."""
        result = MCPCompressionResult(
            id=1,
            session_id=2,
            original_tokens=1000,
            compressed_tokens=500,
            compression_ratio=0.5,
            algorithm="context_aware",
            quality_score=0.9
        )
        
        dict_without = result.to_dict(include_content=False)
        assert "compressed_content" not in dict_without
        assert dict_without["compression_ratio"] == 0.5
        assert dict_without["quality_score"] == 0.9
    
    def test_qdrant_search_result_to_dict(self):
        """Test sérialisation QdrantSearchResult."""
        result = QdrantSearchResult(
            id="vec_123",
            score=0.92,
            content_preview="Preview",
            full_content="Full",
            vector=[0.1, 0.2, 0.3]
        )
        
        dict_result = result.to_dict(include_content=True)
        assert dict_result["id"] == "vec_123"
        assert dict_result["score"] == 0.92
        assert dict_result["vector_dimension"] == 3
    
    def test_provider_routing_decision_to_dict(self):
        """Test sérialisation ProviderRoutingDecision."""
        decision = ProviderRoutingDecision(
            original_provider="groq",
            selected_provider="gemini",
            required_context=100000,
            available_context=1048576,
            context_remaining=948576,
            confidence_score=0.85,
            fallback_triggered=True,
            estimated_cost=0.05
        )
        
        dict_result = decision.to_dict()
        assert dict_result["original_provider"] == "groq"
        assert dict_result["fallback_triggered"] is True
        assert dict_result["confidence_score"] == 0.85


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
