# Plan de Restructuration - Organisation des Scripts

## Résumé Exécutif

Ce document présente un plan complet de restructuration de l'organisation des scripts du projet **Kimi Proxy Dashboard** pour améliorer la maintenabilité, la scalabilité et la clarté architecturale.

**Impact**: Séparation du monolithe `main.py` (112KB) en modules cohésifs, rationalisation des scripts shell, mise en place d'une architecture évolutive.

---

## 1. Analyse de la Structure Actuelle

### 1.1 Problèmes Identifiés

| Problème | Sévérité | Impact |
|----------|----------|--------|
| `main.py` monolithique (112KB, ~2000 lignes) | 🔴 Critique | Difficulté de maintenance, tests impossibles, risque de régression |
| Scripts dupliqués (racine + `scripts/`) | 🟡 Moyen | Confusion sur les scripts canoniques, divergences possibles |
| Dossier `tools/` vide | 🟢 Faible | Ressource gaspillée, incohérence |
| `src/kimi_proxy/` inexploité | 🟡 Moyen | Structure Python standard non utilisée |
| Pas de distinction dev/prod/test | 🟡 Moyen | Environnements non isolés |

### 1.2 Dépendances Circulaires Potentielles

```
main.py
├── Tokenization → utilisée partout
├── Database → utilisée par tous les modules métier
├── LogWatcher → dépend de ConnectionManager
├── Sanitizer → dépend de Tokenization + Database
├── RateLimiter → indépendant
└── Routes FastAPI → dépendent de TOUS les modules
```

### 1.3 Tableau des Scripts Actuels

| Fichier | Localisation | Taille | Responsabilité | Doublon? |
|---------|-------------|--------|----------------|----------|
| `main.py` | Racine | 112KB | Backend complet | Non |
| `start.sh` | Racine | 1.8KB | Démarrage serveur | Oui (`scripts/`) |
| `stop.sh` | Racine | 1.5KB | Arrêt serveur | Oui (`scripts/`) |
| `test_dashboard.sh` | Racine | 5.0KB | Tests automatisés | Oui (`scripts/`) |
| `start.sh` | `scripts/` | 1.8KB | Démarrage serveur | Oui (racine) |
| `stop.sh` | `scripts/` | 1.5KB | Arrêt serveur | Oui (racine) |
| `test_dashboard.sh` | `scripts/` | 5.0KB | Tests automatisés | Oui (racine) |

---

## 2. Architecture Cible

### 2.1 Principe Directeur : Separation of Concerns (SoC)

```
kimi-proxy/
├── bin/                    # Scripts exécutables (entrées utilisateur)
├── src/kimi_proxy/         # Package Python principal
│   ├── __init__.py
│   ├── __main__.py         # Point d'entrée python -m kimi_proxy
│   ├── config/             # Configuration
│   ├── core/               # Cœur métier (tokenization, DB)
│   ├── features/           # Fonctionnalités (MCP, Sanitizer, Compression)
│   ├── proxy/              # Logique de proxy HTTP
│   ├── api/                # Routes FastAPI
│   └── main.py             # Application FastAPI factory
├── tests/                  # Tests unitaires et d'intégration
├── scripts/                # Scripts utilitaires (CI, migration)
├── docs/                   # Documentation (existant)
└── config/                 # Configurations (existantes)
```

### 2.2 Structure Détaillée du Package Python

```
src/kimi_proxy/
├── __init__.py                    # Version, exports publics
├── __main__.py                    # CLI: python -m kimi_proxy
├── main.py                        # FastAPI app factory
│
├── config/                        # Configuration
│   ├── __init__.py
│   ├── loader.py                  # Chargement TOML/YAML
│   ├── settings.py                # Dataclasses settings
│   └── constants.py               # Constantes globales
│
├── core/                          # Cœur métier (sans dépendances externes)
│   ├── __init__.py
│   ├── tokens.py                  # Tiktoken, comptage
│   ├── database.py                # SQLite, migrations
│   ├── models.py                  # Dataclasses métier
│   └── exceptions.py              # Exceptions custom
│
├── features/                      # Fonctionnalités horizontales
│   ├── __init__.py
│   ├── mcp/                       # Phase 2: Mémoire MCP
│   │   ├── __init__.py
│   │   ├── detector.py            # Détection balises MCP
│   │   ├── analyzer.py            # Analyse tokens mémoire
│   │   └── storage.py             # Stockage métriques mémoire
│   │
│   ├── sanitizer/                 # Phase 1: Masking contenu
│   │   ├── __init__.py
│   │   ├── masking.py             # Logique de masking
│   │   ├── routing.py             # Fallback dynamique
│   │   └── storage.py             # Stockage contenu masqué
│   │
│   ├── compression/               # Phase 3: Compression
│   │   ├── __init__.py
│   │   ├── heuristic.py           # Algorithme compression
│   │   ├── summarizer.py          # Résumé LLM
│   │   └── storage.py             # Log compression
│   │
│   └── log_watcher/               # Log Watcher PyCharm
│       ├── __init__.py
│       ├── watcher.py             # Classe LogWatcher
│       ├── patterns.py            # Regex patterns
│       └── parser.py              # Parsing logs
│
├── proxy/                         # Logique de proxy
│   ├── __init__.py
│   ├── client.py                  # Client HTTPX
│   ├── router.py                  # Routing providers
│   ├── transformers.py            # Conversion formats (Gemini, etc.)
│   └── stream.py                  # Gestion streaming
│
├── api/                           # Couche API (FastAPI)
│   ├── __init__.py
│   ├── deps.py                    # Dépendances FastAPI
│   ├── router.py                  # Router principal
│   ├── routes/                    # Endpoints par domaine
│   │   ├── __init__.py
│   │   ├── sessions.py            # CRUD sessions
│   │   ├── providers.py           # Liste providers/modèles
│   │   ├── proxy.py               # /chat/completions
│   │   ├── exports.py             # CSV/JSON export
│   │   ├── sanitizer.py           # API sanitizer
│   │   ├── mcp.py                 # API mémoire MCP
│   │   ├── compression.py         # API compression
│   │   ├── health.py              # Health check
│   │   └── websocket.py           # WebSocket endpoint
│   └── middleware.py              # Middleware CORS, etc.
│
└── services/                      # Services métier
    ├── __init__.py
    ├── rate_limiter.py            # Rate limiting
    ├── websocket_manager.py       # ConnectionManager
    └── alerts.py                  # Seuils et alertes
```

### 2.3 Organisation des Scripts Shell

```
bin/                               # Scripts utilisateur (PATH-ready)
├── kimi-proxy                     # Commande principale (start|stop|restart|status)
├── kimi-proxy-start               # Alias start
├── kimi-proxy-stop                # Alias stop
└── kimi-proxy-test                # Tests rapides

scripts/                           # Scripts utilitaires (CI, admin)
├── migrate.sh                     # Migration de données
├── backup.sh                      # Backup DB
├── reset-db.sh                    # Reset base de données
└── install.sh                     # Installation dépendances

tests/                             # Tests automatisés
├── unit/                          # Tests unitaires
├── integration/                   # Tests d'intégration
├── e2e/                           # Tests end-to-end
└── conftest.py                    # Fixtures pytest
```

---

## 3. Plan de Migration

### 3.1 Phase 1: Préparation (Sécurisation)

**Objectif**: Sécuriser l'existant avant migration

| Tâche | Fichier(s) | Priorité |
|-------|-----------|----------|
| Créer tests de régression | `tests/e2e/test_regression.py` | P0 |
| Freeze dépendances | `requirements.txt` + `requirements-dev.txt` | P0 |
| Script de backup DB | `scripts/backup.sh` | P1 |
| Validation config | `src/kimi_proxy/config/validator.py` | P1 |

### 3.2 Phase 2: Extraction du Cœur (Core)

**Objectif**: Extraire les modules indépendants

**Séquence d'extraction** (par ordre de dépendance croissante):

```
Étape 1: Core (aucune dépendance interne)
├── core/exceptions.py         # Exceptions custom
├── core/constants.py          # Constantes DEFAULT_MAX_CONTEXT, etc.
├── core/tokens.py             # ENCODING, count_tokens_tiktoken()
└── core/models.py             # Dataclasses Session, Metric, etc.

Étape 2: Database (dépend de core/)
└── core/database.py           # init_database(), get_db(), migrations

Étape 3: Features individuelles (dépendent de core/)
├── features/rate_limiter.py   # RateLimiter
├── features/log_watcher/      # LogWatcher
├── features/sanitizer/        # Sanitizer
├── features/mcp/              # MCP Memory
└── features/compression/      # Compression

Étape 4: Services (dépendent des features)
├── services/websocket_manager.py
└── services/alerts.py

Étape 5: Proxy (dépend de core/ + features/)
└── proxy/

Étape 6: API (dépend de tout)
└── api/

Étape 7: Main
└── main.py (factory app)
```

### 3.3 Phase 3: Migration Scripts Shell

| Action | Source | Cible | Maintien compatibilité |
|--------|--------|-------|----------------------|
| Déplacer scripts canoniques | `./start.sh` | `bin/kimi-proxy-start` | Lien symbolique |
| Déplacer scripts canoniques | `./stop.sh` | `bin/kimi-proxy-stop` | Lien symbolique |
| Créer CLI unifiée | - | `bin/kimi-proxy` | Nouveau |
| Scripts utilitaires | `./scripts/*` | `scripts/` (nettoyé) | Conservation |

**Mise à jour Post-Migration (2026-02-15): Intégration MCP**

Les scripts `scripts/start.sh` et `scripts/stop.sh` ont été mis à jour pour intégrer automatiquement la gestion des serveurs MCP externes (Phase 3):

```bash
# scripts/start.sh - Flux mis à jour
1. Vérification port 8000
2. Activation venv
3. Vérification dépendances
4. 🆕 Démarrage MCP servers (./scripts/start-mcp-servers.sh start)
5. Lancement FastAPI

# scripts/stop.sh - Flux mis à jour
1. Arrêt FastAPI
2. Nettoyage PID
3. 🆕 Arrêt MCP servers (./scripts/start-mcp-servers.sh stop)
4. Nettoyage final
```

**Avantages de cette intégration:**
- Démarrage en une seule commande: `./scripts/start.sh`
- Arrêt propre avec timeouts: `./scripts/stop.sh`
- Scripts idempotents (peuvent être exécutés plusieurs fois sans effets de bord)
- Logging cohérent avec couleurs et emojis
- Gestion d'erreurs gracieuse (le proxy continue si MCP échoue)

### 3.4 Phase 4: Refactoring `main.py`

**Avant**:
```python
# main.py (~2000 lignes)
import ...  # 20+ imports

# Constantes globales
# Fonctions utilitaires
# Classes métier (RateLimiter, LogWatcher, etc.)
# Routes FastAPI
# Logique proxy

if __name__ == "__main__":
    uvicorn.run(...)
```

**Après**:
```python
# src/kimi_proxy/main.py (~50 lignes)
from fastapi import FastAPI
from contextlib import asynccontextmanager

from .core.database import init_database
from .services.websocket_manager import manager
from .features.log_watcher import log_watcher
from .api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    await log_watcher.start()
    yield
    await log_watcher.stop()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(api_router)
    return app

app = create_app()
```

---

## 4. Spécifications Techniques

### 4.1 Interface entre Modules

**Core/Database**:
```python
# src/kimi_proxy/core/database.py
from contextlib import contextmanager
import sqlite3
from typing import Generator

DATABASE_FILE = "sessions.db"

@contextmanager
def get_db() -> Generator[sqlite3.Row, None, None]:
    """Context manager pour les connexions DB."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

**Features/Sanitizer**:
```python
# src/kimi_proxy/features/sanitizer/masking.py
from typing import List, Tuple, Dict
from ...core.tokens import count_tokens_text

class ContentMasker:
    def __init__(self, threshold_tokens: int = 1000):
        self.threshold = threshold_tokens
    
    def sanitize(self, messages: List[dict]) -> Tuple[List[dict], Dict]:
        """Retourne (messages_sanitizés, métadonnées)."""
        ...
```

**API/Routes**:
```python
# src/kimi_proxy/api/routes/sessions.py
from fastapi import APIRouter, Depends
from ...core.database import get_db

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("")
async def create_session(data: SessionCreate, db = Depends(get_db)):
    ...
```

### 4.2 Gestion des Imports Circulaires

**Solution**: Utiliser `TYPE_CHECKING` et imports lazy

```python
# src/kimi_proxy/services/websocket_manager.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket

class ConnectionManager:
    # Pas d'import au top level
    async def connect(self, websocket: "WebSocket"):
        ...
```

### 4.3 Configuration Unifiée

```python
# src/kimi_proxy/config/settings.py
from dataclasses import dataclass
from pathlib import Path
import tomllib

@dataclass(frozen=True)
class SanitizerConfig:
    enabled: bool = True
    threshold_tokens: int = 1000
    preview_length: int = 200

@dataclass(frozen=True)
class Settings:
    sanitizer: SanitizerConfig
    default_provider: str = "managed:kimi-code"
    default_max_context: int = 262144
    
    @classmethod
    def from_toml(cls, path: Path) -> "Settings":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(...)
```

---

## 5. Scripts de Transition

### 5.1 Script de Migration des Données

```bash
#!/bin/bash
# scripts/migrate.sh - Migration vers nouvelle structure

set -e

echo "🔄 Migration Kimi Proxy Dashboard"
echo "=================================="

# Backup
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp sessions.db "$BACKUP_DIR/"
cp config.toml "$BACKUP_DIR/"
echo "✅ Backup créé: $BACKUP_DIR"

# Vérification structure
if [ ! -d "src/kimi_proxy" ]; then
    echo "❌ Structure cible non trouvée. Abandon."
    exit 1
fi

# Tests de régression
echo "🧪 Exécution des tests de régression..."
python -m pytest tests/e2e/test_regression.py -v

echo "✅ Migration prête!"
echo "Pour finaliser: ./bin/kimi-proxy-start"
```

### 5.2 Script d'Installation

```bash
#!/bin/bash
# scripts/install.sh - Installation initiale

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .  # Mode editable

# Création liens symboliques pour compatibilité
ln -sf bin/kimi-proxy-start start.sh
ln -sf bin/kimi-proxy-stop stop.sh

echo "✅ Installation terminée"
```

---

## 6. Tests et Validation

### 6.1 Plan de Tests

| Type | Couverture | Outil | CI |
|------|-----------|-------|-----|
| Unitaires | Modules core | pytest | ✅ |
| Intégration | API endpoints | pytest + httpx | ✅ |
| E2E | Flux complet | bash + curl | ✅ |
| Performance | Charge proxy | locust | Optionnel |

### 6.2 Tests de Non-Régression

```python
# tests/e2e/test_regression.py
import pytest
import httpx

@pytest.mark.asyncio
async def test_proxy_streaming():
    """Test que le proxy streaming fonctionne toujours."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/chat/completions",
            json={"messages": [{"role": "user", "content": "test"}]}
        )
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_websocket_connection():
    """Test que WebSocket broadcast fonctionne."""
    ...
```

---

## 7. Documentation à Mettre à Jour

| Document | Modifications |
|----------|--------------|
| `README.md` | Nouvelle structure, commandes d'installation |
| `AGENTS.md` | Architecture modulaire, guide contribution |
| `docs/architecture/README.md` | Diagrammes nouvelle structure |
| `docs/development/README.md` | Guide développement avec nouvelle structure |

---

## 8. Calendrier de Migration

| Phase | Durée Estimée | Livrables |
|-------|--------------|-----------|
| Phase 1: Préparation | 2h | Tests régression, backup |
| Phase 2: Extraction Core | 4h | Modules core fonctionnels |
| Phase 3: Extraction Features | 6h | Toutes les features migrées |
| Phase 4: API & Main | 3h | Nouvelle structure API |
| Phase 5: Scripts Shell | 2h | CLI unifiée |
| Phase 6: Tests & Doc | 3h | Tests passants, doc à jour |
| **Total** | **~20h** | Structure complète migrée |

---

## 9. Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Régression fonctionnelle | Moyenne | Élevé | Tests E2E complets avant chaque phase |
| Imports circulaires | Moyenne | Moyen | Outil `import-linter` en CI |
| Perte données | Faible | Critique | Backup automatique avant migration |
| Incompatibilité Continue | Faible | Élevé | Tests avec vraies requêtes Continue |
| Performance dégradée | Faible | Moyen | Benchmarks avant/après |

---

## 10. Checklist de Validation Finale

- [ ] `bin/kimi-proxy start` fonctionne
- [ ] `bin/kimi-proxy stop` fonctionne
- [ ] Dashboard accessible sur http://localhost:8000
- [ ] WebSocket temps réel fonctionne
- [ ] Proxy Continue fonctionne (requête test)
- [ ] Export CSV/JSON fonctionne
- [ ] Log Watcher détecte les tokens
- [ ] Sanitizer masque les contenus verbeux
- [ ] MCP Memory tracking fonctionne
- [ ] Compression manuelle fonctionne
- [ ] Tous les tests passent

---

*Document créé le 2026-02-15*
*Version: 1.0*
*Auteur: Assistant Claude*
