# Phase 1: Infrastructure de Base - Context Compaction

## Vue d'ensemble

Cette phase implémente l'infrastructure de base pour la gestion avancée de la compaction du contexte LLM dans Kimi Proxy Dashboard. Inspirée de l'implémentation Kimi CLI, cette fonctionnalité permet de réduire automatiquement la taille du contexte en préservant les messages récents et en résumant l'historique.

## Fonctionnalités

### 1. Service SimpleCompaction (`features/compaction/`)

#### Classe `SimpleCompaction`
- **Stratégie de compaction**:
  1. Préserve tous les messages système
  2. Garde les N derniers échanges configurables (défaut: 2 échanges = 4 messages)
  3. Résume les messages intermédiaires en un message de contexte
  4. Calculs précis avec Tiktoken (cl100k_base)

#### Configuration
```python
CompactionConfig(
    max_preserved_messages=2,      # Nombre d'échanges récents à préserver
    preserve_system_messages=True,  # Toujours préserver les messages système
    create_summary=True,            # Créer un résumé des messages supprimés
    summary_max_length=1000,        # Longueur max du résumé
    min_messages_to_compact=6,      # Minimum de messages pour déclencher
    min_tokens_to_compact=500,      # Minimum de tokens pour déclencher
    target_reduction_ratio=0.60     # Objectif de réduction (60%)
)
```

### 2. Extensions Base de Données

#### Nouvelles colonnes dans `sessions`:
- `reserved_tokens`: Tokens réservés pour la compaction
- `compaction_count`: Nombre de compactions effectuées
- `last_compaction_at`: Date de dernière compaction

#### Nouvelle table `compaction_history`:
```sql
CREATE TABLE compaction_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_saved INTEGER NOT NULL,
    preserved_messages INTEGER NOT NULL,
    summarized_messages INTEGER NOT NULL,
    compaction_ratio REAL NOT NULL,
    trigger_reason TEXT
);
```

### 3. API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/compaction/{session_id}` | POST | Déclencher une compaction manuelle |
| `/api/compaction/{session_id}/stats` | GET | Statistiques de compaction d'une session |
| `/api/compaction/stats` | GET | Statistiques globales |
| `/api/compaction/{session_id}/history` | GET | Historique des compactions |
| `/api/compaction/{session_id}/reserved` | POST | Configurer les tokens réservés |
| `/api/compaction/{session_id}/simulate` | POST | Simuler une compaction |

### 4. WebSocket Events

Les événements suivants sont diffusés en temps réel:

```json
{
  "type": "compaction_event",
  "session_id": 1,
  "timestamp": "2026-02-15T14:30:00",
  "compaction": {
    "compacted": true,
    "original_tokens": 10000,
    "compacted_tokens": 4000,
    "tokens_saved": 6000,
    "compaction_ratio": 60.0
  }
}
```

### 5. Modèles Étendus

#### `Session` (ajouts):
- `reserved_tokens: int`
- `compaction_count: int`
- `last_compaction_at: Optional[str]`

#### `StatusSnapshot` (nouveau):
- `context_usage_reserved: float` - Pourcentage avec réservation
- `compaction_ready: bool` - Compaction recommandée

#### `CompactionHistoryEntry` (nouveau):
- Historique complet des opérations de compaction

## Configuration

Ajoutez dans `config.toml`:

```toml
[compaction]
enabled = true
threshold_percentage = 80
max_preserved_messages = 2
min_tokens_to_compact = 500
min_messages_to_compact = 6
target_reduction_ratio = 0.60
reserved_tokens = 5000

[compaction.auto]
auto_compact = false
auto_compact_cooldown = 5
```

## Migration

Pour migrer une base de données existante:

```bash
# Option 1: Script automatisé
./scripts/migrate_compaction.sh

# Option 2: SQL manuel
sqlite3 sessions.db < scripts/migrate_compaction.sql

# Option 3: Au démarrage de l'application
# Les migrations sont appliquées automatiquement
```

## Tests

```bash
# Tests unitaires
PYTHONPATH=src python -m pytest tests/unit/features/test_compaction.py -v

# Tests avec couverture
PYTHONPATH=src python -m pytest tests/unit/features/test_compaction.py --cov=src.kimi_proxy.features.compaction
```

## Utilisation

### Exemple de compaction manuelle

```python
from kimi_proxy.features.compaction import SimpleCompaction, CompactionConfig

# Crée le compacteur
config = CompactionConfig(max_preserved_messages=3)
compactor = SimpleCompaction(config)

# Messages à compacter
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Question 1..."},
    {"role": "assistant", "content": "Answer 1..."},
    # ... plus de messages
]

# Compacter
result = compactor.compact(messages, session_id=1)

if result.compacted:
    print(f"Économie: {result.tokens_saved} tokens ({result.compaction_ratio:.1f}%)")
```

### Exemple via API

```bash
# Simuler une compaction
curl -X POST http://localhost:8000/api/compaction/1/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [...],
    "preserve_messages": 2
  }'

# Voir les statistiques
curl http://localhost:8000/api/compaction/1/stats

# Configurer les tokens réservés
curl -X POST http://localhost:8000/api/compaction/1/reserved \
  -H "Content-Type: application/json" \
  -d '{"reserved_tokens": 5000}'
```

## Métriques

Le système fournit les métriques suivantes:

- **Tokens économisés**: Total des tokens économisés par compaction
- **Ratio de compaction**: Pourcentage moyen de réduction
- **Nombre de compactions**: Par session et global
- **Timeline**: Historique chronologique avec cumuls

## Prochaines Étapes

Cette Phase 1 pose les bases pour:
- Phase 2: Compression avancée avec LLM pour résumé intelligent
- Phase 3: Compaction automatique avec seuils configurables
- Phase 4: Intégration avec le proxy pour compaction transparente

## Références

- [Kimi CLI Context Compaction](https://docs.kimi.com/cli/context-management)
- [Tiktoken Documentation](https://github.com/openai/tiktoken)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
