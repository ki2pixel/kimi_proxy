# Dépannage Kimi Code : 401, clé API manquante, auto-session SQLite et faux `Tokens: 0`

## TL;DR

**Si une session Kimi Code échoue avec `401 Invalid Authentication`, `Aucune clé API trouvée pour managed:kimi-code`, une erreur SQLite sur `external_session_id`, ou des rafales `API ERROR Tokens: 0`, le problème vient généralement d’un triplet cohérent à restaurer: configuration provider, schéma SQLite et classification des erreurs watcher.**

## Le problème

Vous ouvrez une session Kimi Code. Le modèle semble correct, mais le proxy refuse l’authentification, l’auto-session casse sur SQLite, puis le watcher vous noie avec un message qui laisse croire à une limite de contexte alors que les tokens sont à zéro.

Le piège, c’est que ces symptômes ressemblent à trois bugs séparés. En pratique, ils se renforcent mutuellement:

- provider `managed:kimi-code` absent ou incomplet;
- colonne `sessions.external_session_id` absente sur certaines bases locales;
- erreurs runtime/auth affichées comme des dépassements de contexte.

## Les symptômes à reconnaître

- `401 Invalid Authentication`
- `Aucune clé API trouvée pour managed:kimi-code`
- `table sessions has no column named external_session_id`
- `⚠️ [API ERROR] Tokens: 0 (limite atteinte)`

## ✅ Ce qui doit être vrai dans la configuration

Le proxy attend maintenant explicitement un provider Kimi Code et un modèle Kimi Code dans `config.toml`.

### ✅ Configuration attendue

```toml
[models."kimi-code/kimi-for-coding"]
provider = "managed:kimi-code"
model = "kimi-for-coding"
max_context_size = 262144

[providers."managed:kimi-code"]
type = "kimi"
base_url = "https://api.kimi.com/coding/v1"
api_key = "${KIMI_API_KEY}"
```

### ❌ Mauvais état typique

```toml
# Le modèle existe ailleurs ou pas du tout
# mais aucun provider managed:kimi-code n'est défini
```

Dans ce cas, le proxy peut encore essayer d’utiliser `managed:kimi-code` comme provider par défaut, mais il ne trouvera ni configuration valide ni clé API résolue.

## Diagnostic rapide

### 1. Vérifier la structure TOML chargée

```bash
python3 - <<'PY'
import json
from pathlib import Path
try:
    import tomllib as toml_loader
except ModuleNotFoundError:
    import tomli as toml_loader

with Path('config.toml').open('rb') as f:
    config = toml_loader.load(f)

print(json.dumps({
    'provider': config.get('providers', {}).get('managed:kimi-code'),
    'model': config.get('models', {}).get('kimi-code/kimi-for-coding'),
}, ensure_ascii=False, indent=2))
PY
```

### 2. Vérifier l’environnement sans afficher la clé

```bash
python3 - <<'PY'
import os
print(bool(os.environ.get('KIMI_API_KEY')))
PY
```

Le résultat doit être `True`.

### 3. Vérifier que la base a bien la colonne attendue

```bash
python3 - <<'PY'
import sqlite3
conn = sqlite3.connect('sessions.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(sessions)')
print([row[1] for row in cur.fetchall()])
conn.close()
PY
```

La liste doit contenir `external_session_id`.

## Les causes racines corrigées

### 1. Provider Kimi Code absent dans `config.toml`

Le backend utilisait déjà `managed:kimi-code` comme valeur par défaut, mais la configuration réelle ne définissait pas toujours le provider correspondant.

Résultat: le proxy tombait sur une config vide et finissait en erreur d’authentification côté provider.

### 2. Migration SQLite incomplète

Le code de session savait lire et écrire `external_session_id`, mais certaines bases locales n’avaient jamais reçu cette colonne.

Résultat: l’auto-session tombait en erreur SQL au moment d’insérer ou de mettre à jour la session active.

### 3. Classification trop agressive des erreurs analytics

Le watcher traitait toute erreur Kimi globale comme une erreur API générique, puis le backend journalisait cela comme une “limite atteinte” même quand `total_tokens == 0`.

Résultat: bruit trompeur, alors que la vraie erreur pouvait être une auth refusée, un souci réseau, ou une erreur runtime Node.js.

## ✅ Ce que le backend fait maintenant

- distingue `provider absent`, `clé API manquante` et `401 upstream`;
- persiste `external_session_id` sur base neuve et base existante;
- différencie les erreurs Kimi:
  - auth,
  - transport,
  - runtime,
  - limite de contexte.

## Lire les logs correctement

### ✅ Messages désormais attendus

```text
⚠️ [API ERROR] Authentification Kimi refusée
⚠️ [API ERROR] Erreur runtime Kimi détectée
⚠️ [API ERROR] Erreur réseau/timeout Kimi
⚠️ [API ERROR] Tokens: inconnus (limite de contexte atteinte)
```

### ❌ Message trompeur à ne plus interpréter comme vérité unique

```text
⚠️ [API ERROR] Tokens: 0 (limite atteinte)
```

Si vous voyez encore ce message exact après mise à jour, il faut vérifier que le serveur lancé correspond bien au code corrigé.

## Trade-offs

| Approche | Avantage | Limite |
| -------- | -------- | ------ |
| Échouer dès que la config Kimi manque | Diagnostic immédiat | Plus strict qu’un fallback silencieux |
| Ajouter `external_session_id` au schéma et aux migrations | Compatible bases neuves et anciennes | Exige une initialisation DB correcte au démarrage |
| Garder la famille `error` mais qualifier le message | Pas de rupture frontend | La précision dépend encore du contenu réel des logs |

## Golden Rule

**Pour une session Kimi Code saine, il faut trois choses en même temps: un provider explicite, une base SQLite alignée avec l’auto-session, et des logs d’erreur qui disent la vraie panne plutôt qu’un faux dépassement de contexte.**

---

Dernière mise à jour : 2026-03-07