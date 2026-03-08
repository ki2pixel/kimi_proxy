# Migration support Kimi Code — brief PRD

**TL;DR**: le proxy sait aujourd’hui analyser principalement `~/.continue/logs/core.log` et quelques flux locaux Cline. La migration doit introduire une architecture multi-source extensible capable d’ingérer à la fois les logs globaux Kimi Code (`/home/kidpixel/.kimi/logs/kimi.log`) et les sessions fines Kimi Code (`/home/kidpixel/.kimi/sessions/*/(context.jsonl|metadata.json)`), sans casser la compatibilité Continue ni la chaîne WebSocket/dashboard existante.

## Le problème

Le pipeline d’analyse actuel repose sur un `LogWatcher` mono-source avec un parser fortement orienté Continue/CompileChat. Cette hypothèse ne tient plus pour Kimi Code, dont l’écosystème expose deux niveaux de vérité:

1. un flux global structuré (`kimi.log`) utile pour l’observabilité runtime, les erreurs et le contexte provider/modèle ;
2. des artefacts de session (`context.jsonl`, `metadata.json`) utiles pour l’analyse fine, l’enrichissement des métriques et la future détection auto-session modèle/provider.

Si on étend le code existant par conditions ad hoc, on augmente le couplage IDE-spécifique, on fragilise la compatibilité Continue et on rend l’auto-session plus ambiguë.

## Objectifs

- Ajouter le support analytique Kimi Code global + sessionnel.
- Préserver la compatibilité Continue (`/home/kidpixel/.continue/logs`).
- Introduire une abstraction de sources d’analyse extensible à d’autres IDE/providers.
- Produire des métriques globales et par session cohérentes pour le backend, l’API et le dashboard.
- Préparer une détection auto-session basée sur le couple `provider + modèle`, et non plus seulement sur le modèle.

## Sources confirmées

### Continue historique
- `/home/kidpixel/.continue/logs/core.log`

### Kimi Code global
- `/home/kidpixel/.kimi/logs/kimi.log`
- Format observé: lignes structurées `timestamp | LEVEL | module:function:line - message`
- Contenu observé: configuration chargée, provider utilisé, modèle utilisé, outils chargés, erreurs runtime.

### Kimi Code sessionnel
- `/home/kidpixel/.kimi/sessions/*/context.jsonl`
- `/home/kidpixel/.kimi/sessions/*/metadata.json` quand présent
- `context.jsonl` observé: JSONL hétérogène avec rôles `_checkpoint`, `_usage`, `user`, `assistant`, parfois `tool`; certains messages assistant contiennent du contenu multimodal et des `tool_calls`.
- `metadata.json` observé: métadonnées minimales (`session_id`, `title`, `archived`, etc.).
- Réalité opérationnelle: certains dossiers de session ne contiennent que `context.jsonl`, d’autres ont aussi `metadata.json`.

## Contraintes

- Respect strict de l’architecture 5 couches.
- Pas de dépendance à un IDE unique dans les couches Core/Proxy.
- Pas de secrets hardcodés.
- Async/await obligatoire pour I/O ajoutées.
- Typage strict, pas de `Any` nouveau si évitable.
- Pas de régression UI/WebSocket/API pour Continue.

## Risques principaux

1. divergence de formats Continue vs Kimi ;
2. duplication de sessions si fusion globale/session mal corrélée ;
3. charge I/O si scan récursif `.kimi/sessions` naïf ;
4. timestamps incohérents entre sources ;
5. erreurs silencieuses sur JSONL partiels/corrompus ;
6. confusion UI si les labels restent trop orientés Continue.

## Décisions d’architecture proposées

### 1. Séparer découverte, parsing et normalisation
- **Discovery**: localiser les sources disponibles par provider/IDE.
- **Parsing**: parseurs dédiés par type de source.
- **Normalization**: convertir en événements/métriques internes homogènes.

### 2. Garder le dashboard sur un contrat stable
- Continuer d’émettre `log_metric` côté WebSocket, mais enrichir `source` et les payloads pour distinguer `continue`, `kimi_global`, `kimi_session`, `api_error`, etc.

### 3. Faire évoluer l’auto-session
- Passer d’une logique “modèle différent => nouvelle session” à une logique “provider+modèle(+éventuel identifiant de session source)”.

### 4. Prévoir le mode multi-source configurable
- Continue doit rester supporté même si Kimi est absent.
- Kimi doit fonctionner même si Continue n’est pas présent.

## Impacts techniques attendus

- `src/kimi_proxy/features/log_watcher/*`
- `src/kimi_proxy/core/constants.py`
- `src/kimi_proxy/core/auto_session.py`
- `src/kimi_proxy/api/routes/proxy.py`
- `src/kimi_proxy/api/routes/health.py`
- `src/kimi_proxy/main.py`
- `static/js/modules/websocket.js`
- `static/js/modules/sessions.js`
- `static/js/modules/ui.js`
- nouveaux tests unitaires/intégration pour parseurs et auto-session
- documentation technique/log watcher/auto-session/troubleshooting

## Critères d’acceptation

- Le système détecte et parse `kimi.log` sans casser Continue.
- Le système peut lire des sessions Kimi à partir de `context.jsonl` et `metadata.json` de manière robuste.
- Les métriques normalisées alimentent correctement WebSocket + dashboard.
- L’auto-session ne dépend plus uniquement du modèle et reste compatible avec l’existant.
- Les cas `metadata.json` absent, `context.jsonl` vide, JSONL partiel/corrompu et timestamps dégradés sont gérés explicitement.
- Des tests ciblés couvrent Continue + Kimi + non-régression.

## Stratégie de rollback

- Feature flag ou fallback par défaut vers Continue-only tant que la source Kimi n’est pas disponible.
- Parseurs Kimi fail-open: une erreur Kimi ne doit pas empêcher le proxy de fonctionner ni le watcher Continue de produire des métriques.
