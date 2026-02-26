# Optimisation de la fenêtre de contexte via MCP : état de l’art et pistes concrètes pour un Meta‑Serveur « filtre actif »

## Résumé exécutif

Le **Model Context Protocol (MCP)**, open‑sourcé par Anthropic fin 2024, standardise la connexion bidirectionnelle entre des clients (assistants/agents) et des serveurs exposant **outils**, **ressources** et **prompts**. citeturn30view0turn0search4 Dans votre cas, **le client (Cline) est une boîte noire et coûteuse en tokens** : la principale opportunité est donc de **réduire la quantité de texte “observable”** renvoyé par les outils et ressources, *avant* qu’il n’entre dans la fenêtre de contexte.

L’état de l’art (2026‑02‑24) côté écosystème MCP converge vers quatre familles de techniques, dont plusieurs ont déjà des implémentations directement réutilisables :  
- **Troncature / pagination / lecture partielle** au niveau des outils (ex. `max_length` + `start_index`, `head`/`tail`, limites `maxEntries`). citeturn11view0turn10view1turn22view0  
- **Externalisation des gros outputs** vers des **ResourceLinks / URIs éphémères**, en ne renvoyant au LLM qu’un *handle* court et des métadonnées (pattern “handle, not payload”). citeturn22view0turn27view0turn31view1  
- **Filtrage/post‑traitement** au niveau “gateway/proxy” via des hooks (`tool_post_invoke`, `resource_post_fetch`) : garde de longueur, summarizer, redaction, cache. citeturn12view0turn19view0turn19view1turn19view2  
- **Gestion de contexte “agentique”** validée par la recherche : **Observation Masking** (masquage/omission d’observations anciennes) peut être **≈2× moins cher** que l’historique brut, et **aussi efficace que la summarisation LLM** dans SWE‑bench Verified (selon une étude JetBrains Research). citeturn33search0turn33search2turn33search3  

---

## Fondamentaux MCP utiles pour construire un Meta‑Serveur filtrant

### MCP comme surface de contrôle des “observations”
MCP vise à remplacer des intégrations ad‑hoc par un protocole unique “clients ↔ serveurs”, pour connecter les assistants aux systèmes où vivent les données. citeturn30view0turn0search4 Cette architecture est **stateful** : les clients maintiennent des connexions persistantes vers des serveurs, ce qui rend possible la **mémoire côté serveur** (sessions, caches, index, hashes). citeturn0search4

### Le levier principal : transformer ce qui devient du texte dans le contexte
Dans MCP, les réponses d’outils (`tools/call`) renvoient une liste de blocs de contenu (texte, etc.). citeturn3view0turn29view1 Les versions récentes du standard supportent aussi des **Resource Links** et/ou des **ressources embarquées** : l’idée est de faire transiter *un pointeur* plutôt que l’intégralité du dataset. citeturn29view1turn27view0turn31view1  
C’est fondamental pour votre objectif : **le “payload complet” ne doit pas être injecté** dans le contexte du LLM (Cline), sauf nécessité.

### Ressources, abonnements et annotations : primitives exploitées pour les “deltas”
Le standard **Resources** prévoit (optionnellement) des **subscriptions** et des notifications `notifications/resources/updated`, et les ressources peuvent comporter des **annotations** (audience, priorité, lastModified) afin d’aider le client à filtrer/prioriser ce qu’il charge en contexte. citeturn4view0turn4view4  
Même si MCP ne “standardise” pas le concept de diff sémantique, ces primitives permettent un pattern robuste : **signaler qu’une ressource a changé**, puis laisser le client récupérer seulement ce dont il a besoin (ou un diff fourni par un outil dédié).

---

## Passerelles/proxies MCP et systèmes de hooks déjà implémentés

### ContextForge (IBM) : proxy/gateway MCP extensible avec plugins de transformation
**IBM/mcp-context-forge** se présente explicitement comme une **gateway/proxy** “production-grade” devant des serveurs MCP (mais aussi REST/gRPC), avec gouvernance, observabilité, fédération et extensibilité via plugins. citeturn12view0turn14view0  
Ce projet est particulièrement pertinent pour vous car il fournit **déjà** des hooks et des plugins alignés sur votre “Meta‑Serveur MCP filtre actif”, notamment :

- **Output Length Guard Plugin** : post‑traitement `tool_post_invoke` qui **impose une longueur min/max** et peut **truncate** ou **block** la sortie (avec ellipsis), en restant conservateur sur les types supportés. citeturn19view0  
- **Summarizer Plugin** : applique une **summarisation LLM** au‑delà d’un seuil de longueur, et peut s’appliquer à la fois aux **tool outputs** et aux **resource contents** (`resource_post_fetch`, `tool_post_invoke`). Il inclut un *hard truncate* pour borner le coût de la summarisation. citeturn19view1  
- **Resource Filter Plugin** : montre comment bloquer/limiter la taille, filtrer/redacter des patterns, et surtout **maintenir un state entre hooks** via `context.set_state()` / `get_state()`. citeturn19view2  
- **Cached Tool Result Plugin** : cache en mémoire de résultats idempotents avec TTL et clés dérivées d’arguments (utile pour éviter des re‑lectures/re‑listings coûteux). citeturn19view3  

À distinguer de la compression “réseau” : ContextForge documente aussi une **compression HTTP** (Brotli/Zstd/GZip) pour réduire bande passante/latence, mais cela ne réduit pas la taille “en tokens” du texte finalement consommé par le LLM (puisque le client doit décompresser). citeturn16view0

### Proxies “transparents” orientés sécurité : mcproxy
Le dépôt **asii-mov/mcproxy** illustre un pattern de **proxy transparent** entre client MCP et serveur MCP, qui **sanitize** entrées/sorties et valide les messages JSON‑RPC, tout en restant compatible protocolairement. citeturn20view0  
Même si son objectif principal est la sécurité (injections, etc.), l’architecture est directement transposable à un proxy de **compression** ou **masquage** : vous interceptez `tools/call` et réécrivez `result.content` avant retour.

### Réduire la “taxe tokens” des définitions d’outils (outil‑catalog) : mcp-tokens et toolsets dynamiques
Une partie non négligeable du coût de contexte vient des **descriptions + schémas** des outils exposés. Le projet **sd2k/mcp-tokens** sert à analyser combien de tokens chaque outil (nom, description, input schema) consomme et à suivre des régressions (CI). citeturn27view2  
Côté stratégies, Speakeasy décrit des **Dynamic Toolsets** (ex. triptyque `search_tools` / `describe_tools` / `execute_tool`) visant à ne charger en contexte que les schémas nécessaires, avec des gains revendiqués très élevés sur de grands toolsets. citeturn27view3  
Dans un environnement type Cline, c’est un levier complémentaire : **moins d’outils exposés**, ou exposition progressive.

---

## Compression/troncature pour `read_file` et `list_directory` : implémentations et patterns réutilisables

### Le problème est réel côté clients : Cline peut sur‑injecter les lectures de fichiers
Un issue Cline documente que `read_file` peut renvoyer l’intégralité d’un gros JSON (≥100 000 caractères), remplissant inutilement la fenêtre de contexte et menant à des overflows. citeturn31view2  
C’est exactement le scénario où un Meta‑Serveur MCP “filtre actif” devient rationnel : le client ne tronque pas, donc **le serveur doit limiter**.

### Serveur Filesystem “référence” (officiel) : lecture partielle intégrée
Le serveur officiel **Filesystem MCP Server** inclut `read_text_file` avec paramètres `head` et `tail` (lecture des N premières/dernières lignes), plus `list_directory`, `directory_tree`, etc. citeturn10view1  
Ce design est déjà une forme de “compression heuristique” basée sur **extraits** plutôt que contenu intégral. Si vous construisez un Meta‑Serveur, vous pouvez **forcer** cette stratégie : lorsque le client demande `read_file`, votre proxy appelle l’upstream avec `head`/`tail` ou une plage de lignes et ne renvoie jamais le fichier complet sans “escale”.

### Serveur Fetch (officiel) : troncature + lecture en chunks
Le serveur officiel **Fetch MCP Server** “truncate la réponse”, et expose `max_length` + `start_index` pour parcourir un contenu en **segments** jusqu’à trouver l’info. citeturn11view0  
Ce pattern “chunking contrôlé par paramètres” est directement applicable à `read_file` : on renvoie un chunk, et le modèle doit demander le suivant si besoin.

### Pattern avancé : externaliser les gros outputs vers des ressources éphémères
Le serveur **j0hanz/filesystem-mcp** annonce explicitement : “Oversized results are externalized to ephemeral resource URIs instead of truncating inline.” citeturn22view0turn23view0  
Il définit des ressources du type `filesystem-mcp://result/{id}` et indique que lorsqu’une réponse inclut un `resource_link`/`resourceUri`, il faut traiter ce lien comme l’accès au payload complet via `resources/read`. citeturn22view0  
C’est extrêmement aligné avec un Meta‑Serveur “filtre actif” : vous pouvez renvoyer au client **un résumé + un handle** (URI), et conserver le contenu complet côté serveur (ou upstream) sans infliger la totalité au contexte du LLM.

### “Serveur de summarisation” dédié : MCP-summarization-functions
Le dépôt **Braffolk/MCP-summarization-functions** est conçu pour améliorer la fiabilité d’agents comme **Cline** en résumant de gros outputs (command output, file reads, directory listings) et en stockant le contenu complet pour référence. citeturn27view4  
Même si c’est un serveur “service” (plutôt qu’un proxy transparent), il fournit un point de comparaison pratique de ce que votre Meta‑Serveur peut automatiser : **résumer systématiquement** et **mettre en cache**.

### Pourquoi “zlib” est souvent un faux ami pour les tokens
La compression type zlib/gzip est pertinente pour la bande passante (ContextForge implémente ce type de compression HTTP). citeturn16view0  
Mais pour un client qui injecte le résultat décompressé dans le prompt, **le coût tokens reste celui du texte**. En pratique, pour une boîte noire “token‑expensive” comme Cline, les approches réellement efficaces sont : **(a) pagination/extraits**, **(b) externalisation via ResourceLink**, **(c) summarisation/masquage**, et **(d) deltas/diffs**.

---

## Observation masking et “tool output truncation” : ce que dit la recherche et comment l’aligner sur MCP

### Résultat clé (SWE-bench Verified) : masquer peut rivaliser avec résumer
Le papier **“The Complexity Trap: Simple Observation Masking…”** étudie la gestion de contexte d’agents LLM outillés : il compare l’historique brut, la summarisation LLM et une stratégie simple qui **masque/omet des observations anciennes**. Dans SWE‑agent sur SWE‑bench Verified, les auteurs rapportent qu’un **observation‑masking** peut **diviser le coût** vs agent brut tout en égalant (ou dépassant légèrement) la solve rate de la summarisation LLM. citeturn33search0turn33search2turn33search16  
JetBrains a aussi vulgarisé ces résultats et discute une approche hybride. citeturn33search3

### Traduction MCP : “Observation Masking” = réécriture contrôlée des sorties d’outils
Dans MCP, beaucoup de “trajectoires longues” viennent de tool outputs volumineux (logs, JSON, dumps). Si le client n’offre pas nativement l’observation masking, votre **Meta‑Serveur** peut l’appliquer en pratique :  
- Politique “ne jamais retourner brut” au‑delà d’un seuil ; renvoyer un **placeholder** + un **résumé** + un **handle ressource** (ResourceLink). citeturn27view0turn22view0turn19view0  
- Politique “fenêtre d’observation” : conserver quelques dernières sorties complètes *côté serveur*, mais n’en livrer au LLM que des versions compactées (ou seulement les deltas). Cela s’aligne avec l’idée qu’une simple stratégie de masquage peut être très compétitive. citeturn33search0turn33search9  

### Troncature intégrée “dans MCP” : plutôt une propriété d’implémentations que du standard
Le standard MCP spécifie **comment** renvoyer des résultats (`content`, ResourceLinks, ressources), mais ne prescrit pas une stratégie universelle de truncation/masking. citeturn29view1turn4view4  
En revanche, des **implémentations** exposent des contrôles explicites : le **Microsoft Learn MCP endpoint** mentionne par exemple un paramètre `maxTokenBudget` qui limite la taille (en tokens) des réponses de recherche en tronquant le contenu. citeturn27view1  
Côté clients, Cline met en œuvre une **summarisation automatique** (“Auto Compact”) quand la fenêtre de contexte approche la limite, mais cela n’empêche pas forcément un *tool output* massif d’entrer d’abord dans le contexte. citeturn31view0turn31view2

---

## Serveurs MCP stateful et “deltas sémantiques” : implémentations existantes et composables

### Mémoire persistante “simple” (référence officielle) : Knowledge Graph Memory Server
Le serveur officiel **Memory** est une implémentation de mémoire persistante basée sur un **knowledge graph**, stockée localement (fichier JSONL configurable via variable d’environnement), avec des outils pour créer/mettre à jour/rechercher des entités, relations et observations. citeturn10view0turn9search0  
Même si ce n’est pas un “diff de fichier”, c’est un exemple important de **state côté serveur** qui n’a pas besoin de ré‑injecter en contexte l’historique complet à chaque tour : le client peut requêter uniquement ce qui est pertinent.

### Indexation sémantique + delta packs (SQLite, cache, budget tokens) : Civyk Repo Index
Le projet **civyk-repoix** (MCP server local) vise explicitement le problème : les assistants ne peuvent pas lire un codebase entier, donc il propose une “semantic code intelligence” **token‑budgeted**. citeturn25view0  
Aspects directement alignés avec votre besoin “state + deltas” :  
- Il affirme stocker “indexes and caches locally in SQLite” et fonctionner offline. citeturn25view0  
- Il expose des outils de cache d’“understanding” (`store_understanding`, `recall_understanding`) et mentionne une invalidation automatique via content hash. citeturn25view0  
- Il liste un outil `build_delta_context_pack`, qui formalise précisément l’idée “ne renvoyer que les deltas” dans un pack de contexte sous budget tokens. citeturn25view0  

Même si certaines affirmations sont présentées côté “produit”, c’est l’exemple le plus proche (dans l’écosystème MCP actuel) d’un serveur qui **maintient l’état, gère un cache sémantique, et fabrique des context packs différentiels**.

### Diff/patch comme format de delta transmissible
Plusieurs serveurs MCP se concentrent sur **diffs** et **patchs**, donc sur des “deltas” beaucoup plus compacts que des fichiers entiers :  
- **mcp-server-diff-editor** expose des opérations `compare_files`, `generate_patch`, `apply_patch`, et revendique aussi une “semantic comparison” au‑delà du line‑by‑line. citeturn21search0turn5search3  
- **j0hanz/filesystem-mcp** inclut `diff_files` et `apply_patch`, en plus de mécanismes d’outputs externalisés. citeturn22view0  
- Le principe des workflows “patch‑first” est aussi documenté côté OpenAI (outil `apply_patch`) : proposer des diffs structurés plutôt que réécrire des fichiers complets. citeturn21search3  

### Ressources “updated” : notifications sans imposer un “diff”
Le standard resources permet de **notifier** qu’une ressource a changé via `notifications/resources/updated`. citeturn4view0turn4view1  
Votre Meta‑Serveur peut exploiter cela pour un modèle “delta‑driven” : au lieu de pousser du contenu, il pousse des **signaux** (a changé / n’a pas changé), et ne renvoie que des **diffs** quand le client le demande.

---

## Blueprint concret pour votre Meta‑Serveur MCP “filtre actif” devant Cline

### Objectif fonctionnel
Vous voulez un **serveur MCP qui “parle MCP” à Cline**, mais qui se comporte comme un **client MCP** (ou un wrapper stdio/SSE) vers un ou plusieurs serveurs upstream (filesystem, git, etc.), afin de **réécrire** les sorties avant qu’elles n’atteignent le client.

Ce design est cohérent avec MCP : des projets comme ContextForge se positionnent déjà “in front of any MCP server” comme gateway/proxy, et mcproxy illustre le proxy transparent. citeturn12view0turn20view0

### Modules recommandés dans le Meta‑Serveur
Première brique : une couche “post‑tool” inspirée de ContextForge, car elle correspond exactement à votre besoin d’interception :  
- **tool_post_invoke** : appliquer des politiques de longueur (truncate/block), ou de summarisation. citeturn19view0turn19view1  
- **resource_post_fetch** : limiter taille, redaction, summarisation lorsque le client lit une ressource. citeturn19view1turn19view2  

Deuxième brique : un stockage stateful local (SQLite + éventuellement vecteurs) pour :  
- hashes/mtime/taille par fichier et par “snapshot”,  
- cache de “résumés stables” et de “context packs”,  
- index sémantique (optionnel) pour répondre par extraits pertinents sous budget.  
L’approche est validée “in the wild” par Civyk Repo Index (SQLite, cache, delta context packs). citeturn25view0

Troisième brique : externalisation systématique des gros outputs via ResourceLink/URI, au lieu de tronquer “à l’aveugle” :  
- vous renvoyez **un résumé court** + **un handle** vers le payload complet,  
- vous forcez le client à demander explicitement `resources/read` si nécessaire.  
Ce pattern est documenté dans MCP (ResourceLink) et illustré par j0hanz/filesystem-mcp. citeturn29view1turn27view0turn22view0turn31view1

### Politiques concrètes pour `read_file` / `list_directory`
Pour coller à la réalité de Cline (tool outputs pouvant être non tronqués), une politique “safe by default” serait :

**Pour `list_directory`**  
- Renvoyer par défaut un résumé : nombre de fichiers/dossiers, top‑N entrées triées, + suggestions “si vous cherchez X, utilisez pattern/grep/find”.  
- Imposer une limite d’entrées (`maxEntries`) ou pagination (comme le font certains outils). citeturn22view0turn11view0  
- Externaliser le listing complet si nécessaire (ResourceLink).

**Pour `read_file`**  
- Si le fichier dépasse un seuil (caractères ou lignes) : renvoyer (a) un **résumé sémantique**, (b) une **table des matières** (sections/fonctions), (c) un **excerpt** (head/tail ou plage), (d) un ResourceLink vers le contenu complet. Les serveurs officiels montrent déjà des lectures partielles (`head`/`tail`) et du chunking (`start_index`). citeturn10view1turn11view0  
- Conserver un “snapshot” hashé : si le fichier n’a pas changé depuis la dernière lecture, renvoyer “inchangé” + éventuellement un rappel du résumé précédent, au lieu du corps complet (approche “cache d’understanding” à la Civyk). citeturn25view0  
- Si le fichier a changé : renvoyer un **diff** (unified diff) + un résumé des changements, plutôt que le fichier entier (approche “delta”). Les serveurs orientés diff/patch existent déjà. citeturn21search0turn22view0turn21search3  

### Observation masking côté serveur : l’équivalent opérationnel
Une politique de “masking” compatible MCP consiste à remplacer de vieux outputs (ou gros outputs) par :  
- un placeholder court (“[OUTPUT MASQUÉ — disponible via resource URI …]”),  
- un résumé stable,  
- et/ou un diff vs la version précédente.  
Cette approche est soutenue empiriquement par l’étude JetBrains Research montrant que l’observation masking peut être aussi efficace que la summarisation LLM, pour ~50% de coût en moins, dans un cadre agentique outillé. citeturn33search0turn33search3turn33search9

### Point d’attention spécifique à Cline : Tools vs Resources
Cline distingue **Tools** (présentés au LLM dans le system prompt) et **Resources** (fetch on‑demand via URI). citeturn31view1  
Donc, pour optimiser réellement, votre Meta‑Serveur devrait :  
- éviter de multiplier les tools (taxe tokens), et préférer une interface minimaliste + “search/describe/execute” si possible (cf. toolsets dynamiques). citeturn27view3turn27view2  
- basculer autant que possible du “payload in tool output” vers des **resources** (handles). citeturn27view0turn22view0turn31view1  

---

### Conclusion opérationnelle
L’écosystème MCP dispose déjà de **briques très proches** de votre “Meta‑Serveur MCP filtre actif” :  
- **ContextForge** pour les hooks et politiques (truncate/summarize/resource‑filter/cache). citeturn19view0turn19view1turn19view2  
- **j0hanz/filesystem-mcp** comme référence pratique d’externalisation via Resource URIs et surface filesystem riche. citeturn22view0turn23view0  
- **Civyk Repo Index** comme exemple de serveur stateful local (SQLite) fabriquant des context packs et deltas sous budget tokens. citeturn25view0  
- **La recherche récente** (JetBrains Research) suggère que des stratégies simples de masquage peuvent être aussi performantes que des summarizers complexes, ce qui conforte un design “filtre actif + handles”. citeturn33search0turn33search2turn33search3