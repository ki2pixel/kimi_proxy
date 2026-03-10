---
paths:
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/__tests__/**"
---

# Test Strategy Rules

This rule defines testing standards and practices for the codebase.

## Test Categories

- **Unit Tests**: Test individual functions/components in isolation
- **Integration Tests**: Test component interactions
- **End-to-End Tests**: Test complete user workflows
- **Performance Tests**: Test system performance under load

## Test Structure

Use Given/When/Then format for all tests:

```javascript
given('user is logged in')
when('user clicks logout')
then('user is redirected to login page')
```

## Coverage Targets

- Unit tests: 80%+ line coverage
- Integration tests: 70%+ coverage
- Critical paths: 90%+ coverage

## Test Data

- Use factories for test data creation
- Avoid hardcoded test data
- Clean up after tests

## CI/CD Integration

- Tests run on every commit
- Failed tests block deployment
- Coverage reports generated automatically

## Best Practices

- Test behavior, not implementation
- Keep tests fast and reliable
- Use descriptive test names
- Mock external dependencies
- Test error conditions

## Tools

- Jest for JavaScript/TypeScript
- Pytest for Python
- Cypress for E2E tests
- Coverage tools integrated with CI