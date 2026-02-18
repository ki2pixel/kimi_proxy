# MCP Phase 4 - Intégration des 4 Nouveaux Serveurs MCP

**Date**: 2026-02-17  
**Version**: 2.4.0

---

## Vue d'ensemble

La Phase 4 étend l'intégration MCP avec 4 nouveaux serveurs, ajoutant **43 outils** à l'écosystème existant. Ces serveurs sont démarrés en amont du proxy Kimi, similairement au serveur `memory-bank` existant.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Kimi Proxy Dashboard                         │
├─────────────────────────────────────────────────────────────────┤
│  Phase 2: MCP Memory              Phase 3: External MCP         │
│  • detector.py                    • Qdrant (port 6333)          │
│  • analyzer.py                    • Compression (port 8001)     │
│  • storage.py                                                   │
├─────────────────────────────────────────────────────────────────┤
│  🆕 Phase 4: Nouveaux Serveurs MCP                              │
│  • Task Master (port 8002)        • Sequential Thinking (8003)  │
│  • Fast Filesystem (port 8004)    • JSON Query (port 8005)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Les 4 Nouveaux Serveurs

### 1. Task Master MCP (14 outils)

**Port**: 8002  
**Timeout**: 30s  
**Configuration**: `[mcp.task_master]` dans `config.toml`

Gestion complète de tâches avec priorisation, dépendances et analyse de complexité.

#### Outils disponibles

| Outil | Description |
|-------|-------------|
| `get_tasks` | Liste toutes les tâches d'un projet |
| `next_task` | Identifie la prochaine tâche à traiter |
| `get_task` | Récupère les détails d'une tâche spécifique |
| `set_task_status` | Met à jour le statut d'une tâche |
| `update_subtask` | Met à jour une sous-tâche |
| `parse_prd` | Analyse un document PRD (Product Requirements) |
| `expand_task` | Décompose une tâche en sous-tâches |
| `initialize_project` | Initialise un nouveau projet Task Master |
| `analyze_project_complexity` | Analyse la complexité du projet |
| `expand_all` | Décompose toutes les tâches en sous-tâches |
| `add_subtask` | Ajoute une sous-tâche |
| `remove_task` | Supprime une tâche |
| `add_task` | Ajoute une nouvelle tâche |
| `complexity_report` | Génère un rapport de complexité |

#### API Endpoints

```
GET  /api/memory/task-master/tasks       # Liste des tâches
GET  /api/memory/task-master/stats       # Statistiques
POST /api/memory/task-master/call        # Appel d'outil
```

#### Exemple d'utilisation

```python
from kimi_proxy.features.mcp import get_mcp_client

client = get_mcp_client()

# Récupérer les tâches
tasks = await client.get_task_master_tasks(status_filter="pending")

# Appeler un outil spécifique
result = await client.call_task_master_tool(
    "expand_task",
    {"task_id": "123", "num_subtasks": 5}
)
```

---

### 2. Sequential Thinking MCP (1 outil)

**Port**: 8003  
**Timeout**: 60s  
**Configuration**: `[mcp.sequential_thinking]` dans `config.toml`

Raisonnement séquentiel structuré pour résolution de problèmes complexes.

#### Outil disponible

| Outil | Description |
|-------|-------------|
| `sequentialthinking_tools` | Raisonnement étape par étape avec branches et révisions |

#### Paramètres

```python
{
    "thought": "Pensée actuelle",
    "thought_number": 1,              # Numéro de l'étape (1-based)
    "total_thoughts": 5,              # Nombre total d'étapes prévues
    "next_thought_needed": True,      # Besoin d'une étape suivante
    "available_mcp_tools": []         # Outils MCP disponibles (optionnel)
}
```

#### API Endpoint

```
POST /api/memory/sequential-thinking/call
```

#### Exemple d'utilisation

```python
from kimi_proxy.features.mcp import get_mcp_client

client = get_mcp_client()

# Démarrer un raisonnement séquentiel
step = await client.call_sequential_thinking(
    thought="Analyser le problème de routing...",
    thought_number=1,
    total_thoughts=5,
    next_thought_needed=True
)

print(f"Étape {step.step_number}: {step.thought}")
print(f"Prochaine étape nécessaire: {step.next_thought_needed}")
```

---

### 3. Fast Filesystem MCP (25 outils)

**Port**: 8004  
**Timeout**: 10s  
**Configuration**: `[mcp.fast_filesystem]` dans `config.toml`

Opérations fichiers haute performance avec API optimisée.

#### Outils par catégorie

**Lecture (3)**
- `fast_read_file` - Lecture avec chunking auto
- `fast_read_multiple_files` - Lecture parallèle
- `fast_extract_lines` - Extraction de lignes spécifiques

**Écriture (2)**
- `fast_write_file` - Écriture standard
- `fast_large_write_file` - Écriture streaming pour gros fichiers

**Navigation (3)**
- `fast_list_directory` - Liste avec pagination
- `fast_get_directory_tree` - Arbre de répertoires
- `fast_list_allowed_directories` - Répertoires autorisés

**Recherche (2)**
- `fast_search_files` - Recherche par nom/contenu
- `fast_search_code` - Recherche dans le code (regex support)

**Édition (4)**
- `fast_edit_block` - Remplacement de bloc précis
- `fast_safe_edit` - Édition avec confirmation
- `fast_edit_multiple_blocks` - Éditions multiples
- `fast_edit_blocks` - Édition en batch

**Gestion (3)**
- `fast_copy_file` - Copie
- `fast_move_file` - Déplacement
- `fast_delete_file` - Suppression

**Batch (1)**
- `fast_batch_file_operations` - Opérations multiples atomiques

**Compression (2)**
- `fast_compress_files` - Compression (zip/tar)
- `fast_extract_archive` - Extraction

**Sync (1)**
- `fast_sync_directories` - Synchronisation de répertoires

**Info (4)**
- `fast_get_file_info` - Métadonnées
- `fast_create_directory` - Création de répertoire
- `fast_get_disk_usage` - Usage disque
- `fast_find_large_files` - Recherche de gros fichiers

#### API Endpoint

```
POST /api/memory/filesystem/call
```

#### Exemple d'utilisation

```python
from kimi_proxy.features.mcp import get_mcp_client

client = get_mcp_client()

# Lire un fichier
result = await client.call_fast_filesystem_tool(
    "fast_read_file",
    {"path": "/path/to/file.txt", "auto_chunk": True}
)

# Rechercher du code
result = await client.call_fast_filesystem_tool(
    "fast_search_code",
    {"path": "/project", "pattern": "def.*get_", "file_pattern": "*.py"}
)
```

---

### 4. JSON Query MCP (3 outils)

**Port**: 8005  
**Timeout**: 5s  
**Configuration**: `[mcp.json_query]` dans `config.toml`

Requêtes JSON avancées avec JSONPath et recherche.

#### Outils disponibles

| Outil | Description |
|-------|-------------|
| `json_query_jsonpath` | Requêtes JSONPath complexes |
| `json_query_search_keys` | Recherche de clés par pattern |
| `json_query_search_values` | Recherche de valeurs |

#### API Endpoint

```
POST /api/memory/json-query/call
```

#### Exemple d'utilisation

```python
from kimi_proxy.features.mcp import get_mcp_client

client = get_mcp_client()

# Requête JSONPath
result = await client.call_json_query_tool(
    "json_query_jsonpath",
    file_path="/data/config.json",
    query="$.servers[?(@.port > 8000)].name",
    limit=10
)

# Recherche de clés
result = await client.call_json_query_tool(
    "json_query_search_keys",
    file_path="/data/large.json",
    query="*timeout*",
    limit=20
)
```

---

## Détection Automatique

### Patterns de détection

Les patterns regex dans `constants.py` détectent automatiquement les appels d'outils MCP:

```python
MCP_PATTERNS = {
    # Phase 4 - Nouveaux serveurs MCP
    "mcp_task_master": r"(get_tasks|next_task|...|complexity_report)",
    "mcp_sequential_thinking": r"(sequentialthinking_tools|sequential_thinking)",
    "mcp_fast_filesystem": r"(fast_list_allowed_directories|fast_read_file|...|fast_sync_directories)",
    "mcp_json_query": r"(json_query_jsonpath|json_query_search_keys|json_query_search_values)",
}
```

### Utilisation du détecteur

```python
from kimi_proxy.features.mcp import MCPDetector, get_detected_mcp_servers

# Détecter les outils Phase 4
detector = MCPDetector()
phase4_segments = detector.detect_phase4_tools(content)
servers = detector.get_detected_phase4_servers(content)

# Détection complète
all_servers = get_detected_mcp_servers(content)
# Returns: {"memory_bank": True, "phase4_servers": ["task_master", ...], "has_mcp_content": True}
```

---

## Configuration

### config.toml

```toml
# ============================================
# MCP PHASE 4 - Nouveaux Serveurs MCP
# ============================================

[mcp.task_master]
enabled = true
url = "http://localhost:8002"
api_key = ""
timeout_ms = 30000
tasks_root = ".taskmaster"

[mcp.sequential_thinking]
enabled = true
url = "http://localhost:8003"
api_key = ""
timeout_ms = 60000

[mcp.fast_filesystem]
enabled = true
url = "http://localhost:8004"
api_key = ""
timeout_ms = 10000
allowed_directories = ["."]

[mcp.json_query]
enabled = true
url = "http://localhost:8005"
api_key = ""
timeout_ms = 5000

[mcp.phase4]
enabled = true
auto_detect = true
status_check_interval = 30
```

---

## API Endpoints Phase 4

### Statuts des serveurs

```
GET /api/memory/servers/phase4      # Statuts des 4 serveurs Phase 4
GET /api/memory/all-servers         # Tous les serveurs (Phase 3 + Phase 4)
```

### Task Master

```
GET  /api/memory/task-master/tasks       # Liste des tâches
GET  /api/memory/task-master/stats       # Statistiques
POST /api/memory/task-master/call        # Appel outil
```

### Sequential Thinking

```
POST /api/memory/sequential-thinking/call    # Raisonnement séquentiel
```

### Fast Filesystem

```
POST /api/memory/filesystem/call         # Opération filesystem
```

### JSON Query

```
POST /api/memory/json-query/call         # Requête JSON
```

### Générique

```
POST /api/memory/tool/call               # Appel générique d'outil MCP
```

---

## Modèles de données

### TaskMasterTask

```python
@dataclass
class TaskMasterTask:
    id: str
    title: str
    description: str
    status: str           # pending, in-progress, done, blocked, deferred
    priority: str         # high, medium, low
    dependencies: List[str]
    subtasks: List[Dict]
    created_at: Optional[str]
    updated_at: Optional[str]
```

### TaskMasterStats

```python
@dataclass
class TaskMasterStats:
    total_tasks: int
    pending: int
    in_progress: int
    done: int
    blocked: int
    deferred: int
    total_complexity_score: float
```

### SequentialThinkingStep

```python
@dataclass
class SequentialThinkingStep:
    step_number: int
    thought: str
    next_thought_needed: bool
    total_thoughts: int
    branches: List[Dict]
```

### FileSystemResult

```python
@dataclass
class FileSystemResult:
    success: bool
    path: str
    operation: str
    content: Optional[str]
    error: Optional[str]
    bytes_affected: int
```

### JsonQueryResult

```python
@dataclass
class JsonQueryResult:
    success: bool
    query: str
    file_path: str
    results: List[Dict]
    error: Optional[str]
    execution_time_ms: float
```

---

## Client MCP

### Extension de MCPExternalClient

```python
from kimi_proxy.features.mcp import get_mcp_client

client = get_mcp_client()

# Vérification des statuts
task_master_status = await client.check_task_master_status()
sequential_status = await client.check_sequential_thinking_status()
filesystem_status = await client.check_fast_filesystem_status()
json_query_status = await client.check_json_query_status()

# Récupération de tous les statuts Phase 4
all_phase4 = await client.get_all_phase4_server_statuses()

# Appel d'outils spécifiques
tasks = await client.get_task_master_tasks()
stats = await client.get_task_master_stats()

# Appel générique
tool_call = await client.call_mcp_tool(
    server_type="task_master",
    tool_name="expand_task",
    params={"task_id": "123", "num_subtasks": 3}
)

# Vérification de disponibilité
if client.is_task_master_available():
    # Utiliser Task Master
    pass
```

---

## Dépannage

### Ports déjà utilisés

```bash
# Vérifier les ports Phase 4
netstat -tlnp | grep -E ':(8002|8003|8004|8005)'

# Tester les endpoints
curl http://localhost:8000/api/memory/servers/phase4
curl http://localhost:8000/api/memory/task-master/stats
```

### Serveurs non détectés

Vérifiez la configuration dans `config.toml`:
- URLs correctes
- Ports disponibles
- `enabled = true`

### Timeouts

Augmentez les timeouts si nécessaire:
```toml
[mcp.sequential_thinking]
timeout_ms = 90000  # Augmenter pour raisonnement complexe
```

---

## Tests

Les tests Phase 4 sont dans `tests/test_mcp_phase4.py`:

```bash
PYTHONPATH=src python -m pytest tests/test_mcp_phase4.py -v
```

---

## Résumé

| Serveur | Port | Outils | Timeout | Use Case |
|---------|------|--------|---------|----------|
| Task Master | 8002 | 14 | 30s | Gestion de projet |
| Sequential Thinking | 8003 | 1 | 60s | Résolution de problèmes |
| Fast Filesystem | 8004 | 25 | 10s | Opérations fichiers |
| JSON Query | 8005 | 3 | 5s | Requêtes JSON |

**Total**: 43 nouveaux outils MCP pour étendre les capacités du proxy Kimi.
