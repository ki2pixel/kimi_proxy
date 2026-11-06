# Déploiement — Installation et utilisation

**TL;DR** : installez les dépendances, démarrez `./bin/kimi-proxy start`, puis configurez votre client pour appeler `http://localhost:8000/v1/chat/completions` avec `X-Target-Base-URL` et `Authorization`.

## Prérequis

- Python 3.10+
- Un accès réseau au provider LLM choisi
- Les serveurs MCP locaux uniquement si vous utilisez `/api/mcp-gateway`

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Configuration

`config.toml` ne contient **ni provider ni modèle**. Il pilote les features MCP :

```toml
[database]
persist_sessions = false

[context_pruning]
enabled = false

[mcp_tool_pruning]
enabled = false

[mcp.gateway]
cb_enabled = true
```

Les secrets restent en variables d'environnement :

```bash
export KIMI_ADMIN_KEY="..."      # requis en production
export QDRANT_API_KEY="..."      # si Qdrant Cloud
export DEEPINFRA_API_KEY="..."   # si backend DeepInfra
```

## Démarrage

```bash
./bin/kimi-proxy start
./bin/kimi-proxy status
./bin/kimi-proxy logs
./bin/kimi-proxy stop
```

Le serveur écoute par défaut sur `127.0.0.1:8000`. Utilisez `--host` et `--port` pour changer.

## Vérification

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/models
curl -s http://localhost:8000/api/models
curl -s http://localhost:8000/api/memory/stats
```

La racine `/` ne sert plus de dashboard. Elle retourne les métadonnées du service.

## Client OpenAI-compatible

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Target-Base-URL: https://api.openai.com/v1" \
  -H "Authorization: Bearer $PROVIDER_API_KEY" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
```

Si `KIMI_ADMIN_KEY` est défini, ajoutez `X-Admin-Key: $KIMI_ADMIN_KEY`.

## Cline / Continue

- Endpoint : `http://localhost:8000`
- Pour les serveurs MCP : `http://localhost:8000/api/mcp-gateway/{server}/rpc`
- Les serveurs stdio passent par `scripts/mcp_bridge.py`.

## Dépannage

| Symptôme | Cause probable | Solution |
| :--- | :--- | :--- |
| `503 Cible manquante` | `X-Target-Base-URL` absent | Ajouter le header |
| `401 Unauthorized` | `KIMI_ADMIN_KEY` défini sans `X-Admin-Key` | Ajouter `X-Admin-Key` |
| `502` gateway | Serveur MCP arrêté | `./scripts/start-mcp-servers.sh start` |
| `400 Cible invalide` | URL refusée par la validation SSRF | Utiliser HTTPS et un hôte autorisé |
| Base SQLite absente | Persistance désactivée | `KIMI_PERSIST_SESSIONS=true` |

## Backup

```bash
./scripts/backup.sh
```

Le script sauvegarde `config.toml` et le fichier SQLite s'il existe.

## Golden Rule

**Le proxy ne détient aucune clé provider.** Si une configuration vous demande de stocker une clé API dans `config.toml`, elle est obsolète.
