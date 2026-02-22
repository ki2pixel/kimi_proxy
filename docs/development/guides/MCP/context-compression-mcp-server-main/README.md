# Context Compression MCP Server

An MCP (Model Context Protocol) server that helps AI agents manage context window limitations by compressing and storing context data in a SQLite database. Built with FastMCP, this server provides tools for AI agents to store, retrieve, and manage compressed contextual information efficiently.

## Features

- **Context Compression**: Automatically compresses context data using zlib to save storage space
- **Persistent Storage**: Uses SQLite database for reliable data persistence
- **Search & Retrieval**: Find stored contexts by keywords or retrieve by ID
- **Metadata Management**: Store titles, tags, and timestamps with context data
- **Thread-Safe Operations**: Handles concurrent requests safely
- **MCP Integration**: Works seamlessly with any MCP-compatible AI client

## Installation

### Prerequisites

- Python 3.10 or higher
- pip or uv package manager

### Install from PyPI (when published)

```bash
pip install context-compression-mcp
```

### Install from Source

```bash
git clone https://github.com/yourusername/context-compression-mcp.git
cd context-compression-mcp
pip install -e .
```

### Using uv (recommended)

```bash
git clone https://github.com/yourusername/context-compression-mcp.git
cd context-compression-mcp
uv sync
```

### Verify Installation

After installation, you can verify everything is working:

```bash
uv run python test_installation.py
```

## Quick Start

### 1. Start the MCP Server

#### Production Mode
```bash
uv run fastmcp run server.py
```

#### Development Mode (with MCP Inspector)
```bash
uv run fastmcp dev server.py
```

The development mode includes the MCP Inspector web interface for testing and debugging your MCP tools.

The server will start and create a `context_data.db` SQLite database file in the current directory.

### 2. Configure Your MCP Client

Add the server to your MCP client configuration. Here are examples for popular clients:

#### Claude Desktop Configuration (Development)

For development, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "context-compression": {
      "command": "uv",
      "args": ["--directory", "/path/to/context-compression-mcp", "run", "fastmcp", "run", "server.py"],
      "env": {}
    }
  }
}
```

#### Using uvx (Production - when published)

```json
{
  "mcpServers": {
    "context-compression": {
      "command": "uvx",
      "args": ["context-compression-mcp"],
      "env": {}
    }
  }
}
```

## Available Tools

The server provides six MCP tools for context management:

### store_context

Store context data with optional metadata.

**Parameters:**
- `data` (string, required): The context data to store
- `title` (string, optional): A descriptive title for the context
- `tags` (array of strings, optional): Tags for categorization

**Returns:**
```json
{
  "status": "success",
  "id": "ctx_1234567890",
  "original_size": 5000,
  "compressed_size": 1200,
  "compression_ratio": 0.24,
  "compression_method": "zlib"
}
```

**Example Usage:**
```python
# Store API documentation
result = store_context(
    data="API endpoints: GET /users, POST /users...",
    title="User API Documentation",
    tags=["api", "documentation", "users"]
)
```

### retrieve_context

Retrieve and decompress context data by ID.

**Parameters:**
- `context_id` (string, required): The unique context identifier

**Returns:**
```json
{
  "status": "success",
  "id": "ctx_1234567890",
  "title": "User API Documentation",
  "data": "API endpoints: GET /users, POST /users...",
  "tags": ["api", "documentation", "users"],
  "metadata": {
    "original_size": 5000,
    "compressed_size": 1200,
    "compression_method": "zlib",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

### search_contexts

Search for contexts matching a query string.

**Parameters:**
- `query` (string, required): Search query string
- `limit` (integer, optional): Maximum results to return (default: 10, max: 100)

**Returns:**
```json
{
  "status": "success",
  "query": "api documentation",
  "results": [
    {
      "id": "ctx_1234567890",
      "title": "User API Documentation",
      "tags": ["api", "documentation", "users"],
      "created_at": "2024-01-15T10:30:00Z",
      "original_size": 5000,
      "compressed_size": 1200
    }
  ],
  "count": 1
}
```

### list_contexts

List all stored contexts with pagination.

**Parameters:**
- `limit` (integer, optional): Maximum results to return (default: 50, max: 100)
- `offset` (integer, optional): Number of results to skip (default: 0)

**Returns:**
```json
{
  "status": "success",
  "results": [
    {
      "id": "ctx_1234567890",
      "title": "User API Documentation",
      "tags": ["api", "documentation"],
      "created_at": "2024-01-15T10:30:00Z",
      "original_size": 5000,
      "compressed_size": 1200
    }
  ],
  "count": 1,
  "pagination": {
    "limit": 50,
    "offset": 0
  }
}
```

### delete_context

Delete a context by ID.

**Parameters:**
- `context_id` (string, required): The unique context identifier

**Returns:**
```json
{
  "status": "success",
  "message": "Context 'ctx_1234567890' deleted successfully",
  "context_id": "ctx_1234567890"
}
```

### update_context

Update an existing context's data, title, or tags.

**Parameters:**
- `context_id` (string, required): The unique context identifier
- `data` (string, optional): New context data (will be recompressed)
- `title` (string, optional): New title
- `tags` (array of strings, optional): New tags list

**Returns:**
```json
{
  "status": "success",
  "message": "Context 'ctx_1234567890' updated successfully",
  "context_id": "ctx_1234567890",
  "updated_fields": {
    "data": true,
    "title": false,
    "tags": true
  },
  "metadata": {
    "original_size": 6000,
    "compressed_size": 1400,
    "compression_method": "zlib",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T11:45:00Z"
  }
}
```

## Configuration

### Environment Variables

- `CONTEXT_DB_PATH`: Path to SQLite database file (default: `./context_data.db`)
- `COMPRESSION_THRESHOLD`: Minimum size in bytes before compression is applied (default: 1024)
- `MAX_CONTEXT_SIZE`: Maximum context size in bytes (default: 10485760 = 10MB)

### Database Configuration

The server automatically creates and manages the SQLite database. The database file will be created in the current working directory unless specified otherwise via `CONTEXT_DB_PATH`.

## Usage Examples

### Basic Workflow

```python
# 1. Store some context data
store_result = store_context(
    data="Large API documentation content here...",
    title="API Docs v2.1",
    tags=["api", "v2.1", "documentation"]
)
context_id = store_result["id"]

# 2. Retrieve it later
context = retrieve_context(context_id)
print(context["data"])  # Original uncompressed data

# 3. Search for related contexts
results = search_contexts("API documentation")
for result in results["results"]:
    print(f"Found: {result['title']} (ID: {result['id']})")

# 4. Update the context
update_context(
    context_id,
    title="API Docs v2.2",
    tags=["api", "v2.2", "documentation", "updated"]
)

# 5. List all contexts
all_contexts = list_contexts(limit=20)
print(f"Total contexts: {all_contexts['count']}")
```

## Advanced Usage

#### Batch Operations

```python
# Store multiple related contexts
contexts = [
    {"data": "User model documentation", "title": "User Model", "tags": ["model", "user"]},
    {"data": "Order model documentation", "title": "Order Model", "tags": ["model", "order"]},
    {"data": "Payment model documentation", "title": "Payment Model", "tags": ["model", "payment"]}
]

stored_ids = []
for ctx in contexts:
    result = store_context(**ctx)
    stored_ids.append(result["id"])

# Search across all model documentation
model_docs = search_contexts("model documentation", limit=50)
```

#### Working with Large Contexts

```python
# The server automatically compresses large contexts
large_context = "Very large context data..." * 1000  # Large string

result = store_context(
    data=large_context,
    title="Large Context Example"
)

print(f"Original size: {result['original_size']} bytes")
print(f"Compressed size: {result['compressed_size']} bytes")
print(f"Compression ratio: {result['compression_ratio']}")
```

## Error Handling

All tools return structured error responses when issues occur:

```json
{
  "status": "error",
  "error_code": "CONTEXT_NOT_FOUND",
  "message": "Context with ID 'ctx_invalid' not found",
  "details": {
    "context_id": "ctx_invalid"
  }
}
```

### Common Error Codes

- `INVALID_INPUT`: Invalid or missing required parameters
- `INVALID_TAGS_TYPE`: Invalid type provided for tags parameter
- `CONTEXT_NOT_FOUND`: Requested context ID doesn't exist
- `VALIDATION_ERROR`: Data validation failed
- `STORAGE_ERROR`: Database storage operation failed
- `RETRIEVAL_ERROR`: Database retrieval operation failed
- `COMPRESSION_ERROR`: Data compression/decompression failed
- `INTERNAL_ERROR`: Unexpected server error

### Tags Parameter Validation

The `tags` parameter in `store_context` and `update_context` tools accepts flexible input types and performs automatic type conversion:

#### Valid Tags Parameter Values

```python
# None (no tags)
store_context(data="example", tags=None)

# Empty list (no tags)
store_context(data="example", tags=[])

# List of strings (standard usage)
store_context(data="example", tags=["api", "documentation", "v1"])

# Single string (automatically converted to list)
store_context(data="example", tags="important")  # Becomes ["important"]
```

#### Invalid Tags Parameter Values

```python
# Numbers, booleans, or other non-string/list types
store_context(data="example", tags=123)        # Error
store_context(data="example", tags=True)       # Error
store_context(data="example", tags={"key": "value"})  # Error

# Lists containing non-string items
store_context(data="example", tags=["valid", 123, "also_valid"])  # Error
store_context(data="example", tags=[None, "tag"])  # Error
```

#### Tags Type Conversion Behavior

- **Single string**: Automatically converted to a single-item list
  - Input: `"important"` → Output: `["important"]`
- **Empty string**: Converted to single-item list with empty string
  - Input: `""` → Output: `[""]`
- **None**: Remains as None (no tags)
- **Empty list**: Remains as empty list (no tags)
- **Valid string list**: Used as-is

#### Tags Validation Error Response

When invalid types are provided for the tags parameter, you'll receive a detailed error response:

```json
{
  "status": "error",
  "error_code": "INVALID_TAGS_TYPE",
  "message": "Invalid type for tags parameter",
  "details": {
    "received_type": "int",
    "expected_types": ["None", "list of strings", "string"],
    "received_value": 123,
    "parameter": "tags"
  }
}
```

### Troubleshooting Tags Parameter Issues

#### Problem: "Invalid type for parameter 'tags'" Error

**Symptoms**: 
- MCP client receives `INVALID_TAGS_TYPE` error
- Error message indicates unexpected type for tags parameter

**Common Causes & Solutions**:

1. **Passing numbers instead of strings**
   ```python
   # ❌ Wrong
   store_context(data="example", tags=[1, 2, 3])
   
   # ✅ Correct
   store_context(data="example", tags=["1", "2", "3"])
   ```

2. **Passing objects or complex types**
   ```python
   # ❌ Wrong
   store_context(data="example", tags={"category": "api"})
   
   # ✅ Correct
   store_context(data="example", tags=["category:api"])
   ```

3. **Mixed types in list**
   ```python
   # ❌ Wrong
   store_context(data="example", tags=["valid", 123, True])
   
   # ✅ Correct
   store_context(data="example", tags=["valid", "123", "true"])
   ```

4. **MCP client serialization issues**
   - Some MCP clients may serialize data differently
   - Try passing tags as explicit string arrays in your client
   - Check your MCP client's documentation for proper array formatting

#### Problem: Tags Not Being Stored or Retrieved Correctly

**Symptoms**:
- Tags appear to be accepted but don't show up in search results
- Retrieved contexts have missing or incorrect tags

**Solutions**:

1. **Verify tag format after storage**
   ```python
   # Store with tags
   result = store_context(data="example", tags=["test", "debug"])
   
   # Retrieve and verify
   context = retrieve_context(result["id"])
   print(context["tags"])  # Should show ["test", "debug"]
   ```

2. **Check for empty or whitespace-only tags**
   ```python
   # ❌ Problematic
   store_context(data="example", tags=["", "  ", "valid"])
   
   # ✅ Better
   store_context(data="example", tags=["valid"])
   ```

3. **Use consistent tag naming conventions**
   ```python
   # ✅ Recommended patterns
   store_context(data="example", tags=["api-v1", "documentation", "user-guide"])
   store_context(data="example", tags=["category:api", "version:1", "type:plan"])
   ```

#### Problem: Search Not Finding Tagged Contexts

**Symptoms**:
- Contexts stored with tags but search doesn't return them
- Tags visible in `retrieve_context` but not in `search_contexts`

**Solutions**:

1. **Search includes tag content**
   ```python
   # If you stored with tags=["api", "documentation"]
   search_contexts("api")           # Should find it
   search_contexts("documentation") # Should find it
   search_contexts("api plan")      # May find it depending on title/content
   ```

2. **Use `list_contexts` to verify tags**
   ```python
   # List all contexts to see their tags
   all_contexts = list_contexts()
   for ctx in all_contexts["results"]:
       print(f"ID: {ctx['id']}, Tags: {ctx['tags']}")
   ```

#### Best Practices for Tags

1. **Use descriptive, searchable tags**
   ```python
   # ✅ Good
   tags=["rest-api", "authentication", "oauth2", "v2.1"]
   
   # ❌ Less useful
   tags=["a", "b", "c"]
   ```

2. **Establish consistent naming conventions**
   ```python
   # ✅ Consistent patterns
   tags=["type:api", "version:2.1", "status:stable"]
   tags=["lang:python", "framework:fastapi", "feature:auth"]
   ```

3. **Keep tags concise but meaningful**
   ```python
   # ✅ Balanced
   tags=["user-management", "crud-operations", "validation"]
   
   # ❌ Too verbose
   tags=["user-management-system-with-full-crud-operations"]
   ```

4. **Use tags for categorization and filtering**
   ```python
   # Store related contexts with consistent tags
   store_context(data="User API plan", tags=["api", "users", "v2"])
   store_context(data="Order API plan", tags=["api", "orders", "v2"])
   store_context(data="Payment API plan", tags=["api", "payments", "v2"])
   
   # Later search for all v2 API plan
   search_contexts("api v2")
   ```

## Performance

### Compression

- Uses zlib compression algorithm for optimal balance of speed and compression ratio
- Only compresses data larger than 1KB by default
- Typical compression ratios: 20-80% depending on data type
- Fallback to uncompressed storage if compression doesn't provide significant benefit

### Database

- SQLite with optimized indexes for fast searches
- Thread-safe operations with connection pooling
- Efficient storage of binary compressed data
- Automatic database schema creation and management

### Benchmarks

Typical performance on modern hardware:
- Store operation: ~1-5ms for small contexts, ~10-50ms for large contexts
- Retrieve operation: ~1-3ms
- Search operation: ~5-20ms depending on database size
- Compression: ~100MB/s for text data

## Troubleshooting

### Common Issues

#### Server Won't Start

**Problem**: `ModuleNotFoundError: No module named 'fastmcp'`
**Solution**: Install dependencies with `pip install -e .` or `uv sync`

**Problem**: `Permission denied` when creating database
**Solution**: Ensure write permissions in the current directory or set `CONTEXT_DB_PATH` to a writable location

#### MCP Client Connection Issues

**Problem**: Client can't connect to server
**Solution**: 
1. Verify the server is running: `uv run fastmcp run server.py`
2. Check the path in your MCP client configuration
3. Ensure Python environment has required dependencies
4. Make sure the `--directory` path in your MCP config points to the correct project directory

#### Database Issues

**Problem**: `database is locked` error
**Solution**: 
1. Close any other processes using the database
2. Restart the server
3. If persistent, delete `context_data.db` (will lose stored contexts)

#### Memory Issues

**Problem**: High memory usage with large contexts
**Solution**:
1. Set `MAX_CONTEXT_SIZE` environment variable to limit context size
2. Use pagination when listing many contexts
3. Regularly clean up unused contexts with `delete_context`

#### Performance Issues

**Problem**: Slow search operations
**Solution**:
1. Use more specific search queries
2. Limit search results with the `limit` parameter
3. Consider adding more specific tags for better filtering

**Problem**: Large database file size
**Solution**:
1. Regularly delete unused contexts
2. The compression is working - uncompressed data would be much larger
3. Consider archiving old contexts to separate database files

#### Tags Parameter Issues

**Problem**: `INVALID_TAGS_TYPE` error when storing or updating contexts
**Solution**:
1. Ensure tags parameter is None, a string, or a list of strings
2. Convert numbers to strings: use `["1", "2"]` instead of `[1, 2]`
3. Check your MCP client's array serialization format
4. See the "Tags Parameter Validation" section above for detailed examples

**Problem**: Tags not appearing in stored contexts
**Solution**:
1. Verify the tags parameter format matches expected types
2. Check that your MCP client properly serializes string arrays
3. Use `retrieve_context` to verify tags were stored correctly
4. Ensure tags don't contain only whitespace or empty strings

**Problem**: Single string tag not working as expected
**Solution**:
1. Single strings are automatically converted to single-item lists
2. `tags="important"` becomes `tags=["important"]` internally
3. This is normal behavior - verify with `retrieve_context` if needed

## FAQ

### General Questions

**Q: What types of data work best with this server?**
A: Text-based data compresses best (documentation, code, conversations). Binary data or already-compressed data won't see significant compression benefits.

**Q: Is there a limit to how much data I can store?**
A: Individual contexts are limited to 10MB by default (configurable). The SQLite database can handle gigabytes of data, but performance may degrade with very large datasets.

**Q: Can multiple clients use the same server instance?**
A: Yes, the server is designed to handle concurrent requests safely. Each client can store and retrieve contexts independently.

**Q: What happens if the server crashes?**
A: All data is persisted in the SQLite database. Simply restart the server and all contexts will be available.

### Technical Questions

**Q: How does the compression work?**
A: The server uses Python's zlib library with default compression level. Data smaller than 1KB or that doesn't compress well (less than 20% reduction) is stored uncompressed.

**Q: Can I backup my contexts?**
A: Yes, simply copy the `context_data.db` file. You can also export contexts using the `list_contexts` and `retrieve_context` tools.

**Q: Is the data encrypted?**
A: No, data is stored compressed but not encrypted. If you need encryption, consider using database-level encryption or storing encrypted data in the contexts.

**Q: Can I run multiple server instances?**
A: Yes, but each instance should use a separate database file (set different `CONTEXT_DB_PATH` values).

### Integration Questions

**Q: How do I integrate this with my existing MCP setup?**
A: Add the server configuration to your MCP client's config file. The server works alongside other MCP servers.

**Q: Can I use this with non-Python MCP clients?**
A: Yes, MCP is language-agnostic. Any MCP-compatible client can use this server.

**Q: How do I migrate data from another context storage system?**
A: Use the `store_context` tool to import your existing data. You can write a simple script to batch import contexts.

**Q: How do tags work and what types are supported?**
A: Tags can be None, a single string, or a list of strings. Single strings are automatically converted to single-item lists. Tags help categorize and search contexts. See the "Tags Parameter Validation" section for detailed examples and troubleshooting.

## Development

### Running Tests

```bash
# Install development dependencies
uv sync --group dev

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Run specific test file
uv run pytest tests/test_context_manager.py

# Verify installation
uv run python test_installation.py
```

### Code Quality

```bash
# Format code
uv run black .

# Lint code
uv run ruff check .

# Type checking
uv run mypy src/
```

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/yourusername/context-compression-mcp/issues)
- Documentation: This README and inline code documentation
- MCP Protocol: [Model Context Protocol specification](https://modelcontextprotocol.io/)

## Changelog

### v0.1.0 (Initial Release)
- Basic context storage and retrieval
- zlib compression support
- SQLite database backend
- Six MCP tools: store, retrieve, search, list, delete, update
- Thread-safe operations
- Comprehensive test suite