# Docker Setup Guide for SACL MCP Server

This guide provides comprehensive instructions for setting up and running the SACL MCP Server using Docker.

## Quick Start (Recommended)

### Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose
- OpenAI API key

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd sacl

# Copy environment configuration
cp .env.example .env

# Edit .env with your settings
OPENAI_API_KEY=your_openai_key_here
NEO4J_PASSWORD=your_secure_password
SACL_NAMESPACE=my-project-namespace
```

### 2. Prepare Your Codebase

Place your code repository in the `workspace` directory:

```bash
# Option 1: Copy your existing project
cp -r /path/to/your/project ./workspace/

# Option 2: Clone your project
git clone <your-project-url> ./workspace/

# Option 3: Create symbolic link
ln -s /path/to/your/project ./workspace
```

### 3. Start Services

```bash
# Start SACL and Neo4j
docker-compose up -d

# Check logs
docker-compose logs -f sacl-mcp-server

# Verify Neo4j is running
docker-compose logs neo4j
```

### 4. Verify Installation

```bash
# Check service health
docker-compose ps

# Test SACL connection (if HTTP endpoint enabled)
curl http://localhost:8000/health

# Access Neo4j browser (optional)
open http://localhost:7474
```

## Configuration

### Environment Variables

Edit your `.env` file to customize SACL behavior:

```bash
# Required
OPENAI_API_KEY=sk-your-key-here

# Repository Configuration
SACL_REPO_PATH=/workspace                    # Docker path to your code
SACL_NAMESPACE=my-project                    # Unique identifier

# Model Configuration
SACL_LLM_MODEL=gpt-4                        # LLM for semantic analysis
SACL_EMBEDDING_MODEL=text-embedding-3-small # Embedding model
SACL_BIAS_THRESHOLD=0.5                     # Bias detection sensitivity (0-1)
SACL_MAX_RESULTS=10                         # Default search results
SACL_CACHE_ENABLED=true                     # Enable embedding cache

# Neo4j Configuration
NEO4J_USER=neo4j                            # Neo4j username
NEO4J_PASSWORD=your_secure_password         # Neo4j password (change this!)
```

### Advanced Configuration

#### Custom Docker Compose

Create `docker-compose.override.yml` for local customizations:

```yaml
version: '3.8'

services:
  sacl-mcp-server:
    volumes:
      # Mount additional directories
      - /path/to/other/repos:/additional:ro
      # Mount config files
      - ./custom-config:/config:ro
    environment:
      # Override settings
      - SACL_BIAS_THRESHOLD=0.3
      - SACL_MAX_RESULTS=20
    # Expose HTTP port for debugging
    ports:
      - "8000:8000"

  neo4j:
    # Use different Neo4j version
    image: neo4j:5.20.0
    # Add more memory
    environment:
      - NEO4J_dbms_memory_heap_initial__size=512m
      - NEO4J_dbms_memory_heap_max__size=2G
```

#### Production Configuration

For production environments:

```yaml
version: '3.8'

services:
  sacl-mcp-server:
    # Use production image
    image: sacl-mcp-server:latest
    # Security settings
    read_only: true
    user: "1001:1001"
    # Resource limits
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  neo4j:
    # Persistent volumes for production
    volumes:
      - /var/lib/neo4j/data:/data
      - /var/log/neo4j:/logs
    # Security and performance
    environment:
      - NEO4J_dbms_security_auth__minimum__password__length=12
      - NEO4J_dbms_memory_pagecache_size=1G
      - NEO4J_dbms_memory_heap_max__size=2G
```

## Volume Management

### Repository Mounting

The SACL server needs access to your codebase. Choose the best mounting strategy:

#### Option 1: Direct Copy (Isolated)

```bash
# Copy project to workspace
cp -r /path/to/project ./workspace/project-name

# Update in docker-compose.yml
volumes:
  - ./workspace:/workspace:ro
```

#### Option 2: Symbolic Link (Live Updates)

```bash
# Create symbolic link
ln -s /path/to/project ./workspace/project-name

# Ensure Docker can follow symlinks
volumes:
  - ./workspace:/workspace:ro
  - /path/to/project:/workspace/project-name:ro
```

#### Option 3: Direct Mount (Development)

```bash
# Mount project directly
volumes:
  - /path/to/project:/workspace:ro
```

### Data Persistence

Neo4j data is persisted using Docker volumes:

```bash
# List volumes
docker volume ls | grep sacl

# Backup Neo4j data
docker run --rm -v sacl_neo4j_data:/data -v $(pwd):/backup ubuntu tar czf /backup/neo4j-backup.tar.gz -C /data .

# Restore Neo4j data
docker run --rm -v sacl_neo4j_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/neo4j-backup.tar.gz -C /data

# Reset all data (destructive!)
docker-compose down -v
```

## Service Management

### Basic Operations

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart SACL only
docker-compose restart sacl-mcp-server

# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

### Scaling and Updates

```bash
# Pull latest images
docker-compose pull

# Rebuild SACL image
docker-compose build --no-cache sacl-mcp-server

# Update and restart
docker-compose up -d --force-recreate
```

### Health Monitoring

```bash
# Check container health
docker-compose exec sacl-mcp-server ps aux

# Monitor resource usage
docker stats

# Check Neo4j status
docker-compose exec neo4j cypher-shell -u neo4j -p your_password "CALL dbms.components();"
```

## MCP Client Integration

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sacl": {
      "command": "docker",
      "args": [
        "exec", 
        "sacl_sacl-mcp-server_1", 
        "node", 
        "/app/dist/index.js"
      ],
      "env": {
        "OPENAI_API_KEY": "your-key",
        "SACL_REPO_PATH": "/workspace",
        "NEO4J_URI": "bolt://neo4j:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "your_password"
      }
    }
  }
}
```

### Cursor IDE Configuration

Configure Cursor to connect to the containerized SACL server:

```json
{
  "mcp.servers": {
    "sacl": {
      "command": "docker",
      "args": ["exec", "-i", "sacl_sacl-mcp-server_1", "node", "/app/dist/index.js"],
      "cwd": "/workspace"
    }
  }
}
```

### Direct MCP Connection

For development, you can expose the MCP server directly:

```yaml
# In docker-compose.override.yml
services:
  sacl-mcp-server:
    ports:
      - "3000:3000"  # MCP protocol port
    command: ["node", "/app/dist/index.js", "--port", "3000"]
```

## Troubleshooting

### Common Issues

#### 1. Container Won't Start

```bash
# Check logs for errors
docker-compose logs sacl-mcp-server

# Common issues:
# - Missing OPENAI_API_KEY
# - Neo4j connection failure
# - Volume mount permissions
```

#### 2. Neo4j Connection Issues

```bash
# Test Neo4j connectivity
docker-compose exec sacl-mcp-server ping neo4j

# Check Neo4j logs
docker-compose logs neo4j

# Verify authentication
docker-compose exec neo4j cypher-shell -u neo4j -p your_password "RETURN 1;"
```

#### 3. Volume Mount Problems

```bash
# Check mount permissions
docker-compose exec sacl-mcp-server ls -la /workspace

# Fix permissions (if needed)
sudo chown -R $(id -u):$(id -g) ./workspace
```

#### 4. Memory Issues

```bash
# Check memory usage
docker stats

# Increase Neo4j memory in docker-compose.yml:
environment:
  - NEO4J_dbms_memory_heap_max__size=2G
  - NEO4J_dbms_memory_pagecache_size=1G
```

### Debug Mode

Enable debug logging:

```yaml
# In docker-compose.override.yml
services:
  sacl-mcp-server:
    environment:
      - DEBUG=sacl:*
      - NODE_ENV=development
    # Keep container running for debugging
    command: ["tail", "-f", "/dev/null"]
```

Then exec into container:

```bash
docker-compose exec sacl-mcp-server bash
node /app/dist/index.js
```

### Performance Tuning

#### For Large Repositories (>1000 files)

```yaml
services:
  sacl-mcp-server:
    environment:
      - SACL_CACHE_ENABLED=true
      - SACL_MAX_RESULTS=5  # Reduce for faster queries
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'

  neo4j:
    environment:
      - NEO4J_dbms_memory_heap_max__size=3G
      - NEO4J_dbms_memory_pagecache_size=2G
      - NEO4J_dbms_tx__log_rotation_retention__policy=1G size
```

#### For Development Workloads

```yaml
services:
  sacl-mcp-server:
    environment:
      - SACL_BIAS_THRESHOLD=0.3  # More lenient
      - SACL_CACHE_ENABLED=false # Always fresh analysis
```

## Security Considerations

### Production Security

```yaml
services:
  sacl-mcp-server:
    # Run as non-root user
    user: "1001:1001"
    # Read-only filesystem
    read_only: true
    # No privileged access
    privileged: false
    # Limit capabilities
    cap_drop:
      - ALL

  neo4j:
    environment:
      # Strong password policy
      - NEO4J_dbms_security_auth__minimum__password__length=12
      # Disable HTTP connector in production
      - NEO4J_dbms_connector_http_enabled=false
```

### Network Security

```yaml
# Create isolated network
networks:
  sacl-network:
    driver: bridge
    internal: true

services:
  sacl-mcp-server:
    networks:
      - sacl-network
  
  neo4j:
    networks:
      - sacl-network
```

### Secrets Management

Use Docker secrets for sensitive data:

```yaml
secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  neo4j_password:
    file: ./secrets/neo4j_password.txt

services:
  sacl-mcp-server:
    secrets:
      - openai_api_key
      - neo4j_password
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
      - NEO4J_PASSWORD_FILE=/run/secrets/neo4j_password
```

## Backup and Recovery

### Automated Backups

Create a backup script:

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup Neo4j data
docker run --rm \
  -v sacl_neo4j_data:/data \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  ubuntu tar czf /backup/neo4j-data.tar.gz -C /data .

# Backup configuration
cp .env "$BACKUP_DIR/"
cp docker-compose.yml "$BACKUP_DIR/"

echo "Backup completed: $BACKUP_DIR"
```

### Recovery Process

```bash
#!/bin/bash
# restore.sh

BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ]; then
  echo "Usage: $0 <backup_directory>"
  exit 1
fi

# Stop services
docker-compose down

# Restore Neo4j data
docker run --rm \
  -v sacl_neo4j_data:/data \
  -v "$(pwd)/$BACKUP_DIR":/backup \
  ubuntu tar xzf /backup/neo4j-data.tar.gz -C /data

# Restore configuration
cp "$BACKUP_DIR/.env" .
cp "$BACKUP_DIR/docker-compose.yml" .

# Start services
docker-compose up -d

echo "Recovery completed from: $BACKUP_DIR"
```

---

**SACL Docker Setup** - Complete containerized deployment for bias-aware code analysis.