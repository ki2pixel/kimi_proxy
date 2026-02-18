# Guide de Résolution - Transport MCP STDIO vs HTTP

## Problème Identifié

Le dashboard Kimi Proxy affiche **"Certains déconnectés"** pour les serveurs MCP externes malgré le fait que les processus serveurs sont actifs.

## Cause Racine

### Différence Fondamentale: STDIO vs HTTP

| Aspect | Transport STDIO | Transport HTTP |
|--------|-----------------|----------------|
| **Communication** | stdin/stdout (pipes) | TCP sockets (ports) |
| **Use case** | Plugins locaux, CLI | Services réseau, API |
| **Commande** | `fastmcp run server.py` | `python server.py` (avec HTTP) |
| **Ports** | Aucun | 6333 (Qdrant), 8001 (Compression) |
| **Protocole** | Lignes JSON | JSON-RPC 2.0 sur HTTP |

### Le Mismatch

```
┌─────────────────┐         ┌──────────────────┐
│  Client MCP     │  HTTP   │  Serveur MCP     │
│  Kimi Proxy     │ ◄─────► │  (attendu)       │
│  (httpx.Async)  │  ?      │  Port 8001       │
└─────────────────┘         └──────────────────┘
         │                           │
         │   ❌ PAS DE CONNEXION     │
         │   (serveur en STDIO)      │
         ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│  fastmcp        │  STDIO  │  Processus       │
│  run server.py  │ ◄─────► │  (stdin/stdout)  │
└─────────────────┘         └──────────────────┘
```

## Diagnostic

### Script de Diagnostic Automatique

```bash
./scripts/diagnose-mcp.sh
```

Ce script vérifie:
1. Configuration dans `config.toml`
2. Connectivité réseau (ports)
3. Endpoints JSON-RPC
4. Processus fastmcp en mode stdio
5. Connectivité depuis l'API Kimi Proxy

### Diagnostic Manuel

```bash
# Vérifier les ports en écoute
netstat -tlnp | grep -E ':(6333|8001)'

# Tester Qdrant Cloud
curl https://<votre-cluster>.aws.cloud.qdrant.io/healthz

# Tester Compression MCP
curl http://localhost:8001/health

# Tester JSON-RPC
curl -X POST http://localhost:8001/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"health","params":{},"id":1}'
```

## Solution

### Option 1: Démarrage Automatique via start.sh (Recommandé)

**Depuis la mise à jour des scripts**, les serveurs MCP sont démarrés automatiquement avec le proxy:

```bash
# Démarrer le proxy + serveurs MCP automatiquement
./scripts/start.sh

# Les serveurs MCP démarrent AVANT le proxy FastAPI
# Le statut s'affiche dans les logs de démarrage
```

L'arrêt est également automatique:
```bash
# Arrêter le proxy + serveurs MCP
./scripts/stop.sh

# Les serveurs MCP s'arrêtent APRÈS le proxy FastAPI
```

### Option 2: Démarrage Manuel des MCP uniquement

Si vous devez gérer les serveurs MCP séparément:

```bash
# Démarrer uniquement les serveurs MCP
./scripts/start-mcp-servers.sh start

# Vérifier le statut
./scripts/start-mcp-servers.sh status

# Arrêter uniquement les serveurs MCP
./scripts/start-mcp-servers.sh stop
```

### Option 3: Démarrage Manuel Complet

Si vous ne souhaitez pas utiliser `./scripts/start.sh`:

#### Qdrant MCP

**Option A - Qdrant Cloud (Recommandé):**
- Déjà configuré dans `config.toml`
- Aucun démarrage local nécessaire
- Vérifiez votre API key dans la configuration

**Option B - Qdrant Local:**
```bash
# Via Docker
docker run -p 6333:6333 qdrant/qdrant

# Ou installation native
# https://qdrant.tech/documentation/guides/installation/
```

#### Context Compression MCP

```bash
# Le script start-mcp-servers.sh crée automatiquement
# un serveur HTTP compatible sur le port 8001

# Vérifier qu'il fonctionne
curl http://localhost:8001/health
```

### Option 4: Modification du Client (Avancé)

Si vous devez utiliser des serveurs en mode STDIO, modifiez le client MCP pour supporter le transport stdio via subprocess:

```python
# Dans src/kimi_proxy/features/mcp/client.py
# Ajouter un wrapper stdio vers HTTP

import subprocess
import asyncio

class MCPStdioBridge:
    """Bridge entre transport stdio et HTTP local"""
    
    def __init__(self, command: str, port: int):
        self.command = command
        self.port = port
        self.process = None
    
    async def start(self):
        """Démarre le serveur stdio et crée un bridge HTTP"""
        self.process = await asyncio.create_subprocess_exec(
            *self.command.split(),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE
        )
        # Créer un bridge HTTP local...
```

> **Note:** Cette approche est plus complexe et déconseillée sauf cas particulier.

## Vérification Post-Résolution

### 1. Test des Endpoints

```bash
# Qdrant (Cloud)
curl -H "api-key: <votre-api-key>" \
  https://<votre-cluster>.aws.cloud.qdrant.io/healthz

# Compression (Local)
curl http://localhost:8001/health
```

### 2. Test via l'API Kimi Proxy

```bash
# Démarrer le proxy d'abord
./bin/kimi-proxy start

# Tester les serveurs MCP
curl http://localhost:8000/api/memory/servers
```

Réponse attendue:
```json
{
  "servers": [
    {
      "name": "qdrant-mcp",
      "type": "qdrant",
      "connected": true,
      "latency_ms": 45.2,
      "capabilities": ["semantic_search", "vector_store", "clustering"]
    },
    {
      "name": "context-compression-mcp",
      "type": "context-compression",
      "connected": true,
      "latency_ms": 12.5,
      "capabilities": ["zlib", "context_aware"]
    }
  ],
  "all_connected": true
}
```

### 3. Vérification Dashboard

Ouvrez http://localhost:8000 et vérifiez:
- **Panneau "Serveurs MCP Externes"** (violet)
- Statut "Connecté" pour Qdrant MCP
- Statut "Connecté" pour Context Compression MCP
- Latence affichée (<50ms pour Qdrant, <5s pour compression)

## Architecture Correcte

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Kimi Proxy Dashboard                            │
│                         (Port 8000)                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  API FastAPI    │  │  WebSocket      │  │  Dashboard UI       │  │
│  │  /api/memory/*  │  │  /ws            │  │  Statuts MCP        │  │
│  └────────┬────────┘  └─────────────────┘  └─────────────────────┘  │
└───────────┼─────────────────────────────────────────────────────────┘
            │
            │ HTTP /api/memory/servers
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MCPExternalClient                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  Qdrant Check   │  │  Compression    │  │  JSON-RPC 2.0       │  │
│  │  GET /healthz   │  │  POST /rpc      │  │  httpx.AsyncClient  │  │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────────┘  │
└───────────┼────────────────────┼────────────────────────────────────┘
            │                    │
            │ HTTPS              │ HTTP
            ▼                    ▼
┌──────────────────┐    ┌──────────────────┐
│  Qdrant Cloud    │    │  Compression MCP │
│  Port 443        │    │  Port 8001       │
│  (Cloud managed) │    │  (Local HTTP)    │
└──────────────────┘    └──────────────────┘
```

## Troubleshooting

### Qdrant Cloud retourne 403

**Cause:** API key manquante ou invalide

**Solution:**
```bash
# Vérifier la configuration
grep -A 10 '\[mcp.qdrant\]' config.toml

# Tester avec l'API key
curl -H "api-key: <votre-api-key>" \
  https://<votre-cluster>.aws.cloud.qdrant.io/healthz
```

### Port 8001 déjà utilisé

```bash
# Trouver le processus
lsof -ti:8001

# Le tuer si nécessaire
kill -9 $(lsof -ti:8001)

# Ou utiliser un autre port (modifier config.toml)
```

### Timeout sur les requêtes

Augmentez les timeouts dans `config.toml`:
```toml
[mcp.qdrant]
search_timeout_ms = 100  # Au lieu de 50

[mcp.compression]
compression_timeout_ms = 10000  # Au lieu de 5000
```

## Références

- [Protocole MCP](https://modelcontextprotocol.io/)
- [Qdrant MCP Server](https://github.com/qdrant/mcp-server-qdrant)
- [Context Compression MCP](https://github.com/rsakao/context-compression-mcp-server)
- [Client MCP - Kimi Proxy](../src/kimi_proxy/features/mcp/client.py)

---

**Document version:** 1.0  
**Dernière mise à jour:** 2026-02-15  
**Auteur:** Kimi Proxy Dashboard Team
