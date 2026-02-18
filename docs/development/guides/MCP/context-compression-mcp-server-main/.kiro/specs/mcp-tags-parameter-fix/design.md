# Design Document

## Overview

This design addresses the `invalid type for parameter 'tags' in tool store_context` error that occurs when MCP clients call the context storage functions. The issue stems from type validation mismatches between the MCP protocol's type system and Python's type annotations, particularly with optional list parameters.

## Root Cause Analysis

The error occurs due to several potential factors:

1. **MCP Protocol Type Serialization**: The MCP protocol may serialize `None` values differently than expected
2. **FastMCP Type Validation**: FastMCP's type validation may be stricter than Python's native type checking
3. **JSON Schema Validation**: The underlying JSON schema validation may not handle `Optional[List[str]]` as expected
4. **Client-Side Type Conversion**: MCP clients may send different representations of null/empty values

## Architecture

### Current Architecture Issues

```
MCP Client → MCP Protocol → FastMCP → Python Function
     ↓           ↓            ↓           ↓
  Various     JSON/RPC    Type Check   Optional[List[str]]
  formats    serialization validation
```

The type validation failure occurs at the FastMCP layer before reaching our Python functions.

### Proposed Architecture

```
MCP Client → MCP Protocol → Enhanced FastMCP → Robust Python Function
     ↓           ↓              ↓                    ↓
  Various     JSON/RPC    Flexible Type         Normalized
  formats    serialization   Validation         List[str]
```

## Components and Interfaces

### 1. Enhanced Type Validation

**Component**: `TagsParameterValidator`
- **Purpose**: Normalize and validate tags parameter before processing
- **Location**: New utility function in `server.py`
- **Interface**:
  ```python
  def validate_and_normalize_tags(tags: Any) -> Optional[List[str]]
  ```

### 2. Updated Tool Signatures

**Component**: MCP Tool Decorators
- **Purpose**: Use more flexible type annotations that work with MCP protocol
- **Changes**: 
  - Replace `Optional[List[str]]` with `Any` for tags parameter
  - Add runtime validation instead of relying on type annotations

### 3. Enhanced Error Handling

**Component**: Error Response Generator
- **Purpose**: Provide detailed error messages for type validation failures
- **Interface**:
  ```python
  def create_validation_error(param_name: str, received_type: str, expected_type: str) -> Dict[str, Any]
  ```

## Data Models

### Input Validation Schema

```python
TagsInput = Union[
    None,                    # Explicit None
    List[str],              # Valid string list
    List[Any],              # List with mixed types (to be filtered)
    str,                    # Single string (to be converted to list)
    int, float, bool,       # Invalid types (to be rejected)
]
```

### Normalized Output

```python
NormalizedTags = Optional[List[str]]  # Always None or List[str]
```

## Error Handling

### Type Validation Errors

1. **Invalid Type Detection**:
   ```python
   if not isinstance(tags, (type(None), list, str)):
       return validation_error("tags", type(tags).__name__, "None, list, or string")
   ```

2. **List Content Validation**:
   ```python
   if isinstance(tags, list):
       non_string_items = [item for item in tags if not isinstance(item, str)]
       if non_string_items:
           return validation_error("tags", "list with non-string items", "list of strings")
   ```

3. **Graceful Degradation**:
   - Log detailed error information
   - Return structured error response
   - Maintain system stability

### Error Response Format

```python
{
    "status": "error",
    "error_code": "INVALID_TAGS_TYPE",
    "message": "Invalid type for tags parameter",
    "details": {
        "received_type": "int",
        "expected_types": ["None", "list of strings"],
        "received_value": 123,
        "parameter": "tags"
    }
}
```

## Testing Strategy

### Unit Tests

1. **Type Validation Tests**:
   - Test with `None` values
   - Test with empty lists
   - Test with valid string lists
   - Test with invalid types (int, float, bool, dict)
   - Test with mixed-type lists

2. **Integration Tests**:
   - Test MCP client calls with various tag formats
   - Test error response formats
   - Test logging behavior

3. **Regression Tests**:
   - Verify existing functionality remains intact
   - Test all other MCP tools continue to work

### Test Cases

```python
# Valid inputs
test_cases_valid = [
    None,
    [],
    ["tag1"],
    ["tag1", "tag2", "tag3"],
    "single_tag",  # Should convert to ["single_tag"]
]

# Invalid inputs
test_cases_invalid = [
    123,
    12.34,
    True,
    {"key": "value"},
    ["tag1", 123, "tag2"],  # Mixed types
    [None, "tag1"],         # None in list
]
```

## Implementation Approach

### Phase 1: Type Validation Enhancement

1. Create `validate_and_normalize_tags()` function
2. Update `store_context` tool signature
3. Update `update_context` tool signature
4. Add comprehensive error handling

### Phase 2: Testing and Validation

1. Implement unit tests for new validation logic
2. Test with various MCP clients
3. Verify error messages are helpful
4. Ensure logging captures necessary details

### Phase 3: Documentation and Monitoring

1. Update API documentation
2. Add troubleshooting guide
3. Implement monitoring for type validation errors
4. Create example usage patterns

## Backward Compatibility

- Existing valid calls will continue to work unchanged
- Invalid calls will now return structured errors instead of crashing
- No breaking changes to the API interface
- Enhanced error messages provide better debugging information

## Performance Considerations

- Type validation adds minimal overhead (< 1ms per call)
- No impact on compression or database operations
- Error handling is fail-fast to minimize resource usage
- Logging is structured for efficient parsing

## Security Considerations

- Input validation prevents injection attacks through tags
- Type checking prevents unexpected data structures
- Error messages don't expose sensitive system information
- Logging includes sanitized input for debugging