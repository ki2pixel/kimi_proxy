# Core Layer - Logique Fondamentale

## TL;DR
Couche fondamentale sans dépendances externes gérant database SQLite, comptage tokens Tiktoken précis, et structures données typées avec migrations asynchrones.

## Problème
La couche core contient la logique critique (database, tokens, models) sans documentation centralisée, créant des risques de régression et difficultés de maintenance.

## Architecture 5 Couches
Le Core Layer est la couche la plus basse, sans dépendances externes, fournissant les fondations à toutes les couches supérieures.

```
API Layer ← Services Layer ← Features Layer ← Proxy Layer ← Core Layer (SQLite, Tiktoken, Models)
```

## Composants Principaux

### Database
**Localisation** : `src/kimi_proxy/core/database.py`
**Responsabilités** :
- Gestion SQLite asynchrone avec aiosqlite
- Système de migrations automatiques
- Connection pooling et gestion transactions
- Backup et recovery

**Fonction Critique** : `_run_migrations` (Score C - 11)
```python
async def _run_migrations(conn: aiosqlite.Connection):
    """Applique les migrations en ordre séquentiel"""
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Migration 1: Sessions table
    await apply_migration(conn, 1, '''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
```

### Tokens
**Localisation** : `src/kimi_proxy/core/tokens.py`
**Responsabilités** :
- Comptage tokens précis avec Tiktoken
- Support multiple encodings (cl100k_base, p50k_base)
- Calcul cumulatif contexte conversation
- Validation limites modèles

**Fonction Critique** : `count_tokens_tiktoken` (Score C - 15)
```python
def count_tokens_tiktoken(text: str, model: str = "gpt-4") -> int:
    """Comptage précis OBLIGATOIRE - pas d'estimation"""
    import tiktoken
    
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback vers encoding par défaut
        encoding = tiktoken.get_encoding("cl100k_base")
    
    return len(encoding.encode(text))
```

### Models
**Localisation** : `src/kimi_proxy/core/models.py`
**Responsabilités** :
- Structures données typées avec TypedDict
- Validation et sérialisation
- Interfaces immuables
- Conversion entre formats

**Exemples** :
```python
class TokenUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class Session(TypedDict):
    id: str
    created_at: str
    updated_at: str
    metrics: TokenUsage
    status: str
```

### Constants & Exceptions
**Localisation** : `src/kimi_proxy/core/constants.py`, `src/kimi_proxy/core/exceptions.py`
**Responsabilités** :
- Constantes globales typées
- Exceptions personnalisées
- Codes d'erreur standardisés
- Messages d'erreur français

## Patterns Système Appliqués

### Pattern 3 - Immutabilité
```python
# ✅ CORRECT - Structures immuables
@dataclass(frozen=True)
class SessionConfig:
    max_tokens: int
    temperature: float
    model: str

# ❌ INCORRECT - Mutable
class SessionConfig:
    def __init__(self, max_tokens, temperature, model):
        self.max_tokens = max_tokens  # Peut être modifié
```

### Pattern 7 - TypedDict Strict
```python
# ✅ CORRECT - Typage strict
class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: str

# ❌ INCORRECT - Any non typé
def process_message(data: Any) -> Any:
    return data  # Pas de validation
```

## Gestion Tokens Précise

### ❌ Approche Estimation (INTERDITE)
```python
def bad_count_tokens(text: str) -> int:
    # APPROXIMATION - 30% d'erreur possible
    return len(text.split()) * 1.3
```

### ✅ Approche Tiktoken (OBLIGATOIRE)
```python
def count_tokens_tiktoken(text: str, model: str = "gpt-4") -> int:
    """Comptage précis avec Tiktoken"""
    import tiktoken
    
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))
```

## Database Migrations

### Versionnement Automatique
```python
async def ensure_database_schema(db_path: str = "sessions.db"):
    """Crée et migre automatiquement la base de données"""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute('PRAGMA foreign_keys = ON')
        await _run_migrations(conn)
        await conn.commit()
```

### Backup Strategy
```python
async def backup_database(source: str, target: str):
    """Backup atomique de la base de données"""
    async with aiosqlite.connect(source) as source_conn:
        await source_conn.backup(target)
```

## Trade-offs
| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| SQLite | Simple, embedded, ACID | Limitations concurrence |
| PostgreSQL | Scalable, concurrent | Complexité déploiement |
| **Choix Kimi Proxy** | **Simplicité maintenabilité** | **Monitoring requis** |

## Golden Rule
**Tout nouveau composant core doit :**
1. Avoir zéro dépendance externe
2. Utiliser typage strict (TypedDict, dataclass)
3. Inclure tests unitaires isolés
4. Gérer erreurs avec exceptions personnalisées
5. Documenter les invariants

## Métriques Actuelles
- **Database** : 13 opérations ALTER TABLE appliquées automatiquement au démarrage
- **Tokens** : Comptage précis 100% (tiktoken)
- **Models** : 25 structures typées
- **Performance** : < 10ms pour comptage tokens

## Invariants Critiques
1. **Zero External Dependencies** : Core layer reste pure
2. **Precise Token Counting** : Jamais d'estimation
3. **Type Safety** : TypedDict obligatoire
4. **Async-First** : Toutes opérations I/O asynchrones
5. **French Error Messages** : Messages localisés

## Prochaines Évolutions
- [ ] Database sharding pour scale
- [ ] Cache tokens LRU
- [ ] Models versionnés
- [ ] Export/import données

---
*Dernière mise à jour : 2026-02-24*  
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*