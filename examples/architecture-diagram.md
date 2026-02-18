# Diagramme d'Architecture - Kimi Proxy Dashboard v2.0

## Architecture Cible (Modulaire)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COUCHE PRÉSENTATION                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  static/index.html (SPA Vanilla JS + TailwindCSS + Chart.js)               │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COUCHE API (FastAPI)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  api/router.py                                                              │
│  ├── / (Dashboard)                                                          │
│  ├── /ws (WebSocket temps réel)                                            │
│  ├── /chat/completions (Proxy LLM)                                         │
│  ├── /api/sessions/* (Gestion sessions)                                    │
│  ├── /api/providers/* (Providers & Modèles)                                │
│  ├── /api/export/* (CSV/JSON)                                              │
│  ├── /api/sanitizer/* (Phase 1)                                            │
│  ├── /api/memory/* (Phase 2 MCP)                                           │
│  └── /api/compress/* (Phase 3)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COUCHE SERVICES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  services/                                                                  │
│  ├── websocket_manager.py    # ConnectionManager (broadcast temps réel)     │
│  ├── rate_limiter.py         # Rate limiting par provider                   │
│  └── alerts.py               # Seuils et notifications                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COUCHE PROXY (HTTPX)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  proxy/                                                                     │
│  ├── router.py               # Routing vers providers                       │
│  ├── client.py               # Client HTTPX async                         │
│  ├── transformers.py         # Conversion formats (Gemini, etc.)          │
│  └── stream.py               # Gestion streaming SSE                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COUCHE FEATURES (Modules métier)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   SANITIZER     │  │  MCP MEMORY     │  │  COMPRESSION    │             │
│  │   (Phase 1)     │  │  (Phase 2)      │  │  (Phase 3)      │             │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤             │
│  │ • Masking       │  │ • Détection     │  │ • Heuristique   │             │
│  │ • Routing       │  │ • Comptage      │  │ • Résumé LLM    │             │
│  │   dynamique     │  │ • Ratio mémoire │  │ • Log stats     │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    LOG WATCHER                                  │       │
│  │  • Surveillance ~/.continue/logs/core.log                       │       │
│  │  • Parsing CompileChat bloc                                     │       │
│  │  • Détection erreurs API                                        │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COUCHE CORE (Fondation)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  core/                                                                      │
│  ├── tokens.py               # Tiktoken (cl100k_base)                       │
│  ├── database.py             # SQLite + migrations                          │
│  ├── models.py               # Dataclasses métier                           │
│  ├── constants.py            # Constantes globales                          │
│  └── exceptions.py           # Exceptions custom                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COUCHE CONFIGURATION                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  config/                                                                    │
│  ├── loader.py               # Chargement TOML/YAML                         │
│  ├── settings.py             # Dataclasses settings                         │
│  └── constants.py            # Valeurs par défaut                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE EXTERNE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Kimi Code   │  │   NVIDIA     │  │   Mistral    │  │    Groq      │   │
│  │  (256K)      │  │  (256K)      │  │  (32K-256K)  │  │   (131K)     │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │ OpenRouter   │  │ SiliconFlow  │  │   Gemini     │                      │
│  │   (128K)     │  │  (131K-164K) │  │    (1M)      │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                   Continue.dev (PyCharm/VSCode)                  │       │
│  │                      Client IDE principal                        │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Flux de Données

```
Requête Continue.dev
        │
        ▼
┌───────────────┐
│  /chat/completions  │
│   (FastAPI)   │
└───────────────┘
        │
        ├──► Sanitizer (masking si >1000 tokens)
        │
        ├──► MCP Analyzer (détection mémoire)
        │
        ├──► Token Counter (comptage précis)
        │
        ├──► Rate Limiter (throttling)
        │
        ▼
┌───────────────┐
│  Proxy Router │
│ (Sélection    │
│  provider)    │
└───────────────┘
        │
        ├──► Provider API (HTTPX)
        │
        ◄──► Streaming Response (SSE)
        │
        ▼
┌───────────────┐
│  Extraction   │
│  tokens réels │
└───────────────┘
        │
        ├──► SQLite (persistence)
        │
        ├──► WebSocket (broadcast temps réel)
        │
        ▼
┌───────────────┐
│   Dashboard   │
│   (Frontend)  │
└───────────────┘
```

## Dépendances entre Modules

```
                    main.py (FastAPI App)
                         │
       ┌─────────────────┼─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
  api/router      services/          proxy/
       │         ├─ websocket           │
       │         ├─ rate_limiter        │
       │         └─ alerts              │
       │                                │
       ├────────────────────────────────┘
       │
       ▼
  features/
  ├─ sanitizer/
  │   ├─ masking ◄──┐
  │   └─ routing ◄──┤
  ├─ mcp/ ◄─────────┤
  ├─ compression ◄──┤
  └─ log_watcher ◄──┘
       │
       ▼
  core/ ◄──────────┐
  ├─ tokens        │
  ├─ database      │
  └─ constants     │
       │           │
       └───────────┘
            │
            ▼
       config/
```

## Structure des Imports

```python
# Niveau 1: Core (pas de dépendances internes)
from kimi_proxy.core.tokens import count_tokens_tiktoken
from kimi_proxy.core.database import get_db
from kimi_proxy.core.constants import DEFAULT_MAX_CONTEXT

# Niveau 2: Config (dépend de core pour validation)
from kimi_proxy.config.settings import Settings

# Niveau 3: Features (dépendent de core + config)
from kimi_proxy.features.sanitizer.masking import ContentMasker
from kimi_proxy.features.mcp.analyzer import MCPAnalyzer
from kimi_proxy.features.log_watcher.watcher import LogWatcher

# Niveau 4: Services (dépendent de features)
from kimi_proxy.services.websocket_manager import ConnectionManager
from kimi_proxy.services.rate_limiter import RateLimiter

# Niveau 5: Proxy (dépend de core + config)
from kimi_proxy.proxy.router import get_target_url_for_session

# Niveau 6: API (dépend de tout)
from kimi_proxy.api.routes.sessions import router as sessions_router
```

## Avantages de la Structure Modulaire

| Aspect | Avantages |
|--------|-----------|
| **Testabilité** | Tests unitaires par module, mocks facilités |
| **Maintenabilité** | Changements isolés, impact limité |
| **Lisibilité** | Responsabilités claires, navigation facilitée |
| **Évolutivité** | Nouvelles features sans toucher l'existant |
| **Revue de code** | PRs plus petites et ciblées |
| **Onboarding** | Nouveaux devs comprennent plus vite |

## Points d'Attention lors de la Migration

1. **Imports circulaires**: Utiliser `TYPE_CHECKING` et imports lazy
2. **Singletons**: ConnectionManager, LogWatcher doivent rester singletons
3. **Configuration**: Charger une seule fois au démarrage
4. **Base de données**: Conserver le fichier sessions.db existant
5. **Chemins**: Utiliser `pathlib.Path` pour la portabilité
