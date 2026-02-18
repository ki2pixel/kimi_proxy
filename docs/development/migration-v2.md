# Migration v1.0 → v2.0 : Le Grand Déménagement

**TL;DR**: J'ai transformé mon monolithe de 3,073 lignes en une maison modulaire de 52 pièces. Voici comment j'ai fait, et comment tu peux faire pareil.

## L'histoire de cette migration

### Le point de rupture
Un matin de février, j'ai voulu ajouter le support de Gemini. Simple, non? Sauf que pour modifier une fonction dans le sanitizer, je devais toucher à 15 autres endroits. Chaque modification était un pari.

J'ai réalisé que j'étais en train de construire un château de cartes. Une seule fausse manœuvre et tout s'effondrerait.

### La décision
À 10h du matin, j'ai pris une décision radicale : tout démanteler et reconstruire. Pas petit à petit. Un vrai remodelage complet.

## Ce qui a changé

### ❌ Avant : Le Studio de 10m²
```
kimi-proxy/
├── main.py           # 3,073 lignes - tout mélangé
├── start.sh          # Script bash simple
├── stop.sh           # Script bash simple
└── static/index.html # Frontend
```

**Les problèmes** :
- **Impossible à tester** : Pour tester les tokens, je devais démarrer toute l'application
- **Développement paralysant** : Chaque modification risquait de casser quelque chose
- **Nouvelles features = cauchemar** : Ajouter une fonctionnalité signifiait modifier 15 fichiers
- **Debug = chasse au trésor** : "Error in main.py line 1842"

### ✅ Après : La Maison Organisée
```
kimi-proxy/
├── bin/
│   ├── kimi-proxy           # CLI avec sous-commandes
│   ├── kimi-proxy-start     # Alias (compatible)
│   ├── kimi-proxy-stop      # Alias (compatible)
│   └── kimi-proxy-test      # Alias (compatible)
│
├── src/kimi_proxy/
│   ├── main.py              # ~200 lignes - App factory
│   ├── __main__.py          # Point d'entrée CLI
│   │
│   ├── core/                # Fondations (pas de dépendances)
│   │   ├── exceptions.py
│   │   ├── constants.py
│   │   ├── tokens.py
│   │   ├── models.py
│   │   └── database.py
│   │
│   ├── config/              # Configuration
│   │   ├── loader.py
│   │   ├── settings.py
│   │   └── display.py
│   │
│   ├── features/            # Fonctionnalités autonomes
│   │   ├── log_watcher/
│   │   ├── sanitizer/
│   │   ├── mcp/
│   │   └── compression/
│   │
│   ├── proxy/               # Routage HTTP
│   │   ├── router.py
│   │   ├── transformers.py
│   │   ├── stream.py
│   │   └── client.py
│   │
│   ├── services/            # Services partagés
│   │   ├── websocket_manager.py
│   │   ├── rate_limiter.py
│   │   └── alerts.py
│   │
│   └── api/                 # Routes FastAPI
│       ├── router.py
│       └── routes/
│           ├── sessions.py
│           ├── providers.py
│           ├── proxy.py
│           └── ...
│
├── tests/                    # Tests structurés
│   ├── unit/                # Tests par module
│   ├── integration/         # Tests d'intégration
│   └── e2e/                 # Tests end-to-end
│
└── docs/                     # Documentation
```

**Les bénéfices** :
- **Tests rapides** : Je teste `core/tokens.py` seul en 0.001s
- **Développement précis** : Je sais exactement quel fichier modifier
- **Nouvelles features = plaisir** : J'ajoute Gemini en 2 heures
- **Debug = localisé** : "Error in features/sanitizer/masking.py line 42"
│   ├── __main__.py          # Point d'entrée CLI
│   ├── core/                # Cœur métier
│   ├── config/              # Configuration
│   ├── features/            # Fonctionnalités
│   ├── proxy/               # Logique proxy
│   ├── services/            # Services métier
│   └── api/                 # Routes API
│
├── scripts/
│   ├── migrate.sh           # Migration données
│   └── backup.sh            # Backup DB
│
└── tests/                   # Tests structurés
```

### Commandes

| Ancienne Commande | Nouvelle Commande |
|-------------------|-------------------|
| `./start.sh` | `./scripts/start.sh` (avec MCP auto) ou `./bin/kimi-proxy start` |
| `./stop.sh` | `./scripts/stop.sh` (avec MCP auto) ou `./bin/kimi-proxy stop` |
| `./test_dashboard.sh` | `./bin/kimi-proxy test` |
| `python main.py` | `PYTHONPATH=src python -m kimi_proxy` |

**Nouveauté**: Les scripts `./scripts/start.sh` et `./scripts/stop.sh` intègrent maintenant automatiquement les serveurs MCP externes (Phase 3).

Nouvelles commandes disponibles:
```bash
./bin/kimi-proxy status     # Voir le statut
./bin/kimi-proxy logs       # Voir les logs
./bin/kimi-proxy restart    # Redémarrer
./bin/kimi-proxy shell      # Shell Python
```

**Démarrage avec MCP automatique (recommandé):**
```bash
./scripts/start.sh   # Démarre MCP + Proxy
./scripts/stop.sh    # Arrête Proxy + MCP
```

### Imports

**Avant (v1.0):**
```python
# Tout était dans main.py
from main import app, manager, log_watcher
```

**Après (v2.0):**
```python
# Imports modulaires
from kimi_proxy.core.database import get_db
from kimi_proxy.services.websocket_manager import get_connection_manager
from kimi_proxy.features.log_watcher import create_log_watcher
from kimi_proxy.config.loader import get_config
```

### Configuration

La configuration reste dans `config.toml` au niveau projet. Le loader la trouve automatiquement.

## Migration des Données

### Base de Données

La base de données SQLite (`sessions.db`) est conservée et les migrations sont appliquées automatiquement au démarrage:

```python
# Dans main.py - startup
init_database()  # Crée les tables manquantes
```

Tables migrées automatiquement:
- `sessions` - Ajout colonne `model`
- `metrics` - Ajout colonnes `memory_tokens`, `chat_tokens`, `memory_ratio`
- `masked_content` - Ajout colonnes `tags`, `token_count`
- Nouvelle table: `memory_metrics`
- Nouvelle table: `memory_segments`
- Nouvelle table: `compression_log`

### Backup Avant Migration

```bash
# Créer un backup
./scripts/backup.sh

# Ou manuellement
cp sessions.db sessions.db.backup.$(date +%Y%m%d_%H%M%S)
```

## Procédure de Migration

### 1. Backup

```bash
cd /path/to/kimi-proxy
./scripts/backup.sh
```

### 2. Installation v2.0

```bash
# Mettre à jour le code (git pull ou extraction)

# Créer l'environnement virtuel si nécessaire
python -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
# Ou en mode editable
pip install -e .
```

### 3. Vérification

```bash
# Tester l'import
PYTHONPATH=src python -c "from kimi_proxy.main import create_app; print('OK')"

# Démarrer le serveur
./bin/kimi-proxy start

# Vérifier le statut
./bin/kimi-proxy status
```

### 4. Tests

```bash
# Lancer les tests de régression
./bin/kimi-proxy test

# Ou directement
PYTHONPATH=src python -m pytest tests/e2e/test_regression.py -v
```

## Compatibilité

### API REST

Tous les endpoints REST restent identiques:
- `/chat/completions`
- `/api/sessions`
- `/api/providers`
- `/api/sanitizer/stats`
- `/api/compress/{id}`
- etc.

### WebSocket

Le protocole WebSocket sur `/ws` est inchangé.

### Configuration

Le format de `config.toml` est conservé. Aucune modification nécessaire.

### Database

Le schéma est étendu mais rétro-compatible. Les migrations s'exécutent automatiquement.

## Dépannage

### Problème: "Module not found"

**Solution:**
```bash
export PYTHONPATH=src:$PYTHONPATH
./bin/kimi-proxy start
```

### Problème: "Config file not found"

**Solution:**
Vérifiez que vous exécutez depuis le répertoire projet:
```bash
cd /path/to/kimi-proxy
./bin/kimi-proxy start
```

### Problème: Database locked

**Solution:**
Arrêtez le serveur et redémarrez:
```bash
./bin/kimi-proxy stop
./bin/kimi-proxy start
```

## Rollback

En cas de problème, vous pouvez revenir à v1.0:

```bash
# Arrêter v2.0
./bin/kimi-proxy stop
# ou
./scripts/stop.sh

# Restaurer le backup
cp sessions.db.backup.XXX sessions.db

# Revenir au code v1.0
git checkout v1.0  # ou restaurer l'archive

# Démarrer v1.0
./scripts/start.sh
```

**Note**: Même en rollback vers v1.0, vous pouvez utiliser `./scripts/start.sh` qui reste compatible.

## Questions Fréquentes

**Q: Dois-je modifier ma configuration Continue?**
R: Non, la configuration `config.yaml` reste inchangée.

**Q: Les données historiques sont-elles conservées?**
R: Oui, toutes les sessions et métriques sont préservées.

**Q: Puis-je utiliser les anciens scripts?**
R: Oui, `start.sh` et `stop.sh` sont des liens symboliques vers la nouvelle CLI.

**Q: Comment debugger en mode développement?**
R: Utilisez `PYTHONPATH=src python -m kimi_proxy --reload`

---

*Document de migration pour la version 2.0*
