# Architecture MCP Locale avec Continue.app

## TL;DR
Les serveurs MCP Phase 4 (Shrimp Task Manager, Sequential Thinking, Fast Filesystem, JSON Query) fonctionnent maintenant **localement** via Continue.app. Le proxy ne fait plus de validation spécifique MCP.

## Changements architecturaux

### Avant (Proxy)
```
Client → Proxy → Validation MCP → Appel serveur MCP
```

### Maintenant (Local)
```
Client → Continue.app → Serveurs MCP locaux
Proxy → Routage HTTP uniquement (agnostique)
```

## Implications

1. **Validation décentralisée** : Chaque serveur MCP valide ses propres paramètres
2. **Proxy agnostique** : Les utilitaires JSON (`tool-validation.md`) restent utilisés
3. **Pas de couplage** : Le proxy ne connaît plus les outils MCP spécifiques

## Configuration

Voir `config.yaml` de Continue.app pour la configuration des serveurs MCP locaux.

## Migration des fonctionnalités

Les fonctionnalités suivantes ont été déplacées du proxy vers l'extension Continue :

- **Shrimp Task Manager** : Gestion des tâches et planification de projets
- **Sequential Thinking** : Raisonnement séquentiel pour la résolution de problèmes
- **Fast Filesystem** : Opérations fichiers haute performance
- **JSON Query** : Requêtes avancées sur les fichiers JSON

## Documentation obsolète

Le document `docs/features/mcp-client-validation.md` a été archivé car il documentait une logique de validation couplée aux outils MCP qui ne sont plus dans le proxy.

## Standards de codage maintenus

- Architecture 5 couches intacte (API ← Services ← Features ← Proxy ← Core)
- Proxy reste agnostique et réutilisable
- Validation JSON générique conservée dans `docs/proxy/tool-validation.md`
- Pas de dépendances synchrones ou violations des standards
