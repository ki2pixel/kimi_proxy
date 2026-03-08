# Corrections critiques session Kimi Code — brief PRD

**TL;DR**: une session Kimi Code valide échoue actuellement sur trois axes distincts mais liés : (1) l’authentification provider `managed:kimi-code` n’est pas correctement résolue depuis la configuration, ce qui provoque des `401 Invalid Authentication` et le log `Aucune clé API trouvée pour managed:kimi-code`; (2) l’auto-session tente d’écrire `external_session_id` alors que certaines bases SQLite locales n’ont jamais reçu la migration correspondante; (3) le watcher analytics classe trop agressivement certaines erreurs API comme une “limite atteinte”, y compris avec `Tokens: 0`, ce qui génère un bruit trompeur. La mission consiste à corriger ces défauts sans casser l’architecture 5 couches ni la compatibilité Kimi Code.

## Le problème

Les symptômes observés pointent vers une incohérence entre configuration provider, schéma SQLite et interprétation des signaux runtime Kimi/Continue :

1. `managed:kimi-code` est utilisé comme provider par défaut dans plusieurs couches (`API`, `Core`, `Proxy`, `Auto Session`), mais la configuration `config.toml` inspectée ne définit actuellement ni le modèle `kimi-code/kimi-for-coding` ni le provider `[providers."managed:kimi-code"]`.
2. Le code d’auto-session et de persistance sait lire/écrire `external_session_id`, mais `init_database()` crée encore la table `sessions` sans cette colonne et `_run_migrations()` n’ajoute pas cette migration sur les bases déjà existantes.
3. Le watcher global Kimi marque toute ligne `ERROR` comme `is_api_error=True`, puis `main.py` affiche systématiquement `⚠️ [API ERROR] Tokens: {total_tokens} (limite atteinte)` même quand `total_tokens == 0` et qu’aucune preuve ne démontre un dépassement de contexte.

## Symptômes confirmés

- JSON-RPC côté Kimi Code : `401 Invalid Authentication`
- Proxy backend : `⚠️ ATTENTION: Aucune clé API trouvée pour managed:kimi-code`
- Auto-session / SQLite : `table sessions has no column named external_session_id`
- Bruit analytics : `⚠️ [API ERROR] Tokens: 0 (limite atteinte)` en rafales

## Causes probables étayées par collecte

### 1. Provider/configuration absente ou incomplète
- `config.toml` ne contient actuellement aucune entrée `[providers."managed:kimi-code"]`.
- `config.toml` ne contient actuellement aucun modèle `kimi-code/kimi-for-coding`.
- Le proxy utilise pourtant `managed:kimi-code` comme valeur par défaut et cherche `provider_config.get("api_key")`, ce qui renvoie vide si le provider n’existe pas.
- `config/loader.py` sait bien étendre les variables d’environnement `${VAR}` : le problème principal n’est donc pas l’absence d’expansion, mais l’absence de définition provider/modèle correspondante dans la config chargée.

### 2. Migration SQLite manquante
- `create_session(..., external_session_id=...)` insère dans `sessions (name, provider, model, external_session_id, is_active)`.
- `update_session_external_id(...)` exécute `UPDATE sessions SET external_session_id = ?`.
- Pourtant, `CREATE TABLE IF NOT EXISTS sessions (...)` ne définit pas `external_session_id`.
- `_run_migrations()` ajoute `model`, `reserved_tokens`, `compaction_count`, etc., mais n’ajoute jamais `external_session_id`.

### 3. Mauvaise classification des erreurs watcher
- `KimiGlobalLogParser` marque toute ligne `ERROR` comme `is_api_error=True`.
- `LogWatcher` diffuse ensuite ces événements même si `total_tokens == 0`, car le prédicat accepte aussi `event.metrics.is_api_error`.
- `main.py` traduit ensuite uniformément les erreurs en `Tokens: {total_tokens} (limite atteinte)`, sans distinguer les erreurs auth/runtime/timeout des vrais dépassements de contexte.

## Contraintes non négociables

- Respect strict de l’architecture 5 couches : `API ← Services ← Features ← Proxy ← Core`.
- Aucune clé API en dur dans le code ou les tests.
- Pas d’ajout de route API expérimentale.
- Mapping modèle simple uniquement : exact match puis suffix split.
- Compatibilité Kimi Code conservée.
- Async only pour les I/O ajoutées côté proxy/services/features; pas d’introduction de nouvel I/O bloquant dans le chemin async.
- Typage strict, pas de nouveau `Any` évitable.

## Objectifs

- Rétablir la résolution d’authentification pour `managed:kimi-code` quand la config et l’environnement sont corrects.
- Garantir la compatibilité DB pour `sessions.external_session_id` sur base neuve et base existante.
- Supprimer les faux positifs `API ERROR Tokens: 0 (limite atteinte)` et rendre le diagnostic runtime plus fidèle.
- Ajouter des tests ciblés de non-régression pour config/auth, migration DB, auto-session et watcher.
- Documenter la procédure de diagnostic Kimi Code (auth, auto-session, watcher, proxy).

## Portée technique attendue

- `config.toml`
- `src/kimi_proxy/config/loader.py` ou consommation config si nécessaire
- `src/kimi_proxy/proxy/router.py`
- `src/kimi_proxy/api/routes/proxy.py`
- `src/kimi_proxy/core/database.py`
- `src/kimi_proxy/core/auto_session.py`
- `src/kimi_proxy/features/log_watcher/parser.py`
- `src/kimi_proxy/features/log_watcher/watcher.py`
- `src/kimi_proxy/main.py`
- tests unitaires/intégration associés
- documentation troubleshooting/auto-session/proxy

## Risques principaux

1. Régression proxy si l’on modifie mal la résolution provider par défaut.
2. Migration SQLite partielle si la colonne est ajoutée seulement au `CREATE TABLE` mais pas au chemin migration.
3. Régression analytics si l’on coupe trop agressivement les logs d’erreur utiles.
4. Faux sentiment de correction si les tests couvrent la config nominale mais pas le cas provider manquant.

## Critères d’acceptation

- Plus aucun `401 Invalid Authentication` en session Kimi Code valide lorsque `managed:kimi-code` est correctement configuré via env/config.
- Plus aucun log `Aucune clé API trouvée pour managed:kimi-code` quand la configuration est correcte.
- Plus d’erreur SQL `table sessions has no column named external_session_id` sur base neuve ou existante.
- Les erreurs runtime/auth ne sont plus présentées comme `limite atteinte` quand `total_tokens == 0` ou qu’aucune preuve de dépassement n’existe.
- La session chat Kimi Code fonctionne en streaming avec mapping modèle simple conservé.
- Des tests ciblés couvrent le chemin config/auth, la migration `external_session_id`, l’auto-session et la classification watcher.

## Stratégie de rollback

- La correction config reste additive : ajout de provider/modèle sans casser les providers existants.
- La migration DB reste idempotente (`ALTER TABLE ... ADD COLUMN` protégé).
- La correction watcher doit être fail-open : en cas de doute, conserver l’événement d’erreur mais changer son libellé plutôt que le supprimer.