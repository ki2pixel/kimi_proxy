"""
Integration tests for store_context tool with tags parameter validation.

These tests verify the complete integration of the store_context MCP tool
with enhanced tags parameter validation and error handling.
"""

import pytest
import tempfile
import os
import sys
import json
from typing import Any, Dict, List, Optional

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server
from server import context_manager, validate_and_normalize_tags, create_validation_error_response


class TestStoreContextIntegration:
    """Integration tests for store_context tool with tags parameter validation."""
    
    @pytest.fixture(autouse=True)
    def setup_and_cleanup(self):
        """Setup and cleanup for each test."""
        # Setup: Clear any existing contexts before each test
        try:
            # Get all contexts and delete them
            all_contexts = context_manager.list_contexts(limit=100)
            for ctx in all_contexts:
                try:
                    context_manager.delete_context(ctx['id'])
                except:
                    pass  # Ignore errors during cleanup
        except:
            pass  # Ignore errors if no contexts exist
        
        yield
        
        # Cleanup: Clear any contexts created during the test
        try:
            all_contexts = context_manager.list_contexts(limit=100)
            for ctx in all_contexts:
                try:
                    context_manager.delete_context(ctx['id'])
                except:
                    pass  # Ignore errors during cleanup
        except:
            pass  # Ignore errors if no contexts exist
    
    def _simulate_store_context(self, data, title=None, tags=None):
        """Simulate the store_context MCP tool with enhanced tags validation."""
        try:
            # Validate and normalize tags parameter
            try:
                normalized_tags = validate_and_normalize_tags(tags)
            except ValueError as e:
                return create_validation_error_response(
                    param_name="tags",
                    received_value=tags,
                    expected_types=["None", "list of strings", "string"],
                    validation_error=str(e)
                )
            
            # Validate input
            if not data or not data.strip():
                return {
                    "status": "error",
                    "error_code": "INVALID_INPUT",
                    "message": "Context data cannot be empty",
                    "details": {"parameter": "data"}
                }
            
            # Store the context with normalized tags
            context_id = context_manager.store_context(data, title, normalized_tags)
            
            # Get compression info for response
            context_info = context_manager.get_context_summary(context_id)
            metadata = context_info['metadata']
            
            # Calculate compression ratio
            compression_ratio = metadata['compressed_size'] / metadata['original_size'] if metadata['original_size'] > 0 else 1.0
            
            return {
                "status": "success",
                "id": context_id,
                "original_size": metadata['original_size'],
                "compressed_size": metadata['compressed_size'],
                "compression_ratio": round(compression_ratio, 3),
                "compression_method": metadata['compression_method']
            }
            
        except ValueError as e:
            return {
                "status": "error",
                "error_code": "VALIDATION_ERROR",
                "message": str(e)
            }
        except Exception as e:
            return {
                "status": "error",
                "error_code": "STORAGE_ERROR",
                "message": f"Failed to store context: {str(e)}"
            }

    def test_store_context_with_none_tags(self):
        """Test store_context with None tags parameter."""
        # Test data
        test_data = "Test data for None tags parameter"
        test_title = "None Tags Test"
        
        # Call store_context with None tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=None)
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        assert result["id"].startswith("ctx_")
        assert "original_size" in result
        assert "compressed_size" in result
        assert "compression_ratio" in result
        assert "compression_method" in result
        
        # Verify context was stored correctly
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["data"] == test_data
        assert retrieved["title"] == test_title
        assert retrieved["tags"] == []  # None gets converted to empty list in current system
        
        # Verify metadata
        assert "metadata" in retrieved
        assert "created_at" in retrieved["metadata"]
        assert "updated_at" in retrieved["metadata"]
        assert "compression_method" in retrieved["metadata"]
    
    def test_store_context_with_empty_list_tags(self):
        """Test store_context with empty list tags parameter."""
        # Test data
        test_data = "Test data for empty list tags parameter"
        test_title = "Empty List Tags Test"
        
        # Call store_context with empty list tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=[])
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        assert result["id"].startswith("ctx_")
        
        # Verify context was stored correctly
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["data"] == test_data
        assert retrieved["title"] == test_title
        assert retrieved["tags"] == []
        
        # Verify response includes compression information
        assert result["original_size"] > 0
        assert result["compressed_size"] > 0
        assert isinstance(result["compression_ratio"], (int, float))
        assert result["compression_method"] in ["none", "zlib"]
    
    def test_store_context_with_valid_string_list_tags(self):
        """Test store_context with valid string list tags parameter."""
        # Test data
        test_data = "Test data for valid string list tags parameter"
        test_title = "Valid String List Tags Test"
        test_tags = ["integration", "test", "valid", "string-list"]
        
        # Call store_context with valid string list tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=test_tags)
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        assert result["id"].startswith("ctx_")
        
        # Verify context was stored correctly
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["data"] == test_data
        assert retrieved["title"] == test_title
        assert retrieved["tags"] == test_tags
        
        # Verify tags are searchable
        search_results = context_manager.search_contexts("integration")
        found_context = next((ctx for ctx in search_results if ctx['id'] == context_id), None)
        assert found_context is not None
        assert found_context["tags"] == test_tags
        
        # Verify response format
        assert isinstance(result["original_size"], int)
        assert isinstance(result["compressed_size"], int)
        assert isinstance(result["compression_ratio"], (int, float))
        assert isinstance(result["compression_method"], str)
    
    def test_store_context_with_single_string_tag(self):
        """Test store_context with single string tag (should convert to list)."""
        # Test data
        test_data = "Test data for single string tag parameter"
        test_title = "Single String Tag Test"
        test_tag = "single-tag"
        
        # Call store_context with single string tag
        result = self._simulate_store_context(data=test_data, title=test_title, tags=test_tag)
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        
        # Verify context was stored with tag converted to list
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["data"] == test_data
        assert retrieved["title"] == test_title
        assert retrieved["tags"] == [test_tag]  # Should be converted to list
        
        # Verify tag is searchable
        search_results = context_manager.search_contexts("single-tag")
        found_context = next((ctx for ctx in search_results if ctx['id'] == context_id), None)
        assert found_context is not None
        assert found_context["tags"] == [test_tag]
    
    def test_store_context_with_invalid_tags_integer(self):
        """Test store_context with invalid tags parameter (integer)."""
        # Test data
        test_data = "Test data for invalid integer tags parameter"
        test_title = "Invalid Integer Tags Test"
        invalid_tags = 123
        
        # Call store_context with invalid integer tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=invalid_tags)
        
        # Verify error response format
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_TAGS_TYPE"
        assert "Invalid type for tags parameter" in result["message"]
        
        # Verify error details
        assert "details" in result
        details = result["details"]
        assert details["received_type"] == "int"
        assert "None" in details["expected_types"]
        assert "list of strings" in details["expected_types"]
        assert "string" in details["expected_types"]
        assert details["received_value"] == str(invalid_tags)
        assert details["parameter"] == "tags"
        assert "validation_error" in details
        
        # Verify no context was created
        all_contexts = context_manager.list_contexts()
        assert len(all_contexts) == 0
    
    def test_store_context_with_invalid_tags_float(self):
        """Test store_context with invalid tags parameter (float)."""
        # Test data
        test_data = "Test data for invalid float tags parameter"
        test_title = "Invalid Float Tags Test"
        invalid_tags = 12.34
        
        # Call store_context with invalid float tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=invalid_tags)
        
        # Verify error response format
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_TAGS_TYPE"
        assert "Invalid type for tags parameter" in result["message"]
        
        # Verify error details
        details = result["details"]
        assert details["received_type"] == "float"
        assert details["parameter"] == "tags"
        assert "validation_error" in details
        
        # Verify no context was created
        all_contexts = context_manager.list_contexts()
        assert len(all_contexts) == 0
    
    def test_store_context_with_invalid_tags_boolean(self):
        """Test store_context with invalid tags parameter (boolean)."""
        # Test data
        test_data = "Test data for invalid boolean tags parameter"
        test_title = "Invalid Boolean Tags Test"
        invalid_tags = True
        
        # Call store_context with invalid boolean tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=invalid_tags)
        
        # Verify error response format
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_TAGS_TYPE"
        
        # Verify error details
        details = result["details"]
        assert details["received_type"] == "bool"
        assert details["parameter"] == "tags"
        
        # Verify no context was created
        all_contexts = context_manager.list_contexts()
        assert len(all_contexts) == 0
    
    def test_store_context_with_invalid_tags_dict(self):
        """Test store_context with invalid tags parameter (dictionary)."""
        # Test data
        test_data = "Test data for invalid dict tags parameter"
        test_title = "Invalid Dict Tags Test"
        invalid_tags = {"key": "value"}
        
        # Call store_context with invalid dict tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=invalid_tags)
        
        # Verify error response format
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_TAGS_TYPE"
        
        # Verify error details
        details = result["details"]
        assert details["received_type"] == "dict"
        assert details["parameter"] == "tags"
        
        # Verify no context was created
        all_contexts = context_manager.list_contexts()
        assert len(all_contexts) == 0
    
    def test_store_context_with_mixed_type_list_tags(self):
        """Test store_context with mixed-type list tags parameter."""
        # Test data
        test_data = "Test data for mixed-type list tags parameter"
        test_title = "Mixed-Type List Tags Test"
        invalid_tags = ["valid_string", 123, "another_string", True]
        
        # Call store_context with mixed-type list tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=invalid_tags)
        
        # Verify error response format
        assert result["status"] == "error"
        assert result["error_code"] == "INVALID_TAGS_TYPE"
        
        # Verify error details contain information about non-string items
        details = result["details"]
        assert details["parameter"] == "tags"
        assert "validation_error" in details
        assert "non-string items" in details["validation_error"]
        assert "index 1: int" in details["validation_error"]
        assert "index 3: bool" in details["validation_error"]
        
        # Verify no context was created
        all_contexts = context_manager.list_contexts()
        assert len(all_contexts) == 0
    
    def test_store_context_error_response_format_consistency(self):
        """Test that all error responses follow consistent format."""
        test_cases = [
            {"tags": 123, "expected_type": "int"},
            {"tags": 12.34, "expected_type": "float"},
            {"tags": True, "expected_type": "bool"},
            {"tags": {"key": "value"}, "expected_type": "dict"},
            {"tags": ["string", 123], "expected_type": "list"},
        ]
        
        for i, case in enumerate(test_cases):
            result = self._simulate_store_context(
                data=f"Test data {i}",
                title=f"Test {i}",
                tags=case["tags"]
            )
            
            # Verify consistent error response structure
            assert result["status"] == "error"
            assert result["error_code"] == "INVALID_TAGS_TYPE"
            assert "message" in result
            assert "details" in result
            
            # Verify details structure
            details = result["details"]
            assert "received_type" in details
            assert "expected_types" in details
            assert "received_value" in details
            assert "parameter" in details
            assert "validation_error" in details
            
            # Verify expected types are consistent
            expected_types = details["expected_types"]
            assert "None" in expected_types
            assert "list of strings" in expected_types
            assert "string" in expected_types
            
            # Verify received type matches expected
            assert details["received_type"] == case["expected_type"]
            assert details["parameter"] == "tags"
    
    def test_store_context_successful_storage_includes_tags_info(self):
        """Test that successful storage includes tags information in response."""
        test_cases = [
            {
                "name": "none_tags",
                "tags": None,
                "expected_stored": []  # None gets converted to empty list in current system
            },
            {
                "name": "empty_list_tags", 
                "tags": [],
                "expected_stored": []
            },
            {
                "name": "string_list_tags",
                "tags": ["tag1", "tag2", "tag3"],
                "expected_stored": ["tag1", "tag2", "tag3"]
            },
            {
                "name": "single_string_tag",
                "tags": "single-tag",
                "expected_stored": ["single-tag"]
            }
        ]
        
        stored_contexts = []
        
        for case in test_cases:
            # Store context
            result = self._simulate_store_context(
                data=f"Test data for {case['name']}",
                title=f"Test {case['name']}",
                tags=case["tags"]
            )
            
            # Verify successful response
            assert result["status"] == "success"
            assert "id" in result
            
            # Verify compression information is included
            assert "original_size" in result
            assert "compressed_size" in result
            assert "compression_ratio" in result
            assert "compression_method" in result
            
            # Verify stored context has correct tags
            context_id = result["id"]
            retrieved = context_manager.retrieve_context(context_id)
            assert retrieved["tags"] == case["expected_stored"]
            
            # Store for cleanup
            stored_contexts.append(context_id)
        
        # Verify all contexts were stored successfully
        assert len(stored_contexts) == len(test_cases)
        
        # Verify contexts can be found in list
        all_contexts = context_manager.list_contexts()
        stored_ids = {ctx["id"] for ctx in all_contexts}
        for context_id in stored_contexts:
            assert context_id in stored_ids
    
    def test_store_context_with_unicode_tags(self):
        """Test store_context with Unicode characters in tags."""
        # Test data with Unicode
        test_data = "Test data with Unicode tags: 你好世界 🌍"
        test_title = "Unicode Tags Test: 测试"
        test_tags = ["测试", "unicode", "🏷️", "中文标签"]
        
        # Call store_context with Unicode tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=test_tags)
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        
        # Verify context was stored correctly with Unicode tags
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["data"] == test_data
        assert retrieved["title"] == test_title
        assert retrieved["tags"] == test_tags
        
        # Verify Unicode tags are searchable
        search_results = context_manager.search_contexts("测试")
        found_context = next((ctx for ctx in search_results if ctx['id'] == context_id), None)
        assert found_context is not None
        assert found_context["tags"] == test_tags
    
    def test_store_context_with_special_characters_in_tags(self):
        """Test store_context with special characters in tags."""
        # Test data with special characters
        test_data = "Test data with special character tags"
        test_title = "Special Characters Tags Test"
        test_tags = ["tag-with-dashes", "tag_with_underscores", "tag.with.dots", "tag@with@symbols"]
        
        # Call store_context with special character tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=test_tags)
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        
        # Verify context was stored correctly
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["tags"] == test_tags
        
        # Verify special character tags are preserved and searchable
        for tag in test_tags:
            search_results = context_manager.search_contexts(tag)
            found_context = next((ctx for ctx in search_results if ctx['id'] == context_id), None)
            assert found_context is not None
    
    def test_store_context_large_number_of_tags(self):
        """Test store_context with a large number of tags."""
        # Test data with many tags
        test_data = "Test data with many tags"
        test_title = "Large Number of Tags Test"
        test_tags = [f"tag{i}" for i in range(100)]  # 100 tags
        
        # Call store_context with many tags
        result = self._simulate_store_context(data=test_data, title=test_title, tags=test_tags)
        
        # Verify successful response
        assert result["status"] == "success"
        assert "id" in result
        
        # Verify context was stored correctly
        context_id = result["id"]
        retrieved = context_manager.retrieve_context(context_id)
        assert retrieved["tags"] == test_tags
        assert len(retrieved["tags"]) == 100
        
        # Verify some tags are searchable
        for i in [0, 25, 50, 75, 99]:
            search_results = context_manager.search_contexts(f"tag{i}")
            found_context = next((ctx for ctx in search_results if ctx['id'] == context_id), None)
            assert found_context is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])