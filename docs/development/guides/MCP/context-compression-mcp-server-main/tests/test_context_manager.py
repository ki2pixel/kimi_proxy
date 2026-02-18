"""
Unit tests for Context Manager.

Tests all context management operations including storage, retrieval,
search, listing, deletion, and updates.
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock

from src.context_manager import ContextManager
from src.compression import CompressionEngine, CompressionResult
from src.database import DatabaseManager


class TestContextManager:
    """Test suite for ContextManager class."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager(self, temp_db_path):
        """Create ContextManager instance for testing."""
        return ContextManager(db_path=temp_db_path)
    
    @pytest.fixture
    def mock_compression_engine(self):
        """Create mock compression engine."""
        engine = Mock(spec=CompressionEngine)
        engine.compress.return_value = CompressionResult(
            compressed_data=b"compressed_data",
            original_size=100,
            compressed_size=50,
            compression_method="zlib",
            compression_ratio=0.5
        )
        engine.decompress.return_value = "original_data"
        return engine
    
    def test_init(self, temp_db_path):
        """Test ContextManager initialization."""
        cm = ContextManager(db_path=temp_db_path)
        assert cm.db is not None
        assert cm.compression is not None
        assert isinstance(cm.db, DatabaseManager)
        assert isinstance(cm.compression, CompressionEngine)
    
    def test_init_with_custom_compression(self, temp_db_path, mock_compression_engine):
        """Test ContextManager initialization with custom compression engine."""
        cm = ContextManager(db_path=temp_db_path, compression_engine=mock_compression_engine)
        assert cm.compression is mock_compression_engine
    
    def test_generate_context_id(self, context_manager):
        """Test context ID generation."""
        context_id = context_manager._generate_context_id()
        assert context_id.startswith("ctx_")
        assert len(context_id) == 16  # "ctx_" + 12 hex chars
        
        # Test uniqueness
        context_id2 = context_manager._generate_context_id()
        assert context_id != context_id2
    
    def test_serialize_tags(self, context_manager):
        """Test tag serialization."""
        # Test with valid tags
        tags = ["tag1", "tag2", "tag3"]
        result = context_manager._serialize_tags(tags)
        assert result == json.dumps(tags)
        
        # Test with empty list
        result = context_manager._serialize_tags([])
        assert result == '[]'
        
        # Test with None (now converts to empty list)
        result = context_manager._serialize_tags(None)
        assert result == '[]'
    
    def test_deserialize_tags(self, context_manager):
        """Test tag deserialization."""
        # Test with valid JSON
        tags = ["tag1", "tag2", "tag3"]
        tags_json = json.dumps(tags)
        result = context_manager._deserialize_tags(tags_json)
        assert result == tags
        
        # Test with None
        result = context_manager._deserialize_tags(None)
        assert result == []
        
        # Test with empty string
        result = context_manager._deserialize_tags("")
        assert result == []
        
        # Test with invalid JSON
        result = context_manager._deserialize_tags("invalid_json")
        assert result == []
        
        # Test with non-list JSON
        result = context_manager._deserialize_tags('"not_a_list"')
        assert result == []


class TestContextStorage:
    """Test context storage operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager(self, temp_db_path):
        """Create ContextManager instance for testing."""
        return ContextManager(db_path=temp_db_path)
    
    def test_store_context_basic(self, context_manager):
        """Test basic context storage."""
        data = "This is test context data"
        context_id = context_manager.store_context(data)
        
        assert context_id.startswith("ctx_")
        assert len(context_id) == 16
    
    def test_store_context_with_metadata(self, context_manager):
        """Test context storage with title and tags."""
        data = "This is test context data"
        title = "Test Context"
        tags = ["test", "example"]
        
        context_id = context_manager.store_context(data, title=title, tags=tags)
        
        assert context_id.startswith("ctx_")
        
        # Verify storage by retrieving
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved['title'] == title
        assert retrieved['tags'] == tags
        assert retrieved['data'] == data
    
    def test_store_context_empty_data(self, context_manager):
        """Test storing empty data raises ValueError."""
        with pytest.raises(ValueError, match="Context data cannot be empty"):
            context_manager.store_context("")
        
        with pytest.raises(ValueError, match="Context data cannot be empty"):
            context_manager.store_context("   ")
    
    def test_store_context_compression_failure(self, temp_db_path):
        """Test handling of compression failures."""
        mock_compression = Mock()
        mock_compression.compress.side_effect = Exception("Compression failed")
        
        cm = ContextManager(db_path=temp_db_path, compression_engine=mock_compression)
        
        with pytest.raises(RuntimeError, match="Context storage failed"):
            cm.store_context("test data")
    
    def test_store_context_database_failure(self, temp_db_path):
        """Test handling of database insertion failures."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Mock database to return failure
        cm.db.insert_context = Mock(return_value=False)
        
        with pytest.raises(RuntimeError, match="Failed to store context in database"):
            cm.store_context("test data")


class TestContextRetrieval:
    """Test context retrieval operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager_with_data(self, temp_db_path):
        """Create ContextManager with test data."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Store test data
        test_data = "This is test context data for retrieval"
        test_title = "Test Context"
        test_tags = ["test", "retrieval"]
        
        context_id = cm.store_context(test_data, title=test_title, tags=test_tags)
        
        return cm, context_id, test_data, test_title, test_tags
    
    def test_retrieve_context_success(self, context_manager_with_data):
        """Test successful context retrieval."""
        cm, context_id, test_data, test_title, test_tags = context_manager_with_data
        
        result = cm.retrieve_context(context_id)
        
        assert result['id'] == context_id
        assert result['title'] == test_title
        assert result['data'] == test_data
        assert result['tags'] == test_tags
        assert 'metadata' in result
        assert 'original_size' in result['metadata']
        assert 'compressed_size' in result['metadata']
        assert 'compression_method' in result['metadata']
        assert 'created_at' in result['metadata']
        assert 'updated_at' in result['metadata']
    
    def test_retrieve_context_not_found(self, temp_db_path):
        """Test retrieving non-existent context."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(RuntimeError, match="Context 'ctx_nonexistent' not found"):
            cm.retrieve_context("ctx_nonexistent")
    
    def test_retrieve_context_empty_id(self, temp_db_path):
        """Test retrieving with empty context ID."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Context ID cannot be empty"):
            cm.retrieve_context("")
        
        with pytest.raises(ValueError, match="Context ID cannot be empty"):
            cm.retrieve_context("   ")
    
    def test_retrieve_context_decompression_failure(self, temp_db_path):
        """Test handling of decompression failures."""
        mock_compression = Mock()
        mock_compression.compress.return_value = CompressionResult(
            compressed_data=b"compressed",
            original_size=100,
            compressed_size=50,
            compression_method="zlib",
            compression_ratio=0.5
        )
        mock_compression.decompress.side_effect = Exception("Decompression failed")
        
        cm = ContextManager(db_path=temp_db_path, compression_engine=mock_compression)
        
        # Store data first
        context_id = cm.store_context("test data")
        
        # Now retrieval should fail during decompression
        with pytest.raises(RuntimeError, match="Context retrieval failed"):
            cm.retrieve_context(context_id)


class TestContextSearch:
    """Test context search operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager_with_search_data(self, temp_db_path):
        """Create ContextManager with multiple contexts for search testing."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Store multiple test contexts
        contexts = [
            ("Python programming tutorial", "Python Tutorial", ["python", "programming"]),
            ("JavaScript async/await guide", "JS Async Guide", ["javascript", "async"]),
            ("Database design principles", "DB Design", ["database", "design"]),
            ("Python web development", "Python Web", ["python", "web"]),
        ]
        
        context_ids = []
        for data, title, tags in contexts:
            context_id = cm.store_context(data, title=title, tags=tags)
            context_ids.append(context_id)
        
        return cm, context_ids, contexts
    
    def test_search_contexts_by_title(self, context_manager_with_search_data):
        """Test searching contexts by title."""
        cm, context_ids, contexts = context_manager_with_search_data
        
        results = cm.search_contexts("Python")
        
        assert len(results) == 2  # Should find 2 Python-related contexts
        titles = [r['title'] for r in results]
        assert "Python Tutorial" in titles
        assert "Python Web" in titles
    
    def test_search_contexts_by_tags(self, context_manager_with_search_data):
        """Test searching contexts by tags."""
        cm, context_ids, contexts = context_manager_with_search_data
        
        results = cm.search_contexts("programming")
        
        assert len(results) == 1
        assert results[0]['title'] == "Python Tutorial"
        assert "programming" in results[0]['tags']
    
    def test_search_contexts_with_limit(self, context_manager_with_search_data):
        """Test search with result limit."""
        cm, context_ids, contexts = context_manager_with_search_data
        
        results = cm.search_contexts("Python", limit=1)
        
        assert len(results) == 1
    
    def test_search_contexts_no_results(self, context_manager_with_search_data):
        """Test search with no matching results."""
        cm, context_ids, contexts = context_manager_with_search_data
        
        results = cm.search_contexts("nonexistent")
        
        assert len(results) == 0
        assert results == []
    
    def test_search_contexts_empty_query(self, temp_db_path):
        """Test search with empty query."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            cm.search_contexts("")
        
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            cm.search_contexts("   ")
    
    def test_search_contexts_invalid_limit(self, temp_db_path):
        """Test search with invalid limit."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Limit must be positive"):
            cm.search_contexts("test", limit=0)
        
        with pytest.raises(ValueError, match="Limit must be positive"):
            cm.search_contexts("test", limit=-1)
    
    def test_search_contexts_database_error(self, temp_db_path):
        """Test search with database error."""
        cm = ContextManager(db_path=temp_db_path)
        cm.db.search_contexts = Mock(side_effect=Exception("Database error"))
        
        with pytest.raises(RuntimeError, match="Context search failed"):
            cm.search_contexts("test")


class TestContextListing:
    """Test context listing operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager_with_list_data(self, temp_db_path):
        """Create ContextManager with multiple contexts for listing tests."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Store multiple test contexts
        context_ids = []
        for i in range(5):
            data = f"Test context data {i}"
            title = f"Context {i}"
            tags = [f"tag{i}", "common"]
            context_id = cm.store_context(data, title=title, tags=tags)
            context_ids.append(context_id)
        
        return cm, context_ids
    
    def test_list_contexts_default(self, context_manager_with_list_data):
        """Test listing contexts with default parameters."""
        cm, context_ids = context_manager_with_list_data
        
        results = cm.list_contexts()
        
        assert len(results) == 5
        for result in results:
            assert 'id' in result
            assert 'title' in result
            assert 'tags' in result
            assert 'metadata' in result
            assert 'data' not in result  # Data should not be included in listing
    
    def test_list_contexts_with_limit(self, context_manager_with_list_data):
        """Test listing contexts with limit."""
        cm, context_ids = context_manager_with_list_data
        
        results = cm.list_contexts(limit=3)
        
        assert len(results) == 3
    
    def test_list_contexts_with_offset(self, context_manager_with_list_data):
        """Test listing contexts with offset."""
        cm, context_ids = context_manager_with_list_data
        
        # Get all results first
        all_results = cm.list_contexts()
        
        # Get results with offset
        offset_results = cm.list_contexts(limit=3, offset=2)
        
        assert len(offset_results) == 3
        # Results should be different due to offset
        assert offset_results[0]['id'] != all_results[0]['id']
    
    def test_list_contexts_empty_database(self, temp_db_path):
        """Test listing contexts from empty database."""
        cm = ContextManager(db_path=temp_db_path)
        
        results = cm.list_contexts()
        
        assert len(results) == 0
        assert results == []
    
    def test_list_contexts_invalid_limit(self, temp_db_path):
        """Test listing with invalid limit."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Limit must be positive"):
            cm.list_contexts(limit=0)
        
        with pytest.raises(ValueError, match="Limit must be positive"):
            cm.list_contexts(limit=-1)
    
    def test_list_contexts_invalid_offset(self, temp_db_path):
        """Test listing with invalid offset."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Offset cannot be negative"):
            cm.list_contexts(offset=-1)
    
    def test_list_contexts_database_error(self, temp_db_path):
        """Test listing with database error."""
        cm = ContextManager(db_path=temp_db_path)
        cm.db.list_contexts = Mock(side_effect=Exception("Database error"))
        
        with pytest.raises(RuntimeError, match="Context listing failed"):
            cm.list_contexts()


class TestContextDeletion:
    """Test context deletion operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager_with_data(self, temp_db_path):
        """Create ContextManager with test data."""
        cm = ContextManager(db_path=temp_db_path)
        context_id = cm.store_context("Test data for deletion", title="Delete Test")
        return cm, context_id
    
    def test_delete_context_success(self, context_manager_with_data):
        """Test successful context deletion."""
        cm, context_id = context_manager_with_data
        
        # Verify context exists
        result = cm.retrieve_context(context_id)
        assert result['id'] == context_id
        
        # Delete context
        success = cm.delete_context(context_id)
        assert success is True
        
        # Verify context is deleted
        with pytest.raises(RuntimeError, match="not found"):
            cm.retrieve_context(context_id)
    
    def test_delete_context_not_found(self, temp_db_path):
        """Test deleting non-existent context."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(RuntimeError, match="Context 'ctx_nonexistent' not found"):
            cm.delete_context("ctx_nonexistent")
    
    def test_delete_context_empty_id(self, temp_db_path):
        """Test deleting with empty context ID."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Context ID cannot be empty"):
            cm.delete_context("")
        
        with pytest.raises(ValueError, match="Context ID cannot be empty"):
            cm.delete_context("   ")
    
    def test_delete_context_database_error(self, context_manager_with_data):
        """Test deletion with database error."""
        cm, context_id = context_manager_with_data
        
        # Mock database to simulate error
        cm.db.context_exists = Mock(return_value=True)
        cm.db.delete_context = Mock(return_value=False)
        
        with pytest.raises(RuntimeError, match="Failed to delete context"):
            cm.delete_context(context_id)


class TestContextUpdate:
    """Test context update operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager_with_data(self, temp_db_path):
        """Create ContextManager with test data."""
        cm = ContextManager(db_path=temp_db_path)
        context_id = cm.store_context(
            "Original test data", 
            title="Original Title", 
            tags=["original", "test"]
        )
        return cm, context_id
    
    def test_update_context_title_only(self, context_manager_with_data):
        """Test updating only the title."""
        cm, context_id = context_manager_with_data
        
        new_title = "Updated Title"
        success = cm.update_context(context_id, title=new_title)
        assert success is True
        
        # Verify update
        result = cm.retrieve_context(context_id)
        assert result['title'] == new_title
        assert result['data'] == "Original test data"  # Data unchanged
        assert result['tags'] == ["original", "test"]  # Tags unchanged
    
    def test_update_context_tags_only(self, context_manager_with_data):
        """Test updating only the tags."""
        cm, context_id = context_manager_with_data
        
        new_tags = ["updated", "modified"]
        success = cm.update_context(context_id, tags=new_tags)
        assert success is True
        
        # Verify update
        result = cm.retrieve_context(context_id)
        assert result['tags'] == new_tags
        assert result['title'] == "Original Title"  # Title unchanged
        assert result['data'] == "Original test data"  # Data unchanged
    
    def test_update_context_data_only(self, context_manager_with_data):
        """Test updating only the data."""
        cm, context_id = context_manager_with_data
        
        new_data = "Updated test data with new content"
        success = cm.update_context(context_id, data=new_data)
        assert success is True
        
        # Verify update
        result = cm.retrieve_context(context_id)
        assert result['data'] == new_data
        assert result['title'] == "Original Title"  # Title unchanged
        assert result['tags'] == ["original", "test"]  # Tags unchanged
    
    def test_update_context_all_fields(self, context_manager_with_data):
        """Test updating all fields."""
        cm, context_id = context_manager_with_data
        
        new_data = "Completely updated data"
        new_title = "Completely Updated Title"
        new_tags = ["completely", "updated"]
        
        success = cm.update_context(
            context_id, 
            data=new_data, 
            title=new_title, 
            tags=new_tags
        )
        assert success is True
        
        # Verify update
        result = cm.retrieve_context(context_id)
        assert result['data'] == new_data
        assert result['title'] == new_title
        assert result['tags'] == new_tags
    
    def test_update_context_not_found(self, temp_db_path):
        """Test updating non-existent context."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(RuntimeError, match="Context 'ctx_nonexistent' not found"):
            cm.update_context("ctx_nonexistent", title="New Title")
    
    def test_update_context_empty_id(self, temp_db_path):
        """Test updating with empty context ID."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Context ID cannot be empty"):
            cm.update_context("", title="New Title")
    
    def test_update_context_no_fields(self, context_manager_with_data):
        """Test updating with no fields provided."""
        cm, context_id = context_manager_with_data
        
        with pytest.raises(RuntimeError, match="Failed to update context"):
            cm.update_context(context_id)
    
    def test_update_context_empty_data(self, context_manager_with_data):
        """Test updating with empty data."""
        cm, context_id = context_manager_with_data
        
        with pytest.raises(ValueError, match="Context data cannot be empty"):
            cm.update_context(context_id, data="")
        
        with pytest.raises(ValueError, match="Context data cannot be empty"):
            cm.update_context(context_id, data="   ")
    
    def test_update_context_database_error(self, context_manager_with_data):
        """Test update with database error."""
        cm, context_id = context_manager_with_data
        
        # Mock database to simulate error
        cm.db.context_exists = Mock(return_value=True)
        cm.db.update_context = Mock(return_value=False)
        
        with pytest.raises(RuntimeError, match="Failed to update context"):
            cm.update_context(context_id, title="New Title")


class TestContextSummary:
    """Test context summary operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    @pytest.fixture
    def context_manager_with_data(self, temp_db_path):
        """Create ContextManager with test data."""
        cm = ContextManager(db_path=temp_db_path)
        context_id = cm.store_context(
            "Test data for summary", 
            title="Summary Test", 
            tags=["summary", "test"]
        )
        return cm, context_id
    
    def test_get_context_summary_success(self, context_manager_with_data):
        """Test successful context summary retrieval."""
        cm, context_id = context_manager_with_data
        
        result = cm.get_context_summary(context_id)
        
        assert result['id'] == context_id
        assert result['title'] == "Summary Test"
        assert result['tags'] == ["summary", "test"]
        assert 'metadata' in result
        assert 'data' not in result  # Data should not be included in summary
    
    def test_get_context_summary_not_found(self, temp_db_path):
        """Test getting summary for non-existent context."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(RuntimeError, match="Context 'ctx_nonexistent' not found"):
            cm.get_context_summary("ctx_nonexistent")
    
    def test_get_context_summary_empty_id(self, temp_db_path):
        """Test getting summary with empty context ID."""
        cm = ContextManager(db_path=temp_db_path)
        
        with pytest.raises(ValueError, match="Context ID cannot be empty"):
            cm.get_context_summary("")


class TestContextManagerStats:
    """Test context manager statistics and utility methods."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_get_stats(self, temp_db_path):
        """Test getting context manager statistics."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Add some test data
        cm.store_context("Test data 1", title="Test 1")
        cm.store_context("Test data 2", title="Test 2")
        
        stats = cm.get_stats()
        
        assert 'total_contexts' in stats
        assert stats['total_contexts'] == 2
        assert 'database_info' in stats
        assert 'compression_config' in stats
        
        # Check compression config
        config = stats['compression_config']
        assert 'min_size_threshold' in config
        assert 'min_compression_ratio' in config
        assert 'compression_level' in config
    
    def test_get_stats_error_handling(self, temp_db_path):
        """Test stats error handling."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Mock database to cause error
        cm.db.get_database_info = Mock(side_effect=Exception("Database error"))
        
        stats = cm.get_stats()
        assert 'error' in stats
    
    def test_context_manager_context_manager(self, temp_db_path):
        """Test using ContextManager as context manager."""
        with ContextManager(db_path=temp_db_path) as cm:
            context_id = cm.store_context("Test data")
            result = cm.retrieve_context(context_id)
            assert result['data'] == "Test data"
        
        # Context manager should be closed after exiting
        # This is mainly testing that no exceptions are raised
    
    def test_close(self, temp_db_path):
        """Test closing context manager."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Mock database close to verify it's called
        cm.db.close_connections = Mock()
        
        cm.close()
        
        cm.db.close_connections.assert_called_once()


class TestContextManagerConcurrency:
    """Test context manager concurrent operations."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_concurrent_store_operations(self, temp_db_path):
        """Test concurrent context storage operations."""
        import threading
        import time
        
        cm = ContextManager(db_path=temp_db_path)
        results = []
        errors = []
        
        def store_worker(worker_id):
            try:
                for i in range(10):
                    data = f"Worker {worker_id} context data {i} " * 50
                    title = f"Worker {worker_id} Context {i}"
                    tags = [f"worker{worker_id}", f"item{i}"]
                    
                    context_id = cm.store_context(data, title=title, tags=tags)
                    results.append((worker_id, i, context_id))
                    time.sleep(0.001)  # Small delay to increase contention
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple store threads
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=store_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Store thread errors: {errors}"
        assert len(results) == 50  # 5 workers * 10 operations each
        
        # Verify all contexts were stored and can be retrieved
        for worker_id, item_id, context_id in results:
            retrieved = cm.retrieve_context(context_id)
            assert f"Worker {worker_id} context data {item_id}" in retrieved['data']
            assert retrieved['title'] == f"Worker {worker_id} Context {item_id}"
            assert f"worker{worker_id}" in retrieved['tags']
        
        cm.close()
    
    def test_concurrent_mixed_operations(self, temp_db_path):
        """Test concurrent mixed read/write operations."""
        import threading
        import time
        
        cm = ContextManager(db_path=temp_db_path)
        
        # Pre-populate with some data
        initial_contexts = []
        for i in range(10):
            context_id = cm.store_context(f"Initial data {i}", title=f"Initial {i}")
            initial_contexts.append(context_id)
        
        read_results = []
        write_results = []
        search_results = []
        errors = []
        
        def read_worker():
            try:
                for _ in range(20):
                    context_id = initial_contexts[len(read_results) % len(initial_contexts)]
                    result = cm.retrieve_context(context_id)
                    read_results.append(result is not None)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Read error: {str(e)}")
        
        def write_worker(worker_id):
            try:
                for i in range(5):
                    data = f"Concurrent write {worker_id}-{i}"
                    context_id = cm.store_context(data, title=f"Write {worker_id}-{i}")
                    write_results.append(context_id)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(f"Write error: {str(e)}")
        
        def search_worker():
            try:
                for _ in range(10):
                    results = cm.search_contexts("Initial", limit=5)
                    search_results.append(len(results))
                    time.sleep(0.002)
            except Exception as e:
                errors.append(f"Search error: {str(e)}")
        
        # Start concurrent operations
        threads = []
        
        # Start read threads
        for _ in range(2):
            thread = threading.Thread(target=read_worker)
            threads.append(thread)
            thread.start()
        
        # Start write threads
        for worker_id in range(2):
            thread = threading.Thread(target=write_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Start search thread
        thread = threading.Thread(target=search_worker)
        threads.append(thread)
        thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(errors) == 0, f"Concurrent operation errors: {errors}"
        assert len(read_results) == 40  # 2 threads * 20 reads each
        assert len(write_results) == 10  # 2 threads * 5 writes each
        assert len(search_results) == 10  # 1 thread * 10 searches
        
        assert all(read_results)  # All reads should succeed
        assert all(ctx_id.startswith("ctx_") for ctx_id in write_results)  # All writes should succeed
        assert all(count >= 0 for count in search_results)  # All searches should return valid counts
        
        cm.close()


class TestContextManagerEdgeCases:
    """Test context manager edge cases and error conditions."""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_large_context_handling(self, temp_db_path):
        """Test handling of very large context data."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Test with 1MB of data
        large_data = "Large context data. " * 50000  # ~1MB
        context_id = cm.store_context(large_data, title="Large Context")
        
        # Retrieve and verify
        result = cm.retrieve_context(context_id)
        assert result['data'] == large_data
        assert result['title'] == "Large Context"
        assert result['metadata']['original_size'] == len(large_data.encode('utf-8'))
        
        cm.close()
    
    def test_unicode_and_special_characters(self, temp_db_path):
        """Test handling of Unicode and special characters."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Test with various Unicode characters
        unicode_data = "Unicode test: 你好世界 🌍 Здравствуй мир 🌎 مرحبا بالعالم 🌏"
        unicode_title = "Unicode Title: 测试标题 🏷️"
        unicode_tags = ["unicode", "测试", "🏷️", "тест"]
        
        context_id = cm.store_context(unicode_data, title=unicode_title, tags=unicode_tags)
        
        # Retrieve and verify
        result = cm.retrieve_context(context_id)
        assert result['data'] == unicode_data
        assert result['title'] == unicode_title
        assert result['tags'] == unicode_tags
        
        # Test search with Unicode
        search_results = cm.search_contexts("测试")
        assert len(search_results) >= 1
        assert any(r['title'] == unicode_title for r in search_results)
        
        cm.close()
    
    def test_malformed_data_handling(self, temp_db_path):
        """Test handling of malformed or edge case data."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Test with data containing null bytes
        null_data = "Data with\x00null\x00bytes"
        context_id = cm.store_context(null_data, title="Null Bytes Test")
        
        result = cm.retrieve_context(context_id)
        assert result['data'] == null_data
        
        # Test with very long tags
        long_tags = [f"very_long_tag_name_{i}" * 10 for i in range(100)]
        context_id = cm.store_context("Test data", title="Long Tags", tags=long_tags)
        
        result = cm.retrieve_context(context_id)
        assert result['tags'] == long_tags
        
        # Test with empty tags list
        context_id = cm.store_context("Test data", title="Empty Tags", tags=[])
        result = cm.retrieve_context(context_id)
        assert result['tags'] == []
        
        cm.close()
    
    def test_database_recovery_scenarios(self, temp_db_path):
        """Test context manager behavior in database recovery scenarios."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Store some data
        context_id = cm.store_context("Recovery test data", title="Recovery Test")
        
        # Simulate database connection issues by mocking
        original_get_connection = cm.db._get_connection
        
        def failing_connection():
            raise Exception("Database connection failed")
        
        # Temporarily break the connection
        cm.db._get_connection = failing_connection
        
        # Operations should fail gracefully
        with pytest.raises(RuntimeError):
            cm.store_context("Should fail", title="Fail Test")
        
        with pytest.raises(RuntimeError):
            cm.retrieve_context(context_id)
        
        # Restore connection
        cm.db._get_connection = original_get_connection
        
        # Operations should work again
        result = cm.retrieve_context(context_id)
        assert result['data'] == "Recovery test data"
        
        cm.close()
    
    def test_memory_usage_with_many_contexts(self, temp_db_path):
        """Test memory usage patterns with many contexts."""
        import gc
        
        cm = ContextManager(db_path=temp_db_path)
        
        # Store many small contexts
        context_ids = []
        for i in range(1000):
            data = f"Context data {i} " * 10
            context_id = cm.store_context(data, title=f"Context {i}", tags=[f"tag{i}"])
            context_ids.append(context_id)
            
            # Force garbage collection periodically
            if i % 100 == 0:
                gc.collect()
        
        # Test batch retrieval
        retrieved_count = 0
        for context_id in context_ids[::10]:  # Every 10th context
            result = cm.retrieve_context(context_id)
            assert "Context data" in result['data']
            retrieved_count += 1
        
        assert retrieved_count == 100
        
        # Test search across many contexts
        search_results = cm.search_contexts("Context", limit=50)
        assert len(search_results) == 50
        
        # Test listing with pagination
        list_results = cm.list_contexts(limit=100, offset=0)
        assert len(list_results) == 100
        
        list_results = cm.list_contexts(limit=100, offset=900)
        assert len(list_results) == 100
        
        cm.close()
    
    def test_context_id_uniqueness_and_collision_handling(self, temp_db_path):
        """Test context ID uniqueness and collision handling."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Generate many context IDs and ensure uniqueness
        context_ids = set()
        for _ in range(1000):
            context_id = cm._generate_context_id()
            assert context_id not in context_ids, f"Duplicate context ID: {context_id}"
            context_ids.add(context_id)
            assert context_id.startswith("ctx_")
            assert len(context_id) == 16  # "ctx_" + 12 hex chars
        
        # Test that all generated IDs are valid hex
        for context_id in list(context_ids)[:10]:  # Test first 10
            hex_part = context_id[4:]  # Remove "ctx_" prefix
            int(hex_part, 16)  # Should not raise ValueError
        
        cm.close()
    
    def test_tag_serialization_edge_cases(self, temp_db_path):
        """Test tag serialization with edge cases."""
        cm = ContextManager(db_path=temp_db_path)
        
        # Test with various tag types
        edge_case_tags = [
            [],  # Empty list
            [""],  # List with empty string
            ["tag with spaces", "tag-with-dashes", "tag_with_underscores"],
            ["🏷️", "标签", "тег"],  # Unicode tags
            [str(i) for i in range(100)],  # Many tags
            ["tag" * 100],  # Very long tag
        ]
        
        for i, tags in enumerate(edge_case_tags):
            context_id = cm.store_context(f"Test data {i}", title=f"Tag Test {i}", tags=tags)
            result = cm.retrieve_context(context_id)
            assert result['tags'] == tags, f"Tag mismatch for test case {i}: expected {tags}, got {result['tags']}"
        
        cm.close()


if __name__ == "__main__":
    pytest.main([__file__])