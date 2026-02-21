# Validation Paramètres Task Master MCP - `_validate_task_master_params`

**TL;DR**: Cette fonction valide et corrige automatiquement les paramètres des outils Task Master MCP, appliquant des règles métier strictes avec messages d'erreur informatifs. Elle transforme les appels API malformés en requêtes valides avec defaults appropriés.

## Le Problème de Validation Paramètres MCP

Vous intégrez des serveurs MCP externes (Task Master, Sequential Thinking, etc.) avec leurs APIs spécifiques. Chaque outil a des paramètres obligatoires et optionnels différents:

- `initialize_project` nécessite `projectRoot` absolu
- `parse_prd` nécessite `input` comme chemin absolu
- `set_task_status` nécessite `id` et `status`

Au lieu de laisser les erreurs 400 "Missing parameter" remonter, vous voulez:

- Valider automatiquement les paramètres requis
- Corriger les noms de paramètres (snake_case ↔ camelCase)
- Ajouter des defaults appropriés
- Fournir des messages d'erreur précis en français

La fonction `_validate_task_master_params` centralise cette logique de validation pour tous les outils Task Master.

### ❌ L'Approche Éparse
```python
# Dans chaque handler d'outil
def handle_initialize_project(params):
    if "projectRoot" not in params:
        if "project_root" in params:
            projectRoot = params["project_root"]
        else:
            return {"error": "projectRoot manquant"}

    # Vérification du chemin dupliquée partout
    if not projectRoot.startswith("/"):
        return {"error": "Chemin absolu requis"}

    # Defaults dupliqués partout
    addAliases = params.get("addAliases", True)
    initGit = params.get("initGit", True)
    # ...
```

### ✅ L'Approche Centralisée
```python
def _validate_task_master_params(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validation unifiée pour tous les outils Task Master."""
    validated = params.copy()

    if tool_name == "initialize_project":
        # Validation centralisée
        validated = validate_initialize_project_params(validated)
    elif tool_name == "parse_prd":
        validated = validate_parse_prd_params(validated)
    # ...

    return validated
```

## Architecture de Validation

La fonction valide 14 outils Task Master avec des règles spécifiques:

### Outils de Gestion Projet
- **`initialize_project`**: `projectRoot` obligatoire (absolu), defaults pour `addAliases`, `initGit`, `storeTasksInGit`
- **`parse_prd`**: `input` obligatoire (absolu), defaults pour `research`, `numTasks`

### Outils de Gestion Tâches
- **`add_task`**: `prompt` OU (`title` + `description`) obligatoire
- **`expand_task`**: `id` obligatoire, `num` default "5"
- **`expand_all`**: `num` default "5"
- **`set_task_status`**: `id` et `status` obligatoires, `projectRoot` default
- **`get_task`**: `id` obligatoire
- **`get_tasks`**: Paramètres optionnels
- **`next_task`**: Pas de paramètres requis

### Outils de Sous-tâches
- **`add_subtask`**: `id` obligatoire, `title` OU `description` requis
- **`update_subtask`**: `id` obligatoire (format parentId.subtaskId)
- **`remove_task`**: `id` obligatoire

### Outils d'Analyse
- **`analyze_project_complexity`**: `threshold` default 5, `research` default False
- **`complexity_report`**: Pas de paramètres requis

## Règles de Validation Appliquées

### Correction Automatique des Noms
```python
# Correction snake_case → camelCase
if "projectRoot" not in params:
    if "project_root" in params:
        validated["projectRoot"] = params["project_root"]
    else:
        return {"error": "Paramètre 'projectRoot' obligatoire"}
```

### Validation Chemins Absolus
```python
# Pour tous les chemins de fichiers
if not input_path.startswith("/"):
    return {"error": f"Le paramètre 'input' doit être un chemin absolu, reçu: {input_path}"}
```

### Messages d'Erreur Informatifs
```python
# Messages spécifiques par outil
return {"error": "Paramètre 'id' obligatoire pour expand_task"}
return {"error": "Au moins 'title' ou 'description' requis pour add_subtask"}
return {"error": "Paramètre 'prompt' ou ('title' + 'description') obligatoire pour add_task"}
```

## Exemples Concrets

### Exemple 1: Correction Nom Paramètre
```python
# Appel avec paramètre snake_case
params = {"project_root": "/home/user/project", "addAliases": false}

# Après validation
validated = {
    "projectRoot": "/home/user/project",  # Corrigé
    "addAliases": false,                 # Préservé
    "initGit": true,                     # Default ajouté
    "storeTasksInGit": true             # Default ajouté
}
```

### Exemple 2: Validation Chemin Absolu
```python
# Appel avec chemin relatif
params = {"input": "docs/prd.txt"}

# Résultat erreur
{"error": "Le paramètre 'input' doit être un chemin absolu, reçu: docs/prd.txt"}
```

### Exemple 3: Validation Paramètres Obligatoires
```python
# Appel set_task_status incomplet
params = {"status": "done"}  # id manquant

# Résultat erreur
{"error": "Paramètre 'id' obligatoire pour set_task_status"}
```

### Exemple 4: Defaults Appropriés
```python
# Appel expand_task minimal
params = {"id": "5"}

# Après validation
validated = {
    "id": "5",
    "num": "5",        # Default ajouté
    "force": false,    # Default ajouté
    "research": true   # Default ajouté
}
```

## Trade-offs de Conception

| Aspect | Choix | Avantages | Inconvénients |
|--------|-------|-----------|---------------|
| **Centralisation** | Une fonction pour tous les outils | Maintenance facile, règles cohérentes | Fonction longue (156 LOC) |
| **Correction automatique** | snake_case → camelCase | Tolérance aux erreurs de nommage | Cache les erreurs de développement |
| **Messages français** | Messages d'erreur localisés | UX améliorée pour utilisateurs francophones | Maintenance multilangue complexe |
| **Defaults conservateurs** | Valeurs sûres par défaut | Réduction erreurs, fonctionnement out-of-box | Moins de flexibilité utilisateur |
| **Validation stricte** | Rejet paramètres invalides | Prévention erreurs runtime | UX plus stricte |

## Patterns Système Appliqués

- **Pattern 6 (Error Handling)**: Validation précoce avec messages informatifs
- **Pattern 4 (MCP Integration)**: Adaptation aux spécificités MCP Task Master
- **Pattern 1 (Clean Architecture)**: Séparation logique de validation
- **Pattern 3 (Configuration)**: Gestion defaults et paramètres optionnels

## Common Misconceptions

### "La validation devrait être dans chaque outil"

**Réalité**: La centralisation évite la duplication et garantit la cohérence. Chaque outil Task Master a des règles similaires (chemins absolus, IDs obligatoires).

### "Les defaults masquent les erreurs"

**Réalité**: Les defaults sont conservateurs et documentés. Ils améliorent l'UX en permettant des appels simplifiés tout en gardant la possibilité de les overrider.

### "Les messages en français sont inutiles"

**Réalité**: Kimi Proxy est un projet francophone. Les messages d'erreur en français améliorent significativement l'expérience utilisateur.

## Golden Rule: Validation Stricte avec Correction Tolérante

**Tout paramètre invalide doit être rejeté avec un message clair, mais les erreurs de nommage mineures doivent être corrigées automatiquement.** La fonction `_validate_task_master_params` incarne cette règle en transformant les appels API défaillants en requêtes robustes.

---

*Cette documentation explique la logique de validation MCP Task Master. Pour l'implémentation complète, voir `src/kimi_proxy/features/mcp/client.py:856`.*