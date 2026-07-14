# Audit backend Kimi Proxy

Date: 2026-07-15

## TL;DR

Le backend est utilisable en environnement local contrôlé, mais il n’est pas prêt pour une exposition réseau. Les priorités sont claires: retirer l’usage de `eval`, fermer le mode proxy ouvert, ajouter une authentification minimale, corriger les erreurs runtime détectées par Ruff, puis durcir les limites de taille et les fuites d’informations.

## Périmètre

Cet audit couvre uniquement le backend Python/FastAPI de Kimi Proxy. Le frontend est hors périmètre car il est absent ou déprécié dans cette version.

Éléments analysés:

- API FastAPI et routeurs HTTP.
- Pipeline proxy OpenAI-compatible et passthrough session-less.
- Gateway MCP, pruning, masking et stockage mémoire.
- Configuration, persistance SQLite, sanitizer et logs.
- Résultats de vérification statique et tests disponibles.

Aucun pentest réseau actif n’a été effectué. Les constats reposent sur la revue statique du code, la lecture des chemins d’exécution critiques et les commandes de validation exécutées pendant l’audit.

## Architecture observée

L’application est structurée autour de `./src/kimi_proxy`:

- `./src/kimi_proxy/main.py`: factory FastAPI, middleware CORS, inclusion du routeur principal.
- `./src/kimi_proxy/api/router.py`: agrégation des routeurs API.
- `./src/kimi_proxy/api/routes/proxy.py`: route historique `POST /chat/completions` avec sessions, métriques et compaction.
- `./src/kimi_proxy/api/routes/mcp_passthrough.py`: route `POST /v1/chat/completions` session-less.
- `./src/kimi_proxy/proxy/passthrough.py`: résolution dynamique de la cible provider via headers.
- `./src/kimi_proxy/api/routes/mcp_gateway.py`: gateway JSON-RPC vers serveurs MCP locaux.
- `./src/kimi_proxy/core/database.py`: persistance SQLite, sessions et métriques.
- `./config.toml`: configuration runtime, fonctionnalités MCP, compaction, pruning et proxy.

Le design actuel mélange deux modes:

1. Un mode historique orienté sessions, métriques et auto-compaction.
2. Un mode session-less où le client fournit la cible upstream avec `X-Target-Base-URL`.

Cette coexistence explique une partie de la complexité et des défauts de sécurité: certaines routes supposent un usage local de confiance, tandis que d’autres exposent des primitives de proxy réseau.

## Points positifs

- Le backend est organisé en couches relativement lisibles: routes API, proxy, features, services, core et configuration.
- La configuration évite globalement de stocker des secrets directs dans `./config.toml`; les valeurs sensibles passent plutôt par variables d’environnement, par exemple `QDRANT_API_KEY`.
- La persistance des sessions SQLite est désactivée par défaut dans `./config.toml:39` à `./config.toml:42`.
- Le log watcher est désactivé par défaut dans `./config.toml:31` à `./config.toml:33`.
- Les requêtes SQLite inspectées utilisent des paramètres SQL plutôt que de la concaténation directe, par exemple `./src/kimi_proxy/features/sanitizer/storage.py:123` à `./src/kimi_proxy/features/sanitizer/storage.py:125`.
- Les tests E2E passent, ce qui indique que les chemins principaux couverts par ces tests restent fonctionnels.
- `python3 -m compileall -q ./src/kimi_proxy` passe, donc les fichiers Python du package compilent syntaxiquement.

## Verdict production

Statut recommandé: ne pas exposer sur un réseau non fiable avant correction des points P0.

La combinaison suivante est le risque principal:

- bind réseau par défaut sur `0.0.0.0`;
- absence d’authentification globale;
- route proxy session-less acceptant une cible arbitraire fournie par le client;
- CORS permissif;
- fallback `eval` sur arguments de tool calls;
- endpoints de gestion et d’observabilité accessibles sans garde explicite.

Dans un poste de développement local, ces choix peuvent être acceptables temporairement. Sur un serveur partagé, un conteneur exposé, une VM accessible ou un réseau d’entreprise, ils deviennent des risques critiques.

## Constat P0-01: `eval` sur arguments de tool calls

Sévérité: critique

Preuve: `./src/kimi_proxy/proxy/tool_utils.py:619` à `./src/kimi_proxy/proxy/tool_utils.py:626`.

Le fallback de réparation JSON exécute:

```python
fixed_dict = eval(fixed.replace('true', 'True').replace('false', 'False').replace('null', 'None'))
```

Ce code s’applique à des arguments de tool calls normalisés dans le pipeline proxy. Les arguments proviennent du body client ou de réponses modèle/tool potentiellement contrôlables. Même si l’intention est de corriger du JSON malformé, `eval` transforme une erreur de parsing en primitive d’exécution Python côté serveur.

Impact:

- exécution de code serveur si un attaquant peut atteindre cette branche;
- lecture ou modification de fichiers selon les permissions du processus;
- fuite de variables d’environnement, dont clés provider;
- pivot possible vers les services locaux accessibles par le processus.

Remédiation:

1. Supprimer complètement `eval`.
2. Utiliser `json.loads` comme source de vérité.
3. Si un fallback Python-like est absolument nécessaire, utiliser `ast.literal_eval`, puis valider strictement que le résultat est un `dict[str, object]` sérialisable JSON.
4. Ajouter des tests de régression avec payloads hostiles: appels à `__import__`, attributs dunder, compréhensions, lambdas, objets non JSON.
5. En cas d’échec de réparation, retourner la chaîne originale ou une erreur contrôlée, jamais exécuter.

Priorité: correction immédiate avant toute exposition réseau.

## Constat P0-02: proxy ouvert et risque SSRF via `X-Target-Base-URL`

Sévérité: critique

Preuves:

- Route session-less: `./src/kimi_proxy/api/routes/mcp_passthrough.py:24` à `./src/kimi_proxy/api/routes/mcp_passthrough.py:30`.
- Lecture de la cible client: `./src/kimi_proxy/proxy/passthrough.py:54` à `./src/kimi_proxy/proxy/passthrough.py:63`.
- Construction directe de l’endpoint: `./src/kimi_proxy/proxy/passthrough.py:264` à `./src/kimi_proxy/proxy/passthrough.py:273`.
- Bind par défaut: `./src/kimi_proxy/__main__.py:15` et `./bin/kimi-proxy:75`.

Le client peut fournir `X-Target-Base-URL`. Le backend concatène ensuite cette valeur avec `/chat/completions` pour envoyer une requête HTTP. Aucune validation de scheme, host, IP, DNS, port ou allowlist n’a été observée dans ce chemin.

Impact:

- open proxy non authentifié si le service est exposé;
- SSRF vers services internes ou metadata endpoints;
- accès potentiel à `localhost`, réseaux privés, link-local, Docker bridge, Kubernetes services;
- contournement de politiques réseau côté client en utilisant le serveur comme relais.

Remédiation:

1. Changer les valeurs par défaut de bind vers `127.0.0.1`.
2. Exiger une authentification pour `POST /v1/chat/completions` si `X-Target-Base-URL` est autorisé.
3. Remplacer la cible libre par une allowlist de providers ou domaines configurés.
4. Refuser tout scheme autre que `https`, sauf exception locale explicitement configurée.
5. Résoudre DNS et bloquer les plages privées, loopback, link-local, multicast et metadata.
6. Normaliser l’URL avec `urllib.parse`, valider host/port, puis reconstruire l’URL à partir des composants validés.
7. Journaliser le host validé, jamais l’URL complète si elle peut contenir des secrets.

Priorité: correction immédiate.

## Constat P0-03: absence d’authentification globale sur routes sensibles

Sévérité: critique si exposition réseau, élevée en local partagé

Preuves:

- Inclusion des routeurs sans dépendance auth visible: `./src/kimi_proxy/api/router.py:23` à `./src/kimi_proxy/api/router.py:36`.
- Routes sanitizer: `./src/kimi_proxy/api/routes/sanitizer.py:22` à `./src/kimi_proxy/api/routes/sanitizer.py:80`.
- Routes mémoire MCP: `./src/kimi_proxy/api/routes/mcp.py:71` à `./src/kimi_proxy/api/routes/mcp.py:120`.
- Route gateway MCP: `./src/kimi_proxy/api/routes/mcp_gateway.py:296` à `./src/kimi_proxy/api/routes/mcp_gateway.py:320`.
- Health check détaillé: `./src/kimi_proxy/api/routes/health.py:59` à `./src/kimi_proxy/api/routes/health.py:75`.

Aucune dépendance FastAPI d’authentification globale n’a été trouvée autour des routeurs sensibles. Plusieurs endpoints permettent de lire ou modifier de l’état interne: sanitizer, mémoire, compression, gateway MCP, sessions et health détaillé.

Impact:

- lecture d’informations internes;
- modification de paramètres runtime, par exemple toggle sanitizer;
- déclenchement d’appels vers serveurs MCP locaux;
- abus de ressources CPU, mémoire ou réseau;
- exposition de chemins locaux et état session.

Remédiation:

1. Ajouter une dépendance d’authentification commune sur les routeurs sensibles.
2. Prévoir une clé admin locale via variable d’environnement, au minimum pour `/api/*` hors routes strictement publiques.
3. Séparer routes publiques, routes admin et routes internal-only.
4. Retourner un `/health` minimal par défaut: `status`, `version`, éventuellement uptime.
5. Déplacer les détails de diagnostic vers `/api/admin/health` protégé.

## Constat P0-04: CORS permissif avec credentials

Sévérité: élevée à critique selon exposition

Preuve: `./src/kimi_proxy/main.py:163` à `./src/kimi_proxy/main.py:170`.

La configuration CORS autorise toutes les origines, méthodes et headers, avec `allow_credentials=True`.

Impact:

- surface d’abus depuis un navigateur si une authentification par cookie ou header persistant est ajoutée plus tard;
- politique incompatible avec un durcissement production;
- confusion entre usage local de développement et usage exposé.

Remédiation:

1. Remplacer `allow_origins=["*"]` par une liste explicite.
2. Désactiver `allow_credentials` par défaut.
3. Lire les origins autorisées depuis config ou variable d’environnement.
4. En mode développement, limiter à `http://127.0.0.1:*` et `http://localhost:*` si nécessaire.

## Constat P1-01: réponse non-streaming réussie renvoyée comme erreur

Sévérité: élevée

Preuve: `./src/kimi_proxy/api/routes/proxy.py:649` à `./src/kimi_proxy/api/routes/proxy.py:652`.

Dans la route historique `POST /chat/completions`, après le chemin non-streaming, le code retourne:

```python
return JSONResponse(
    content={"error": response.text},
    status_code=response.status_code
)
```

Si le provider répond avec succès en non-streaming, le client peut recevoir un objet `error` au lieu de la réponse JSON provider.

Impact:

- incompatibilité OpenAI-compatible;
- clients qui traitent une réponse réussie comme erreur applicative;
- métriques et workflows aval incohérents.

Remédiation:

1. Pour `2xx`, retourner `response.json()` si JSON valide.
2. Si JSON invalide, retourner un `Response` brut avec content-type provider filtré.
3. Conserver les branches d’erreur `4xx/5xx` séparées.
4. Ajouter tests pour `stream=false`, provider `200`, provider `401`, provider `429`, body JSON invalide.

## Constat P1-02: erreurs runtime détectées par Ruff `F821`

Sévérité: élevée

Preuves principales:

- `./src/kimi_proxy/api/routes/proxy.py:385` et `./src/kimi_proxy/api/routes/proxy.py:388` utilisent `build_gemini_endpoint` et `convert_to_gemini_format` sans import local dans ce fichier.
- `./src/kimi_proxy/api/routes/proxy.py:691` utilise `detect_and_store_memories` sans import visible.
- `./src/kimi_proxy/api/routes/compaction.py:63` utilise `get_recent_metrics` avant l’import local existant plus bas dans le fichier.
- `./src/kimi_proxy/api/routes/compaction.py:568` référence `totals`, qui n’est pas défini dans ce scope.

Les commandes de lint ont confirmé 256 erreurs Ruff, dont plusieurs `F821 Undefined name`. Ces erreurs sont prioritaires car elles correspondent à des crashs runtime sur chemins atteignables.

Impact:

- exceptions `NameError` en production;
- branches Gemini et mémoire MCP cassées;
- endpoints compaction instables;
- dette technique qui masque les vrais défauts.

Remédiation:

1. Corriger d’abord tous les `F821`.
2. Ajouter ou déplacer les imports nécessaires.
3. Remplacer le fallback `totals` par une valeur définie ou une erreur contrôlée.
4. Configurer CI pour échouer sur `ruff check ./src ./tests`.
5. Traiter ensuite les autres règles Ruff par lots.

## Constat P1-03: sanitizer stocke et réexpose le contenu original sensible

Sévérité: élevée

Preuves:

- Écriture disque du contenu original: `./src/kimi_proxy/features/sanitizer/storage.py:87` à `./src/kimi_proxy/features/sanitizer/storage.py:99`.
- Écriture SQLite du contenu original: `./src/kimi_proxy/features/sanitizer/storage.py:103` à `./src/kimi_proxy/features/sanitizer/storage.py:112`.
- Réexposition via API: `./src/kimi_proxy/api/routes/sanitizer.py:31` à `./src/kimi_proxy/api/routes/sanitizer.py:39`.

Le sanitizer masque des contenus, mais conserve `original_content` en clair sur disque et en base, puis le retourne via `GET /api/mask/{content_hash}`.

Impact:

- fuite de prompts, code source, secrets accidentels ou données client;
- stockage durable de données que l’utilisateur croit masquées;
- endpoint de récupération non protégé;
- risque accru en cas de compromission du disque ou de la base SQLite.

Remédiation:

1. Ne pas stocker `original_content` par défaut.
2. Si conservation requise, chiffrer côté serveur avec clé dédiée hors dépôt.
3. Protéger l’endpoint de récupération par auth admin.
4. Ajouter TTL et purge automatique des contenus masqués.
5. Retourner uniquement hash, preview, tags, token count et metadata non sensibles par défaut.

## Constat P1-04: fuite partielle de clés API dans les logs

Sévérité: élevée

Preuves:

- `./src/kimi_proxy/api/routes/proxy.py:332` à `./src/kimi_proxy/api/routes/proxy.py:337`.
- `./src/kimi_proxy/proxy/passthrough.py:231` à `./src/kimi_proxy/proxy/passthrough.py:236`.

Les logs affichent les premiers caractères des clés API. Même tronquées, ces valeurs peuvent être sensibles: elles facilitent la corrélation entre environnements, providers et incidents.

Impact:

- fuite partielle dans `server.log`, journaux systemd, conteneurs ou collecteurs centralisés;
- exposition indirecte de provider utilisé;
- réduction de l’entropie effective lors d’une autre fuite.

Remédiation:

1. Ne jamais journaliser de fragment de clé.
2. Remplacer par un booléen: clé présente ou absente.
3. Si traçabilité nécessaire, journaliser un fingerprint HMAC non réversible avec clé de log séparée.
4. Ajouter tests ou règles de lint simples pour éviter `api_key[:...]` dans les logs.

## Constat P1-05: clé Gemini placée dans l’URL

Sévérité: élevée

Preuve: `./src/kimi_proxy/proxy/transformers.py:7` à `./src/kimi_proxy/proxy/transformers.py:26`.

`build_gemini_endpoint` construit une URL contenant `?key={api_key}`.

Impact:

- la clé peut apparaître dans logs HTTP, traces, exceptions, proxies, APM et historiques;
- difficile à filtrer partout;
- fuite plus probable que via header.

Remédiation:

1. Préférer un header si l’API provider le supporte.
2. Si Gemini impose la query string pour ce mode, centraliser la redaction stricte de toute URL avant logging.
3. Ne jamais inclure `target_endpoint` complet dans les erreurs utilisateur.
4. Ajouter une fonction de sanitation d’URL qui masque `key`, `api_key`, `token`, `authorization`.

## Constat P1-06: absence de limites de taille request/stream explicites

Sévérité: élevée

Preuves:

- Lecture complète du body dans `./src/kimi_proxy/api/routes/proxy.py:115`.
- Bufferisation du stream: `./src/kimi_proxy/proxy/stream.py:41`, `./src/kimi_proxy/proxy/stream.py:54` et `./src/kimi_proxy/proxy/stream.py:60`.
- Décodage complet du buffer: `./src/kimi_proxy/proxy/stream.py:254`.

Le proxy lit le body complet et accumule les chunks streamés en mémoire pour extraire les tokens d’usage.

Impact:

- consommation mémoire non bornée;
- déni de service par body volumineux ou stream long;
- pression GC et latence sous charge;
- risque accru si plusieurs streams concurrents.

Remédiation:

1. Ajouter limite de taille body via middleware ASGI ou vérification `Content-Length` plus compteur de lecture.
2. Configurer une limite stricte pour les payloads JSON.
3. Limiter le buffer de stream aux derniers N kilo-octets utiles pour extraire `usage`.
4. Ajouter timeouts par chunk réellement appliqués.
5. Définir quotas par IP ou par clé auth.

## Constat P1-07: cache MCP Gateway global non borné et mutation des objets cachés

Sévérité: moyenne à élevée

Preuves:

- Cache global: `./src/kimi_proxy/api/routes/mcp_gateway.py:158` à `./src/kimi_proxy/api/routes/mcp_gateway.py:159`.
- Lecture cache: `./src/kimi_proxy/api/routes/mcp_gateway.py:237` à `./src/kimi_proxy/api/routes/mcp_gateway.py:243`.
- Mutation en place: `./src/kimi_proxy/api/routes/mcp_gateway.py:240` à `./src/kimi_proxy/api/routes/mcp_gateway.py:242`.
- Écriture sans limite: `./src/kimi_proxy/api/routes/mcp_gateway.py:245` à `./src/kimi_proxy/api/routes/mcp_gateway.py:252`.

Le cache TTL est un dictionnaire global sans taille maximale. Lors d’un hit, le code ajoute `_gateway_cached` directement sur l’objet de réponse stocké.

Impact:

- croissance mémoire non bornée si les clés varient;
- pollution des réponses cachées;
- comportements difficiles à reproduire;
- risque de fuite entre requêtes si les réponses contiennent des champs contextuels.

Remédiation:

1. Utiliser un cache LRU avec `maxsize` configurable.
2. Copier profondément la réponse avant d’ajouter `_gateway_cached`.
3. Supprimer ou rendre optionnel le champ `_gateway_cached`.
4. Ajouter métriques de taille cache, hits et evictions.
5. Nettoyer périodiquement les entrées expirées.

## Constat P2-01: compaction instable et duplication de persistance

Sévérité: moyenne

Preuves:

- Double persistance: `./src/kimi_proxy/api/routes/compaction.py:115` à `./src/kimi_proxy/api/routes/compaction.py:121`.
- Fallback messages de test: `./src/kimi_proxy/api/routes/compaction.py:78` à `./src/kimi_proxy/api/routes/compaction.py:92`.
- Variable non définie `totals`: `./src/kimi_proxy/api/routes/compaction.py:562` à `./src/kimi_proxy/api/routes/compaction.py:568`.

La route de compaction persiste deux fois le même résultat. Si les métriques récentes sont insuffisantes, elle bascule sur des messages de test hardcodés. Un autre endpoint fallback sur `totals`, non défini.

Impact:

- données de compaction dupliquées;
- résultats artificiels qui ne reflètent pas la session réelle;
- crash runtime sur endpoint de statut;
- bruit dans les métriques et l’UX.

Remédiation:

1. Supprimer le second `persist_compaction_result`.
2. Ne jamais compacter des messages de test en production.
3. Retourner une réponse contrôlée si les données réelles sont insuffisantes.
4. Corriger `totals` en utilisant `session_totals` ou une valeur par défaut explicite.
5. Ajouter tests unitaires sur sessions sans métriques, sessions avec peu de messages et erreurs DB.

## Constat P2-02: pruning MCP activé par défaut malgré son rôle avancé

Sévérité: moyenne

Preuve: `./config.toml:68` à `./config.toml:70`.

`[mcp_tool_pruning] enabled = true`, alors que le commentaire indique une volonté de middleware minimaliste. Les tests unitaires du moteur de pruning montrent deux régressions.

Impact:

- latence et complexité par défaut;
- dépendance à des comportements de pruner dans le chemin gateway;
- risque de modifier des réponses MCP de manière inattendue;
- surface de bugs plus élevée.

Remédiation:

1. Désactiver par défaut dans la configuration de base.
2. Exiger opt-in explicite.
3. Corriger les deux tests unitaires en échec dans `./tests/unit/features/test_mcp_tool_pruning_engine.py`.
4. Ajouter métriques d’efficacité et taux de fail-open.

## Constat P2-03: `/health` expose trop de détails

Sévérité: moyenne

Preuve: `./src/kimi_proxy/api/routes/health.py:59` à `./src/kimi_proxy/api/routes/health.py:75`.

Le health check retourne `active_session`, chemins de logs, états des sources et état du rate limiter.

Impact:

- fuite de chemins locaux;
- exposition d’état session;
- meilleure reconnaissance pour un attaquant;
- couplage entre endpoint de disponibilité et diagnostics internes.

Remédiation:

1. `/health`: réponse minimale.
2. `/api/admin/health`: réponse détaillée protégée.
3. Masquer chemins absolus ou ne retourner que des booléens.
4. Garder les métriques détaillées derrière auth et feature flag.

## Constat P2-04: dépendances de sécurité manquantes dans l’environnement dev

Sévérité: faible à moyenne

Preuve: `./requirements-dev.txt:11` à `./requirements-dev.txt:20` ne contient pas Bandit. La commande `python3 -m bandit -r ./src/kimi_proxy -q` n’a pas pu s’exécuter car Bandit n’est pas installé.

Impact:

- absence de scan sécurité simple en local et CI;
- détection tardive de patterns dangereux comme `eval`;
- dette sécurité non visible dans les checks standard.

Remédiation:

1. Ajouter `bandit` aux dépendances dev.
2. Ajouter une cible CI pour Bandit.
3. Configurer des suppressions seulement avec justification ciblée.
4. Ajouter éventuellement `pip-audit` ou équivalent pour vulnérabilités de dépendances.

## Vérifications exécutées

Commandes et résultats observés pendant l’audit:

```text
python -m ...
Résultat: échec, binaire python indisponible dans l’environnement.

python3 -m compileall -q ./src/kimi_proxy
Résultat: succès.

python3 -m pytest ./tests/e2e -q
Résultat: 15 passed.

python3 -m pytest ./tests/unit ./tests/integration -q
Résultat: 204 passed, 2 failed, 64 warnings.
Échecs: ./tests/unit/features/test_mcp_tool_pruning_engine.py.

python3 -m pytest ./tests/mcp -q -m "not e2e"
Résultat: échec en collection.
Cause: modules/classes MCP attendus absents, notamment TaskMasterMCPClient, FileSystemMCPClient, JsonQueryMCPClient, SequentialThinkingMCPClient.

python3 -m ruff check ./src ./tests
Résultat: 256 errors.
Points critiques: plusieurs F821 Undefined name.

python3 -m mypy ./src/kimi_proxy
Résultat: 120 errors in 29 files.

python3 -m bandit -r ./src/kimi_proxy -q
Résultat: impossible, Bandit non installé.
```

Interprétation:

- La compilation Python et les E2E valident une base fonctionnelle.
- Les échecs unitaires ciblent le pruning MCP, donc une feature avancée activée par défaut.
- Ruff signale des erreurs runtime concrètes qui doivent précéder les refactors stylistiques.
- Mypy confirme une dette de typage significative, mais moins urgente que `eval`, SSRF et `F821`.

## Plan de remédiation priorisé

### P0: avant toute exposition réseau

1. Supprimer `eval` de `./src/kimi_proxy/proxy/tool_utils.py`.
2. Remplacer le bind par défaut `0.0.0.0` par `127.0.0.1`.
3. Ajouter une authentification minimale pour routes proxy, MCP, sanitizer, mémoire et admin.
4. Valider strictement ou supprimer `X-Target-Base-URL` libre.
5. Restreindre CORS à des origins explicites.
6. Réduire `/health` à un statut minimal.

### P1: stabilisation fonctionnelle

1. Corriger les `F821` Ruff.
2. Corriger la réponse non-streaming de `./src/kimi_proxy/api/routes/proxy.py`.
3. Protéger ou désactiver la réexposition du contenu original sanitizer.
4. Supprimer tout logging de fragments de clés API.
5. Ajouter limites de taille body et stream.
6. Corriger la compaction double-persist et les fallbacks non définis.

### P2: durcissement et maintenabilité

1. Désactiver `mcp_tool_pruning` par défaut, puis corriger les tests en échec.
2. Ajouter Bandit et scans dépendances en CI.
3. Borner le cache MCP Gateway.
4. Nettoyer les routes et imports obsolètes.
5. Réduire progressivement les erreurs mypy.
6. Séparer clairement mode local-dev, mode session-less et mode production.

## Recommandation d’architecture cible

L’architecture devrait distinguer trois profils runtime:

### Profil local-dev

- Bind `127.0.0.1`.
- CORS permissif limité à localhost.
- Auth optionnelle mais avertissement visible si absente.
- Gateway MCP et pruning activables pour expérimentation.

### Profil production minimal

- Auth obligatoire.
- Providers configurés en allowlist.
- Pas de `X-Target-Base-URL` libre.
- `/health` minimal.
- Pas de stockage clair de contenu original.
- Limites body, stream, timeout et cache.

### Profil internal-lab

- Peut autoriser certains services MCP locaux.
- Doit conserver auth, allowlist réseau et limites de ressources.
- Diagnostics détaillés derrière routes admin.

Cette séparation évite de traiter un middleware local expérimental comme un backend exposable par défaut.

## Conclusion

Kimi Proxy possède une base backend exploitable et une séparation de modules globalement compréhensible. Le problème principal n’est pas l’absence de structure; c’est le décalage entre un usage local de confiance et des primitives réseau puissantes exposées sans garde suffisante.

La première itération doit être courte et défensive: retirer `eval`, fermer le proxy ouvert, ajouter auth, limiter CORS et corriger les `F821`. Une fois ces risques traités, les chantiers de stabilité: compaction, pruning, sanitizer, cache et typage, pourront être abordés sans masquer les vulnérabilités critiques.
