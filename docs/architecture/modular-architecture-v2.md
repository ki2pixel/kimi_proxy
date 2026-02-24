# Architecture Modulaire v2.0 : La Maison Étagée

**TL;DR**: J'ai transformé un monolithe de 3,073 lignes en 52 modules organisés par étages, chaque étage ne dépendant que de celui en dessous.

Imaginez une maison où chaque étage a sa fonction : le rez-de-chaussée accueille les visiteurs (API), l'étage gère les services (WebSocket), le suivant abrite les fonctionnalités spéciales (Sanitizer), puis vient le routage (Proxy), et les fondations (Core). Chaque étage peut être rénové sans effondrer la maison.

C'est exactement ça mon architecture v2.0.

## Pourquoi j'ai tout démantelé

### ❌ Le monolithe d'avant : La chambre unique
J'avais tout dans un fichier `main.py` de 3,073 lignes. C'était comme vivre dans un studio de 10m² :

- **Impossible à tester** : Pour tester le compteur de tokens, je devais démarrer toute l'application
- **Développement paralysant** : Chaque modification risquait de casser quelque chose à l'autre bout
- **Nouvelles fonctionnalités = cauchemar** : Ajouter le sanitizer signifiait modifier 15 endroits différents
- **Collaboration impossible** : Deux développeurs ne pouvaient pas travailler sur le même fichier

### ✅ L'architecture modulaire : La maison organisée
Maintenant, chaque module a sa responsabilité. Je peux travailler sur le sanitizer sans toucher au proxy. Je peux tester les tokens en isolation. C'est maintenabilité et évolutivité.

| Aspect | Avant (Monolithe) | Après (Modulaire) |
|--------|-------------------|-------------------|
| Fichiers Python | 1 | 52 |
| Lignes main.py | 3,073 | 208 |
| LOC total | 3,073 | 7,784 |
| Tests possibles | 0 | Unit + Integration + E2E |
| Nouvelle feature | Risqué | Simple |
| Debug | Chasse au trésor | Localisé |

## Métriques Architecture (Audit 2026-02-20)

**TL;DR**: L'architecture 5 couches maintient 7784 LOC Python avec complexité moyenne C, optimisée pour maintenance et testabilité.

### Métriques Courantes
- **LOC total** : 7784 (code + commentaires 10958)
- **Fichiers** : 70 Python
- **Complexité moyenne** : C (17.07)
- **Ratio commentaires/code** : 40.8%

### Répartition par Couche
| Couche | LOC | Complexité Max | Responsabilités |
| ------ | --- | -------------- | --------------- |
| Core   | 1200 | B | Base de données, tokens, modèles |
| Proxy  | 1800 | F | Routage, streaming, transformations |
| Features| 2500 | D | MCP, sanitizer, compression |
| Services| 1500 | C | WebSocket, rate limiting |
| API    | 784 | C | Routes FastAPI |

### Évolution Complexité
La montée en complexité (F dans proxy) reflète l'ajout de gestion d'erreurs robuste, justifiant la documentation détaillée selon Pattern 6.

### Règle d'Or : Complexité Proportionnelle à la Robustesse
Accepter complexité F quand elle apporte résilience (retry, extraction partielle) plutôt que simplicité fragile.

## Les 5 étages de la maison

### Rez-de-chaussée : API Layer (`src/kimi_proxy/api/`)
**La porte d'entrée** - C'est ce que voient les utilisateurs. FastAPI avec tous les endpoints REST.

```python
# api/routes/sessions.py
@app.post("/api/sessions")
async def create_session(session_data: SessionCreate):
    # Logique métier déléguée aux couches inférieures
    return session_service.create(session_data)
```

**Règle d'or** : L'API ne fait que de la validation et du routage. Zéro logique métier.

### 1er étage : Services Layer (`src/kimi_proxy/services/`)
**Les services communs** - WebSocket, rate limiting, alertes. Partagés par toute la maison.

```python
# services/websocket_manager.py
def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
```

**Pattern** : Singleton via factory functions pour éviter les imports circulaires.

### 2ème étage : Features Layer (`src/kimi_proxy/features/`)
**Les fonctionnalités spéciales** - Sanitizer, MCP, compression, Log Watcher. Chaque feature est un appartement indépendant.

```
features/
├── sanitizer/     # Masquage automatique
├── mcp/          # Mémoire standardisée  
├── compression/  # Compression d'urgence
└── log_watcher/  # Surveillance PyCharm
```

**Avantage** : Je peux désactiver le sanitizer sans casser le reste.

### 3ème étage : Proxy Layer (`src/kimi_proxy/proxy/`)
**Le standard téléphonique** - Routage intelligent vers 8 providers LLM.

```python
# proxy/router.py
def route_request(provider: str, model: str):
    config = get_provider_config(provider)
    return ProviderClient(config)
```

**Défi** : Chaque provider a son format. Gemini utilise `contents`, OpenAI utilise `messages`. Les transformers gèrent la conversion.

### Fondations : Core Layer (`src/kimi_proxy/core/`)
**Les fondations** - Database, tokens, models, constants. Tout ce qui ne dépend de personne.

```python
# core/tokens.py
def count_tokens_tiktoken(text: str) -> int:
    return len(ENCODING.encode(text))
```

**Principe** : Importable par tout le monde, ne dépend de personne.

## Le voyage d'une requête : De l'IDE à l'API

### Scénario : Je demande de l'aide pour du code dans PyCharm

```
Continue.dev (PyCharm)
    │ "Help me debug this function"
    ▼
API Layer (/chat/completions)
    │ Validation + parsing
    ▼
Features Layer (Sanitizer vérifie si y'a du bruit)
    │ "Pas de tools/console, tout va bien"
    ▼
Proxy Layer (Router vers Kimi Code)
    │ "Format OpenAI → Format Kimi"
    ▼
Services Layer (Rate Limiter)
    │ "OK, pas de limite dépassée"
    ▼
Provider API (kimi.com)
    │ Réponse streaming avec tokens
    ▼
Core Layer (Database sauvegarde)
    │ 1500 tokens entrants, 800 sortants
    ▼
Services Layer (WebSocket broadcast)
    │ "Nouvelle métrique pour session #42"
    ▼
Dashboard (Mise à jour temps réel)
    │ Jauge : 45% → 52%
```

**La magie** : Chaque étage fait sa job sans se soucier des autres. Le sanitizer peut être désactivé, le proxy peut changer de provider, le dashboard continue de fonctionner.

## Feature exemple : Cline (local) (import lecture seule)

Tu utilises Cline sur ta machine; Cline conserve déjà des métriques d’usage dans un ledger local.

L’objectif de Kimi Proxy n’est pas de “se brancher” à Cline, ni de lire des conversations. C’est juste d’importer des chiffres (tokens/cost) de manière sûre.

### ✅ Le flux (dans la maison 5 étages)

```
Ledger local allowlisté (taskHistory.json)
  -> Features: ClineImporter (parsing strict + refus symlink)
  -> Core: SQLite (cline_task_usage)
  -> API: /api/cline/* (import, usage, status)
  -> Services: polling optionnel + broadcast WebSocket
  -> UI: section "Cline (local)" du dashboard
```

### Surface de sécurité

### ❌ Un lecteur de fichiers générique

Accepter un chemin arbitraire fourni par l’utilisateur devient immédiatement une surface d’exfiltration.

### ✅ Allowlist strict + stockage minimal

- Un seul chemin exact est autorisé : `/home/kidpixel/.cline/data/state/taskHistory.json`.
- Le code refuse symlinks/redirections.
- Seules des métriques numériques sont stockées; aucun prompt/log/conversation.

Documentation: `docs/features/cline.md`.

## Les règles de la maison : Imports et dépendances

### La règle d'or des imports
```
Core peut importer personne
Config peut importer Core seulement
Features peuvent importer Core + Config
Proxy peut importer Core + Config
Services peuvent importer tout sauf API
API peut importer tout le monde
```

### Le piège des imports circulaires
J'ai eu ce problème : ConnectionManager avait besoin de WebSocket, mais WebSocket avait besoin de ConnectionManager.

**Solution** : TYPE_CHECKING au secours!

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import WebSocket
    from kimi_proxy.core.models import Session

class ConnectionManager:
    async def connect(self, websocket: "WebSocket") -> None:
        # WebSocket est une string, pas un vrai import
```

### Les imports paresseux (lazy)
Pour les modules lourds comme les transformers de provider :

```python
def get_gemini_transformer():
    from .transformers import GeminiTransformer  # Import à l'exécution
    return GeminiTransformer()
```

**Pourquoi?** Évite de charger 50MB de transformers au démarrage si on utilise jamais Gemini.

## Mes patterns préférés : Ce qui marche vraiment

### Factory Pattern - Le gestionnaire d'objets
Au lieu de créer des instances partout, j'ai des fonctions factory :

```python
# services/websocket_manager.py
_manager: Optional[ConnectionManager] = None

def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
```

**Pourquoi?** Un seul WebSocket manager pour toute l'application. Pas de surprises.

### Context Managers - La gestion propre des ressources
Pour la base de données, j'aime pas les `try/finally` partout :

```python
# core/database.py
@contextmanager
def get_db() -> Generator[sqlite3.Row, None, None]:
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
```

**Usage** :
```python
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sessions")
    # Connexion fermée automatiquement
```

### Dependency Injection - La flexibilité avant tout
Le Log Watcher a besoin de diffuser des messages via WebSocket. Mais je veux pas le coupler :

```python
# features/log_watcher/watcher.py
class LogWatcher:
    def __init__(self, broadcast_callback: Callable = None):
        self.broadcast_callback = broadcast_callback
```

**Dans main.py** :
```python
log_watcher = LogWatcher(broadcast_callback=manager.broadcast)
```

**Résultat** : Je peux tester le Log Watcher sans WebSocket.

## Tests : Comment je vérifie que tout marche

### La structure en 3 niveaux
```
tests/
├── unit/           # Tests rapides, isolés
│   ├── core/test_tokens.py      # Test Tiktoken seul
│   └── features/test_sanitizer.py
├── integration/   # Tests plusieurs modules ensemble
│   └── test_api.py              # API + Database
└── e2e/           # Tests complets, avec serveur
    └── test_regression.py       # Workflow utilisateur
```

### Mon test préféré : Tokens en isolation
```python
# tests/unit/core/test_tokens.py
def test_count_tokens_tiktoken():
    text = "Hello, world!"
    count = count_tokens_tiktoken(text)
    assert count == 4  # Hello, world! = 4 tokens
```

**Pourquoi j'aime** : 0.001s, pas de dépendances, je le lance 100 fois par jour.

### Test E2E : Le vrai scénario
```python
# tests/e2e/test_regression.py
async def test_full_workflow():
    # 1. Démarrer serveur
    # 2. Créer session
    # 3. Envoyer requête proxy
    # 4. Vérifier dashboard update
    # 5. Compresser contexte
    # 6. Vérifier économie tokens
```

**Execution** :
```bash
PYTHONPATH=src python -m pytest tests/ -v
# 23 tests passés en 2.3s
```

## Les bénéfices concrets : Ce que j'ai gagné

### Maintenabilité - La paix de l'esprit
**Avant** : Changer une ligne dans le sanitizer pouvait casser le proxy. Je passais 30 minutes à tracer l'erreur.

**Maintenant** : Je modifie le sanitizer, je lance `python -m pytest tests/unit/features/test_sanitizer.py`, 0.8s plus tard je sais si ça marche.

### Évolutivité - Ajouter des features sans stress
Semaine dernière, j'ai ajouté le support de Gemini. Dans l'ancienne architecture, j'aurais dû modifier 15 fichiers.

**Maintenant** :
1. `proxy/transformers.py` - Ajouté `GeminiTransformer`
2. `config.toml` - Ajouté config Gemini
3. `api/routes/providers.py` - Ajouté Gemini à la liste
4. Tests - 3 tests unitaires

**Total** : 2 heures au lieu de 2 jours.

### Collaboration - On peut travailler à plusieurs
Mon collègue travaille sur le Log Watcher pendant que j'améliore le sanitizer. Zero conflits de merge.

### Débogage - Les erreurs ont une adresse
**Avant** : "Error in main.py line 1842" - Merci, très utile.

**Maintenant** : "Error in features/sanitizer/masking.py line 42" - Je sais exactement où aller.

## La Règle d'Or : Chaque module a une seule raison de changer

**Le principe** : Si un module fait deux choses, il devrait être splité.

- `core/tokens.py` ne fait QUE compter des tokens
- `features/sanitizer.py` ne fait QUE masquer du contenu  
- `proxy/router.py` ne fait QUE router vers les providers

Quand j'ai besoin de modifier le comptage de tokens, je vais dans `core/tokens.py`. Quand j'ai besoin de modifier le sanitizer, je vais dans `features/sanitizer.py. Simple.

## Migration : Comment je suis passé de la chambre à la maison

### Le plan en 5 phases
J'ai fait la migration sur une semaine, par étapes, sans jamais casser le service.

1. **Phase 1 : Extraction Core** - Les fondations d'abord
2. **Phase 2 : Extraction Config** - Configuration isolée  
3. **Phase 3 : Extraction Features** - Fonctionnalités autonomes
4. **Phase 4 : Extraction Proxy** - Routage séparé
5. **Phase 5 : Refactoring Main** - Le fichier principal à 200 lignes

### Le script qui m'a sauvé la vie
```bash
#!/bin/bash
# migrate.sh
echo "Backup de la base de données..."
cp sessions.db sessions.db.backup.$(date +%Y%m%d_%H%M%S)

echo "Migration structure..."
mkdir -p src/kimi_proxy/{core,config,features,proxy,services,api}
# ... création des 52 fichiers

echo "Tests de régression..."
PYTHONPATH=src python -m pytest tests/e2e/test_regression.py

echo "Migration terminée!"
```

### La compatibilité préservée
Les anciens scripts fonctionnent toujours :
```bash
./scripts/start.sh     # Démarre MCP + Proxy (mis à jour pour Phase 3)
./scripts/stop.sh      # Arrête Proxy + MCP (mis à jour pour Phase 3)
./bin/kimi-proxy-start # Alias vers CLI
./bin/kimi-proxy-stop  # Alias vers CLI
./test.sh              # → ./bin/kimi-proxy-test
```

**Note sur les scripts Phase 3 & 4**: `./scripts/start.sh` et `./scripts/stop.sh` intègrent maintenant automatiquement la gestion des serveurs MCP externes:
- **Phase 3**: Qdrant MCP (port 6333) + Context Compression MCP (port 8001)
- **Phase 4**: Shrimp Task Manager MCP (port 8002) + Sequential Thinking MCP (port 8003) + Fast Filesystem MCP (port 8004) + JSON Query MCP (port 8005)

**Pourquoi?** Je voulais pas que mes utilisateurs changent leurs habitudes, tout en apportant les nouvelles fonctionnalités automatiquement.

## Le mot de la fin

Cette architecture modulaire n'est pas juste une question d'organisation. C'est une question de survie pour un projet qui grandit.

Chaque nouvelle feature devient plus facile à ajouter. Chaque bug devient plus rapide à trouver. Chaque test devient plus pertinent à écrire.

**La leçon** : Investir du temps dans l'architecture, c'est se payer du temps pour la suite.

---

*Architecture v2.0 - Modular Monolith Pattern*  
*Construit avec amour et beaucoup de café*
