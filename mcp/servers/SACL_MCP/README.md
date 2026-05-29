# SACL MCP Server

**Semantic-Augmented Reranking and Localization for Code Retrieval**

A Model Context Protocol (MCP) server that implements the SACL research framework to provide bias-aware code retrieval for AI coding assistants like Claude Code, Cursor, and other MCP-enabled tools.

## 🎯 Overview

SACL addresses the critical problem of **textual bias** in code retrieval systems. Traditional systems over-rely on surface-level features like docstrings, comments, and variable names, leading to biased results that favor well-documented code regardless of functional relevance.

### Key Features

- **🧠 Bias Detection**: Identifies over-reliance on textual features
- **🔍 Semantic Augmentation**: Enriches code understanding beyond surface text
- **📊 Intelligent Reranking**: Prioritizes functional relevance over documentation
- **🎯 Code Localization**: Pinpoints functionally relevant code segments
- **🔗 Relationship Analysis**: Maps code dependencies and relationships
- **🎨 Context-Aware Retrieval**: Returns results with related components
- **🚀 Agent-Controlled Updates**: Explicit file updates for Docker compatibility
- **🗄️ Knowledge Graph**: Persistent semantic storage with Graphiti/Neo4j
- **🔧 MCP Integration**: Works with Claude Code, Cursor, and other AI tools

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Assistant  │────│  SACL MCP Server │────│   Graphiti/Neo4j │
│ (Claude, Cursor)│    │                 │    │  Knowledge Graph │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                    ┌─────────────────┐
                    │  SACL Framework │
                    │                 │
                    │ • Bias Detection│
                    │ • Semantic Aug. │
                    │ • Reranking     │
                    │ • Localization  │
                    │ • Relationships │
                    │ • Context-Aware │
                    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Neo4j database
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd sacl

# Install dependencies
npm install

# Copy environment configuration
cp .env.example .env

# Edit .env with your settings
OPENAI_API_KEY=your_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Using Docker (Recommended)

```bash
# Start Neo4j and SACL server
docker-compose up -d

# Check logs
docker-compose logs -f sacl-mcp-server
```

### Manual Setup

```bash
# Build the project
npm run build

# Start the server
npm start
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `SACL_REPO_PATH` | Repository to analyze | Current directory |
| `SACL_NAMESPACE` | Unique namespace | Auto-generated |
| `SACL_LLM_MODEL` | LLM model for analysis | `gpt-4` |
| `SACL_EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `SACL_BIAS_THRESHOLD` | Bias detection sensitivity (0-1) | `0.5` |
| `SACL_MAX_RESULTS` | Maximum search results | `10` |
| `SACL_CACHE_ENABLED` | Enable embedding cache | `true` |
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |

## 🎮 Usage

### MCP Tools

The SACL server provides comprehensive MCP tools for bias-aware code analysis:

#### 1. `analyze_repository`
Performs full SACL analysis of a repository:

```json
{
  "repositoryPath": "/path/to/repo",
  "incremental": false
}
```

#### 2. `query_code`
Bias-aware code search with optional context:

```json
{
  "query": "function that sorts arrays efficiently",
  "repositoryPath": "/path/to/repo",
  "maxResults": 10,
  "includeContext": false  // Set true for relationship context
}
```

#### 3. `query_code_with_context` 🆕
Enhanced search with relationship context and related components:

```json
{
  "query": "authentication middleware",
  "repositoryPath": "/path/to/repo",
  "maxResults": 10,
  "includeRelated": true
}
```

#### 4. `update_file` 🆕
Explicitly update single file analysis when changes are made:

```json
{
  "filePath": "src/services/auth.js",
  "changeType": "modified"  // "created", "modified", or "deleted"
}
```

#### 5. `update_files` 🆕
Batch update multiple files:

```json
{
  "files": [
    { "filePath": "src/index.js", "changeType": "modified" },
    { "filePath": "src/utils/new.js", "changeType": "created" }
  ]
}
```

#### 6. `get_relationships` 🆕
Analyze code relationships and dependencies:

```json
{
  "filePath": "src/controllers/UserController.js",
  "maxDepth": 3,
  "relationshipTypes": ["imports", "calls", "extends"]  // Optional filter
}
```

#### 7. `get_file_context` 🆕
Get comprehensive context for a file:

```json
{
  "filePath": "src/models/User.js",
  "includeSnippets": true  // Include code previews
}
```

#### 8. `get_bias_analysis`
Detailed bias metrics and debugging:

```json
{
  "filePath": "src/utils/sort.js"  // Optional
}
```

#### 9. `get_system_stats`
System performance and statistics:

```json
{}
```

### MCP Client Configuration

#### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sacl": {
      "command": "node",
      "args": ["/path/to/sacl/dist/index.js"],
      "env": {
        "OPENAI_API_KEY": "your-key",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password"
      }
    }
  }
}
```

#### Cursor IDE

Configure in your Cursor settings to connect to the SACL MCP server.

## 📊 SACL Framework

### Stage 1: Bias Detection

Identifies three types of textual bias:

- **Docstring Dependency**: Over-reliance on documentation
- **Identifier Name Bias**: Focusing on variable/function names
- **Comment Over-reliance**: Prioritizing commented code

### Stage 2: Semantic Augmentation

Enriches code representations with:

- **Functional Signatures**: What the code actually does
- **Behavior Patterns**: Computational patterns (iteration, recursion, etc.)
- **Structural Features**: Complexity metrics, AST analysis
- **Augmented Embeddings**: Bias-adjusted semantic vectors

### Stage 3: Reranking & Localization

- **Bias-Aware Ranking**: Reduces textual weight based on bias score
- **Code Localization**: Identifies functionally relevant segments
- **Semantic Similarity**: Uses augmented embeddings
- **Functional Relevance**: Considers computational patterns

### Stage 4: Relationship Analysis 🆕

Maps code relationships and dependencies:

- **Import/Export Analysis**: Module dependencies and exports
- **Function Call Mapping**: Call graphs and method invocations
- **Class Inheritance**: Extends/implements relationships
- **Dependency Tracking**: External and internal dependencies
- **Context-Aware Results**: Related components with each query result

## 🧪 Example Workflow

1. **Repository Analysis**:
   ```
   AI Assistant → analyze_repository → SACL processes all files → Knowledge graph populated
   ```

2. **Code Query with Context**:
   ```
   AI Assistant → query_code_with_context("authentication") → SACL retrieval → Context-aware results
   ```

3. **File Updates**:
   ```
   AI modifies code → update_file("src/auth.js", "modified") → SACL re-analyzes → Relationships updated
   ```

4. **Relationship Exploration**:
   ```
   AI Assistant → get_relationships("UserController.js") → Dependency graph → Related components
   ```

5. **Results Include**:
   - Original textual similarity score
   - Semantic similarity score  
   - Bias-adjusted final score
   - Localized code regions
   - Related components and dependencies
   - Context explanation with relationship importance
   - Explanation of ranking decisions

## 📈 Performance

Based on SACL research benchmarks:

- **12.8%** improvement in Recall@1 on HumanEval
- **9.4%** improvement on MBPP
- **7.0%** improvement on SWE-Bench-Lite
- **P95 latency**: <300ms for retrieval operations

## 🔍 Bias Analysis Example

```
🧠 SACL Bias Analysis

File: src/algorithms/quicksort.js

Bias Metrics:
• Overall Bias Score: 73.2% 🔴
• Semantic Pattern: Recursive divide-and-conquer sorting
• Functional Signature: Array input → sorted array output

Bias Indicators:
• docstring_dependency: High docstring dependency (15.3% of code)
• identifier_name_bias: High reliance on descriptive names
• comment_over_reliance: Excessive comments (18.7% of code)

💡 Improvement Suggestions:
• Reduce reliance on variable naming for semantic understanding
• Focus on structural patterns over comments
• Improve functional signature extraction
```

## 🛠️ Development

### Project Structure

```
src/
├── core/                    # SACL framework implementation
│   ├── BiasDetector.ts      # Textual bias detection
│   ├── SemanticAugmenter.ts # Semantic enhancement
│   ├── SACLReranker.ts      # Reranking and localization with context
│   └── SACLProcessor.ts     # Main orchestrator with relationship support
├── mcp/                     # MCP server implementation
│   └── SACLMCPServer.ts     # MCP protocol handlers (9 tools)
├── graphiti/                # Knowledge graph integration
│   └── GraphitiClient.ts    # Graphiti/Neo4j interface with relationships
├── utils/                   # Utility modules
│   └── CodeAnalyzer.ts      # AST analysis and relationship extraction
├── types/                   # TypeScript type definitions
│   ├── index.ts             # Core types and interfaces
│   └── relationships.ts     # Relationship type definitions
└── index.ts                 # Application entry point
```

### Building

```bash
npm run build    # Build TypeScript
npm run dev      # Development with auto-reload
npm run lint     # Code linting
npm run format   # Code formatting
npm test         # Run tests
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes following SACL methodology
4. Add tests for new functionality
5. Submit a pull request

## 📚 Research Background

This implementation is based on the research paper:

**"SACL: Understanding and Combating Textual Bias in Code Retrieval with Semantic-Augmented Reranking and Localization"**
- Authors: Dhruv Gupta, Gayathri Ganesh Lakshmy, Yiqing Xie
- arXiv: 2506.20081v2

### Key Research Contributions

1. **Systematic Bias Detection**: Identifies textual bias through feature masking
2. **Semantic Augmentation**: Enhances code understanding beyond text
3. **Bias-Aware Ranking**: Reduces surface-level feature dependency
4. **Localization**: Pinpoints functionally relevant code regions

## 🔗 Integration

### Supported AI Tools

- **Claude Code**: Direct MCP integration
- **Cursor**: MCP server connection
- **VS Code Extensions**: Via MCP protocol
- **Custom Tools**: Any MCP-compatible client

### Language Support

- **JavaScript/TypeScript**: Full AST analysis with relationship extraction
  - Import/export tracking
  - Function call analysis
  - Class inheritance detection
  - Dynamic imports support
  
- **Python**: Regex-based analysis
  - Import statement parsing
  - Class inheritance detection
  - Function call patterns
  
- **Other Languages** (Java, C++, C#, Go, Rust): Basic analysis
  - Import/include statements
  - Class declarations
  - Function definitions
  
- **Extensible**: Easy to add new language analyzers

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- **Issues**: GitHub Issues
- **Documentation**: See `/docs` directory
- **Research Paper**: [arXiv:2506.20081v2](https://arxiv.org/abs/2506.20081v2)

## 🔮 Future Enhancements

- [ ] Multi-language AST parsing for all supported languages
- [ ] Real-time Graphiti integration (currently uses mock methods)
- [ ] Semantic relationship detection beyond syntactic analysis
- [ ] Visual relationship graphs in MCP responses
- [ ] Custom bias threshold configuration per project
- [ ] Integration with Language Server Protocol (LSP)
- [ ] Advanced localization algorithms with machine learning
- [ ] Performance optimizations for large codebases (>10k files)
- [ ] Real-time bias notifications during code writing
- [ ] Custom relationship type definitions

---

**SACL MCP Server** - Bringing research-backed bias-aware code retrieval to AI coding assistants.