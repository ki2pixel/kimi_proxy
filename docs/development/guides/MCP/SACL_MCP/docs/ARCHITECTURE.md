# SACL Architecture Documentation

This document provides a comprehensive overview of the SACL MCP Server architecture, design decisions, and implementation details.

## Table of Contents

- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Relationship Analysis Pipeline](#relationship-analysis-pipeline)
- [MCP Integration](#mcp-integration)
- [Knowledge Graph Design](#knowledge-graph-design)
- [Performance Characteristics](#performance-characteristics)
- [Design Decisions](#design-decisions)

## System Overview

The SACL MCP Server implements a comprehensive bias-aware code retrieval system based on the SACL research framework, enhanced with relationship analysis and context-aware retrieval capabilities.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Assistants Layer                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Claude Code │  │   Cursor    │  │  Other MCP Clients  │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────┬───────────────────────────────────────────┘
                  │ MCP Protocol
┌─────────────────▼───────────────────────────────────────────┐
│                SACL MCP Server                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                MCP Handler Layer                        │ │
│  │  • Tool Definitions   • Request Routing   • Responses  │ │
│  └─────────────────────┬───────────────────────────────────┘ │
│  ┌─────────────────────▼───────────────────────────────────┐ │
│  │              SACL Processing Layer                      │ │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │ │
│  │  │    Bias     │ │  Semantic   │ │     Reranking       │ │ │
│  │  │  Detection  │ │ Augmenter   │ │  & Localization     │ │ │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘ │ │
│  └─────────────────────┬───────────────────────────────────┘ │
│  ┌─────────────────────▼───────────────────────────────────┐ │
│  │            Relationship Analysis Layer                  │ │
│  │  • Import/Export  • Function Calls  • Inheritance      │ │
│  │  • Dependencies   • Context Graph   • Traversal        │ │
│  └─────────────────────┬───────────────────────────────────┘ │
│  ┌─────────────────────▼───────────────────────────────────┐ │
│  │             Code Analysis Layer                         │ │
│  │  • AST Parsing    • Feature Extraction  • Multi-lang   │ │
│  │  • Structure      • Textual Features   • Relationships │ │
│  └─────────────────────┬───────────────────────────────────┘ │
└─────────────────────────┼───────────────────────────────────┘
                          │ Graphiti Client
┌─────────────────────────▼───────────────────────────────────┐
│              Knowledge Graph (Graphiti/Neo4j)              │
│  • Code Representations  • Semantic Features               │
│  • Bias Scores           • Relationship Graph              │
│  • Embeddings            • Context Metadata                │
└─────────────────────────────────────────────────────────────┘
```

## Component Architecture

### Core Components

#### 1. SACLProcessor (Orchestrator)

```typescript
class SACLProcessor {
  // Core SACL pipeline orchestration
  - biasDetector: TextualBiasDetector
  - semanticAugmenter: SemanticAugmenter  
  - reranker: SACLReranker
  - graphitiClient: GraphitiClient
  - codeAnalyzer: CodeAnalyzer
  
  // Main workflows
  + processRepository(): ProcessingStats
  + processFile(filePath): CodeRepresentation
  + queryCode(query): RetrievalResult[]
  + queryCodeWithContext(query): EnhancedRetrievalResult[]
  + updateFile(filePath, changeType): UpdateResponse
  + getRelatedComponents(filePath): RelatedComponent[]
}
```

**Responsibilities**:
- Pipeline orchestration
- File processing coordination
- Relationship storage management
- Query routing and result enhancement

#### 2. TextualBiasDetector

```typescript
class TextualBiasDetector {
  // Bias detection methods
  + detectBias(code): number
  + getBiasIndicators(code): BiasIndicator[]
  
  // Feature masking for bias analysis
  - calculateMaskedSimilarity(original, masked): number
  - extractTextualFeatures(code): Features
  - computeBiasScore(similarities): number
}
```

**Responsibilities**:
- Three-type bias detection (docstring, identifier, comment)
- Feature masking and comparison
- Bias scoring and indicators

#### 3. SemanticAugmenter

```typescript
class SemanticAugmenter {
  + augmentRepresentation(code): CodeRepresentation
  
  // LLM-powered analysis
  - generateFunctionalSignature(code): string
  - extractBehaviorPattern(code): string
  - createAugmentedEmbedding(code): number[]
}
```

**Responsibilities**:
- LLM-powered semantic enhancement
- Functional signature extraction
- Behavior pattern analysis
- Embedding augmentation

#### 4. SACLReranker

```typescript
class SACLReranker {
  // Basic reranking
  + rerank(results, query): RetrievalResult[]
  
  // Enhanced reranking with context
  + rerankWithContext(results, query): EnhancedRetrievalResult[]
  
  // Scoring components
  - calculateTextualSimilarity(code, query): number
  - combineScores(textual, semantic, functional, bias): number
  - generateContextExplanation(code, related): ContextExplanation
}
```

**Responsibilities**:
- Multi-score ranking combination
- Bias-aware score weighting
- Context explanation generation
- Result enhancement with relationships

#### 5. CodeAnalyzer

```typescript
class CodeAnalyzer {
  // Core analysis
  + analyzeFile(filePath): CodeRepresentation
  + findCodeFiles(repoPath): string[]
  
  // Feature extraction
  - extractTextualFeatures(content): TextualFeatures
  - extractStructuralFeatures(content): StructuralFeatures
  
  // Relationship extraction
  + extractRelationships(content, filePath): CodeRelationships
  - extractJavaScriptRelationships(content): void
  - extractPythonRelationships(content): void
  - extractGenericRelationships(content): void
}
```

**Responsibilities**:
- Multi-language code analysis
- AST parsing and feature extraction
- Relationship detection and mapping
- File discovery and filtering

### Relationship Analysis Components

#### 6. GraphitiClient

```typescript
class GraphitiClient {
  // Core storage
  + storeCodeRepresentation(code): void
  + searchCode(query): CodeRepresentation[]
  
  // Relationship management
  + storeRelationship(from, to, type, details): void
  + storeFileRelationships(filePath, relationships): void
  + getRelatedComponents(filePath, config): RelatedComponent[]
  + traverseRelationships(startFile, types, depth): GraphTraversalResult
  + deleteFileRelationships(filePath): void
}
```

**Responsibilities**:
- Knowledge graph interface
- Relationship storage and retrieval
- Graph traversal algorithms
- Namespace management

#### 7. MCP Server Layer

```typescript
class SACLMCPServer {
  // MCP protocol handling
  + listTools(): Tool[]
  + handleTool(name, args): MCPResponse
  
  // Tool handlers (9 tools)
  - handleAnalyzeRepository(args): MCPResponse
  - handleQueryCode(args): MCPResponse
  - handleQueryCodeWithContext(args): MCPResponse
  - handleUpdateFile(args): MCPResponse
  - handleUpdateFiles(args): MCPResponse
  - handleGetRelationships(args): MCPResponse
  - handleGetFileContext(args): MCPResponse
  - handleGetBiasAnalysis(args): MCPResponse
  - handleGetSystemStats(): MCPResponse
}
```

**Responsibilities**:
- MCP protocol implementation
- Tool definition and routing
- Response formatting
- Error handling

## Data Flow

### 1. Repository Analysis Flow

```
Repository Path
      │
      ▼
┌─────────────┐
│ File        │
│ Discovery   │ → CodeAnalyzer.findCodeFiles()
└─────┬───────┘
      │
      ▼
┌─────────────┐
│ File        │
│ Processing  │ → SACLProcessor.processFile()
└─────┬───────┘
      │
      ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Textual   │    │ Structural  │    │Relationship │
│  Features   │    │  Features   │    │ Extraction  │
└─────┬───────┘    └─────┬───────┘    └─────┬───────┘
      │                  │                  │
      ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────┐
│              Bias Detection                         │
│ • Docstring dependency • Identifier bias           │
│ • Comment over-reliance • Feature masking          │
└─────┬───────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│            Semantic Augmentation                    │
│ • LLM functional signature • Behavior patterns     │
│ • Augmented embeddings     • Bias adjustment       │
└─────┬───────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│           Knowledge Graph Storage                   │
│ • Code representation • Relationships              │
│ • Semantic features   • Bias scores                │
└─────────────────────────────────────────────────────┘
```

### 2. Query Processing Flow

```
User Query
    │
    ▼
┌─────────────┐
│   Query     │
│ Processing  │ → SACLProcessor.queryCodeWithContext()
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  Initial    │
│ Retrieval   │ → GraphitiClient.searchCode()
└─────┬───────┘
      │
      ▼
┌─────────────┐
│ Relationship│
│  Context    │ → GraphitiClient.getRelatedComponents()
└─────┬───────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│              SACL Reranking                         │
│ • Textual similarity  • Semantic similarity        │
│ • Functional relevance • Bias-aware weighting      │
└─────┬───────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│            Context Enhancement                      │
│ • Related components  • Dependency chains          │
│ • Relationship graphs • Context explanations       │
└─────┬───────────────────────────────────────────────┘
      │
      ▼
Enhanced Results with Context
```

### 3. File Update Flow

```
File Change Notification
         │
         ▼
┌─────────────┐
│  Validate   │
│ File Path   │ → SACLProcessor.validateFilePath()
└─────┬───────┘
      │
      ▼
┌─────────────┐
│  Process    │
│ File Change │ → SACLProcessor.updateFile()
└─────┬───────┘
      │
      ▼
┌─────────────┐    ┌─────────────┐
│  Re-analyze │    │  Update     │
│    File     │    │Relationships│
└─────┬───────┘    └─────┬───────┘
      │                  │
      ▼                  ▼
┌─────────────────────────────────┐
│      Update Knowledge Graph    │
│ • New code representation      │
│ • Updated relationships        │
│ • Invalidate related cache     │
└─────────────────────────────────┘
```

## Relationship Analysis Pipeline

### Relationship Types Hierarchy

```
CodeRelationships
├── ImportRelation[]
│   ├── from: string (importing file)
│   ├── to: string (imported module/file)
│   ├── symbols: string[] (imported symbols)
│   └── importType: 'default' | 'named' | 'namespace' | 'dynamic'
│
├── ExportRelation[]
│   ├── from: string (exporting file)
│   ├── symbol: string (exported symbol)
│   └── exportType: 'default' | 'named' | 'namespace'
│
├── CallRelation[]
│   ├── from: string (calling context)
│   ├── to: string (called function)
│   ├── object?: string (calling object)
│   └── callType: 'direct' | 'method' | 'constructor' | 'async'
│
├── InheritanceRelation[]
│   ├── from: string (child class)
│   ├── to: string (parent class/interface)
│   └── type: 'extends' | 'implements' | 'mixin'
│
└── DependencyRelation[]
    ├── from: string (dependent file)
    ├── to: string (dependency)
    ├── dependencyType: 'npm' | 'local' | 'builtin'
    └── usage: string[] (how it's used)
```

### Language-Specific Analysis

#### JavaScript/TypeScript (AST-based)

```typescript
// Import analysis
traverse(ast, {
  ImportDeclaration: (path) => {
    // Extract import information
    const importPath = path.node.source.value;
    const symbols = extractSymbols(path.node.specifiers);
    const importType = determineImportType(path.node.specifiers);
    
    relationships.imports.push({
      from: filePath,
      to: resolveImportPath(importPath, filePath),
      symbols,
      importType,
      lineNumber: path.node.loc?.start.line
    });
  }
});
```

#### Python (Regex-based)

```typescript
// Import statement matching
const importMatch = line.match(/^import\s+(.+)/);
if (importMatch) {
  const modules = importMatch[1].split(',').map(m => m.trim());
  modules.forEach(module => {
    relationships.imports.push({
      from: filePath,
      to: module,
      symbols: [module],
      importType: 'named',
      lineNumber: i + 1
    });
  });
}
```

#### Generic Languages (Pattern-based)

```typescript
// Generic import patterns
const importPatterns = [
  /^#include\s*[<"]([^>"]+)[>"]/, // C/C++
  /^import\s+([^;]+);/,           // Java
  /^using\s+([^;]+);/             // C#
];

for (const pattern of importPatterns) {
  const match = line.match(pattern);
  if (match) {
    relationships.dependencies.push({
      from: filePath,
      to: match[1],
      dependencyType: 'builtin',
      usage: ['include']
    });
  }
}
```

### Relationship Storage in Knowledge Graph

```cypher
// Example Cypher queries for relationship storage
CREATE (file:File {path: $filePath})
CREATE (dependency:File {path: $dependencyPath})
CREATE (file)-[:IMPORTS {
  symbols: $symbols,
  importType: $importType,
  lineNumber: $lineNumber
}]->(dependency)
```

### Graph Traversal Algorithms

#### Breadth-First Relationship Traversal

```typescript
async traverseRelationships(
  startFile: string,
  relationshipTypes: RelationshipType[],
  maxDepth: number
): Promise<GraphTraversalResult> {
  const visited = new Set<string>();
  const queue = [{ file: startFile, depth: 0 }];
  const relatedComponents: RelatedComponent[] = [];
  
  while (queue.length > 0 && queue[0].depth < maxDepth) {
    const { file, depth } = queue.shift()!;
    
    if (visited.has(file)) continue;
    visited.add(file);
    
    // Get direct relationships
    const relationships = await this.getDirectRelationships(file, relationshipTypes);
    
    for (const rel of relationships) {
      if (!visited.has(rel.to)) {
        queue.push({ file: rel.to, depth: depth + 1 });
        relatedComponents.push({
          filePath: rel.to,
          relationshipType: rel.type,
          distance: depth + 1,
          relevanceScore: this.calculateRelevanceScore(rel, depth)
        });
      }
    }
  }
  
  return {
    startNode: startFile,
    relatedComponents,
    traversalStats: {
      nodesVisited: visited.size,
      edgesTraversed: relatedComponents.length,
      maxDepthReached: Math.max(...relatedComponents.map(c => c.distance))
    }
  };
}
```

## MCP Integration

### Protocol Implementation

The SACL server implements the Model Context Protocol (MCP) specification:

```typescript
// Tool definition structure
interface Tool {
  name: string;
  description: string;
  inputSchema: JSONSchema;
}

// Request/Response pattern
interface MCPRequest {
  method: 'tools/call';
  params: {
    name: string;
    arguments: any;
  };
}

interface MCPResponse {
  content: Array<{
    type: 'text';
    text: string;
  }>;
}
```

### Tool Architecture

```
MCP Client Request
        │
        ▼
┌─────────────┐
│   Request   │
│  Validation │ → JSON Schema validation
└─────┬───────┘
        │
        ▼
┌─────────────┐
│   Tool      │
│   Routing   │ → Route to appropriate handler
└─────┬───────┘
        │
        ▼
┌─────────────┐
│  Business   │
│   Logic     │ → SACL processing
└─────┬───────┘
        │
        ▼
┌─────────────┐
│  Response   │
│ Formatting  │ → Convert to MCP format
└─────┬───────┘
        │
        ▼
MCP Client Response
```

### Error Handling Strategy

```typescript
// Centralized error handling
try {
  const result = await this.saclProcessor.processRequest(args);
  return this.formatSuccessResponse(result);
} catch (error) {
  if (error instanceof ValidationError) {
    return this.formatValidationError(error);
  } else if (error instanceof FileNotFoundError) {
    return this.formatFileNotFoundError(error);
  } else {
    return this.formatGenericError(error);
  }
}
```

## Knowledge Graph Design

### Node Types

```typescript
// File nodes
{
  type: 'File',
  properties: {
    path: string,
    biasScore: number,
    lastModified: Date,
    complexity: number,
    size: number
  }
}

// Component nodes
{
  type: 'Function' | 'Class' | 'Interface',
  properties: {
    name: string,
    filePath: string,
    startLine: number,
    endLine: number,
    complexity: number
  }
}
```

### Edge Types

```typescript
// Relationship edges
{
  type: 'IMPORTS' | 'EXPORTS' | 'CALLS' | 'EXTENDS' | 'IMPLEMENTS',
  properties: {
    symbols?: string[],
    lineNumber?: number,
    weight: number,
    strength: number
  }
}
```

### Graph Queries

```cypher
// Find related components
MATCH (start:File {path: $filePath})-[r:IMPORTS|CALLS|EXTENDS*1..3]-(related:File)
WHERE r.weight > $minWeight
RETURN related, r, length(path) as distance
ORDER BY r.weight DESC
LIMIT $maxResults

// Analyze dependency chains
MATCH path = (start:File {path: $filePath})-[:IMPORTS*]-(end:File)
WHERE length(path) <= $maxDepth
RETURN path, length(path) as depth
ORDER BY depth ASC
```

## Performance Characteristics

### Processing Performance

| Operation | Small Repo (<100 files) | Medium Repo (100-1000 files) | Large Repo (>1000 files) |
|-----------|-------------------------|-------------------------------|---------------------------|
| Initial Analysis | 10-30 seconds | 2-5 minutes | 10-30 minutes |
| Single File Update | <1 second | 1-3 seconds | 2-5 seconds |
| Batch Update (10 files) | 2-5 seconds | 5-15 seconds | 15-30 seconds |
| Basic Query | <500ms | 500ms-1s | 1-2 seconds |
| Context Query | 1-2 seconds | 2-5 seconds | 5-10 seconds |
| Relationship Traversal | <500ms | 500ms-2s | 1-5 seconds |

### Memory Usage

```typescript
// Estimated memory usage per file
const memoryPerFile = {
  codeRepresentation: 50, // KB
  relationships: 20,      // KB
  embeddings: 1.5,        // KB (384-dim float32)
  cache: 30               // KB
};

// Total memory = files * memoryPerFile + overhead
const estimatedMemory = fileCount * 101.5 / 1024; // MB
```

### Optimization Strategies

#### 1. Caching Strategy

```typescript
// Multi-level caching
class CacheManager {
  private memoryCache: Map<string, CodeRepresentation>;
  private diskCache: FileSystemCache;
  private embeddingCache: Map<string, number[]>;
  
  async get(key: string): Promise<CodeRepresentation | null> {
    // L1: Memory cache
    if (this.memoryCache.has(key)) {
      return this.memoryCache.get(key);
    }
    
    // L2: Disk cache
    const cached = await this.diskCache.get(key);
    if (cached && this.isValid(cached)) {
      this.memoryCache.set(key, cached);
      return cached;
    }
    
    return null;
  }
}
```

#### 2. Lazy Loading

```typescript
// Relationship lazy loading
class RelationshipManager {
  async getRelatedComponents(
    filePath: string,
    depth: number = 1
  ): Promise<RelatedComponent[]> {
    // Load relationships on-demand
    const cached = this.relationshipCache.get(filePath);
    if (cached && cached.depth >= depth) {
      return cached.components.filter(c => c.distance <= depth);
    }
    
    // Fetch additional depth if needed
    return await this.fetchRelationships(filePath, depth);
  }
}
```

#### 3. Batch Processing

```typescript
// Efficient batch updates
async updateFiles(files: FileUpdate[]): Promise<BatchUpdateResponse> {
  // Group by operation type
  const grouped = this.groupByChangeType(files);
  
  // Process in parallel batches
  const results = await Promise.allSettled([
    this.processModified(grouped.modified),
    this.processCreated(grouped.created),
    this.processDeleted(grouped.deleted)
  ]);
  
  return this.combineBatchResults(results);
}
```

## Design Decisions

### 1. Architecture Choices

#### Agent-Controlled Updates vs File Watching

**Decision**: Implement explicit agent-controlled updates
**Rationale**: 
- Docker compatibility (file watching unreliable in containers)
- Explicit control over when analysis occurs
- Better performance (no continuous monitoring)
- Clearer integration with AI assistants

#### AST vs Regex Analysis

**Decision**: Use AST for JavaScript/TypeScript, regex for others
**Rationale**:
- AST provides accurate relationship extraction for primary languages
- Regex sufficient for basic pattern matching in other languages
- Performance balance between accuracy and speed
- Extensible architecture for adding full AST support

#### Graphiti vs Direct Neo4j

**Decision**: Use Graphiti client wrapper
**Rationale**:
- Higher-level abstraction for knowledge graph operations
- Built-in support for semantic search and embeddings
- Easier relationship modeling and traversal
- Future-proof for advanced graph analytics

### 2. Performance Trade-offs

#### Full Repository vs Incremental Analysis

**Decision**: Support both with incremental as default
**Rationale**:
- Full analysis ensures consistency
- Incremental analysis improves performance
- User choice based on requirements
- Maintains system responsiveness

#### Context Depth vs Performance

**Decision**: Default 3-level traversal with configurable depth
**Rationale**:
- 3 levels provide good context coverage
- Exponential complexity beyond 3 levels
- User control for specific use cases
- Performance acceptable for most codebases

### 3. Integration Design

#### MCP vs REST API

**Decision**: Primary MCP integration with optional HTTP endpoints
**Rationale**:
- Direct integration with AI assistants
- Standardized protocol for AI tools
- Better context and session management
- Future compatibility with MCP ecosystem

#### Single vs Multiple Namespaces

**Decision**: Single namespace per repository with explicit configuration
**Rationale**:
- Simpler deployment and management
- Clear isolation between projects
- Easier caching and optimization
- Reduced complexity for users

### 4. Data Modeling

#### Embedded vs Separate Relationship Storage

**Decision**: Store relationships in knowledge graph alongside code representations
**Rationale**:
- Unified query interface
- Efficient graph traversal
- Consistent data model
- Leverage Neo4j relationship capabilities

#### Synchronous vs Asynchronous Processing

**Decision**: Asynchronous processing with progress indicators
**Rationale**:
- Better user experience for large repositories
- Non-blocking operations
- Scalable architecture
- Error handling and recovery

---

**SACL Architecture** - Comprehensive system design for bias-aware code analysis and retrieval.