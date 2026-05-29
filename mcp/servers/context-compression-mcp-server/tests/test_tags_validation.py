"""
Unit tests for tags parameter validation functionality.

Tests the validate_and_normalize_tags() function with various input types
to ensure proper handling of None, empty lists, valid string lists,
single strings, and invalid types.
"""

import pytest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import validate_and_normalize_tags


class TestTagsValidation:
    """Unit tests for tags parameter validation."""
    
    def test_validate_tags_with_none_input(self):
        """Test validate_and_normalize_tags() with None input."""
        # Test requirement 1.1: WHEN an MCP client passes None to the tags parameter 
        # THEN the system SHALL store the context successfully
        # Note: None gets converted to empty list to clear tags
        result = validate_and_normalize_tags(None)
        assert result == []
    
    def test_validate_tags_with_empty_list_input(self):
        """Test validate_and_normalize_tags() with empty list input."""
        # Test requirement 1.2: WHEN an MCP client passes an empty list to the tags parameter 
        # THEN the system SHALL store the context successfully
        result = validate_and_normalize_tags([])
        assert result == []
        assert isinstance(result, list)
    
    def test_validate_tags_with_valid_string_list_input(self):
        """Test validate_and_normalize_tags() with valid string list input."""
        # Test requirement 1.3: WHEN an MCP client passes a list of strings to the tags parameter 
        # THEN the system SHALL store the context successfully
        
        # Test single string in list
        result = validate_and_normalize_tags(["tag1"])
        assert result == ["tag1"]
        assert isinstance(result, list)
        
        # Test multiple strings in list
        result = validate_and_normalize_tags(["tag1", "tag2", "tag3"])
        assert result == ["tag1", "tag2", "tag3"]
        assert isinstance(result, list)
        
        # Test with various string formats
        result = validate_and_normalize_tags(["simple", "with-dash", "with_underscore", "with123numbers"])
        assert result == ["simple", "with-dash", "with_underscore", "with123numbers"]
        
        # Test with Unicode strings
        result = validate_and_normalize_tags(["unicode", "测试", "🏷️", "тест"])
        assert result == ["unicode", "测试", "🏷️", "тест"]
    
    def test_validate_tags_with_single_string_input(self):
        """Test validate_and_normalize_tags() with single string input."""
        # Test string to list conversion functionality
        
        # Test simple string
        result = validate_and_normalize_tags("single_tag")
        assert result == ["single_tag"]
        assert isinstance(result, list)
        
        # Test string with spaces
        result = validate_and_normalize_tags("tag with spaces")
        assert result == ["tag with spaces"]
        
        # Test Unicode string
        result = validate_and_normalize_tags("测试标签")
        assert result == ["测试标签"]
        
        # Test emoji string
        result = validate_and_normalize_tags("🏷️")
        assert result == ["🏷️"]
    
    def test_validate_tags_with_invalid_int_type(self):
        """Test validate_and_normalize_tags() with invalid int type."""
        # Test requirement 1.4: WHEN an MCP client passes an invalid type to the tags parameter 
        # THEN the system SHALL return an appropriate error message
        
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(123)
        
        error_message = str(exc_info.value)
        assert "Invalid type for tags parameter" in error_message
        assert "int" in error_message
        assert "Expected None, string, or list of strings" in error_message
    
    def test_validate_tags_with_invalid_float_type(self):
        """Test validate_and_normalize_tags() with invalid float type."""
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(12.34)
        
        error_message = str(exc_info.value)
        assert "Invalid type for tags parameter" in error_message
        assert "float" in error_message
        assert "Expected None, string, or list of strings" in error_message
    
    def test_validate_tags_with_invalid_bool_type(self):
        """Test validate_and_normalize_tags() with invalid bool type."""
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(True)
        
        error_message = str(exc_info.value)
        assert "Invalid type for tags parameter" in error_message
        assert "bool" in error_message
        assert "Expected None, string, or list of strings" in error_message
        
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(False)
        
        error_message = str(exc_info.value)
        assert "Invalid type for tags parameter" in error_message
        assert "bool" in error_message
    
    def test_validate_tags_with_invalid_dict_type(self):
        """Test validate_and_normalize_tags() with invalid dict type."""
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags({"key": "value"})
        
        error_message = str(exc_info.value)
        assert "Invalid type for tags parameter" in error_message
        assert "dict" in error_message
        assert "Expected None, string, or list of strings" in error_message
    
    def test_validate_tags_with_mixed_type_lists(self):
        """Test validate_and_normalize_tags() with mixed-type lists."""
        # Test list with string and int
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(["tag1", 123, "tag2"])
        
        error_message = str(exc_info.value)
        assert "All items in tags list must be strings" in error_message
        assert "index 1: int" in error_message
        
        # Test list with string and None
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(["tag1", None, "tag2"])
        
        error_message = str(exc_info.value)
        assert "All items in tags list must be strings" in error_message
        assert "index 1: NoneType" in error_message
        
        # Test list with multiple invalid types
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(["tag1", 123, True, "tag2", 45.6])
        
        error_message = str(exc_info.value)
        assert "All items in tags list must be strings" in error_message
        assert "index 1: int" in error_message
        assert "index 2: bool" in error_message
        assert "index 4: float" in error_message
        
        # Test list with dict and list
        with pytest.raises(ValueError) as exc_info:
            validate_and_normalize_tags(["tag1", {"key": "value"}, ["nested"]])
        
        error_message = str(exc_info.value)
        assert "All items in tags list must be strings" in error_message
        assert "index 1: dict" in error_message
        assert "index 2: list" in error_message
    
    def test_validate_tags_edge_cases(self):
        """Test validate_and_normalize_tags() with edge cases."""
        # Test empty string
        result = validate_and_normalize_tags("")
        assert result == [""]
        
        # Test string with only whitespace
        result = validate_and_normalize_tags("   ")
        assert result == ["   "]
        
        # Test list with empty strings
        result = validate_and_normalize_tags(["", "tag1", ""])
        assert result == ["", "tag1", ""]
        
        # Test very long string
        long_string = "a" * 1000
        result = validate_and_normalize_tags(long_string)
        assert result == [long_string]
        
        # Test list with very long strings
        result = validate_and_normalize_tags([long_string, "short"])
        assert result == [long_string, "short"]
    
    def test_validate_tags_preserves_order(self):
        """Test that validate_and_normalize_tags() preserves order of tags."""
        original_tags = ["zebra", "alpha", "beta", "gamma"]
        result = validate_and_normalize_tags(original_tags)
        assert result == original_tags
        # Note: Function returns the same object for efficiency, which is acceptable
    
    def test_validate_tags_handles_duplicates(self):
        """Test that validate_and_normalize_tags() preserves duplicates."""
        tags_with_duplicates = ["tag1", "tag2", "tag1", "tag3", "tag2"]
        result = validate_and_normalize_tags(tags_with_duplicates)
        assert result == tags_with_duplicates
        # Duplicates should be preserved as-is
        assert result.count("tag1") == 2
        assert result.count("tag2") == 2
    
    def test_validate_tags_return_types(self):
        """Test that validate_and_normalize_tags() returns correct types."""
        # None input should return empty list (behavior changed for MCP compatibility)
        result = validate_and_normalize_tags(None)
        assert result == []
        assert isinstance(result, list)
        
        # String input should return list
        result = validate_and_normalize_tags("tag")
        assert isinstance(result, list)
        assert len(result) == 1
        
        # List input should return list
        result = validate_and_normalize_tags(["tag1", "tag2"])
        assert isinstance(result, list)
        assert len(result) == 2
        
        # Empty list should return empty list
        result = validate_and_normalize_tags([])
        assert isinstance(result, list)
        assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__])