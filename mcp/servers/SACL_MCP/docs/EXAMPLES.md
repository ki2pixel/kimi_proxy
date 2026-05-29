# SACL Usage Examples

This document provides comprehensive examples of using the SACL MCP Server for bias-aware code analysis and retrieval.

## Table of Contents

- [Basic Usage Examples](#basic-usage-examples)
- [Relationship Analysis Examples](#relationship-analysis-examples)
- [Context-Aware Query Examples](#context-aware-query-examples)
- [File Update Examples](#file-update-examples)
- [Bias Analysis Examples](#bias-analysis-examples)
- [Advanced Workflows](#advanced-workflows)

## Basic Usage Examples

### Repository Analysis

**Scenario**: Initial setup of SACL for a new project

```json
{
  "tool": "analyze_repository",
  "arguments": {
    "repositoryPath": "/workspace/my-react-app",
    "incremental": false
  }
}
```

**Expected Response**:
```
📊 Repository Analysis Complete

**Processing Statistics:**
• Files processed: 147/150
• Average bias score: 0.425
• High bias files detected: 12
• Processing time: 23.4s

🔍 SACL Framework Applied:
• Textual bias detection completed
• Semantic augmentation applied
• Knowledge graph populated
• Ready for bias-aware code retrieval

Use 'query_code' to search with reduced textual bias.
```

### Basic Code Query

**Scenario**: Finding authentication-related code

```json
{
  "tool": "query_code", 
  "arguments": {
    "query": "user authentication and validation",
    "repositoryPath": "/workspace/my-react-app",
    "maxResults": 3
  }
}
```

**Expected Response**:
```
🔍 SACL Query Results for: "user authentication and validation"

Found 3 bias-aware matches:

**1. src/auth/AuthService.js**
• Bias Score: 45.2% 🟡
• SACL Score: 87.3%
• Pattern: Service layer authentication with validation pipeline

```javascript
class AuthService {
  async validateUser(credentials) {
    // Validate user credentials
    const user = await this.userRepository.findByEmail(credentials.email);
    if (!user || !await this.comparePasswords(credentials.password, user.hashedPassword)) {
      throw new AuthenticationError('Invalid credentials');
    }
    return this.generateToken(user);
  }
}
```

📝 SACL Ranking Analysis:
• Query: "user authentication and validation"
• Textual Similarity: 78.5%
• Semantic Similarity: 91.2%
• Functional Relevance: 89.7%
• Bias Level: Medium (45.2%)
• Final Score: 87.3%
```

## Relationship Analysis Examples

### File Relationship Exploration

**Scenario**: Understanding dependencies of a controller

```json
{
  "tool": "get_relationships",
  "arguments": {
    "filePath": "src/controllers/UserController.js",
    "maxDepth": 2,
    "relationshipTypes": ["imports", "calls"]
  }
}
```

**Expected Response**:
```
🔗 Code Relationships Analysis

**File:** src/controllers/UserController.js
**Traversal Depth:** 2
**Related Components:** 8

**Key Relationships:**

1. **UserService** (imports)
   • File: src/services/UserService.js
   • Relationship: Service imported by controller
   • Relevance: 95.0%
   • Distance: 1 hop

2. **validateRequest** (calls)
   • File: src/middleware/validation.js
   • Relationship: Validation middleware called in routes
   • Relevance: 88.0%
   • Distance: 1 hop

3. **DatabaseConnection** (calls)
   • File: src/database/connection.js
   • Relationship: Database operations through service
   • Relevance: 75.0%
   • Distance: 2 hops

**Traversal Statistics:**
• Nodes Visited: 12
• Edges Traversed: 8
• Max Depth Reached: 2
• Processing Time: 145ms
```

### File Context Analysis

**Scenario**: Understanding a component's role in the system

```json
{
  "tool": "get_file_context",
  "arguments": {
    "filePath": "src/models/User.js",
    "includeSnippets": true
  }
}
```

**Expected Response**:
```
🎯 File Context Analysis

**File:** src/models/User.js
**Total Related:** 12

**Context Summary:**
• imports: 3 components
• exports: 1 components
• calls: 6 components
• extends: 1 components

**Relationship Breakdown:**

**IMPORTS (3):**
• mongoose
  └─ Database modeling framework imported
  └─ Code: const mongoose = require('mongoose');

• bcrypt
  └─ Password hashing utility imported
  └─ Code: const bcrypt = require('bcrypt');

**EXTENDS (1):**
• BaseModel
  └─ Inherits from base model class
  └─ Code: class User extends BaseModel { constructor(data) { super(data);

**CALLS (6):**
• hashPassword
  └─ Password hashing method called in pre-save hook
• validateEmail
  └─ Email validation called in schema validation
• generateToken
  └─ JWT token generation for authentication

**Usage Recommendations:**
• Use 'query_code_with_context' to find similar patterns
• Check imports/exports when modifying interfaces
• Consider impact on calling functions when refactoring
```

## Context-Aware Query Examples

### Enhanced Search with Relationships

**Scenario**: Finding middleware with full context

```json
{
  "tool": "query_code_with_context",
  "arguments": {
    "query": "error handling middleware",
    "repositoryPath": "/workspace/express-api",
    "maxResults": 2,
    "includeRelated": true
  }
}
```

**Expected Response**:
```
🔍 Enhanced SACL Query Results for: "error handling middleware"

Found 2 context-aware matches:

**1. src/middleware/errorHandler.js**
• Bias Score: 32.1% 🟢
• SACL Score: 92.4%
• Pattern: Express middleware for centralized error handling
• Key Region: Lines 15-45
• Related Components: 4
  └─ Logger (imports)
  └─ AppError (imports)
  └─ ValidationError (calls)

```javascript
const errorHandler = (err, req, res, next) => {
  // Log error details
  logger.error(`${err.name}: ${err.message}`, {
    stack: err.stack,
    url: req.url,
    method: req.method
  });

  // Handle different error types
  if (err instanceof ValidationError) {
    return res.status(400).json({
      error: 'Validation Error',
      details: err.details
    });
  }
```

🧠 **Context:** src/middleware/errorHandler.js has 4 related components including 2 imports, 1 function calls, and 0 inheritance relationships. Most relevant for "error handling middleware": Logger service imported for error tracking.

**Key Dependencies:**
🔴 imports: Logger service imported for error tracking
🟡 calls: ValidationError handling for request validation
🟢 imports: AppError custom error class imported

📝 SACL Ranking Analysis:
• Query: "error handling middleware"
• Textual Similarity: 89.2%
• Semantic Similarity: 94.8%
• Functional Relevance: 91.7%
• Bias Level: Low (32.1%)
• Final Score: 92.4%
• Bias Adjustment: Minimal

🔗 Relationship Context:
• Related Components: 4
• Key Relationships: Logger service imported for error tracking, ValidationError handling for request validation, AppError custom error class imported
• Context Relevance: High
```

## File Update Examples

### Single File Update

**Scenario**: AI assistant modifies authentication logic

```json
{
  "tool": "update_file",
  "arguments": {
    "filePath": "src/auth/AuthService.js",
    "changeType": "modified"
  }
}
```

**Expected Response**:
```
📝 File Update Result

**File:** src/auth/AuthService.js
**Change Type:** modified
**Status:** ✅ Success
**Message:** File src/auth/AuthService.js processed successfully. Bias score: 0.387

🔍 SACL Analysis Updated:
• Bias detection applied
• Semantic augmentation completed
• Relationships extracted and stored
• Knowledge graph updated

File is now ready for bias-aware retrieval.
```

### Batch File Updates

**Scenario**: Major refactoring affecting multiple files

```json
{
  "tool": "update_files",
  "arguments": {
    "files": [
      { "filePath": "src/services/UserService.js", "changeType": "modified" },
      { "filePath": "src/controllers/UserController.js", "changeType": "modified" },
      { "filePath": "src/models/UserModel.js", "changeType": "modified" },
      { "filePath": "src/utils/validation.js", "changeType": "created" },
      { "filePath": "src/deprecated/oldAuth.js", "changeType": "deleted" }
    ]
  }
}
```

**Expected Response**:
```
📁 Batch File Update Result

**Total Files:** 5
**Successful:** 4 ✅
**Failed:** 1 ❌

**Individual Results:**
✅ src/services/UserService.js: File processed successfully. Bias score: 0.423
✅ src/controllers/UserController.js: File processed successfully. Bias score: 0.356
✅ src/models/UserModel.js: File processed successfully. Bias score: 0.445
✅ src/utils/validation.js: File processed successfully. Bias score: 0.234
❌ src/deprecated/oldAuth.js: File not found or already deleted

🔍 SACL Analysis Completed:
• 4 files analyzed for bias
• Semantic features extracted
• Code relationships mapped
• Knowledge graph updated

Updated files are ready for enhanced code retrieval.
```

## Bias Analysis Examples

### File-Specific Bias Analysis

**Scenario**: Investigating why a well-documented file ranks poorly

```json
{
  "tool": "get_bias_analysis",
  "arguments": {
    "filePath": "src/algorithms/quicksort.js"
  }
}
```

**Expected Response**:
```
🧠 SACL Bias Analysis

**File:** src/algorithms/quicksort.js

**Bias Metrics:**
• Overall Bias Score: 73.2% 🔴
• Semantic Pattern: Recursive divide-and-conquer sorting
• Functional Signature: Array input → sorted array output with comparator

**Bias Indicators:**
• docstring_dependency: High docstring dependency (15.3% of code)
• identifier_name_bias: High reliance on descriptive names
• comment_over_reliance: Excessive comments (18.7% of code)

**Repository Overview:**
• Average Bias Score: 42.5%
• High Bias Files: 8
• Distribution: 89 low, 45 medium, 8 high

💡 Improvement Suggestions:
• Reduce reliance on variable naming for semantic understanding
• Focus on structural patterns over comments
• Improve functional signature extraction
• Consider extracting documentation to separate files
```

### Repository-Wide Bias Analysis

**Scenario**: Understanding overall codebase bias patterns

```json
{
  "tool": "get_bias_analysis",
  "arguments": {}
}
```

**Expected Response**:
```
🧠 SACL Bias Analysis

**Repository Overview:**
• Average Bias Score: 42.5%
• High Bias Files: 8
• Distribution: 89 low, 45 medium, 8 high

**High Bias Files:**
• src/algorithms/quicksort.js (73.2%)
• src/utils/stringHelpers.js (68.7%)
• src/components/UserProfile.tsx (65.4%)
• src/services/EmailService.js (62.8%)

💡 Improvement Suggestions:
• Reduce reliance on variable naming for semantic understanding
• Focus on structural patterns over comments
• Improve functional signature extraction
• Consider documentation refactoring for high-bias files
• Implement consistent naming conventions
```

## Advanced Workflows

### New Developer Onboarding

**Workflow**: Help new developer understand authentication system

```bash
# 1. Get overall system overview
get_system_stats → Review repository statistics

# 2. Find authentication-related code
query_code_with_context {
  "query": "user authentication flow",
  "maxResults": 5
}

# 3. Explore main auth component relationships
get_file_context {
  "filePath": "src/auth/AuthService.js",
  "includeSnippets": true
}

# 4. Understand dependencies
get_relationships {
  "filePath": "src/auth/AuthService.js",
  "maxDepth": 3
}
```

### Code Quality Assessment

**Workflow**: Assess and improve code quality

```bash
# 1. Check overall bias patterns
get_bias_analysis → Identify high-bias files

# 2. Analyze problematic files
get_file_context {
  "filePath": "src/algorithms/quicksort.js"
}

# 3. Find better implementations
query_code_with_context {
  "query": "efficient sorting algorithm low bias",
  "maxResults": 3
}

# 4. After improvements, update analysis
update_file {
  "filePath": "src/algorithms/quicksort.js",
  "changeType": "modified"
}
```

### Refactoring Impact Analysis

**Workflow**: Understand impact of proposed changes

```bash
# 1. Analyze current relationships
get_relationships {
  "filePath": "src/services/UserService.js",
  "maxDepth": 2
}

# 2. Get full context
get_file_context {
  "filePath": "src/services/UserService.js",
  "includeSnippets": false
}

# 3. Find similar patterns
query_code_with_context {
  "query": "service layer pattern with dependency injection"
}

# 4. After refactoring, batch update
update_files {
  "files": [/* affected files */]
}

# 5. Verify relationships updated
get_relationships {
  "filePath": "src/services/UserService.js",
  "maxDepth": 2
}
```

### Debugging Poor Search Results

**Workflow**: Investigate why search doesn't return expected results

```bash
# 1. Check bias impact
get_bias_analysis {
  "filePath": "expected/file/path.js"
}

# 2. Try different query approaches
query_code {
  "query": "original query",
  "includeContext": false
}

query_code_with_context {
  "query": "original query",
  "includeRelated": true
}

# 3. Explore relationships of expected file
get_file_context {
  "filePath": "expected/file/path.js",
  "includeSnippets": true
}

# 4. Check system health
get_system_stats
```

## Performance Considerations

### Query Optimization

```javascript
// Fast: Basic query without context
{
  "tool": "query_code",
  "arguments": {
    "query": "user validation",
    "includeContext": false,
    "maxResults": 5
  }
}

// Slower: Full context analysis
{
  "tool": "query_code_with_context",
  "arguments": {
    "query": "user validation",
    "maxResults": 5,
    "includeRelated": true
  }
}
```

### Relationship Traversal

```javascript
// Efficient: Limited depth and filtered types
{
  "tool": "get_relationships",
  "arguments": {
    "filePath": "src/large/file.js",
    "maxDepth": 2,
    "relationshipTypes": ["imports", "calls"]
  }
}

// Resource-intensive: Deep traversal of all types
{
  "tool": "get_relationships", 
  "arguments": {
    "filePath": "src/large/file.js",
    "maxDepth": 5
    // No filter = all relationship types
  }
}
```

## Error Handling Examples

### File Not Found

```json
{
  "tool": "update_file",
  "arguments": {
    "filePath": "src/nonexistent/file.js",
    "changeType": "modified"
  }
}
```

**Response**:
```
📝 File Update Result

**File:** src/nonexistent/file.js
**Change Type:** modified
**Status:** ❌ Failed
**Message:** File path src/nonexistent/file.js is outside repository or does not exist
```

### Invalid Relationship Types

```json
{
  "tool": "get_relationships",
  "arguments": {
    "filePath": "src/valid/file.js",
    "relationshipTypes": ["invalid_type"]
  }
}
```

**Response**:
```
🔗 Code Relationships Analysis

**File:** src/valid/file.js
**Related Components:** 0

No significant relationships found for this file.

This could mean:
• File is standalone with minimal dependencies
• Invalid relationship types specified
• File hasn't been processed yet (run analyze_repository first)
```

---

**SACL Examples** - Comprehensive usage patterns for bias-aware code analysis and retrieval.