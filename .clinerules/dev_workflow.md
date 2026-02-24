---
paths:
  - "**/*"
---

# Development Workflow

## Overview

This document outlines the development workflow for Kimi Proxy, emphasizing code quality, testing, and systematic progress tracking.

## Core Principles

### 1. Task Management with Shrimp Task Manager

All development work must be tracked and managed through the Shrimp Task Manager system.

**Why Shrimp Task Manager?**
- **Structured Planning**: Break down complex features into manageable subtasks
- **Progress Tracking**: Clear visibility into what's done, in progress, and pending
- **Dependency Management**: Handle task dependencies automatically
- **Research Integration**: Built-in research capabilities for informed decisions

### 2. Code Quality Standards

- Follow all rules in `codingstandards.md`
- Write tests for all business logic
- Maintain clean, readable code
- Use TypeScript for type safety
- Follow async/await patterns for I/O

### 3. Testing Strategy

- **Unit Tests**: Test individual functions and modules
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete user workflows
- **Performance Tests**: Ensure scalability requirements

## Development Process

### Phase 1: Task Planning

1. **Create Task Brief**: Write detailed requirements in `.shrimp_task_manager/plan/`
2. **Analyze Complexity**: Use `analyze_task` to assess technical feasibility
3. **Break Down Work**: Use `split_tasks` to create actionable subtasks
4. **Set Dependencies**: Define task relationships and prerequisites

### Phase 2: Implementation

1. **Start Small**: Begin with the simplest subtask
2. **Write Tests First**: TDD approach for business logic
3. **Incremental Progress**: Complete one subtask before starting another
4. **Regular Commits**: Commit frequently with clear messages

### Phase 3: Quality Assurance

1. **Code Review**: Self-review or pair programming
2. **Run Tests**: Ensure all tests pass
3. **Performance Check**: Verify performance requirements
4. **Documentation**: Update relevant docs

### Phase 4: Integration

1. **Merge Changes**: Integrate completed work
2. **End-to-End Testing**: Test complete workflows
3. **Deployment**: Follow deployment procedures
4. **Monitoring**: Monitor for issues in production

## Tools and Commands

### Shrimp Task Manager Commands

```bash
# Initialize project
task-master init

# Add new task
task-master add "Implement user authentication"

# Get next task
task-master next

# Update task status
task-master status 1 done

# Expand task into subtasks
task-master expand 1
```

### Development Commands

```bash
# Start development server
./bin/kimi-proxy start --reload

# Run tests
./bin/kimi-proxy test

# Run linting
./bin/kimi-proxy lint

# Build for production
./bin/kimi-proxy build
```

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/user-auth

# Make small, focused commits
git commit -m "feat: implement basic auth middleware"

# Push and create PR
git push origin feature/user-auth
```

## Code Review Guidelines

### For Authors
- Write clear commit messages
- Include tests with new code
- Update documentation
- Provide context in PR description

### For Reviewers
- Check code follows standards
- Verify tests are adequate
- Ensure documentation is updated
- Test the changes locally

## Performance Considerations

### Database Optimization
- Use appropriate indexes
- Avoid N+1 queries
- Implement connection pooling
- Cache frequently accessed data

### API Design
- Use pagination for large datasets
- Implement rate limiting
- Cache responses appropriately
- Use efficient serialization

### Frontend Performance
- Minimize bundle size
- Optimize images and assets
- Use lazy loading
- Implement virtual scrolling for lists

## Security Checklist

- [ ] Input validation on all user inputs
- [ ] Authentication for protected endpoints
- [ ] Authorization checks for data access
- [ ] SQL injection prevention
- [ ] XSS protection
- [ ] CSRF protection
- [ ] Secure headers (CSP, HSTS, etc.)
- [ ] Dependency vulnerability scanning

## Deployment Process

1. **Code Freeze**: Stop new features 24h before deployment
2. **Testing**: Run full test suite
3. **Build**: Create production artifacts
4. **Deploy**: Use blue-green or canary deployment
5. **Verify**: Check health endpoints and key functionality
6. **Rollback Plan**: Have immediate rollback capability

## Monitoring and Alerting

### Key Metrics
- Response times
- Error rates
- Throughput
- Resource utilization
- User satisfaction scores

### Alert Conditions
- Error rate > 5%
- Response time > 2s (95th percentile)
- CPU usage > 80%
- Memory usage > 90%

## Troubleshooting

### Common Issues

**Database Connection Errors**
- Check connection string
- Verify database server is running
- Check network connectivity
- Review connection pool settings

**Test Failures**
- Run tests individually to isolate issues
- Check test setup and teardown
- Verify mock configurations
- Review recent code changes

**Performance Degradation**
- Profile application with tools
- Check database query performance
- Review recent deployments
- Monitor resource usage

## Best Practices

### Code Organization
- Keep functions small and focused
- Use meaningful variable names
- Add comments for complex logic
- Follow consistent formatting

### Error Handling
- Use specific exception types
- Provide helpful error messages
- Log errors appropriately
- Implement graceful degradation

### Documentation
- Keep README updated
- Document API endpoints
- Include code comments
- Maintain changelog

### Communication
- Use clear commit messages
- Write helpful PR descriptions
- Document breaking changes
- Communicate deployment schedules