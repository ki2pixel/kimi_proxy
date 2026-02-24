---
paths:
  - "**/*"
---

# Skills Integration

## Overview

This document outlines the integration and routing matrix for Kimi Proxy development skills based on pattern matching and priority hierarchy.

## Skill Detection Matrix

### Pattern-Based Activation

Skills are automatically activated based on request content analysis:

| Skill | Trigger Patterns | Priority |
|-------|------------------|----------|
| **debugging-strategies** | "debug", "bug", "error", "fix", "issue", "problem", "troubleshoot" | High |
| **documentation** | "docs", "readme", "guide", "write", "document", "api" | Medium |
| **kimi-proxy-config-manager** | "config", "toml", "provider", "api key", "routing" | High |
| **kimi-proxy-frontend-architecture** | "frontend", "ui", "dashboard", "websocket", "chart.js" | High |
| **kimi-proxy-mcp-integration** | "mcp", "server", "memory", "semantic", "qdrant" | High |
| **kimi-proxy-performance-optimization** | "performance", "optimize", "speed", "latency", "cache" | Medium |
| **kimi-proxy-streaming-debug** | "streaming", "timeout", "readerror", "sse", "connection" | High |
| **kimi-proxy-testing-strategies** | "test", "pytest", "unit", "integration", "e2e" | Medium |
| **shrimp-task-manager** | "task", "plan", "manage", "subtask", "workflow" | Medium |
| **sequentialthinking-logic** | "architecture", "design", "logic", "extension", "complex" | Medium |
| **fast-filesystem-ops** | "file", "directory", "read", "write", "filesystem" | Low |
| **json-query-expert** | "json", "query", "extract", "data", "parse" | Low |

### Context-Aware Routing

Skills activate based on:
1. **Explicit Mentions**: Direct skill name references
2. **Content Analysis**: Keywords and phrases in requests
3. **File Context**: Currently open files and their types
4. **Project Structure**: Relevant directories and components

## Priority Hierarchy

### High Priority (Core Functionality)
- **debugging-strategies**: Critical for issue resolution
- **kimi-proxy-* skills**: Domain-specific expertise
- **config-manager**: Essential for setup and configuration

### Medium Priority (Development Workflow)
- **documentation**: Content creation and maintenance
- **performance-optimization**: Ongoing improvement
- **testing-strategies**: Quality assurance
- **task-manager**: Project organization

### Low Priority (Utility)
- **filesystem-ops**: General file operations
- **json-query-expert**: Data manipulation

## Activation Rules

### Single Skill Focus
- **Primary Skill**: Highest priority match gets full context
- **Supporting Skills**: Lower priority skills load metadata only
- **Conflict Resolution**: Explicit mentions override pattern matching

### Context Preservation
- **Skill State**: Maintain activation state across related requests
- **Context Carryover**: Transfer relevant information between skills
- **Memory Integration**: Link with memory bank for continuity

## Integration Guidelines

### Skill Dependencies
- **MCP Integration**: Requires active MCP server connections
- **File System**: Depends on fast-filesystem operations
- **Memory Bank**: Integrates with activeContext tracking

### Performance Considerations
- **Lazy Loading**: Skills load only when triggered
- **Context Limits**: Respect token limits and context windows
- **Caching**: Cache skill metadata for faster activation

## Troubleshooting

### Common Issues
- **Skill Not Activating**: Check pattern matching and priority
- **Context Overload**: Reduce concurrent skill activation
- **MCP Connection**: Verify server connectivity
- **File Access**: Confirm workspace permissions

### Debug Commands
- **Skill Status**: Check active skills and their state
- **Pattern Matching**: Test trigger pattern recognition
- **Context Analysis**: Review current context and triggers

## Best Practices

### Skill Usage
- **Targeted Requests**: Be specific about requirements
- **Context Awareness**: Reference relevant files and components
- **Progressive Disclosure**: Start general, then specialize

### Maintenance
- **Pattern Updates**: Regularly review and update trigger patterns
- **Priority Tuning**: Adjust priorities based on usage patterns
- **Documentation**: Keep skill documentation current

## Future Enhancements

### Planned Improvements
- **Machine Learning**: AI-powered skill recommendation
- **Dynamic Routing**: Context-aware skill combinations
- **Performance Metrics**: Track skill effectiveness and usage
- **User Customization**: Allow custom skill priorities and patterns