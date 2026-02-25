# Configurer Cline pour consommer des serveurs MCP via HTTP et corriger “Invalid MCP settings schema” avec un endpoint JSON‑RPC over HTTP POST

## Analyse du problème et pourquoi l’erreur apparaît avant même toute connexion réseau

L’erreur **“Invalid MCP settings schema”** dans Cline ne provient pas d’un échec de connexion à votre MCP Gateway, mais d’un échec de **validation du fichier `cline_mcp_settings.json`** au chargement. Dans le code de Cline, le fichier est d’abord parsé en JSON ; si le parsing échoue, Cline affiche un message du type “Invalid MCP settings format…”. Ensuite, Cline valide l’objet JSON obtenu via un schéma Zod ; **si cette validation échoue, Cline affiche précisément “Invalid MCP settings schema.”** citeturn12view1

Dans votre cas, le déclencheur le plus probable est la valeur de transport que vous avez essayée : vous avez remplacé `command/args/env` par `url` et changé `type` de `"stdio"` à `"http"` (avec parfois `headers`) pour pointer vers `…/api/mcp-gateway/{server}/rpc`. Votre fichier montre explicitement plusieurs serveurs déclarés avec **`"type": "http"`**. fileciteturn0file0  
Or, **`"http"` n’est pas une valeur valide pour le champ `type` dans Cline** (d’où la validation qui échoue et donc l’erreur “Invalid MCP settings schema”).

Il est important de noter que **la présence de JSON valide n’implique pas une configuration valide** : le JSON peut être syntactiquement correct, mais refuser le schéma (ex. enum de `type`, URL invalide, mauvais type de champ). citeturn12view1

## Ce que Cline supporte réellement côté transports MCP en 2026

### Cline supporte bien MCP over HTTP, mais sous le nom “Streamable HTTP”
Contrairement à l’idée “Cline = stdio + sse uniquement”, la doc Cline indique qu’en **remote**, Cline supporte :
- **Streamable HTTP (recommandé)**  
- **SSE (legacy)** citeturn1view0turn2view4

Et côté implémentation, Cline importe explicitement les transports du SDK MCP, dont **`StreamableHTTPClientTransport`** (en plus de `SSEClientTransport` et `StdioClientTransport`). citeturn12view1

### Pourquoi “JSON‑RPC over HTTP POST” n’est pas synonyme de “type: http” dans Cline
Le standard MCP s’appuie sur **JSON‑RPC** pour encoder les messages, et la spécification modernisée définit deux transports standards : **stdio** et **Streamable HTTP**. citeturn4view0  
Dans Streamable HTTP, **chaque message JSON‑RPC côté client est envoyé via HTTP POST** sur un endpoint MCP unique ; le serveur peut répondre en JSON ou ouvrir un flux SSE selon la négociation de contenu. citeturn4view0turn4view2  
Donc, votre besoin “POST JSON‑RPC 2.0” correspond conceptuellement à **Streamable HTTP**, mais **dans Cline le transport s’appelle `streamableHttp` (camelCase)** — pas `http`.

## Schéma JSON attendu par Cline et décodage précis de “Invalid MCP settings schema”

### Le schéma exact (source : code de Cline)
Le schéma Zod de Cline attend un objet :

- Racine : `{ "mcpServers": { "<nom>": <configServeur> } }` citeturn12view0  
- Pour `<configServeur>`, Cline accepte **trois formes** (union) :  
  - **stdio** : présence de `command` (obligatoire), `args/env/cwd` optionnels  
  - **sse** : présence de `url` (obligatoire, format URL valide), `headers` optionnel  
  - **streamableHttp** : présence de `url` (obligatoire, format URL valide), `headers` optionnel citeturn12view0  

Les champs “transverses” reconnus au niveau de chaque serveur incluent notamment : `autoApprove`, `disabled`, `timeout` (avec minimum), et un marqueur interne `remoteConfigured`. citeturn12view0

**Point clé** : le champ `type` (si présent) doit être l’un de :
- `"stdio"`
- `"sse"`
- `"streamableHttp"` citeturn12view0turn2view4

Donc :
- ✅ `type: "streamableHttp"` est valide  
- ❌ `type: "http"` est invalide → **Zod refuse** → “Invalid MCP settings schema”  

Cela colle aussi avec des cas observés en communauté (ex. utilisateurs configurant `type: "http"` et rencontrant la même erreur). citeturn20view0

### Subtilité importante : si vous omettez `type`, Cline risque de “matcher” SSE par défaut
Le schéma de Cline est une union qui teste d’abord la variante stdio, puis **SSE**, puis streamable HTTP. Le fichier `schemas.ts` documente explicitement que **les configs “URL‑only” matchent SSE avant d’atteindre Streamable HTTP**. citeturn12view0turn15view0  
Conséquence pratique : si vous mettez juste `"url": "…"`, vous pouvez vous retrouver “SSE par défaut”, même si votre endpoint est en réalité Streamable HTTP. Un bug/limitation de ce comportement est discuté publiquement côté Cline. citeturn15view0turn1view0

### Différences de naming entre outils (source fréquente d’erreurs)
Si vous copiez une config depuis un autre client MCP, attention :  
- Continue documente `type: streamable-http` (kebab-case) citeturn18view0  
- Cline attend `type: streamableHttp` (camelCase) citeturn2view4turn12view0  
Cette différence suffit à déclencher “Invalid MCP settings schema”.

## Configurations recommandées pour un endpoint MCP Gateway en JSON‑RPC over HTTP POST

### Configuration finale proposée pour Cline (cas Streamable HTTP)
Si votre endpoint `/api/mcp-gateway/{server_name}/rpc` accepte bien des requêtes MCP sur HTTP (POST JSON‑RPC) et se comporte comme un endpoint Streamable HTTP (au minimum en répondant en JSON), la correction de schéma la plus directe est :

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "type": "streamableHttp",
      "url": "http://localhost:8000/api/mcp-gateway/sequential-thinking/rpc",
      "headers": {},
      "timeout": 60,
      "disabled": false,
      "autoApprove": ["<NOMS_DES_TOOLS_A_AUTO_APPROUVER>"]
    }
  }
}
```

Ce format correspond à “Advanced Configuration” côté documentation Cline (URL + type + disabled/autoApprove/timeout). citeturn2view4turn1view0  
Et il est compatible avec le schéma réel (variant Streamable HTTP : `type: "streamableHttp"` + `url` + `headers` optionnels + champs transverses). citeturn12view0

**Application à votre fichier** : dans votre `cline_mcp_settings.json`, remplacez pour chaque serveur concerné la valeur `"type": "http"` par `"type": "streamableHttp"`. Votre fichier contient plusieurs serveurs dans ce cas. fileciteturn0file0

### Variante SSE (si votre gateway expose aussi un endpoint SSE)
Cline supporte aussi SSE pour remote servers, avec `url` et `headers` (ex. Bearer token), tel que documenté dans “Adding & Configuring Servers”. citeturn3view4turn1view2  
Dans ce cas :

```json
{
  "mcpServers": {
    "my-remote-sse": {
      "type": "sse",
      "url": "https://<votre-gateway-ou-server>/sse",
      "headers": { "Authorization": "Bearer <token>" },
      "timeout": 60
    }
  }
}
```

### Résultat attendu après correction du `type`
Une fois `type` corrigé (et l’URL valide), vous ne devriez plus voir “Invalid MCP settings schema” (puisque la validation devrait passer). À ce moment-là, si votre endpoint est incompatible MCP/transport, l’erreur changera : elle deviendra un **problème de connexion/handshake** (timeout, 4xx/5xx, méthodes non supportées, etc.), mais ce sera une étape “saine” : vous aurez franchi la barrière de validation locale. citeturn12view1turn4view0

## Procédure de validation et dépannage si ça ne connecte pas après correction du schéma

### Vérifier que l’endpoint correspond bien au transport Streamable HTTP
La spec Streamable HTTP impose notamment :
- envoi des messages via **HTTP POST** sur l’endpoint MCP ;
- présence d’un header `Accept` supportant `application/json` et `text/event-stream` côté client ;
- réponses possibles en `application/json` (réponse unique) ou `text/event-stream` (stream) ;
- option de GET pouvant répondre `text/event-stream` ou `405 Method Not Allowed` si le serveur ne propose pas de stream “listen-only”. citeturn4view0turn4view2  

Si votre gateway est un “MCP Gateway” standard (ex. solutions connues type Microsoft MCP Gateway ou ContextForge), leurs endpoints “client” Streamable HTTP sont typiquement exposés sous un chemin `/…/mcp` (et non forcément `/rpc`). Par exemple, Microsoft décrit l’accès data-plane via `POST /adapters/{name}/mcp` (Streamable HTTP) et utilise des exemples de config `.vscode/mcp.json` pointant vers `/adapters/{name}/mcp`. citeturn10view0  
Si votre gateway a **une route `/mcp` distincte** et que `/rpc` est une route interne ou “JSON-RPC fallback”, il est plausible que Cline doive viser `/mcp` plutôt que `/rpc`.

### Attention : état actuel et bugs/edge cases côté Cline sur Streamable HTTP
Il existe des issues publiques où des utilisateurs signalent des comportements inattendus (ex. tentative de GET / problèmes de méthode) lorsqu’ils testent Streamable HTTP dans Cline. citeturn13view0turn15view0  
Cela ne veut pas dire “impossible”, mais cela implique que si la connexion échoue après correction du schéma, vous devez distinguer :
- **problème de transport/interop** (endpoint pas conforme Streamable HTTP) ;
- **bug côté Cline/SDK** sur un cas particulier.

## Alternatives et workarounds viables si votre MCP Gateway “POST JSON‑RPC /rpc” n’est pas compatible Streamable HTTP pour Cline

### Workaround robuste : convertir HTTP→stdio (proxy local)
Si Cline refuse/échoue en remote (streamableHttp) mais que votre gateway répond bien aux requêtes JSON‑RPC en POST, le workaround le plus fiable est de **repasser Cline en stdio** (très stable) et d’interposer un petit “bridge” local qui :
- lit des messages JSON‑RPC ligne-par-ligne sur stdin ;
- fait `POST` vers votre endpoint `/rpc` ;
- renvoie la réponse sur stdout.

Ce contournement s’aligne sur le transport stdio MCP (messages JSON‑RPC UTF‑8 délimités par newline, sans newlines embarqués). citeturn4view0turn1view1  

Dans votre fichier, vous gardez alors une config stdio (avec `command/args`) au lieu d’une config URL. Le bénéfice immédiat : vous sortez des subtilités Streamable HTTP (GET/Accept/SSE/session) et vous “parlez” à votre gateway comme un simple client HTTP.

### Workaround “prêt à l’emploi” si vous utilisez ContextForge/IBM MCP Gateway
Si votre “MCP Gateway” est (ou ressemble à) ContextForge, il existe un wrapper officiel côté gateway permettant d’exposer un endpoint HTTP en **stdio** (“mcpgateway.wrapper”). La doc montre le principe : définir `MCP_SERVER_URL` et `MCP_AUTH`, puis lancer `python3 -m mcpgateway.wrapper`, ce qui fournit une interface stdio consommable par des clients MCP. citeturn9view4turn8view0  

### Impact sur l’expérience utilisateur (trade-offs)
Passer de remote HTTP natif à stdio+proxy a des impacts :
- **Fiabilité accrue dans Cline** : stdio est le chemin le plus éprouvé dans Cline et ne dépend pas de la négociation SSE/GET/proxy réseau. citeturn1view1turn12view0  
- **Complexité d’exploitation** : vous devez exécuter un process local (le proxy) en tâche de fond.
- **Observabilité** : vous pouvez centraliser la journalisation dans le proxy (utile pour diagnostiquer le handshake MCP et les méthodes réellement appelées).
- **Sécurité** : si vous passez des tokens dans `headers` ou via env, préférez les variables d’environnement plutôt que de committer des secrets dans le JSON. (Votre fichier contient déjà des informations sensibles ; évitez de le partager tel quel.) fileciteturn0file0  

---

**Synthèse actionnable (le “fix” le plus probable pour votre erreur actuelle)** : dans Cline, le transport HTTP ne se configure pas avec `type: "http"`, mais avec **`type: "streamableHttp"`** (ou `type: "sse"` si vous avez un endpoint SSE). Le message “Invalid MCP settings schema” est cohérent avec une valeur `type` non reconnue, car Cline rejette toute configuration qui ne respecte pas son schéma Zod. citeturn12view0turn12view1turn2view4