---
name: kimi-proxy-config-manager
description: Expert configuration management for Kimi Proxy Dashboard. Use when managing TOML/YAML configurations, adding new providers, setting up API keys, or troubleshooting configuration issues. Handles provider routing, model mappings, and environment variable integration.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Configuration Manager

**TL;DR**: Use this skill when editing `config.toml`, provider/model mappings, or env-backed API keys. The source of truth is the current code in `src/kimi_proxy/config/loader.py`, `src/kimi_proxy/proxy/router.py`, `config.toml`, and the API routes that expose providers/models.

## Source of Truth

Current configuration behavior is driven by:

- `config.toml`: providers, models, proxy timeouts, MCP sections
- `config.yaml`: optional Continue.dev / editor-facing config
- `src/kimi_proxy/config/loader.py`: recursive `${VAR}` expansion and model/provider initialization
- `src/kimi_proxy/proxy/router.py`: target URL selection, host header extraction, model-name mapping

## Architecture Rules

Configuration belongs to the config layer.

- `config/` can be consumed by Features and API
- `config/` must not depend on `features/*`
- Secrets stay in environment variables or env-expanded TOML values
- Routing decisions must stay compatible with the 5-layer architecture

## Current Provider Pattern

### ✅ Real `config.toml` pattern

```toml
[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144

[models."openrouter/aurora-alpha"]
provider = "openrouter"
model = "openrouter/aurora-alpha"
max_context_size = 128000

[models."gemini/gemini-2.5-flash"]
provider = "gemini"
model = "gemini-2.5-flash"
max_context_size = 1048576

[models."nano-gpt/kimi-k2.5"]
provider = "nano-gpt"
model = "moonshotai/kimi-k2.5"
max_context_size = 262144

[providers."managed:kimi-code"]
type = "kimi"
base_url = "https://api.kimi.com/coding/v1"
api_key = "${KIMI_API_KEY}"

[providers.openrouter]
type = "openai"
base_url = "https://openrouter.ai/api/v1"
api_key = "${OPENROUTER_API_KEY}"

[providers.gemini]
type = "gemini"
base_url = "https://generativelanguage.googleapis.com/v1beta"
api_key = "${GEMINI_API_KEY}"

[providers.nano-gpt]
type = "openai"
base_url = "https://nano-gpt.com/api/v1"
api_key = "${NANO_GPT_API_KEY}"
```

### Environment variables currently relevant

```bash
KIMI_API_KEY=...
NVIDIA_API_KEY=...
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=...
SILICONFLOW_API_KEY=...
GROQ_API_KEY=...
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
NANO_GPT_API_KEY=...
```

## Loader Behavior

`src/kimi_proxy/config/loader.py` does recursive env expansion.

### ✅ Real behavior

```python
from kimi_proxy.config.loader import get_config, init_models, init_providers

config = get_config()
providers = init_providers(config)
models = init_models(config)
```

`_expand_env_vars()` expands `${VAR}` inside strings, dicts, and lists. Do not document secret loading paths that bypass this flow.

## Routing Logic That Must Stay Documented

### `get_target_url_for_session()`

Uses the active session provider to resolve the upstream `base_url`, with loop protection against `localhost:8000` / `127.0.0.1:8000`.

### `get_provider_host_header(target_url)`

This function does **not** switch on provider type. It parses the final target URL and returns `urlparse(target_url).netloc`.

```python
from kimi_proxy.proxy.router import get_provider_host_header

host_header = get_provider_host_header("https://openrouter.ai/api/v1")
# returns "openrouter.ai"
```

### `map_model_name(client_model, models)`

Current mapping is intentionally simple:

1. Exact configured model key
2. Exact upstream provider model already present in config
3. Fallback to suffix split after the first `/`

```python
from kimi_proxy.proxy.router import map_model_name

mapped = map_model_name("nano-gpt/kimi-k2.5", models)
# exact key -> "moonshotai/kimi-k2.5"

mapped = map_model_name("z-ai/glm5", models)
# if already present as upstream model, keep as-is

mapped = map_model_name("provider/custom-model", models)
# fallback -> "custom-model"
```

## Continue / Editor Configuration

`config.yaml` remains the editor-facing companion config for Continue-style clients.

```yaml
models:
  - model: kimi-code/kimi-for-coding
    api_base: http://localhost:8000/v1
    api_key: proxy-key
  - model: gemini/gemini-2.5-flash
    api_base: http://localhost:8000/v1
    api_key: proxy-key
```

## Troubleshooting

### Validate the active config

```bash
PYTHONPATH=src python -c "from kimi_proxy.config.loader import get_config; c=get_config(); print(sorted(c.get('providers', {}).keys()))"
```

### Inspect routing inputs

```bash
PYTHONPATH=src python -c "from kimi_proxy.config.loader import get_config, init_models; from kimi_proxy.proxy.router import map_model_name; models=init_models(get_config()); print(map_model_name('gemini/gemini-2.5-flash', models))"
```

### Check provider inventory exposed by the app

```bash
curl -s http://localhost:8000/api/providers | jq
curl -s http://localhost:8000/api/models/all | jq
```

### Safe backup before editing

```bash
cp config.toml config.toml.backup.$(date +%Y%m%d_%H%M%S)
```

## ❌ Outdated Patterns to Avoid

- Documenting `config.toml.example`: not part of the current repo flow
- Referencing `scripts/setup-env.sh`: not present in the current project
- Using `tomllib.dump(...)` as the standard migration path: not how config changes are applied here
- Using shell indirection like `${${provider^^}_API_KEY}`: not portable and not used by the codebase
- Describing `get_provider_host_header()` as provider-type-specific logic: it is URL-based now

## Golden Rule

**Keep config docs tied to the actual TOML keys, env vars, and router functions that exist today.** When provider support changes, update `config.toml`, `loader.py`, and this skill together.