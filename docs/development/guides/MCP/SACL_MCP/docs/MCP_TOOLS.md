# SACL MCP Tools Documentation

This document provides comprehensive documentation for all MCP tools available in the SACL server.

## Overview

The SACL MCP Server provides 9 tools for bias-aware code analysis and retrieval:

- **Core Tools**: Repository analysis, code querying, bias analysis, system stats
- **Relationship Tools**: Relationship analysis, file context, enhanced querying
- **Update Tools**: Single file and batch file updates

## Tool Reference

### 1. `analyze_repository`

Performs comprehensive SACL analysis of an entire repository.

**Purpose**: Initial repository processing with bias detection, semantic augmentation, and relationship extraction.

**Parameters**:
```typescript
{
  repositoryPath: string;     // Path to repository
  incremental?: boolean;      // Default: false (full scan)
}
```

**Example Usage**:
```json
{
  "repositoryPath": "/path/to/my-project",
  "incremental": false
}
```

**Response**:
- Processing statistics (files processed, bias detected, processing time)
- SACL framework status
- Knowledge graph population confirmation

**Use Cases**:
- Initial project setup
- Full repository reanalysis
- After major refactoring

---

### 2. `query_code`

Basic bias-aware code search with optional relationship context.

**Purpose**: Search for code using SACL's bias-aware ranking system.

**Parameters**:
```typescript
{
  query: string;              // Natural language query
  repositoryPath: string;     // Repository to search
  maxResults?: number;        // Default: 10
  includeContext?: boolean;   // Default: false
}
```

**Example Usage**:
```json
{
  "query": "function that validates user input",
  "repositoryPath": "/path/to/project",
  "maxResults": 5,
  "includeContext": true
}
```

**Response**:
- Ranked code results with bias scores
- SACL scoring breakdown (textual, semantic, functional)
- Code localization (relevant segments)
- Ranking explanations

**Use Cases**:
- Quick code search
- Finding similar functionality
- Understanding bias impact on results

---

### 3. `query_code_with_context` 🆕

Enhanced search with full relationship context and related components.

**Purpose**: Comprehensive code search with dependency analysis and related component discovery.

**Parameters**:
```typescript
{
  query: string;              // Natural language query
  repositoryPath: string;     // Repository to search
  maxResults?: number;        // Default: 10
  includeRelated?: boolean;   // Default: true
}
```

**Example Usage**:
```json
{
  "query": "authentication middleware",
  "repositoryPath": "/path/to/api",
  "maxResults": 8,
  "includeRelated": true
}
```

**Response**:
- Enhanced results with relationship context
- Related components for each result
- Dependency chains
- Context explanations with relationship importance
- Relationship graphs

**Use Cases**:
- Understanding component relationships
- Finding related functionality
- Comprehensive codebase exploration

---

### 4. `update_file` 🆕

Explicitly update analysis for a single file when changes are made.

**Purpose**: Agent-controlled file updates for Docker compatibility (replaces file watching).

**Parameters**:
```typescript
{
  filePath: string;           // Path to changed file
  changeType: "created" | "modified" | "deleted";
}
```

**Example Usage**:
```json
{
  "filePath": "src/services/UserService.js",
  "changeType": "modified"
}
```

**Response**:
- Update status and success/failure
- New bias score (if applicable)
- Relationship extraction confirmation
- Knowledge graph update status

**Use Cases**:
- After code modifications
- When AI assistants change files
- Maintaining analysis freshness

---

### 5. `update_files` 🆕

Batch update analysis for multiple files efficiently.

**Purpose**: Process multiple file changes in a single operation.

**Parameters**:
```typescript
{
  files: Array<{
    filePath: string;
    changeType: "created" | "modified" | "deleted";
  }>;
}
```

**Example Usage**:
```json
{
  "files": [
    { "filePath": "src/index.js", "changeType": "modified" },
    { "filePath": "src/utils/helpers.js", "changeType": "created" },
    { "filePath": "src/old/deprecated.js", "changeType": "deleted" }
  ]
}
```

**Response**:
- Batch operation summary
- Individual file results
- Success/failure counts
- Overall analysis status

**Use Cases**:
- After major refactoring
- Bulk file operations
- Efficient batch processing

---

### 6. `get_relationships` 🆕

Analyze code relationships and dependencies for a specific file.

**Purpose**: Explore how a file relates to other components in the codebase.

**Parameters**:
```typescript
{
  filePath: string;           // File to analyze
  maxDepth?: number;          // Default: 3
  relationshipTypes?: string[]; // Optional filter
}
```

**Supported Relationship Types**:
- `imports` - Import statements
- `exports` - Export statements  
- `calls` - Function calls
- `extends` - Class inheritance
- `implements` - Interface implementation
- `uses` - Composition/usage
- `depends_on` - Dependencies

**Example Usage**:
```json
{
  "filePath": "src/controllers/UserController.js",
  "maxDepth": 2,
  "relationshipTypes": ["imports", "calls", "extends"]
}
```

**Response**:
- Relationship breakdown by type
- Related components with relevance scores
- Traversal statistics (nodes visited, edges traversed)
- Relationship visualization data

**Use Cases**:
- Understanding component dependencies
- Impact analysis before changes
- Architecture exploration

---

### 7. `get_file_context` 🆕

Get comprehensive context and environment for a specific file.

**Purpose**: Understand a file's role and relationships within the codebase.

**Parameters**:
```typescript
{
  filePath: string;           // File to analyze
  includeSnippets?: boolean;  // Default: false
}
```

**Example Usage**:
```json
{
  "filePath": "src/models/User.js",
  "includeSnippets": true
}
```

**Response**:
- Context summary and component breakdown
- Relationships grouped by type
- Usage recommendations
- Code snippets (if requested)
- Dependency analysis

**Use Cases**:
- Onboarding new developers
- Understanding unfamiliar code
- Refactoring preparation

---

### 8. `get_bias_analysis`

Detailed bias metrics and analysis for debugging SACL decisions.

**Purpose**: Understand how bias detection affects code retrieval.

**Parameters**:
```typescript
{
  filePath?: string;          // Optional: specific file analysis
}
```

**Example Usage**:
```json
{
  "filePath": "src/algorithms/quicksort.js"
}
```

**Response**:
- File-specific bias metrics (if filePath provided)
- Repository-wide bias distribution
- Bias indicators and explanations
- Improvement suggestions

**Use Cases**:
- Debugging poor search results
- Understanding bias patterns
- Code quality improvement

---

### 9. `get_system_stats`

System performance, configuration, and operational statistics.

**Purpose**: Monitor SACL system health and configuration.

**Parameters**:
```typescript
{}  // No parameters required
```

**Example Usage**:
```json
{}
```

**Response**:
- Repository processing statistics
- Knowledge graph metrics
- System configuration
- Framework status
- Available tools list

**Use Cases**:
- System monitoring
- Performance analysis
- Configuration verification

## Usage Patterns

### Initial Setup Workflow

1. **Repository Analysis**:
   ```
   analyze_repository → Full SACL processing → Knowledge graph ready
   ```

2. **Code Exploration**:
   ```
   query_code_with_context → Enhanced results with relationships
   ```

3. **File Investigation**:
   ```
   get_file_context → Understand component role and dependencies
   ```

### Development Workflow

1. **Code Modification**:
   ```
   AI modifies files → update_file/update_files → Analysis updated
   ```

2. **Impact Analysis**:
   ```
   get_relationships → Understand change impact → Related components
   ```

3. **Quality Check**:
   ```
   get_bias_analysis → Review bias patterns → Improvement opportunities
   ```

### Debugging Workflow

1. **Poor Search Results**:
   ```
   get_bias_analysis → Understand bias impact → query_code with context
   ```

2. **System Issues**:
   ```
   get_system_stats → Check system health → Verify configuration
   ```

## Best Practices

### Performance Optimization

- Use `update_file` for single changes rather than full reanalysis
- Set appropriate `maxDepth` for relationship traversal
- Filter `relationshipTypes` when specific relationships are needed
- Use `includeContext: false` for faster basic queries

### Effective Querying

- Use specific functional terms rather than implementation details
- Try both `query_code` and `query_code_with_context` for different perspectives
- Check bias analysis if results seem unexpected
- Explore relationships to understand why certain results appear

### Maintenance

- Run `analyze_repository` periodically for full consistency
- Monitor `get_system_stats` for performance trends
- Use batch `update_files` for efficient bulk operations
- Review bias patterns regularly for codebase improvement

## Error Handling

All tools provide clear error messages and status indicators:

- **Success**: Operation completed successfully
- **Partial Success**: Some operations failed (batch updates)
- **Failure**: Operation failed with detailed error message
- **Not Found**: File or repository not found
- **Invalid Input**: Parameter validation errors

## Integration Examples

### Claude Code Integration

```typescript
// Query with context
const results = await claude.useTool("query_code_with_context", {
  query: "user authentication logic",
  repositoryPath: workspace.rootPath,
  maxResults: 5
});

// Update after modification
await claude.useTool("update_file", {
  filePath: "src/auth/middleware.js",
  changeType: "modified"
});
```

### Cursor Integration

```typescript
// Explore file relationships
const context = await cursor.mcp.call("get_file_context", {
  filePath: currentFile.path,
  includeSnippets: true
});

// Batch update after refactoring
await cursor.mcp.call("update_files", {
  files: modifiedFiles.map(f => ({
    filePath: f.path,
    changeType: f.changeType
  }))
});
```

---

**SACL MCP Tools** - Comprehensive bias-aware code analysis and retrieval for AI coding assistants.