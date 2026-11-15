---
name: fast-filesystem-ops
description: Lecture, recherche et arborescence via fast-filesystem avec chemins absolus obligatoires. Édition ciblée via filesystem-agent.edit_file. Ne jamais utiliser de chemin relatif, "." ou "..".
---

# Fast Filesystem Operations

> **TL;DR** : `fast-filesystem` sert à lire, rechercher, lister et écrire des fichiers entiers. `filesystem-agent` sert à l'édition ciblée (`edit_file`). **Tous les chemins passés à `fast_*` doivent être absolus et commencer par `/home/kidpixel/`.** Les chemins relatifs, `.` et `..` sont refusés avec l'erreur JSON-RPC `-32602`.

## Règles de chemins (non négociables)

Le serveur `fast-filesystem` est un daemon HTTP partagé entre tous les projets. Il ne connaît pas votre workspace courant. Un chemin relatif serait résolu contre le répertoire de lancement du daemon (souvent `kimi-proxy`), pas contre votre projet.

❌ **Interdit** :
```text
fast_read_file({ path: "memory-bank/activeContext.md" })
fast_get_directory_tree({ path: "." })
fast_search_files({ directory: "./docs", pattern: "TODO" })
fast_read_file({ path: "../autre-projet/README.md" })
```

✅ **Correct** :
```text
fast_read_file({ path: "/home/kidpixel/photomaton_simple_new/memory-bank/activeContext.md" })
fast_get_directory_tree({ path: "/home/kidpixel/photomaton_simple_new", max_depth: 2 })
fast_search_files({ directory: "/home/kidpixel/photomaton_simple_new/docs", pattern: "TODO" })
```

- Un chemin **absolu** est autorisé sous `/home/kidpixel` (accès inter-projets explicite).
- Un chemin **relatif** n'est accepté que via le pont local OpenCode, qui injecte le workspace courant. Il doit rester **dans** ce workspace ; toute évasion `..` est refusée.
- Si un résultat semble provenir d'un autre dépôt, arrêtez-vous : vérifiez le champ `path` de la réponse et réessayez avec un chemin absolu.

## Séparation des deux serveurs

| Besoin | Serveur | Outil |
|---|---|---|
| Lire un fichier | `fast-filesystem` | `fast_read_file({ path })` |
| Lister un répertoire | `fast-filesystem` | `fast_list_directory({ path })` |
| Arborescence | `fast-filesystem` | `fast_get_directory_tree({ path, max_depth, include_files })` |
| Rechercher par sous-chaîne | `fast-filesystem` | `fast_search_files({ directory, pattern })` |
| Lire plusieurs fichiers | `fast-filesystem` | `fast_read_multiple_files({ paths: [...] })` |
| Écrire un fichier entier | `fast-filesystem` | `fast_write_file({ path, content })` |
| Édition ciblée / patch | `filesystem-agent` | `edit_file(...)` |
| Recherche regex avancée | `ripgrep-agent` | `search`, `advanced-search` |

`fast-filesystem` **n'expose pas** `edit_file`, `--lines`, `--language`, `--context` ni `--pattern`. Ces options n'existent pas dans son schéma MCP.

## Workflow recommandé

1. **Localiser** avec `fast_search_files` sur un répertoire absolu.
2. **Lire** uniquement les fichiers nécessaires avec `fast_read_multiple_files` (chemins absolus).
3. **Comprendre la structure** avec `fast_get_directory_tree` (`max_depth` limité).
4. **Éditer** avec `filesystem-agent.edit_file` pour un patch ciblé, ou `fast_write_file` pour un remplacement complet.
5. **Vérifier** le résultat et le champ `path` retourné.

### Exemple — audit d'un projet

```text
fast_get_directory_tree({
  path: "/home/kidpixel/photomaton_simple_new",
  max_depth: 2,
  include_files: true
})

fast_search_files({
  directory: "/home/kidpixel/photomaton_simple_new",
  pattern: "activeContext"
})

fast_read_multiple_files({
  paths: [
    "/home/kidpixel/photomaton_simple_new/memory-bank/activeContext.md",
    "/home/kidpixel/photomaton_simple_new/AGENTS.md"
  ]
})
```

### Exemple — édition ciblée

```text
filesystem-agent.edit_file({
  path: "/home/kidpixel/kimi-proxy/scripts/example.py",
  edits: [{ oldText: "old", newText: "new" }]
})
```

## Optimisation token

- Ne jamais charger un fichier de plus de 1000 lignes en entier : rechercher d'abord, puis lire une zone précise avec un outil adapté (shell, `sed`, `rg`) ou `fast_read_multiple_files` sur des fichiers ciblés.
- Utiliser `max_depth` petit pour `fast_get_directory_tree`.
- Utiliser `fast_search_files` (substring) pour trouver un nom de fichier, puis `ripgrep-agent` pour le contenu.
- Pour un gros JSON, ne pas prétendre que `json_query_query_json` lit un fichier : il attend `json_data`. Lire le JSON par un moyen adapté, puis passer son contenu à `json_query_query_json({ json_data, query })`.

## Sécurité et permissions

- **Racine autorisée** : `MCP_ALLOWED_ROOT=/home/kidpixel`. La racine `/` est refusée au démarrage.
- **Anti-traversal** : `Path.resolve(strict=False)` + `relative_to` ; les symlinks sortants sont refusés.
- **Daemon partagé** : ne jamais compter sur le `cwd` du serveur. Le pont local OpenCode injecte `params._meta["ai.kimi-proxy/workspaceRoot"]`, mais ce n'est qu'une base de résolution, pas une autorisation.
- **`filesystem-agent`** : le bridge supprime la capability `roots` pour éviter que les roots de l'IDE écrasent la politique CLI. Continuez à fournir des chemins absolus.
- **Erreurs** :
  - `-32602 RELATIVE_PATH_UNSUPPORTED` : chemin relatif sans contexte workspace.
  - `-32602 RELATIVE_PATH_ESCAPES_WORKSPACE` : `..` sort du workspace.
  - `-32602 PATH_REQUIRED` : paramètre de chemin manquant.
  - `-32000 PATH_OUTSIDE_ALLOWED_ROOT` : chemin absolu hors de `/home/kidpixel`.

## Debugging checklist

- [ ] Le chemin commence-t-il par `/home/kidpixel/` ?
- [ ] Le champ `path` de la réponse correspond-il au projet attendu ?
- [ ] Le fichier existe-t-il réellement ?
- [ ] Un symlink sortant est-il impliqué ?
- [ ] L'erreur est-elle `RELATIVE_PATH_UNSUPPORTED` (utiliser l'absolu) ou `PATH_OUTSIDE_ALLOWED_ROOT` (hors racine) ?
- [ ] Pour une édition, utiliser `filesystem-agent.edit_file`, pas `fast-filesystem`.

## When to use this skill

- Lecture ou recherche de fichiers dans un projet sous `/home/kidpixel`.
- Audit de structure avec `fast_get_directory_tree`.
- Lecture multi-fichiers ciblée.
- Écriture complète d'un fichier.
- Diagnostic d'un résultat inattendu (mauvais dépôt, chemin refusé).

## Integration patterns

- **Avec `filesystem-agent`** : `fast_*` pour lire/chercher, `edit_file` pour patcher.
- **Avec `ripgrep-agent`** : `fast_search_files` pour les noms, `ripgrep` pour le contenu regex.
- **Avec JSON Query** : passer le contenu JSON dans `json_data`, pas un chemin de fichier.
- **Avec la Memory Bank** : toujours un chemin absolu, par exemple `/home/kidpixel/kimi-proxy/memory-bank/activeContext.md` ou `/home/kidpixel/photomaton_simple_new/memory-bank/activeContext.md`.
