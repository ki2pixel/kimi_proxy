# Log watcher : Continue + Kimi, sans casser l’existant

## TL;DR
Le log watcher n’est plus mono-source. **Il surveille maintenant les logs Continue, le fichier global `kimi.log` et les artefacts de session Kimi (`context.jsonl` + `metadata.json`) avec un parsing incrémental et fail-open.**

## Le problème
Vous voulez une vue temps réel cohérente du dashboard, mais les signaux n’arrivent plus d’un seul endroit.

Continue produit encore ses logs historiques. Kimi, lui, sépare les informations entre:

- un log global;
- des sessions par workspace;
- des fichiers JSON/JSONL qui peuvent être partiels, invalides ou en cours d’écriture.

Si le watcher reste centré sur un seul fichier, vous perdez soit la compatibilité Continue, soit la granularité Kimi.

## ❌ L’ancien monde: une seule source, un seul format

```python
watcher = LogWatcher(log_path="core.log")
events = await watcher.poll()
```

Cette approche fonctionne pour un pipeline homogène. Elle devient trop pauvre dès qu’il faut distinguer:

- `continue_compile_chat`;
- `kimi_global`;
- `kimi_session_user`, `kimi_session_usage`, `kimi_session_tool`, etc.

## ✅ Le monde actuel: plusieurs sources, un format normalisé

```python
default_sources = [
    ContinueLogSource(log_path=log_path),
    KimiGlobalLogSource(),
    KimiSessionSource(),
]
```

Chaque source produit ensuite le même type d’événement normalisé:

```python
AnalyticsEvent(
    source_id="kimi_sessions",
    source_kind="kimi_session",
    metrics=metrics,
    provider=provider,
    model=model,
    session_external_id=session_external_id,
    preview=preview,
)
```

## Les trois flux réellement surveillés

### Continue

Le watcher conserve la compatibilité historique avec les logs Continue.

Il continue de produire:

- `continue_logs`
- `continue_compile_chat`
- `continue_api_error`

### Kimi global

Le watcher lit `~/.kimi/logs/kimi.log` pour détecter notamment:

- le provider actif;
- le modèle actif;
- le `max_context` observé;
- les erreurs runtime Kimi.

### Kimi sessions

Le watcher lit les artefacts par session sous `~/.kimi/sessions/<workdir-hash>/<session-id>/`.

Les fichiers utiles sont:

- `context.jsonl`
- `metadata.json`

Les rôles actuellement interprétés sont:

- `_checkpoint`
- `_usage`
- `user`
- `assistant`
- `tool`

## JSON partiel: la vraie difficulté

Le problème n’est pas seulement de parser du JSON. Le problème est de parser du JSON qui peut être:

- invalide temporairement;
- écrit pendant qu’on le lit;
- absent pour certaines sessions;
- incomplet au moment du polling.

## ✅ Le choix fait ici: fail-open et incrémental

### Pour `context.jsonl`

Chaque ligne est traitée indépendamment. Une ligne invalide est ignorée sans casser le reste du flux.

```python
try:
    payload = json.loads(line)
except json.JSONDecodeError:
    return None
```

### Pour `metadata.json`

Si le metadata est invalide, le watcher retombe sur un état vide et continue de produire des événements à partir du nom du dossier de session.

```python
except (OSError, json.JSONDecodeError):
    state.metadata = {}
    state.metadata_mtime = metadata_mtime
    return
```

Cette règle évite le pire scénario: perdre toute une session parce qu’un fichier auxiliaire a été écrit au mauvais moment.

## Ce que le dashboard reçoit maintenant

Le backend diffuse toujours un événement `log_metric`, mais avec une normalisation enrichie:

- `source`
- `source_family`
- `source_label`

Cela permet au frontend de distinguer proprement:

- Continue compile;
- erreurs analytics;
- log global Kimi;
- événements de session Kimi.

## Pourquoi le parsing est borné

Le watcher Kimi ne rescane pas tout l’arbre de sessions à chaque tick.

Il applique plusieurs garde-fous:

- découverte par batch de roots;
- nombre maximum de sessions par poll;
- lecture uniquement depuis la dernière position connue;
- tail initial borné pour éviter de relire tout l’historique.

Ce n’est pas seulement une optimisation. C’est ce qui rend le watcher viable quand le répertoire `.kimi/sessions/` grossit.

## Continue n’a pas été sacrifié

La migration n’a pas remplacé Continue par Kimi. Elle a transformé le watcher en orchestrateur multi-source.

Autrement dit:

- Continue reste pris en charge;
- Kimi ajoute des sources plus fines;
- le dashboard parle maintenant un vocabulaire commun.

## Trade-offs

| Approche | Avantage | Limite |
| -------- | -------- | ------ |
| Une seule source Continue | Très simple | Impossible de représenter correctement Kimi |
| Parsing strict des JSON Kimi | Plus rigoureux | Trop fragile sur des fichiers en cours d’écriture |
| Parsing fail-open + incrémental | Robuste et compatible temps réel | Demande plus de normalisation côté backend/frontend |

## Golden Rule

**Quand un artefact Kimi est invalide, on doit perdre l’événement fautif, pas toute la chaîne analytics.**

---
Dernière mise à jour : 2026-03-07