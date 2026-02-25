# Brief — Extension de l’accès MCP aux workspaces /home/kidpixel/*

## Objectif
Modifier la logique d’autorisation/validation des chemins côté intégration MCP afin d’autoriser l’accès à **tous les workspaces sous `/home/kidpixel/`**.

Aujourd’hui, l’accès semble restreint au workspace courant `/home/kidpixel/kimi-proxy`, ce qui provoque des erreurs **403** (accès refusé) et parfois **502** (gateway) lorsque des serveurs MCP (ex: fast-filesystem) reçoivent des chemins hors de ce périmètre.

## Portée
- Modifier la logique **globale** d’autorisation des chemins (pas de liste blanche par workspace).
- Autoriser tout chemin dont la racine résolue est sous `/home/kidpixel/`.
- Conserver une protection robuste contre le **path traversal** et les symlinks malveillants.

## Exigences de sécurité
- Utiliser `Path.resolve()` pour normaliser.
- Vérifier l’appartenance via `resolved_path.relative_to(allowed_root)`.
- Rejeter tout chemin en dehors de `/home/kidpixel/`.

## Workspaces/chemins à couvrir (tests manuels)
- `/home/kidpixel/workflow_mediapipe`
- `/home/kidpixel/kimi-proxy/render_signal_server-main`
- `/home/kidpixel/kimi-proxy/photomaton_simple_new`
- `/home/kidpixel/kimi-proxy/SwitchBot`
- `/home/kidpixel/kimi-proxy/After_Effects_Scripts_Plugins_Bundle`

## Livrables
- Changement de code: validation des chemins MCP mise à jour.
- Tests: unitaires (validation), et au minimum une vérification intégration (MCP filesystem / gateway).
- Documentation: note courte sur le nouveau périmètre autorisé (si pertinent).

## Critères d’acceptation
- Les requêtes MCP impliquant des chemins sous `/home/kidpixel/` ne renvoient plus 403.
- Les chemins hors `/home/kidpixel/` restent bloqués.
- Aucun contournement trivial via `..` ou symlinks.
