# Auto-session : corrélation provider, modèle et session externe

## TL;DR
L’auto-session ne se contente plus du modèle. **Le backend corrèle maintenant `provider`, `model` et `external_session_id` quand ils sont disponibles, puis retombe sur l’ancien comportement basé sur le modèle quand ces signaux sont absents.**

## Le problème
Vous changez de provider ou de session Kimi, mais le modèle peut rester identique. Avec une corrélation basée uniquement sur `model`, le dashboard risque de réutiliser la mauvaise session applicative et de mélanger des conversations qui ne devraient pas l’être.

Le vrai problème est là: le modèle seul n’est plus un identifiant assez précis dès qu’on mélange Continue, Kimi global, sessions Kimi et réouvertures de conversation.

## ❌ L’ancienne règle: le modèle décide seul

```python
def should_auto_create_session(detected_provider, detected_model, current_session):
    if not current_session:
        return True

    current_model = current_session.get("model")
    return detected_model != current_model
```

Cette règle restait simple, mais elle ratait deux cas importants:

- même modèle, provider différent;
- même provider et même modèle, mais session Kimi externe différente.

## ✅ La règle actuelle: comparer le triplet quand il existe

```python
def should_auto_create_session(
    detected_provider,
    detected_model,
    current_session,
    detected_external_session_id=None,
):
    if not current_session:
        return True

    if detected_provider and current_session.get("provider"):
        if detected_provider != current_session.get("provider"):
            return True

    if detected_external_session_id and current_session.get("external_session_id"):
        if detected_external_session_id != current_session.get("external_session_id"):
            return True

    return detected_model != current_session.get("model")
```

La logique est volontairement priorisée:

1. `provider` si connu des deux côtés;
2. `external_session_id` si connu des deux côtés;
3. fallback historique sur `model`.

## Ce qui a changé côté backend

### Persistance de `external_session_id`

Le backend ajoute maintenant un champ optionnel `external_session_id` à la table `sessions`.

Pourquoi: une corrélation inter-requêtes a besoin d’un état persistant. Sans stockage côté session applicative, l’identifiant externe ne sert qu’au moment de la requête courante.

### ✅ Compatibilité base neuve et base existante

Le point important n’est pas seulement d’avoir le champ dans le code Python. Il faut aussi que le schéma SQLite réel le contienne.

La correction repose sur deux niveaux:

- `CREATE TABLE IF NOT EXISTS sessions (...)` inclut désormais `external_session_id`;
- la chaîne de migrations ajoute aussi `external_session_id` pour les bases locales déjà créées avant cette évolution.

### ❌ Le piège classique

```text
Le code lit external_session_id,
mais la base locale n'a jamais reçu la colonne.
```

Dans ce cas, l’auto-session semble correcte au niveau métier, mais échoue au premier `INSERT` ou `UPDATE`.

### ✅ Ce que garantit la correction

```text
Base neuve: colonne créée immédiatement.
Base existante: colonne ajoutée par migration idempotente.
```

### Extraction best-effort depuis la requête

Le backend ne dépend pas du watcher runtime pour cette étape. Il lit seulement des clés explicites dans le body entrant:

- `external_session_id`
- `session_external_id`
- `metadata.external_session_id`
- `metadata.session_external_id`
- `session.external_session_id`
- `session.session_external_id`

Même idée pour `provider`:

- `provider`
- `metadata.provider`
- `session.provider`

## Fail-open JSON et rétrocompatibilité

L’auto-session reste permissive.

- Si `provider` n’est pas fourni explicitement, il est redéduit depuis le modèle.
- Si `external_session_id` manque, la décision retombe sur la logique historique.
- Si le client ne connaît rien de Kimi, Continue continue de fonctionner sans changement de contrat.

## Ce qui n’a PAS changé

### ❌ Ce module ne dépend pas directement du log watcher

Le backend n’attend pas un événement analytics pour décider quelle session utiliser.

### ✅ Le log watcher enrichit l’observabilité, pas la décision immédiate

Les événements analytics Kimi transportent déjà `provider`, `model` et `session_external_id`, mais l’auto-session reste capable de décider à partir de la requête seule.

Ce choix évite un couplage fragile entre:

- le trafic entrant `/chat/completions`;
- le polling asynchrone des fichiers `.kimi/sessions/*/*/context.jsonl`.

## Intégration frontend

Le frontend conserve la même expérience utilisateur:

- toggle auto-session inchangé;
- synchronisation WebSocket inchangée;
- événement `auto_session_created` toujours diffusé.

La différence est dans la précision de la corrélation, pas dans l’interface de contrôle.

## Trade-offs

| Approche | Avantage | Limite |
| -------- | -------- | ------ |
| Modèle seul | Très simple | Trop ambigu dès qu’un même modèle vit sur plusieurs providers ou sessions externes |
| Provider + modèle | Corrige les changements de provider | Ne distingue pas deux sessions Kimi différentes sur le même modèle |
| Provider + modèle + session externe | Corrélation la plus précise | Dépend d’un `external_session_id` parfois absent |

## Golden Rule

**Quand `provider` et `external_session_id` existent, ils doivent affiner la décision; quand ils n’existent pas, l’auto-session doit rester compatible avec l’ancien monde.**

## Dépannage lié à la persistance

Si vous voyez encore une erreur du type `table sessions has no column named external_session_id`, ce n’est plus un problème de logique d’auto-session. C’est un signal que l’instance en cours n’a pas encore exécuté l’initialisation/migration du schéma corrigé.

Dans ce cas:

1. redémarrez le backend pour forcer `init_database()`;
2. inspectez `PRAGMA table_info(sessions)`;
3. vérifiez que la base utilisée est bien celle de l’instance courante.

---
Dernière mise à jour : 2026-03-07