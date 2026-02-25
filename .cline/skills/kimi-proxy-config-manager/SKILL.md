---
name: kimi-proxy-config-manager
description: Expert configuration management for Kimi Proxy Dashboard. Use when managing TOML/YAML configurations, adding new providers, setting up API keys, or troubleshooting configuration issues. Handles provider routing, model mappings, and environment variable integration.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Configuration Manager

This skill provides comprehensive configuration management for Kimi Proxy Dashboard.

## Configuration Structure

### Primary Configuration Files

**config.toml** - Main configuration
```toml
[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144

[providers."managed:kimi-code"]
type = "kimi"
base_url = "https://api.kimi.com/coding/v1"
api_key = "${KIMI_API_KEY}"

[sanitizer]
enabled = true
threshold_tokens = 1000
preview_length = 200
```

**config.yaml** - Continue.dev configuration
```yaml
models:
  - model: kimi-code/kimi-for-coding
    api_base: http://localhost:8000/v1
    api_key: proxy-key
  - model: nvidia/kimi-k2.5
    api_base: http://localhost:8000/v1
    api_key: proxy-key
```

## Provider Management

### Adding New Providers

1. **Add provider to config.toml**
```toml
[providers."managed:new-provider"]
type = "openai-compatible"
base_url = "https://api.new-provider.com/v1"
api_key = "${NEW_PROVIDER_API_KEY}"
```

2. **Add models configuration**
```toml
[models."new-provider/model-name"]
provider = "managed:new-provider"
model = "model-name"
max_context_size = 128000
```

3. **Update routing logic if needed**
```python
# In src/kimi_proxy/proxy/router.py
def get_provider_host_header(provider_type: str) -> str:
    if provider_type == "new-provider":
        return "api.new-provider.com"
```

### Environment Variables

**Required variables for .env file:**
```bash
# Primary providers
KIMI_API_KEY=sk-kimi-...
NVIDIA_API_KEY=nvapi-...
MISTRAL_API_KEY=

# Optional providers
OPENROUTER_API_KEY=or-v1-...
SILICONFLOW_API_KEY=sk-...
GROQ_API_KEY=gsk_...
CEREBRAS_API_KEY=csb-...
GEMINI_API_KEY=AIza...
```

**Automatic loading:**
```bash
# Script loads .env automatically
source .env 2>/dev/null || echo "No .env file found"
export $(grep -v '^#' .env | xargs)
```

## Configuration Validation

### Validate Configuration

```bash
# Check TOML syntax
python -c "import tomllib; tomllib.load(open('config.toml', 'rb'))"

# Check API keys are set
./scripts/diagnose-mcp.sh  # Includes config validation

# Test provider connectivity
curl -H "Authorization: Bearer $KIMI_API_KEY" \
     https://api.kimi.com/coding/v1/models
```

### Common Configuration Issues

**Missing API keys:**
```bash
# Check environment variables
env | grep -E "(KIMI|NVIDIA|MISTRAL|OPENROUTER)_API_KEY"

# Validate config.toml expansion
python -c "
import os
from kimi_proxy.config.loader import get_config
config = get_config()
print('API keys loaded:', bool(config.get('providers', {}).get('managed:kimi-code', {}).get('api_key')))
"
```

**Invalid TOML syntax:**
```toml
# ❌ BAD - Missing quotes
[providers.managed:kimi-code]
type = kimi

# ✅ GOOD - Proper quotes
[providers."managed:kimi-code"]
type = "kimi"
```

**Model mapping issues:**
```python
# Test model name resolution
from kimi_proxy.proxy.router import map_model_name
result = map_model_name("kimi-for-coding", "kimi")
print(f"Mapped to: {result}")
```

## Advanced Configuration

### Multi-Provider Routing

```toml
[smart_routing]
enabled = true
prefer_low_cost = true
prefer_high_context = true
fallback_providers = ["kimi", "nvidia", "mistral"]

[smart_routing.weights]
cost = 0.4
latency = 0.3
context_size = 0.3
```

### Provider-Specific Settings

```toml
[proxy.timeouts]
# Fast providers
groq = 30.0
cerebras = 30.0

# Medium providers
kimi = 120.0
nvidia = 150.0

# Slow providers
gemini = 180.0

[proxy.retries]
max_retries = 3
retry_delay = 1.0
backoff_factor = 2.0
```

### MCP Server Configuration

```toml
[mcp.shrimp_task_manager]
enabled = true
url = "http://localhost:8002"
timeout_ms = 30000

[mcp.sequential_thinking]
enabled = true
url = "http://localhost:8003"
timeout_ms = 60000

[mcp.fast_filesystem]
enabled = true
url = "http://localhost:8004"
timeout_ms = 10000
workspace_path = "/home/kidpixel/kimi-proxy"
```

## Configuration Templates

### Development Environment
```toml
[development]
debug = true
log_level = "DEBUG"
auto_reload = true

[database]
path = "sessions_dev.db"
backup_enabled = true
```

### Production Environment
```toml
[production]
debug = false
log_level = "INFO"
auto_reload = false

[database]
path = "sessions.db"
backup_enabled = true
backup_interval = 3600  # 1 hour
```

## Migration Scripts

### Update Configuration
```bash
# Backup current config
cp config.toml config.toml.backup.$(date +%Y%m%d)

# Apply new configuration
python -c "
import tomllib
with open('config.toml.new', 'rb') as f:
    config = tomllib.load(f)
# Validate and save
with open('config.toml', 'wb') as f:
    tomllib.dump(config, f)
"
```

### Reset to Defaults
```bash
# Restore default configuration
cp config.toml.example config.toml

# Reconfigure with environment variables
./scripts/setup-env.sh
```

## Troubleshooting Commands

### Check Configuration Status
```bash
# Current configuration summary
curl http://localhost:8000/api/providers

# Active models
curl http://localhost:8000/api/models/all

# MCP server status
curl http://localhost:8000/api/memory/servers
```

### Debug Loading Issues
```python
# Debug configuration loading
from kimi_proxy.config.loader import get_config
import logging
logging.basicConfig(level=logging.DEBUG)
config = get_config()
print(f"Loaded providers: {list(config.get('providers', {}).keys())}")
```

### Test Provider Access
```bash
# Test each provider
for provider in kimi nvidia mistral; do
    echo "Testing $provider..."
    curl -s -H "Authorization: Bearer ${${provider^^}_API_KEY}" \
         "https://api.$provider.com/v1/models" | jq '.data[0].id' || echo "FAILED"
done
```