"""
Integration tests for FastMCP server tools.

Tests all MCP tools with realistic scenarios and error conditions.
"""

import pytest
import tempfile
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_manager import ContextManager


class TestMCPServerIntegration:
    """Integration tests for MCP server tools."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Set up a temporary database for each test."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Create a context manager with temp database
        self.context_manager = ContextManager(self.temp_db.name)
        
        yield
        
        # Cleanup
        self.context_manager.close()
        try:
            os.unlink(self.temp_db.name)
        except OSError:
            pass
    
    def _simulate_store_context(self, data, title=None, tags=None):
        """Simulate the store_context MCP tool."""
        try:
            if not data or not data.strip():
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Context data cannot be empty",
                    "details": {}
                }
            
            context_id = self.context_manager.store_context(data, title, tags)
            context_info = self.context_manager.get_context_summary(context_id)
            metadata = context_info['metadata']
            compression_ratio = metadata['compressed_size'] / metadata['original_size'] if metadata['original_size'] > 0 else 1.0
            
            return {
                "status": "success",
                "id": context_id,
                "original_size": metadata['original_size'],
                "compressed_size": metadata['compressed_size'],
                "compression_ratio": round(compression_ratio, 3),
                "compression_method": metadata['compression_method']
            }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "STORAGE_ERROR",
                "message": f"Failed to store context: {str(e)}",
                "details": {}
            }
    
    def _simulate_retrieve_context(self, context_id):
        """Simulate the retrieve_context MCP tool."""
        try:
            if not context_id or not context_id.strip():
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Context ID cannot be empty",
                    "details": {}
                }
            
            context_data = self.context_manager.retrieve_context(context_id.strip())
            return {
                "status": "success",
                **context_data
            }
        except RuntimeError as e:
            if "not found" in str(e).lower():
                return {
                    "status": "error",
                    "error_code": "CONTEXT_NOT_FOUND",
                    "message": str(e),
                    "details": {"context_id": context_id}
                }
            else:
                return {
                    "status": "error",
                    "error_code": "RETRIEVAL_ERROR",
                    "message": str(e),
                    "details": {"context_id": context_id}
                }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "details": {"context_id": context_id}
            }
    
    def _simulate_search_contexts(self, query, limit=10):
        """Simulate the search_contexts MCP tool."""
        try:
            if not query or not query.strip():
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Search query cannot be empty",
                    "details": {}
                }
            
            if limit <= 0 or limit > 100:
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Limit must be between 1 and 100",
                    "details": {"limit": limit}
                }
            
            results = self.context_manager.search_contexts(query.strip(), limit=limit)
            return {
                "status": "success",
                "query": query.strip(),
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "SEARCH_ERROR",
                "message": f"Failed to search contexts: {str(e)}",
                "details": {"query": query, "limit": limit}
            }
    
    def _simulate_list_contexts(self, limit=50, offset=0):
        """Simulate the list_contexts MCP tool."""
        try:
            if limit <= 0 or limit > 100:
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Limit must be between 1 and 100",
                    "details": {"limit": limit}
                }
            
            if offset < 0:
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Offset cannot be negative",
                    "details": {"offset": offset}
                }
            
            results = self.context_manager.list_contexts(limit=limit, offset=offset)
            return {
                "status": "success",
                "results": results,
                "count": len(results),
                "pagination": {
                    "limit": limit,
                    "offset": offset
                }
            }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "LIST_ERROR",
                "message": f"Failed to list contexts: {str(e)}",
                "details": {"limit": limit, "offset": offset}
            }
    
    def _simulate_delete_context(self, context_id):
        """Simulate the delete_context MCP tool."""
        try:
            if not context_id or not context_id.strip():
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Context ID cannot be empty",
                    "details": {}
                }
            
            success = self.context_manager.delete_context(context_id.strip())
            if success:
                return {
                    "status": "success",
                    "message": f"Context '{context_id}' deleted successfully",
                    "context_id": context_id.strip()
                }
            else:
                return {
                    "status": "error",
                    "error_code": "DELETION_ERROR",
                    "message": f"Failed to delete context '{context_id}'",
                    "details": {"context_id": context_id}
                }
        except RuntimeError as e:
            if "not found" in str(e).lower():
                return {
                    "status": "error",
                    "error_code": "CONTEXT_NOT_FOUND",
                    "message": str(e),
                    "details": {"context_id": context_id}
                }
            else:
                return {
                    "status": "error",
                    "error_code": "DELETION_ERROR",
                    "message": str(e),
                    "details": {"context_id": context_id}
                }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "details": {"context_id": context_id}
            }
    
    def _simulate_update_context(self, context_id, data=None, title=None, tags=None):
        """Simulate the update_context MCP tool."""
        try:
            if not context_id or not context_id.strip():
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Context ID cannot be empty",
                    "details": {}
                }
            
            if not any([data is not None, title is not None, tags is not None]):
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "At least one field (data, title, or tags) must be provided for update",
                    "details": {"context_id": context_id}
                }
            
            if data is not None and (not data or not data.strip()):
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Context data cannot be empty when provided",
                    "details": {"context_id": context_id}
                }
            
            success = self.context_manager.update_context(
                context_id.strip(),
                data=data,
                title=title,
                tags=tags
            )
            
            if success:
                updated_context = self.context_manager.get_context_summary(context_id.strip())
                return {
                    "status": "success",
                    "message": f"Context '{context_id}' updated successfully",
                    "context_id": context_id.strip(),
                    "updated_fields": {
                        "data": data is not None,
                        "title": title is not None,
                        "tags": tags is not None
                    },
                    "metadata": updated_context['metadata']
                }
            else:
                return {
                    "status": "error",
                    "error_code": "UPDATE_ERROR",
                    "message": f"Failed to update context '{context_id}'",
                    "details": {"context_id": context_id}
                }
        except RuntimeError as e:
            if "not found" in str(e).lower():
                return {
                    "status": "error",
                    "error_code": "CONTEXT_NOT_FOUND",
                    "message": str(e),
                    "details": {"context_id": context_id}
                }
            else:
                return {
                    "status": "error",
                    "error_code": "UPDATE_ERROR",
                    "message": str(e),
                    "details": {"context_id": context_id}
                }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "INTERNAL_ERROR",
                "message": f"An unexpected error occurred: {str(e)}",
                "details": {"context_id": context_id}
            }
    
    def test_store_context_success(self):
        """Test successful context storage."""
        result = self._simulate_store_context(
            data="This is test context data for storage",
            title="Test Context",
            tags=["test", "integration"]
        )
        
        assert result["status"] == "success"
        assert "id" in result
        assert result["id"].startswith("ctx_")
        assert result["original_size"] > 0
        assert result["compressed_size"] > 0
        assert "compression_ratio" in result
        assert "compression_method" in result
    
    def test_store_context_empty_data(self):
        """Test storing empty data returns error."""
        result = self._simulate_store_context(data="")
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "empty" in result["message"].lower()
    
    def test_store_context_whitespace_only(self):
        """Test storing whitespace-only data returns error."""
        result = self._simulate_store_context(data="   \n\t  ")
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "empty" in result["message"].lower()
    
    def test_retrieve_context_success(self):
        """Test successful context retrieval."""
        # First store a context
        store_result = self._simulate_store_context(
            data="Test data for retrieval",
            title="Retrieval Test",
            tags=["retrieve", "test"]
        )
        context_id = store_result["id"]
        
        # Then retrieve it
        result = self._simulate_retrieve_context(context_id)
        
        assert result["status"] == "success"
        assert result["id"] == context_id
        assert result["data"] == "Test data for retrieval"
        assert result["title"] == "Retrieval Test"
        assert result["tags"] == ["retrieve", "test"]
        assert "metadata" in result
        assert "created_at" in result["metadata"]
    
    def test_retrieve_context_not_found(self):
        """Test retrieving non-existent context."""
        result = self._simulate_retrieve_context("ctx_nonexistent")
        
        assert result["status"] == "error"
        assert result["error_code"] == "CONTEXT_NOT_FOUND"
        assert "not found" in result["message"].lower()
    
    def test_retrieve_context_empty_id(self):
        """Test retrieving with empty context ID."""
        result = self._simulate_retrieve_context("")
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "empty" in result["message"].lower()
    
    def test_search_contexts_success(self):
        """Test successful context search."""
        # Store multiple contexts
        self._simulate_store_context(data="Python programming tutorial", title="Python Guide", tags=["python", "tutorial"])
        self._simulate_store_context(data="JavaScript basics", title="JS Basics", tags=["javascript", "basics"])
        self._simulate_store_context(data="Python advanced concepts", title="Advanced Python", tags=["python", "advanced"])
        
        # Search for Python contexts
        result = self._simulate_search_contexts("python", limit=10)
        
        assert result["status"] == "success"
        assert result["query"] == "python"
        assert result["count"] >= 2  # Should find at least 2 Python contexts
        assert len(result["results"]) >= 2
        
        # Check result structure
        for context in result["results"]:
            assert "id" in context
            assert "title" in context
            assert "tags" in context
            assert "metadata" in context
    
    def test_search_contexts_empty_query(self):
        """Test search with empty query."""
        result = self._simulate_search_contexts("")
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "empty" in result["message"].lower()
    
    def test_search_contexts_invalid_limit(self):
        """Test search with invalid limit."""
        result = self._simulate_search_contexts("test", limit=0)
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "limit" in result["message"].lower()
        
        result = self._simulate_search_contexts("test", limit=101)
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "limit" in result["message"].lower()
    
    def test_list_contexts_success(self):
        """Test successful context listing."""
        # Store multiple contexts
        for i in range(5):
            self._simulate_store_context(
                data=f"Test context data {i}",
                title=f"Context {i}",
                tags=[f"tag{i}"]
            )
        
        # List contexts
        result = self._simulate_list_contexts(limit=10, offset=0)
        
        assert result["status"] == "success"
        assert result["count"] >= 5
        assert len(result["results"]) >= 5
        assert "pagination" in result
        assert result["pagination"]["limit"] == 10
        assert result["pagination"]["offset"] == 0
        
        # Check result structure
        for context in result["results"]:
            assert "id" in context
            assert "title" in context
            assert "tags" in context
            assert "metadata" in context
    
    def test_list_contexts_pagination(self):
        """Test context listing with pagination."""
        # Store multiple contexts
        for i in range(10):
            self._simulate_store_context(data=f"Context {i}", title=f"Title {i}")
        
        # Test pagination
        result1 = self._simulate_list_contexts(limit=3, offset=0)
        result2 = self._simulate_list_contexts(limit=3, offset=3)
        
        assert result1["status"] == "success"
        assert result2["status"] == "success"
        assert len(result1["results"]) == 3
        assert len(result2["results"]) == 3
        
        # Results should be different
        ids1 = {ctx["id"] for ctx in result1["results"]}
        ids2 = {ctx["id"] for ctx in result2["results"]}
        assert ids1.isdisjoint(ids2)  # No overlap
    
    def test_list_contexts_invalid_params(self):
        """Test list contexts with invalid parameters."""
        # Invalid limit
        result = self._simulate_list_contexts(limit=0)
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        
        result = self._simulate_list_contexts(limit=101)
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        
        # Invalid offset
        result = self._simulate_list_contexts(offset=-1)
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
    
    def test_delete_context_success(self):
        """Test successful context deletion."""
        # Store a context
        store_result = self._simulate_store_context(data="Context to delete", title="Delete Me")
        context_id = store_result["id"]
        
        # Delete it
        result = self._simulate_delete_context(context_id)
        
        assert result["status"] == "success"
        assert result["context_id"] == context_id
        assert "deleted successfully" in result["message"]
        
        # Verify it's gone
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["status"] == "error"
        assert retrieve_result["error_code"] == "CONTEXT_NOT_FOUND"
    
    def test_delete_context_not_found(self):
        """Test deleting non-existent context."""
        result = self._simulate_delete_context("ctx_nonexistent")
        
        assert result["status"] == "error"
        assert result["error_code"] == "CONTEXT_NOT_FOUND"
        assert "not found" in result["message"].lower()
    
    def test_delete_context_empty_id(self):
        """Test deleting with empty context ID."""
        result = self._simulate_delete_context("")
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "empty" in result["message"].lower()
    
    def test_update_context_data_success(self):
        """Test successful context data update."""
        # Store a context
        store_result = self._simulate_store_context(data="Original data", title="Original Title")
        context_id = store_result["id"]
        
        # Update the data
        result = self._simulate_update_context(context_id, data="Updated data")
        
        assert result["status"] == "success"
        assert result["context_id"] == context_id
        assert result["updated_fields"]["data"] is True
        assert result["updated_fields"]["title"] is False
        assert result["updated_fields"]["tags"] is False
        
        # Verify the update
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["data"] == "Updated data"
        assert retrieve_result["title"] == "Original Title"  # Unchanged
    
    def test_update_context_title_and_tags(self):
        """Test updating title and tags."""
        # Store a context
        store_result = self._simulate_store_context(data="Test data", title="Old Title", tags=["old"])
        context_id = store_result["id"]
        
        # Update title and tags
        result = self._simulate_update_context(
            context_id, 
            title="New Title", 
            tags=["new", "updated"]
        )
        
        assert result["status"] == "success"
        assert result["updated_fields"]["data"] is False
        assert result["updated_fields"]["title"] is True
        assert result["updated_fields"]["tags"] is True
        
        # Verify the update
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["data"] == "Test data"  # Unchanged
        assert retrieve_result["title"] == "New Title"
        assert retrieve_result["tags"] == ["new", "updated"]
    
    def test_update_context_not_found(self):
        """Test updating non-existent context."""
        result = self._simulate_update_context("ctx_nonexistent", title="New Title")
        
        assert result["status"] == "error"
        assert result["error_code"] == "CONTEXT_NOT_FOUND"
        assert "not found" in result["message"].lower()
    
    def test_update_context_no_fields(self):
        """Test updating without providing any fields."""
        # Store a context first
        store_result = self._simulate_store_context(data="Test data")
        context_id = store_result["id"]
        
        # Try to update without any fields
        result = self._simulate_update_context(context_id)
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "at least one field" in result["message"].lower()
    
    def test_update_context_empty_data(self):
        """Test updating with empty data."""
        # Store a context first
        store_result = self._simulate_store_context(data="Test data")
        context_id = store_result["id"]
        
        # Try to update with empty data
        result = self._simulate_update_context(context_id, data="")
        
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_INPUT"
        assert "empty" in result["message"].lower()
    
    def test_end_to_end_workflow(self):
        """Test complete workflow: store, search, retrieve, update, delete."""
        # Store multiple contexts
        contexts = []
        for i in range(3):
            result = self._simulate_store_context(
                data=f"Workflow test data {i}",
                title=f"Workflow Test {i}",
                tags=["workflow", f"test{i}"]
            )
            contexts.append(result["id"])
        
        # Search for contexts
        search_result = self._simulate_search_contexts("workflow")
        assert search_result["status"] == "success"
        assert search_result["count"] >= 3
        
        # List all contexts
        list_result = self._simulate_list_contexts()
        assert list_result["status"] == "success"
        assert list_result["count"] >= 3
        
        # Retrieve each context
        for context_id in contexts:
            retrieve_result = self._simulate_retrieve_context(context_id)
            assert retrieve_result["status"] == "success"
            assert "Workflow test data" in retrieve_result["data"]
        
        # Update one context
        update_result = self._simulate_update_context(
            contexts[0], 
            title="Updated Workflow Test",
            tags=["workflow", "updated"]
        )
        assert update_result["status"] == "success"
        
        # Verify update
        retrieve_result = self._simulate_retrieve_context(contexts[0])
        assert retrieve_result["title"] == "Updated Workflow Test"
        assert "updated" in retrieve_result["tags"]
        
        # Delete contexts
        for context_id in contexts:
            delete_result = self._simulate_delete_context(context_id)
            assert delete_result["status"] == "success"
        
        # Verify deletion
        for context_id in contexts:
            retrieve_result = self._simulate_retrieve_context(context_id)
            assert retrieve_result["status"] == "error"
            assert retrieve_result["error_code"] == "CONTEXT_NOT_FOUND"
    
    def test_large_data_integration(self):
        """Test integration with large data sets."""
        # Store large context (1MB)
        large_data = "Large integration test data. " * 50000  # ~1MB
        result = self._simulate_store_context(
            data=large_data,
            title="Large Data Integration Test",
            tags=["large", "integration", "performance"]
        )
        
        assert result["status"] == "success"
        context_id = result["id"]
        assert result["original_size"] > 1000000  # Should be > 1MB
        
        # Retrieve large data
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["status"] == "success"
        assert retrieve_result["data"] == large_data
        assert len(retrieve_result["data"]) > 1000000
        
        # Search should find it
        search_result = self._simulate_search_contexts("Large Data")
        assert search_result["status"] == "success"
        assert search_result["count"] >= 1
        
        # Update with different large data
        new_large_data = "Updated large integration test data. " * 40000  # ~800KB
        update_result = self._simulate_update_context(context_id, data=new_large_data)
        assert update_result["status"] == "success"
        
        # Verify update
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["data"] == new_large_data
        
        # Clean up
        delete_result = self._simulate_delete_context(context_id)
        assert delete_result["status"] == "success"
    
    def test_unicode_integration(self):
        """Test integration with Unicode data."""
        unicode_data = """
        Unicode Integration Test:
        Chinese: 你好世界，这是一个测试。
        Japanese: こんにちは世界、これはテストです。
        Korean: 안녕하세요 세계, 이것은 테스트입니다.
        Arabic: مرحبا بالعالم، هذا اختبار.
        Russian: Привет мир, это тест.
        Emoji: 🌍🌎🌏 Hello World! 🚀✨🎉
        """
        
        unicode_title = "Unicode Test: 多语言测试 🌍"
        unicode_tags = ["unicode", "多语言", "🏷️", "тест", "テスト"]
        
        # Store Unicode context
        result = self._simulate_store_context(
            data=unicode_data,
            title=unicode_title,
            tags=unicode_tags
        )
        
        assert result["status"] == "success"
        context_id = result["id"]
        
        # Retrieve and verify Unicode preservation
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["status"] == "success"
        assert retrieve_result["data"] == unicode_data
        assert retrieve_result["title"] == unicode_title
        assert retrieve_result["tags"] == unicode_tags
        
        # Search with Unicode terms
        search_result = self._simulate_search_contexts("多语言")
        assert search_result["status"] == "success"
        assert search_result["count"] >= 1
        
        # Update with Unicode
        new_unicode_title = "Updated Unicode: 更新的测试 🔄"
        update_result = self._simulate_update_context(
            context_id, 
            title=new_unicode_title,
            tags=["updated", "更新", "🔄"]
        )
        assert update_result["status"] == "success"
        
        # Verify Unicode update
        retrieve_result = self._simulate_retrieve_context(context_id)
        assert retrieve_result["title"] == new_unicode_title
        assert "更新" in retrieve_result["tags"]
        
        # Clean up
        delete_result = self._simulate_delete_context(context_id)
        assert delete_result["status"] == "success"
    
    def test_stress_test_many_contexts(self):
        """Test system behavior with many contexts."""
        context_ids = []
        
        # Store many contexts
        for i in range(100):
            result = self._simulate_store_context(
                data=f"Stress test context {i} with some additional data to make it longer",
                title=f"Stress Test {i}",
                tags=[f"stress", f"test{i}", f"batch{i//10}"]
            )
            assert result["status"] == "success"
            context_ids.append(result["id"])
        
        # Test search across many contexts
        search_result = self._simulate_search_contexts("stress", limit=50)
        assert search_result["status"] == "success"
        assert search_result["count"] == 50  # Should be limited to 50
        
        # Test listing with pagination
        list_result1 = self._simulate_list_contexts(limit=30, offset=0)
        assert list_result1["status"] == "success"
        assert len(list_result1["results"]) == 30
        
        list_result2 = self._simulate_list_contexts(limit=30, offset=30)
        assert list_result2["status"] == "success"
        assert len(list_result2["results"]) == 30
        
        # Verify no overlap in pagination
        ids1 = {ctx["id"] for ctx in list_result1["results"]}
        ids2 = {ctx["id"] for ctx in list_result2["results"]}
        assert ids1.isdisjoint(ids2)
        
        # Test batch updates
        for i in range(0, 20, 2):  # Update every other context in first 20
            update_result = self._simulate_update_context(
                context_ids[i],
                title=f"Updated Stress Test {i}",
                tags=["stress", "updated", f"test{i}"]
            )
            assert update_result["status"] == "success"
        
        # Verify updates
        for i in range(0, 20, 2):
            retrieve_result = self._simulate_retrieve_context(context_ids[i])
            assert retrieve_result["status"] == "success"
            assert retrieve_result["title"] == f"Updated Stress Test {i}"
            assert "updated" in retrieve_result["tags"]
        
        # Test batch deletion
        for context_id in context_ids[:50]:  # Delete first 50
            delete_result = self._simulate_delete_context(context_id)
            assert delete_result["status"] == "success"
        
        # Verify deletions
        for context_id in context_ids[:50]:
            retrieve_result = self._simulate_retrieve_context(context_id)
            assert retrieve_result["status"] == "error"
            assert retrieve_result["error_code"] == "CONTEXT_NOT_FOUND"
        
        # Verify remaining contexts still exist
        for context_id in context_ids[50:60]:  # Check 10 remaining contexts
            retrieve_result = self._simulate_retrieve_context(context_id)
            assert retrieve_result["status"] == "success"
        
        # Clean up remaining contexts
        for context_id in context_ids[50:]:
            self._simulate_delete_context(context_id)
    
    def test_error_recovery_integration(self):
        """Test error recovery and system resilience."""
        # Store some valid contexts first
        valid_contexts = []
        for i in range(5):
            result = self._simulate_store_context(
                data=f"Valid context {i}",
                title=f"Valid {i}",
                tags=[f"valid{i}"]
            )
            assert result["status"] == "success"
            valid_contexts.append(result["id"])
        
        # Test various error conditions don't break the system
        error_tests = [
            ("", "Empty data"),
            ("   \n\t  ", "Whitespace only"),
            (None, "None data") if hasattr(self, '_test_none_data') else None,
        ]
        
        for test_data, description in filter(None, error_tests):
            result = self._simulate_store_context(test_data)
            assert result["status"] == "error", f"Should fail for {description}"
        
        # Verify system still works after errors
        for context_id in valid_contexts:
            retrieve_result = self._simulate_retrieve_context(context_id)
            assert retrieve_result["status"] == "success"
        
        # Test search still works
        search_result = self._simulate_search_contexts("Valid")
        assert search_result["status"] == "success"
        assert search_result["count"] >= 5
        
        # Test operations on non-existent contexts
        fake_ids = ["ctx_nonexistent1", "ctx_nonexistent2", "ctx_fake123456"]
        for fake_id in fake_ids:
            retrieve_result = self._simulate_retrieve_context(fake_id)
            assert retrieve_result["status"] == "error"
            assert retrieve_result["error_code"] == "CONTEXT_NOT_FOUND"
            
            delete_result = self._simulate_delete_context(fake_id)
            assert delete_result["status"] == "error"
            assert delete_result["error_code"] == "CONTEXT_NOT_FOUND"
            
            update_result = self._simulate_update_context(fake_id, title="New Title")
            assert update_result["status"] == "error"
            assert update_result["error_code"] == "CONTEXT_NOT_FOUND"
        
        # Verify valid contexts still work after error operations
        for context_id in valid_contexts:
            retrieve_result = self._simulate_retrieve_context(context_id)
            assert retrieve_result["status"] == "success"
        
        # Clean up
        for context_id in valid_contexts:
            delete_result = self._simulate_delete_context(context_id)
            assert delete_result["status"] == "success"
    
    def test_compression_integration_scenarios(self):
        """Test integration scenarios focusing on compression behavior."""
        # Test small data (should not compress)
        small_data = "Small data that won't compress"
        result = self._simulate_store_context(small_data, title="Small Data Test")
        assert result["status"] == "success"
        assert result["compression_ratio"] == 1.0  # Should not be compressed
        
        small_context_id = result["id"]
        retrieve_result = self._simulate_retrieve_context(small_context_id)
        assert retrieve_result["data"] == small_data
        
        # Test highly compressible data
        compressible_data = "A" * 5000  # Highly repetitive, should compress well
        result = self._simulate_store_context(compressible_data, title="Compressible Data Test")
        assert result["status"] == "success"
        assert result["compression_ratio"] < 0.1  # Should compress very well
        
        compressible_context_id = result["id"]
        retrieve_result = self._simulate_retrieve_context(compressible_context_id)
        assert retrieve_result["data"] == compressible_data
        
        # Test incompressible data
        import random
        random.seed(42)  # For reproducible tests
        incompressible_data = ''.join(chr(random.randint(32, 126)) for _ in range(5000))
        result = self._simulate_store_context(incompressible_data, title="Incompressible Data Test")
        assert result["status"] == "success"
        # Compression ratio will vary, but should still work
        
        incompressible_context_id = result["id"]
        retrieve_result = self._simulate_retrieve_context(incompressible_context_id)
        assert retrieve_result["data"] == incompressible_data
        
        # Test mixed data types in search
        search_result = self._simulate_search_contexts("Data Test")
        assert search_result["status"] == "success"
        assert search_result["count"] >= 3
        
        # Verify all contexts have correct compression metadata
        for context in search_result["results"]:
            assert "original_size" in context["metadata"]
            assert "compressed_size" in context["metadata"]
            assert "compression_method" in context["metadata"]
            assert context["metadata"]["compression_method"] in ["zlib", "none"]
        
        # Clean up
        for context_id in [small_context_id, compressible_context_id, incompressible_context_id]:
            delete_result = self._simulate_delete_context(context_id)
            assert delete_result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])