# Shrimp Task Manager Integration

## Overview

Shrimp Task Manager provides comprehensive task management with AI-powered planning, execution tracking, and research capabilities.

## Core Commands

### Task Lifecycle
- **init**: Initialize project with Task Master
- **add**: Create new tasks with AI analysis
- **get**: Retrieve task details and status
- **status**: Update task completion status
- **expand**: Break tasks into detailed subtasks

### Advanced Features
- **analyze**: Assess task complexity and requirements
- **research**: AI-powered research for informed decisions
- **split**: Divide complex tasks into manageable parts
- **verify**: Validate task completion and quality

## MCP Tool Integration

### Core Tools (7 tools)
- `get_tasks`, `next_task`, `get_task`, `set_task_status`, `update_subtask`, `parse_prd`, `expand_task`

### Standard Tools (14 tools)
- Core + `initialize_project`, `analyze_project_complexity`, `expand_all`, `add_subtask`, `remove_task`, `add_task`, `complexity_report`

### All Tools (44+ tools)
- Standard + dependencies, tags, research, autopilot, scoping, models, rules

## Configuration

### Environment Variables
```bash
# API Keys (required for providers)
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
# ... other provider keys

# Endpoints
OLLAMA_BASE_URL=http://localhost:11434/api
AZURE_OPENAI_ENDPOINT=your_endpoint
```

### Project Configuration
- `.taskmaster/config.json`: Model settings, parameters, logging
- Managed via `task-master models --setup`

## Development Workflow Integration

### Task Creation
```bash
# AI-powered task creation
task-master add "Implement user authentication"

# Manual task with details
task-master add --description "Detailed requirements" \
                --details "Implementation steps" \
                "Task title"
```

### Task Management
```bash
# Get next actionable task
task-master next

# Update task status
task-master status 1 in-progress
task-master status 1 done

# Expand into subtasks
task-master expand 1
```

### Research Integration
```bash
# Research-backed task creation
task-master add --research "Implement OAuth2 authentication"

# Update task with research
task-master update 1 --research "Add research findings"
```

## Best Practices

### Task Planning
- Use `analyze_task` for complexity assessment
- Break large tasks with `split_tasks`
- Define clear acceptance criteria
- Set realistic time estimates

### Progress Tracking
- Update status regularly
- Use subtasks for detailed tracking
- Document blockers and dependencies
- Maintain task context

### Quality Assurance
- Use `verify_task` for completion validation
- Include testing requirements
- Document edge cases
- Review against acceptance criteria

## Integration Guidelines

### Development Process
1. **Planning**: Create tasks with detailed requirements
2. **Analysis**: Assess complexity and dependencies
3. **Execution**: Work through tasks systematically
4. **Verification**: Validate completion and quality

### Team Collaboration
- Share task visibility across team members
- Use consistent task naming conventions
- Document decisions and rationale
- Maintain task history for reference

## Troubleshooting

### Common Issues
- **MCP Connection**: Verify server status and configuration
- **Tool Availability**: Check tool tier settings
- **API Keys**: Ensure proper environment variables
- **File Permissions**: Confirm workspace access

### Performance
- Use appropriate tool tiers for needs
- Cache research results when possible
- Monitor token usage and costs
- Optimize task granularity

## Advanced Features

### Tag Management
- Organize tasks by context/tags
- Switch between different workstreams
- Maintain separate task spaces

### Autopilot Mode
- Automated task execution workflows
- Integration with CI/CD pipelines
- Batch processing capabilities

### Research Capabilities
- AI-powered information gathering
- Integration with multiple sources
- Context-aware research suggestions

## File Structure

```
.taskmaster/
├── config.json          # Configuration settings
├── tasks.json          # Task definitions
├── reports/            # Analysis reports
├── plan/              # Task planning documents
└── archives/          # Completed task history
```

## Command Reference

### Core Commands
- `task-master init`: Initialize project
- `task-master add [options] <description>`: Add task
- `task-master get <id>`: Get task details
- `task-master status <id> <status>`: Update status
- `task-master expand <id>`: Create subtasks

### Analysis Commands
- `task-master analyze <id>`: Analyze complexity
- `task-master research <query>`: Research topic
- `task-master verify <id>`: Validate completion

### Management Commands
- `task-master list`: List all tasks
- `task-master remove <id>`: Delete task
- `task-master update <id>`: Modify task

## Integration with Development Workflow

### Pre-commit Hooks
- Validate task completion
- Check acceptance criteria
- Update task status automatically

### CI/CD Integration
- Automated task progression
- Quality gate enforcement
- Deployment tracking

### Documentation
- Task-based documentation updates
- Change log generation
- Release notes automation

## Performance Optimization

### Tool Selection
- Use core tools for basic operations
- Standard tools for development workflows
- All tools for complex analysis

### Caching Strategy
- Cache research results
- Reuse analysis data
- Minimize redundant operations

### Resource Management
- Monitor API usage
- Optimize batch operations
- Balance automation with manual control