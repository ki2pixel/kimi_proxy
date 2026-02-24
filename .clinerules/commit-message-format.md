# Conventional Commit Format

All commit messages must follow the [Conventional Commits](https://conventionalcommits.org/) specification.

## Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **perf**: A code change that improves performance
- **test**: Adding missing tests or correcting existing tests
- **build**: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
- **ci**: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)
- **chore**: Other changes that don't modify src or test files
- **revert**: Reverts a previous commit

## Examples

```
feat: add user authentication feature

fix: resolve memory leak in session manager

docs: update API documentation for v2.0

style: format code with prettier

refactor: extract common utilities to shared module

perf: optimize database query performance

test: add unit tests for user service

build: update webpack configuration

ci: add GitHub Actions workflow

chore: update dependencies

revert: revert "feat: add user authentication"
```

## Breaking Changes

Breaking changes must be indicated by adding `!` after the type/scope and adding a `BREAKING CHANGE:` footer.

```
feat!: remove deprecated API endpoints

BREAKING CHANGE: The /v1/users endpoint has been removed. Use /v2/users instead.
```

## Scope (Optional)

Scopes provide additional context and are enclosed in parentheses:

```
feat(auth): add OAuth2 login support
fix(ui): resolve button styling issue
```

## Body and Footer

- **Body**: Provides additional context about the changes
- **Footer**: Used for breaking changes, issue references, etc.

```
feat: implement user profile page

- Add profile avatar upload
- Display user statistics
- Include edit functionality

Closes #123
BREAKING CHANGE: Profile API now requires authentication
```

## Why Conventional Commits?

- **Automated Versioning**: Tools like semantic-release can automatically determine version bumps
- **Clear History**: Makes it easy to understand what changed and why
- **Automated Changelogs**: Generate changelogs automatically from commit messages
- **Enforced Standards**: Linting tools can validate commit message format

## Tools

- **commitizen**: Interactive CLI for creating conventional commits
- **commitlint**: Lint commit messages to ensure they follow the convention
- **semantic-release**: Automate versioning and changelog generation

## Configuration

Add to `package.json` for commitlint:

```json
{
  "commitlint": {
    "extends": ["@commitlint/config-conventional"]
  }
}
```

Or use the global configuration in `.commitlintrc.js`:

```javascript
module.exports = {
  extends: ['@commitlint/config-conventional']
};
```