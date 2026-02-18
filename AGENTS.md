# Kimi Proxy Dashboard - Guide pour Agents IA

**TL;DR**: C'est un proxy transparent FastAPI + SQLite qui intercepte les requêtes LLM, compte les tokens avec Tiktoken, et économise 20-40% de coûts via sanitizer/compression.

J'ai construit ce système parce que j'en avais marre de payer $30/mois pour des services de transcription alors que les APIs me coûtaient $0.36/heure. Le problème? Je ne voyais pas ce que je consommais, et je perdais mon contexte au milieu de conversations importantes.

## Ce que tu dois savoir avant de coder

### L'architecture en 5 couches
```
API Layer (FastAPI) ← Interface utilisateur
Services Layer ← WebSocket, Rate Limiting  
Features Layer ← Sanitizer, MCP, Compression
Proxy Layer ← Routage vers les APIs
Core Layer ← Database, Tokens, Models
```

**Pourquoi cette structure?** Chaque couche ne dépend que de celles en dessous. Je peux tester les tokens sans démarrer l'API. Je peux remplacer le sanitizer sans casser le proxy.

### Key Features
- **Multi-Provider Support**: 8 providers, 20+ models with granular model selection
- **Modular Architecture**: Clean separation of concerns (Core / Features / Services / API)
- **Streaming Proxy**: Transparent redirection to APIs with Server-Sent Events (SSE) streaming
- **🆕 Robust Streaming Error Handling**: Gestion gracieuse des erreurs réseau (ReadError, Timeout) avec retry et extraction tokens partiels
- **Real-time Dashboard**: WebSocket-based live updates without page refresh
- **Advanced Log Watcher**: PyCharm integration with CompileChat block parsing
- **Precise Token Tracking**: Tiktoken-based tokenization (cl100k_base) with cumulative context calculation
- **SQLite Persistence**: Session-based metrics storage with full conversation history
- **Visual Gauges**: Color-coded alerts (Green → Yellow → Red) for context usage thresholds
- **Data Export**: CSV and JSON export capabilities for analysis
- **🆕 Compaction Phase 1**: Infrastructure de base pour compaction automatique du contexte LLM
- **🆕 Sanitizer Phase 1**: Masking automatique des contenus verbeux (tools/console) et routing dynamique
- **🆕 MCP Phase 2**: Intégration mémoire standardisée avec détection balises MCP
- **🆕 Compression Phase 3**: Bouton d'urgence manuel pour compresser l'historique
- **🆕 MCP Phase 3**: Intégration serveurs MCP externes (Qdrant, Context Compression) avec recherche sémantique <50ms
- **🆕 MCP Phase 4**: 4 nouveaux serveurs MCP (Task Master, Sequential Thinking, Fast Filesystem, JSON Query) - 43 outils - **TESTÉS ET FONCTIONNELS ✅**
- **🆕 Smart Routing**: Routage provider optimisé basé sur capacité contexte/coût/latence
- **🆕 Standardized Memory**: Types frequent/episodic/semantic avec auto-promotion des patterns

### Project Language
All documentation, comments, and UI text are in **French**.

---

## Architecture Overview (v2.0)

### Modular Structure

```
src/kimi_proxy/
├── main.py                   # FastAPI app factory (~200 lines)
├── __main__.py               # CLI entry point
│
├── core/                     # Core business logic (no external deps)
│   ├── exceptions.py         # Custom exceptions
│   ├── constants.py          # Global constants
│   ├── tokens.py             # Tiktoken tokenization
│   ├── models.py             # Dataclasses (Session, Metric, etc.)
│   └── database.py           # SQLite + migrations
│
├── config/                   # Configuration
│   ├── loader.py             # TOML loading
│   ├── settings.py           # Dataclasses settings
│   └── display.py            # Display names & helpers
│
├── features/                 # Horizontal features
│   ├── log_watcher/          # PyCharm log monitoring
│   ├── compaction/           # Phase 1: Context compaction infrastructure
│   ├── sanitizer/            # Phase 1: Content masking
│   ├── mcp/                  # Phase 2&3: MCP memory + External servers
│   │   ├── detector.py       # MCP tag detection
│   │   ├── analyzer.py       # Memory analysis
│   │   ├── storage.py        # Memory metrics storage
│   │   ├── client.py         # External MCP servers (Qdrant, Compression)
│   │   └── memory.py         # Standardized memory management
│   └── compression/          # Phase 3: Context compression
│
├── proxy/                    # HTTP proxy logic
│   ├── router.py             # Provider routing
│   ├── transformers.py       # Format conversion (Gemini)
│   ├── stream.py             # SSE streaming management
│   └── client.py             # HTTPX client
│
├── services/                 # Business services
│   ├── websocket_manager.py  # WebSocket connections
│   ├── rate_limiter.py       # Rate limiting
│   └── alerts.py             # Threshold alerts
│
└── api/                      # FastAPI routes
    ├── router.py             # Main router
    └── routes/               # Domain endpoints
        ├── sessions.py
        ├── providers.py
        ├── proxy.py
        ├── exports.py
        ├── sanitizer.py
        ├── mcp.py
        ├── compression.py
        ├── compaction.py
        ├── models.py
        ├── health.py
        └── websocket.py
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                           │
│                          (main.py - 200 lignes)                      │
├─────────────────────────────────────────────────────────────────────┤
│  API Layer              │  Services              │  Features         │
│  ──────────             │  ────────              │  ────────         │
│  /chat/completions      │  WebSocket Manager     │  Log Watcher      │
│  /api/sessions          │  Rate Limiter          │  Sanitizer        │
│  /api/providers         │  Alert Manager         │  MCP Memory       │
│  /api/compress          │  Smart Router          │  External MCP*    │
│  /api/compaction        │                        │  Compression      │
│  /api/memory/**         │                        │  Compaction       │
├─────────────────────────────────────────────────────────────────────┤
│  Core Layer                                                          │
│  ──────────                                                          │
│  Database (SQLite)      │  Tokenization          │  Models            │
│  Exceptions             │  Constants             │  Config            │
├─────────────────────────────────────────────────────────────────────┤
│  External Services*                                                  │
│  Phase 3:                                                            │
│  • Qdrant MCP (:6333)  - Semantic search, clustering                 │
│  • Compression MCP (:8001) - Advanced compression                    │
│  Phase 4:                                                            │
│  • Task Master MCP (:8002) - Task management (14 tools)              │
│  • Sequential Thinking MCP (:8003) - Structured reasoning (1 tool)   │
│  • Fast Filesystem MCP (:8004) - File operations (25 tools)          │
│  • JSON Query MCP (:8005) - JSON querying (3 tools)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## MCP Phase 4 - Intégration Réussie (2026-02-17)

### ✅ **Statut : TOUS LES OUTILS MCP FONCTIONNELS**

Les 4 serveurs MCP Phase 4 ont été testés avec succès avec Nvidia Kimi 2.5 :

#### 🛠️ **Task Master MCP** (Port 8002 - 14 outils)
- **Fonction**: Gestion de tâches, analyse PRD, expansion de tâches
- **Test réussi**: Analyse complète d'un cahier des charges React/Node.js/MongoDB
- **Résultats**: Plan de développement structuré avec estimations horaires et risques identifiés
- **Sécurité**: Contrôles workspace activés - accès limité au répertoire `/home/kidpixel/kimi-proxy`

#### 🧠 **Sequential Thinking MCP** (Port 8003 - 1 outil)
- **Fonction**: Raisonnement séquentiel structuré étape par étape
- **Test réussi**: Résolution du problème du sous-array contigu avec plus grande somme
- **Résultats**: Algorithme de Kadane complet avec implémentation Python optimisée O(n)
- **Performance**: Temps de réponse < 30 secondes pour raisonnement complexe

#### 📁 **Fast Filesystem MCP** (Port 8004 - 25 outils)
- **Fonction**: Opérations fichiers haute performance
- **Test réussi**: Lecture/écriture fichiers, recherche, gestion répertoires
- **Sécurité**: Permissions workspace strictes - accès refusé hors workspace autorisé
- **Performance**: Opérations < 10 secondes pour fichiers volumineux

#### 🔍 **JSON Query MCP** (Port 8005 - 3 outils)
- **Fonction**: Requêtes JSON avancées avec JSONPath
- **Test réussi**: Analyse fichier `test_config.json` avec extraction endpoints, providers actifs, modèles
- **Résultats**: Détection automatique des clés API manquantes et configuration invalide
- **Sécurité**: Validation chemins fichiers - accès limité au workspace

### 🔧 **Correctifs Implémentés**

#### Sécurité Workspace
- **Contrôles d'accès**: Tous les serveurs MCP vérifient les chemins avant opérations
- **Isolation**: Chaque workspace protégé contre accès non autorisé
- **Erreurs explicites**: Messages 403 pour accès refusé avec détails

#### Corrections Techniques
- **URLs MCP**: Ajout des champs `url` manquants dans les modèles pour éviter erreurs frontend
- **Compression MCP**: Ajout du démarrage automatique du serveur (port 8001)
- **Configuration API**: Correction clé Mistral pour Task Master MCP
- **Gestion erreurs**: Amélioration robustesse réseau et timeouts

#### Démarrage Automatique
- **Script intégré**: `./scripts/start-mcp-servers.sh` démarre tous les serveurs automatiquement
- **Surveillance**: Vérification statut temps réel via dashboard
- **Persistance**: Serveurs redémarrent automatiquement après reboot système

### 📊 **Performances Validées**

| Serveur MCP | Port | Outils | Temps Réponse | Sécurité |
|-------------|------|--------|---------------|----------|
| Task Master | 8002 | 14 | < 30s | ✅ Workspace |
| Sequential Thinking | 8003 | 1 | < 30s | ✅ Sécurisé |
| Fast Filesystem | 8004 | 25 | < 10s | ✅ Permissions |
| JSON Query | 8005 | 3 | < 5s | ✅ Validation |
| Context Compression | 8001 | 3 | < 5s | ✅ Auto-démarrage |

### 🎯 **Impact Métier**

- **Économie temps**: Automatisation tâches développement complexes
- **Qualité code**: Algorithmes optimisés et tests structurés  
- **Sécurité renforcée**: Isolation complète des workspaces
- **Fiabilité**: Gestion d'erreurs robuste et récupération automatique

**Les outils MCP Phase 4 sont maintenant prêts pour utilisation en production ! 🚀**

---

## Technology Stack

### Backend
- **FastAPI**: Async web framework (Python 3.10+)
- **SQLite**: Zero-config database for sessions and metrics persistence
- **WebSockets**: Bidirectional real-time communication via `ConnectionManager`
- **HTTPX**: Async HTTP client for proxying requests
- **TOML**: Configuration loading from `config.toml`
- **Tiktoken**: Precise token counting (cl100k_base encoding)
- **aiofiles**: Async file reading for Log Watcher
- **Uvicorn**: ASGI server with auto-reload

### Frontend
- **ES6 Modules**: Modern JavaScript with native module system
- **Vanilla JavaScript**: No heavy frameworks (SPA)
- **TailwindCSS**: Utility-first CSS with dark mode
- **Chart.js**: Interactive charts
- **Lucide Icons**: Modern icon set

#### Frontend Architecture (ES6 Modules)

Le JavaScript a été refactorisé d'un monolithe de ~1744 lignes vers une architecture modulaire ES6:

```
static/js/
├── main.js              # Point d'entrée, orchestration
└── modules/
    ├── utils.js         # Utilitaires, bus d'événements
    ├── api.js           # Couche d'accès API
    ├── charts.js        # Graphiques Chart.js
    ├── sessions.js      # État des sessions et métriques
    ├── websocket.js     # Gestion WebSocket
    ├── ui.js            # Manipulations DOM
    ├── modals.js        # Gestion des modales
    └── compaction.js    # Fonctionnalités de compaction
```

**Pourquoi cette structure**: Chaque module a une responsabilité unique. Le bus d'événements (`utils.js`) permet une communication découplée entre modules sans créer de dépendances circulaires. Le cache DOM dans `ui.js` évite les requêtes répétées.

---

## Project Structure

```
.
├── bin/                        # Executable scripts
│   ├── kimi-proxy             # Main CLI (start|stop|restart|status|logs|test)
│   ├── kimi-proxy-start       # Start alias
│   ├── kimi-proxy-stop        # Stop alias
│   └── kimi-proxy-test        # Test alias
│
├── src/kimi_proxy/            # Python source code
│   ├── main.py                # FastAPI factory app
│   ├── __main__.py            # CLI entry point
│   ├── core/                  # Core modules
│   ├── config/                # Configuration
│   ├── features/              # Feature modules
│   ├── proxy/                 # Proxy logic
│   ├── services/              # Business services
│   └── api/                   # API routes
│
├── scripts/                   # Utility scripts
│   ├── migrate.sh             # Data migration
│   └── backup.sh              # DB backup
│
├── tests/                     # Test suite
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── e2e/                   # End-to-end tests
│
├── config.toml                # Provider configuration
├── config.yaml                # Continue.dev configuration
├── static/index.html          # Frontend SPA
├── sessions.db                # SQLite database
├── requirements.txt           # Dependencies
├── requirements-dev.txt       # Dev dependencies
├── setup.py                   # Setup script
├── README.md                  # User documentation (French)
└── AGENTS.md                  # This file - agent reference
```

---

## Build and Run Commands

### Prerequisites
- Python 3.10+ with pip
- Linux/Unix environment

### Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# Or in editable mode
pip install -e .
```

### Start the Server
```bash
# Using CLI (recommended) - démarre automatiquement les serveurs MCP externes
./bin/kimi-proxy start
./bin/kimi-proxy start --port 9000 --reload

# Using scripts (legacy) - démarre aussi les serveurs MCP automatiquement
./scripts/start.sh

# Or manually (sans MCP)
PYTHONPATH=src python -m kimi_proxy
# Or
PYTHONPATH=src uvicorn kimi_proxy.main:app --reload
```

**Note sur les serveurs MCP**: Depuis la mise à jour des scripts, `./scripts/start.sh` démarre automatiquement les serveurs MCP externes (Qdrant + Context Compression) avant le proxy FastAPI. `./scripts/stop.sh` les arrête proprement après le proxy.

### CLI Commands
```bash
./bin/kimi-proxy start [--port PORT] [--host HOST] [--reload]
./bin/kimi-proxy stop
./bin/kimi-proxy restart
./bin/kimi-proxy status
./bin/kimi-proxy logs          # View server logs
./bin/kimi-proxy test          # Run tests
./bin/kimi-proxy shell         # Python shell with env loaded
```

### Run Tests
```bash
# Using CLI
./bin/kimi-proxy test

# Or with pytest directly
PYTHONPATH=src python -m pytest tests/ -v
```

### Access Dashboard
Open browser at: **http://localhost:8000**

---

## API Endpoints

### Proxy
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/completions` | POST | Proxy to configured API (streaming & non-streaming) |
| `/models` | GET | OpenAI-compatible model list |

### Sessions
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List all sessions |
| `/api/sessions` | POST | Create new session (accepts `name`, `provider`, `model`) |
| `/api/sessions/active` | GET | Active session with stats and max_context |
| `/api/sessions/{id}/memory` | GET | Memory metrics for session |

### Providers & Models
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/providers` | GET | List all providers with models grouped |
| `/api/models/all` | GET | List all models with metadata |

### Export
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/export/csv` | GET | Export active session to CSV |
| `/api/export/json` | GET | Export active session to JSON |

### Sanitizer (Phase 1)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mask` | GET | Liste les contenus masqués récents |
| `/api/mask/{hash}` | GET | Récupère un contenu masqué par son hash |
| `/api/sanitizer/stats` | GET | Statistiques du sanitizer |
| `/api/sanitizer/toggle` | POST | Active/désactive le sanitizer |

### MCP Memory (Phase 2, 3 & 4)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/memory/stats` | GET | Statistiques globales mémoire MCP |
| `/api/sessions/{id}/memory` | GET | Historique des métriques mémoire |
| `/api/memory/servers` | GET | **Phase 3**: Statuts serveurs MCP externes |
| `/api/memory/similarity` | POST | **Phase 3**: Recherche sémantique (<50ms) |
| `/api/memory/compress` | POST | **Phase 3**: Compression via MCP |
| `/api/memory/store` | POST | **Phase 3**: Stockage mémoire standardisée |
| `/api/memory/frequent` | GET | **Phase 3**: Mémoires fréquemment utilisées |
| `/api/memory/cluster/{id}` | POST | **Phase 3**: Clustering sémantique |
| `/api/memory/stats/advanced` | GET | **Phase 3**: Stats avancées avec serveurs |
| `/api/memory/servers/phase4` | GET | **Phase 4**: Statuts serveurs MCP Phase 4 |
| `/api/memory/task-master/tasks` | GET | **Phase 4**: Liste des tâches Task Master |
| `/api/memory/task-master/stats` | GET | **Phase 4**: Statistiques Task Master |
| `/api/memory/task-master/call` | POST | **Phase 4**: Appel outil Task Master |
| `/api/memory/sequential-thinking/call` | POST | **Phase 4**: Raisonnement séquentiel |
| `/api/memory/filesystem/call` | POST | **Phase 4**: Opération Fast Filesystem |
| `/api/memory/json-query/call` | POST | **Phase 4**: Requête JSON Query |
| `/api/memory/tool/call` | POST | **Phase 4**: Appel générique d'outil MCP |
| `/api/memory/all-servers` | GET | **Phase 4**: Tous les serveurs MCP (Phase 3 + 4) |

### Compression (Phase 3)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/compress/{session_id}` | POST | Compresser l'historique d'une session |
| `/api/compress/{session_id}/stats` | GET | Stats de compression d'une session |
| `/api/compress/stats` | GET | Stats globales de compression |

### Compaction (Phase 2 - Fonctionnalités Utilisateur)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/compaction/{session_id}` | POST | Déclencher une compaction manuelle |
| `/api/compaction/{session_id}/stats` | GET | Stats de compaction d'une session |
| `/api/compaction/{session_id}/history` | GET | Historique des compactions |
| `/api/compaction/{session_id}/reserved` | POST | Configurer les tokens réservés |
| `/api/compaction/{session_id}/simulate` | POST | Simuler une compaction |
| `/api/compaction/{session_id}/preview` | GET | **Preview avant compaction (Phase 2)** |
| `/api/compaction/{session_id}/toggle-auto` | POST | **Activer/désactiver auto-compaction (Phase 2)** |
| `/api/compaction/{session_id}/auto-status` | GET | **Statut auto-compaction (Phase 2)** |
| `/api/compaction/{session_id}/history-chart` | GET | **Données graphique historique (Phase 2)** |
| `/api/compaction/config/ui` | GET | **Configuration UI compaction (Phase 2)** |
| `/api/compaction/stats` | GET | Stats globales de compaction |

### Real-time
| Endpoint | Description |
|----------|-------------|
| `/ws` | WebSocket for live updates |
| `/health` | Health check with status |
| `/api/rate-limit` | Rate limiting status |

---

## Configuration

### Local Proxy Configuration (`config.toml`)

```toml
[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144

[providers."managed:kimi-code"]
type = "kimi"
base_url = "https://api.kimi.com/coding/v1"
api_key = "sk-kimi-..."

[sanitizer]
enabled = true
threshold_tokens = 1000
preview_length = 200
tmp_dir = "/tmp/kimi_proxy_masked"

[sanitizer.routing]
fallback_threshold = 0.90
heavy_duty_fallback = true

# MCP Phase 4 - Nouveaux serveurs
[mcp.task_master]
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

[mcp.json_query]
enabled = true
url = "http://localhost:8005"
timeout_ms = 5000
```

---

## Key Implementation Details

### Import Patterns (Avoiding Circular Imports)

Use `TYPE_CHECKING` for type hints that would cause circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket

class ConnectionManager:
    async def connect(self, websocket: "WebSocket"):  # Use string annotation
        ...
```

### Configuration Access

Always use `get_config()` from `config.loader`:

```python
from kimi_proxy.config.loader import get_config

config = get_config()
providers = config.get("providers", {})
models = config.get("models", {})
```

### Database Access

Use the context manager from `core.database`:

```python
from kimi_proxy.core.database import get_db

with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions")
    rows = cursor.fetchall()
```

### WebSocket Broadcasting

Use the connection manager from `services`:

```python
from kimi_proxy.services.websocket_manager import get_connection_manager

manager = get_connection_manager()
await manager.broadcast({
    "type": "metric",
    "data": {...}
})
```

---

## Module Reference

### Core Module (`kimi_proxy.core`)

```python
# Exceptions
from kimi_proxy.core.exceptions import (
    KimiProxyError,
    ConfigurationError,
    ProviderError,
    DatabaseError,
)

# Constants
from kimi_proxy.core.constants import (
    DEFAULT_MAX_CONTEXT,
    DATABASE_FILE,
    DEFAULT_PROVIDER,
)

# Tokenization
from kimi_proxy.core.tokens import (
    ENCODING,
    count_tokens_tiktoken,
    count_tokens_text,
)

# Models
from kimi_proxy.core.models import (
    Session,
    Metric,
    Provider,
    Model,
)

# Database
from kimi_proxy.core.database import (
    get_db,
    init_database,
    create_session,
    get_active_session,
)
```

### Features Module (`kimi_proxy.features`)

```python
# Log Watcher
from kimi_proxy.features.log_watcher import (
    LogWatcher,
    create_log_watcher,
)

# Sanitizer
from kimi_proxy.features.sanitizer import (
    ContentMasker,
    sanitize_messages,
    get_masked_content,
)

# MCP (Phase 2, 3 & 4)
from kimi_proxy.features.mcp import (
    # Phase 2
    MCPDetector,
    analyze_mcp_memory_in_messages,
    save_memory_metrics,
    # Phase 3 - External Servers
    MCPExternalClient,
    MCPClientConfig,
    MCPClientError,
    MCPConnectionError,
    get_mcp_client,
    # Phase 3 - Memory Management
    MemoryManager,
    get_memory_manager,
    FREQUENT_ACCESS_THRESHOLD,
    # Phase 4 - New MCP Servers Detection
    extract_phase4_tools,
    get_detected_mcp_servers,
)

# Compaction (Phase 2 - Fonctionnalités Utilisateur)
from kimi_proxy.features.compaction import (
    SimpleCompaction,
    CompactionResult,
    CompactionConfig,
    get_compactor,
    persist_compaction_result,
    get_session_compaction_stats,
    # Phase 2 - Auto Trigger
    CompactionAutoTrigger,
    AutoTriggerConfig,
    get_auto_trigger,
)

# Compression
from kimi_proxy.features.compression import (
    compress_session_history,
    get_compression_stats,
)
```

### Services Module (`kimi_proxy.services`)

```python
from kimi_proxy.services.websocket_manager import get_connection_manager
from kimi_proxy.services.rate_limiter import get_rate_limiter
from kimi_proxy.services.alerts import check_threshold_alert
```

### Proxy Module (`kimi_proxy.proxy`)

```python
# Streaming avec gestion d'erreurs
from kimi_proxy.proxy.stream import (
    stream_generator,
    extract_usage_from_stream,
    extract_usage_from_response,
)

# Client HTTPX avec retry
from kimi_proxy.proxy.client import (
    create_proxy_client,
    ProxyClient,
    PROVIDER_TIMEOUTS,
)

# Routing (Phase 2 & 3)
from kimi_proxy.proxy.router import (
    get_target_url_for_session,
    get_provider_host_header,
    map_model_name,
    # Phase 3 - Smart Routing
    find_optimal_provider,
    get_provider_capacities,
    calculate_routing_score,
    get_routing_recommendation,
    ProviderRoutingDecision,
)

# Transformers (Gemini)
from kimi_proxy.proxy.transformers import (
    convert_to_gemini_format,
    build_gemini_endpoint,
)
```

#### Gestion des Erreurs Streaming

Le module `stream.py` gère automatiquement les erreurs réseau:

```python
# Le générateur capture les erreurs sans crasher
async for chunk in stream_generator(
    response,
    session_id=1,
    metric_id=1,
    provider_type="kimi",
    models=models,
    manager=manager
):
    yield chunk
# Même si ReadError, le flux continue et les tokens sont extraits
```

Types d'erreurs gérées:
- `httpx.ReadError`: Connexion interrompue par le provider
- `httpx.ConnectError`: Impossible de se connecter
- `httpx.TimeoutException`: Timeout lors de la lecture

#### Configuration Timeouts

```python
# Timeouts par provider (secondes)
PROVIDER_TIMEOUTS = {
    "gemini": 180.0,      # Plus lent sur gros contextes
    "kimi": 120.0,
    "nvidia": 150.0,      # Cold starts possibles
    "groq": 60.0,         # Ultra-rapide
    "cerebras": 60.0,
    "default": 120.0
}
```

---

## Troubleshooting

### Port Already in Use
```bash
./bin/kimi-proxy stop && ./bin/kimi-proxy start
```

### Database Issues
```bash
# Backup first
./scripts/backup.sh

# Reset
rm sessions.db && ./bin/kimi-proxy start
```

### Import Errors
Make sure `PYTHONPATH` includes `src/`:
```bash
export PYTHONPATH=src:$PYTHONPATH
python -m kimi_proxy
```

### Config Not Found
The config loader searches for `config.toml` in the project root (parent of `src/`). Ensure your working directory is correct.

### Streaming Errors (ReadError, Timeout)

#### Symptômes
```
🔴 [STREAM_ERROR] Connexion interrompue par le provider
httpx.ReadError: Server disconnected without sending a response.
```

#### Causes possibles
1. **Provider instable**: Le provider a fermé la connexion prématurément
2. **Timeout**: La réponse prend trop de temps (> timeout configuré)
3. **Réseau**: Interruption réseau entre le proxy et le provider

#### Solutions
1. **Vérifier les timeouts** dans `config.toml`:
```toml
[proxy]
stream_timeout = 120.0
max_retries = 2
retry_delay = 1.0

[proxy.timeouts]
gemini = 180.0  # Gemini est plus lent
kimi = 120.0
```

2. **Augmenter le timeout** pour les providers lents:
```python
# Dans votre appel API, le timeout est auto-configuré par provider
# Mais vous pouvez le surcharger dans config.toml
```

3. **Vérifier les logs** pour identifier le provider problématique:
```bash
./bin/kimi-proxy logs | grep "STREAM_ERROR"
```

4. **Activer le retry** (déjà activé par défaut):
- Le client retry automatiquement 2 fois avec backoff exponentiel
- Les erreurs 4xx ne sont pas retry (erreur client)
- Les erreurs réseau (ReadError, ConnectError) sont retry

#### Comportement attendu
- Le stream peut échouer mais les tokens déjà reçus sont comptabilisés
- Une alerte WebSocket est envoyée (`streaming_error`)
- Le dashboard affiche l'erreur sans crasher

### MCP Servers Disconnected ("Certains déconnectés")

#### Symptômes
- Dashboard affiche "Certains déconnectés" dans le panneau MCP
- Statuts des serveurs: "N/A" ou "Déconnecté"
- Pourtant les processus serveurs semblent actifs (`ps aux | grep mcp`)

#### Cause Racine: Transport Mismatch (STDIO vs HTTP)

Le client MCP (`MCPExternalClient`) attend des serveurs **HTTP**:
- Qdrant: `https://*.aws.cloud.qdrant.io/healthz` (Cloud) ou `http://localhost:6333` (Local)
- Compression: `http://localhost:8001/rpc` (JSON-RPC 2.0)

Mais `fastmcp run server.py` démarre en mode **STDIO** (stdin/stdout), pas HTTP:
```
┌─────────────┐      STDIO      ┌──────────────┐
│  fastmcp    │ ◄──────────────►│  Processus   │
│  (stdio)    │   (pipes)       │  (pas HTTP)  │
└─────────────┘                 └──────────────┘
```

#### Diagnostic

```bash
# Script de diagnostic automatique
./scripts/diagnose-mcp.sh

# Vérifier manuellement les ports (Phase 3 + Phase 4)
netstat -tlnp | grep -E ':(6333|8001|8002|8003|8004|8005)'

# Tester les endpoints Phase 3
curl http://localhost:8001/health
curl -X POST http://localhost:8001/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"health","params":{},"id":1}'

# Tester les endpoints Phase 4
curl http://localhost:8000/api/memory/servers/phase4
curl http://localhost:8000/api/memory/task-master/stats
curl http://localhost:8000/api/memory/all-servers
```

#### Solution

**Démarrage des serveurs en mode HTTP (Automatique depuis start.sh):**

Les serveurs MCP sont maintenant démarrés automatiquement par `./scripts/start.sh`. Aucune commande séparée n'est nécessaire.

```bash
# Démarrer le proxy + MCP automatiquement
./scripts/start.sh

# Vérifier le statut MCP depuis le dashboard
# ou via API:
curl http://localhost:8000/api/memory/servers
```

**Démarrage manuel (si besoin):**
```bash
# Démarrer uniquement les serveurs MCP
./scripts/start-mcp-servers.sh start

# Vérifier le statut
./scripts/start-mcp-servers.sh status

# Arrêter uniquement les serveurs MCP
./scripts/start-mcp-servers.sh stop
```

**Configuration Qdrant:**
- **Cloud** (recommandé): Déjà configuré dans `config.toml`, vérifiez votre API key
- **Local**: `docker run -p 6333:6333 qdrant/qdrant`

**Configuration Compression:**
- Le script `start-mcp-servers.sh` crée automatiquement un serveur HTTP sur le port 8001
- Compatible JSON-RPC 2.0 avec les méthodes: `health`, `compress`, `decompress`

#### Documentation Complète

Voir [docs/MCP_TRANSPORT_HTTP_GUIDE.md](../docs/MCP_TRANSPORT_HTTP_GUIDE.md) pour:
- Explication détaillée STDIO vs HTTP
- Architecture correcte
- Troubleshooting avancé

---

## Migration from v1.0 (Monolith)

The project was restructured from a single 3,073-line `main.py` to a modular architecture:

| Aspect | v1.0 (Monolith) | v2.0 (Modular) |
|--------|-----------------|----------------|
| Main file | `main.py` (3,073 lines) | `src/kimi_proxy/main.py` (200 lines) |
| Python files | 1 | 52 |
| Structure | Flat | Modular (core/features/services/api) |
| Testing | Difficult | Easy (unit/integration/e2e) |
| Maintenance | Hard | Easy |

### Backward Compatibility
- Old scripts (`./start.sh`, `./stop.sh`) are now symlinks to the new CLI
- Database schema is preserved and auto-migrated
- API endpoints remain unchanged

---

## Recent Changes

### Gestion Erreurs Streaming - Robustesse Réseau (2026-02-15)
- **Nouvelle Exception `StreamingError`**: Exception dédiée avec contexte (provider, type d'erreur, retry count)
- **Gestion `httpx.ReadError`**: Capture et gestion gracieuse des interruptions de connexion provider
- **Timeouts par Provider**: Configuration granulaire (Gemini 180s, Groq 60s, etc.)
- **Retry avec Backoff**: Jusqu'à 2 retries avec délai exponentiel (1s, 2s, 4s)
- **Extraction Tokens Partiels**: Même si le stream échoue, les tokens reçus sont comptabilisés
- **Broadcast WebSocket**: Notification temps réel des erreurs streaming (`streaming_error`)
- **Logging Structuré**: Messages d'erreur détaillés avec métriques (chunks reçus, durée, provider)
- **Headers SSE Optimisés**: `X-Accel-Buffering: no` pour éviter buffering nginx
- **Tests**: 20+ tests unitaires et E2E pour la gestion d'erreurs streaming
- **Configuration**: Section `[proxy]` dans config.toml pour timeouts et retry settings

Fichiers modifiés:
- `src/kimi_proxy/core/exceptions.py` - Ajout `StreamingError`
- `src/kimi_proxy/proxy/stream.py` - Gestion d'erreurs complète
- `src/kimi_proxy/proxy/client.py` - Retry et timeouts configurables
- `src/kimi_proxy/api/routes/proxy.py` - Gestion codes 502/504
- `config.toml` - Section `[proxy]` avec timeouts par provider

### Phase 2: Fonctionnalités Utilisateur - Compaction (2026-02-15)
- **UI Compaction Manuelle**: Bouton "Compacter Contexte" avec modal preview
- **Preview Impact Tokens**: Estimation des tokens économisés avant compaction
- **Indicateur Loading**: Feedback visuel asynchrone pendant la compaction
- **Toggle Auto-Compaction**: Par session avec persistance DB (`auto_compaction_enabled`, `auto_compaction_threshold`)
- **Triggers Automatiques**: Seuils configurables via `compaction.auto.auto_compact_threshold`
- **Jauges Multi-Couches**: Usage + réservé + seuil avec tooltips détaillés
- **Graphique Historique**: Visualisation des compactions et tokens économisés
- **Alertes WebSocket**: Notifications temps réel des seuils atteints (`compaction_alert`, `auto_compaction_toggled`)
- **API Endpoints étendus**: `/api/compaction/{id}/preview`, `/toggle-auto`, `/auto-status`, `/history-chart`, `/config/ui`
- **Service AutoTrigger**: `CompactionAutoTrigger` avec cooldown et compteurs
- **Tests E2E**: Workflow complet de compaction testé

### Phase 3: Intégration MCP Avancée (2026-02-15)
- **Serveurs MCP Externes**:
  - **Qdrant MCP** (`github.com/qdrant/mcp-server-qdrant`): Recherche sémantique <50ms, détection redondances, clustering
  - **Context Compression MCP** (`github.com/rsakao/context-compression-mcp-server`): Compression 20-80%, stockage persistant SQLite
- **Client MCP JSON-RPC 2.0**: `MCPExternalClient` avec retry, backoff exponentiel, timeouts configurables
- **Mémoire Standardisée**:
  - Types: `frequent` (patterns), `episodic` (conversations), `semantic` (vecteurs Qdrant)
  - Auto-promotion des patterns fréquents
  - Recherche similaire sémantique ou fallback textuel
  - Table `mcp_memory_entries` avec index optimisés
- **Routage Provider Optimisé**:
  - Score combiné: capacité (40%), coût (30%), latence (20%), marge (10%)
  - `find_optimal_provider()`: Sélection intelligente basée sur contexte restant
  - Fallback automatique vers modèles avec plus de contexte
  - Table `mcp_routing_decisions` pour historique
- **Nouveaux Endpoints API**:
  - `/api/memory/servers`: Statuts des serveurs MCP
  - `/api/memory/similarity`: Recherche sémantique
  - `/api/memory/compress`: Compression via MCP
  - `/api/memory/store`: Stockage mémoire standardisée
  - `/api/memory/frequent`: Mémoires fréquemment utilisées
  - `/api/memory/cluster/{id}`: Clustering sémantique
- **UI Dashboard Étendu**:
  - Panneau statuts serveurs MCP (violet)
  - Visualisation mémoires fréquentes
  - Modales recherche sémantique et compression
  - Indicateurs temps réel
- **Configuration**: Section `[mcp]` complète dans `config.toml`
- **Tests**: `tests/test_mcp_phase3.py` - 20+ tests unitaires

### Phase 1: Context Compaction Infrastructure (2026-02-15)
- **SimpleCompaction service**: Algorithm de compaction inspiré Kimi CLI
- **Extensions DB**: Colonnes `reserved_tokens`, `compaction_count`, table `compaction_history`
- **API Endpoints**: `/api/compaction/*` pour gestion et simulation
- **WebSocket Events**: Broadcast temps réel des événements de compaction
- **Configuration**: Section `[compaction]` dans config.toml
- **Tests**: 23 tests unitaires couvrant logique et edge cases
- **Migration**: Script `scripts/migrate_compaction.sh` avec backup automatique

### Architecture Restructuring (2026-02-15)
- **Complete modularization**: Extracted 52 Python files from monolith
- **Clean architecture**: Separation of Core/Features/Services/API
- **New CLI**: Unified command interface with `./bin/kimi-proxy`
- **Improved testing**: Unit, integration, and E2E test structure
- **Setup script**: Added `setup.py` for proper package installation

See `docs/development/plan-restructuration-scripts.md` for the full migration plan.

### Intégration Automatique MCP dans Scripts (2026-02-15)
- **Scripts start.sh/stop.sh mis à jour**: Intégration automatique de la gestion des serveurs MCP externes
- **Démarrage séquentiel**: MCP servers d'abord, puis proxy FastAPI (dans start.sh)
- **Arrêt propre**: Proxy FastAPI d'abord, puis MCP servers (dans stop.sh)
- **Détection répertoire**: Scripts fonctionnent depuis n'importe quel répertoire (`SCRIPT_DIR` auto-détecté)
- **Logging amélioré**: Messages cohérents avec couleurs et emojis
- **Gestion d'erreurs**: Le proxy continue même si MCP échoue (fonctionnalités optionnelles)
- **Nettoyage PID**: Suppression automatique des fichiers PID MCP lors de l'arrêt

**Scripts modifiés:**
- `scripts/start.sh` - Ajout appel à `start-mcp-servers.sh start` après vérif dépendances
- `scripts/stop.sh` - Ajout appel à `start-mcp-servers.sh stop` après arrêt FastAPI
- `scripts/start-mcp-servers.sh` - Compatibilité chemins absolus

### Frontend Modularization (2026-02-15)
- **ES6 Modules Migration**: Refactorisation du monolithe JavaScript (~1744 lignes) vers 9 modules ES6
- **Event Bus Pattern**: Bus d'événements centralisé pour communication découplée entre modules
- **DOM Cache**: Préchargement des éléments fréquemment utilisés pour optimiser les performances
- **Explicit Dependencies**: Imports/exports ES6 clairs entre modules
- **Separation of Concerns**: utils, api, charts, sessions, websocket, ui, modals, compaction

### Phase 4: Intégration de 4 Nouveaux Serveurs MCP (2026-02-17)

#### Task Master MCP (14 outils)
- **Gestion de tâches complète**: `get_tasks`, `next_task`, `set_task_status`, `parse_prd`, `expand_task`, etc.
- Configuration: Port 8002, timeout 30s via `[mcp.task_master]`
- API: `/api/memory/task-master/tasks`, `/api/memory/task-master/call`
- Modèles: `TaskMasterTask`, `TaskMasterStats`

#### Sequential Thinking MCP (1 outil)
- **Raisonnement séquentiel structuré**: Résolution de problèmes complexes étape par étape
- Configuration: Port 8003, timeout 60s via `[mcp.sequential_thinking]`
- API: `/api/memory/sequential-thinking/call`
- Modèle: `SequentialThinkingStep`

#### Fast Filesystem MCP (25 outils)
- **Opérations fichiers haute performance**: Lecture, écriture, recherche, édition, compression
- Outils clés: `fast_read_file`, `fast_search_code`, `fast_edit_block`, `fast_compress_files`
- Configuration: Port 8004, timeout 10s via `[mcp.fast_filesystem]`
- API: `/api/memory/filesystem/call`
- Modèle: `FileSystemResult`

#### JSON Query MCP (3 outils)
- **Requêtes JSON avancées**: JSONPath, recherche de clés/valeurs
- Outils: `json_query_jsonpath`, `json_query_search_keys`, `json_query_search_values`
- Configuration: Port 8005, timeout 5s via `[mcp.json_query]`
- API: `/api/memory/json-query/call`
- Modèle: `JsonQueryResult`

#### Détection et Intégration
- **Patterns regex** dans `constants.py` pour détection automatique des 43 outils
- `MCPDetector` étendu avec méthodes Phase 4: `detect_phase4_tools()`, `get_detected_phase4_servers()`
- `MCPExternalClient` étendu avec méthodes pour les 4 serveurs
- Appel générique via `call_mcp_tool()` avec routage automatique

#### Nouveaux Endpoints API
- `GET /api/memory/servers/phase4` - Statuts des 4 serveurs Phase 4
- `GET /api/memory/task-master/tasks`, `GET /api/memory/task-master/stats`
- `POST /api/memory/task-master/call`
- `POST /api/memory/sequential-thinking/call`
- `POST /api/memory/filesystem/call`
- `POST /api/memory/json-query/call`
- `POST /api/memory/tool/call` - Appel générique
- `GET /api/memory/all-servers` - Tous les serveurs (Phase 3 + Phase 4)

#### Configuration
- Section `[mcp.phase4]` dans `config.toml` pour activation globale
- Auto-détection des serveurs démarrés

---

*Generated for AI coding agents working on the Kimi Proxy Dashboard project.*
*Version: 2.4.0*
