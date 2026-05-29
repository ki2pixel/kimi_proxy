# Bias-Aware Code Retrieval et RAG appliqué au code source autour de SACL

## Pourquoi le RAG “classique” sur le code produit un biais textuel

Le **Retrieval-Augmented Code Generation (RACG)** (souvent appelé RAG appliqué au code) vise à améliorer la génération/modification de code en **récupérant** des documents/snippets pertinents depuis un corpus avant de générer. SACL (“**Semantic‑Augmented Reranking and Localization**”) part d’un constat empirique : même des retrievers entraînés sur du code peuvent **sur‑pondérer des signaux textuels “de surface”** (docstrings, commentaires, noms d’identifiants) plutôt que la sémantique fonctionnelle réelle. citeturn2view0turn2view1

Dans l’article **SACL (Findings EMNLP 2025)**, les auteurs utilisent une analyse par **normalisation** (masquage/remplacement systématique de features textuelles tout en préservant la fonctionnalité) pour répondre à deux questions : sur quoi les retrievers se basent-ils, et y a‑t‑il un biais ? Ils rapportent notamment :
- une **dépendance forte à des features textuelles** (docstrings, noms de fonctions/variables), avec une **chute massive** des performances quand ces signaux sont normalisés ; citeturn2view1turn1view0  
- un **biais en faveur du code “bien documenté”**, y compris lorsque la doc est **fonctionnellement non pertinente**, ce qui peut pousser le système à préférer du code verbeux mais incorrect/moins pertinent. citeturn2view1turn2view0

Ces observations sont directement reliées à votre objectif d’“**atténuation du biais textuel**” pour la recherche de code : si l’indexation et les embeddings “avalent” beaucoup de texte non‑fonctionnel (longues docstrings, commentaires), vous risquez de récupérer du code “bien raconté” plutôt que du code “vrai”. citeturn2view0turn2view1

## Ce que propose SACL et comment le relier à une architecture RAG “code-first”

SACL introduit deux idées structurantes (très compatibles avec une architecture RAG moderne pour repositories) :

**Reranking sémantiquement augmenté (Semantic‑Augmented Code Reranking).** Après une première récupération top‑k, SACL **génère des descriptions textuelles** des snippets récupérés (objectif : créer une représentation “texte” plus directement comparable à la requête), puis **agrège** la similarité requête↔code et requête↔description via une formule de combinaison pondérée. citeturn2view2turn1view0  
Cette logique est explicitée dans l’article via un score final combinant les deux signaux, illustrant le principe : ne pas laisser la docstring dominer, mais **réinjecter une sémantique contrôlée** (description “fonctionnelle”) au moment du rerank. citeturn2view2

**Localisation sémantiquement augmentée (Semantic‑Augmented in‑context Localization).** Pour les tâches “repo-level” (localiser quel fichier modifier), SACL enrichit la **structure du dépôt** avec des **résumés descriptifs par fichier** pour aider le modèle à identifier le bon fichier, surtout quand les noms de fichiers sont peu informatifs. citeturn2view2turn1view0

Sur benchmarks, SACL revendique des gains de **Recall@1** (HumanEval/MBPP/SWE‑Bench‑Lite) et des gains sur la performance de génération, ce qui renforce l’idée qu’une couche “bias‑aware” peut améliorer le end‑to‑end. citeturn1view0turn2view1

Enfin, un point pratique important pour votre question “serveurs MCP” : il existe un **serveur MCP SACL** open‑source qui implémente cette approche et annonce une intégration avec un **Knowledge Graph Neo4j/Graphiti**, ainsi que des outils de “relationship analysis” et “localization”. citeturn4view0turn1view3


## Bibliothèques Python actuelles pour AST multi‑langages, dépendances, et ingestion Qdrant temps réel

Votre contrainte “**<50ms**” implique presque toujours une architecture **incrémentale** (par fichier modifié) avec une “fast path” légère, et éventuellement une “slow path” asynchrone pour une résolution sémantique plus coûteuse (ex. call graph précis). La difficulté principale n’est pas seulement l’AST : c’est la **résolution** des symboles (qui appelle quoi) qui peut exploser en coût si on veut être exact.

### Parsing multi‑langages et extraction structurée

**Tree‑sitter (py-tree-sitter) est aujourd’hui l’option la plus pragmatique côté Python** pour un parsing multi‑langages rapide et industrialisable. Tree‑sitter est décrit comme une librairie de parsing **incrémentale** : elle peut construire un **concrete syntax tree** et le **mettre à jour efficacement** lors d’éditions. citeturn7search1turn5search0  
Le binding Python officiel/documenté existe (py-tree-sitter). citeturn5search0turn5search4

Pour un projet réellement multi‑langages, le point bloquant devient la gestion des grammaires. Deux options Python “prêtes à l’emploi” ressortent :
- **tree-sitter-language-pack** (PyPI + repo) : fournit des helpers `get_language()` / `get_parser()` et s’aligne sur tree-sitter 0.25.x+, ce qui réduit fortement la friction d’intégration multi‑langages. citeturn5search1turn5search9  
- **tree-sitter-languages** (grantjenks) : fournit des wheels “all languages”, mais le repo indique explicitement être **unmaintained** et recommande `tree-sitter-language-pack` comme alternative. citeturn5search21turn5search24  

Pour l’extraction d’éléments (imports, définitions, appels), Tree‑sitter dispose d’un langage de **queries** (S‑expressions) pour matcher des patterns dans l’arbre. La doc explique la syntaxe : une query contient des patterns (S‑expressions) qui matchent des nœuds et leurs enfants. citeturn7search18turn7search10  
En pratique, c’est ce mécanisme qui permet de faire un “AST mining” multi‑langages sans écrire un parser différent pour chaque langage.

### Analyse Python “précise” (docstrings/commentaires, transformations sûres)

Pour Python, un outil très utile pour votre objectif “**supprimer/filtrer docstrings & commentaires** sans casser le code” est **LibCST**. LibCST parse Python en **CST** en gardant les détails de formatage (commentaires, espaces, parenthèses), ce qui est précisément ce qui manque à l’AST standard quand on veut manipuler/supprimer proprement. citeturn5search3turn5search7  
La doc “Why LibCST” insiste sur le fait que LibCST préserve l’espace et place la whitespace sur les nœuds, ce qui facilite des transformations complexes. citeturn5search30

Conclusion pratique : **Tree‑sitter** pour le multi‑langages, et **LibCST** comme “spécialiste Python” dès que vous voulez une suppression fiable de docstrings/commentaires, ou une réécriture contrôlée.

### Dépendances “imports” et “calls” : compromis précision ↔ latence

Pour les **imports**, Python a un excellent outil “dépendance de fichiers” : **importlab** (Google) calcule automatiquement un **dependency graph** et peut ordonner des fichiers avec détection de cycles. citeturn6search2turn6search6  
Pour les **call graphs**, deux options Python fréquemment citées :
- **PyCG** (Practical Python Call Graphs) : call graph statique, avec un papier ICSE et une méthodologie d’analyse inter‑procédurale (via relations d’assignation, résolution d’appels potentiels). citeturn6search1turn6search9  
- **pyan3** : call graph statique “approx” (analyzer basé sur `ast` + `symtable`). citeturn6search0turn6search4

Mais attention à votre contrainte latence : un call graph “entier repo” en statique peut dépasser 50ms, surtout si vous le reconstruisez trop souvent. D’où une architecture recommandée :
- **Fast path** (<50ms) : extraction *syntactique* (imports/calls en pattern matching Tree‑sitter, sans résolution complète), mise à jour des embeddings + upsert Qdrant.  
- **Slow path** (asynchrone) : enrichissement “sémantique” (résolution plus précise avec PyCG/pyan3/importlab, ou via LSP/indexers) puis mise à jour du graphe Neo4j.

### Ingestion Qdrant temps réel : client, protocole, et goulot d’étranglement “embeddings”

Côté Qdrant, trois points “load‑bearing” pour la performance :

**Ports & interfaces.** Qdrant expose classiquement REST sur **6333** et gRPC sur **6334** (illustré dans le Quickstart). citeturn16search1  
La doc “API & SDKs” indique aussi que la gRPC interface est disponible sur le port configuré, typiquement `grpc_port: 6334`, et qu’il existe une méthode gRPC correspondante à chaque endpoint REST. citeturn16search11

**qdrant-client Python + gRPC.** Le package `qdrant-client` est activement maintenu (ex. release 1.17.0 en février 2026). citeturn5search6  
PyPI mentionne explicitement que pour un upload “typiquement beaucoup plus rapide”, on peut initialiser le client avec `grpc_port=6334` et `prefer_grpc=True`. citeturn16search5  
La doc du client précise que `QdrantClient` est l’entrée pour communiquer via REST ou gRPC et que les méthodes acceptent des structures gRPC/REST avec conversion auto. citeturn16search0turn16search19

**Le vrai coût : générer l’embedding.** Si vous utilisez un service embeddings distant, <50ms P95 devient difficile (latence réseau + queue). Pour tendre vers <50ms, il faut typiquement : embeddings locaux + cache + batch micro‑batch. (Le client Qdrant mentionne aussi des intégrations d’embeddings “FastEmbed” via mixins, ce qui peut aider à éviter d’appeler une API distante, même si le choix dépend de vos contraintes modèles/hardware.) citeturn16search0turn16search12

### Détection de changements “temps réel”

Une brique utile est un watcher de fichiers performant. **watchfiles** se présente comme un file watching **simple et high performance**, avec des notifications gérées par une lib Rust (“Notify”) et des wheels binaires. citeturn7search3turn7search11  
C’est typiquement la pièce qui déclenche la fast path “parse → chunk → embed → upsert”.

**Synthèse recommandée (bibliothèques)**  
Pour votre cahier des charges, la stack Python la plus “actuelle” et réaliste est : Tree‑sitter (py-tree-sitter) + tree-sitter-language-pack pour le multi‑langages, LibCST pour Python CST/transformations, importlab/PyCG (slow path) pour graphes plus précis, watchfiles pour l’incrémental, et qdrant-client en gRPC. citeturn5search0turn5search1turn5search3turn6search2turn6search1turn7search3turn16search5


## Chunking “intelligent” et anti‑biais : préserver la sémantique, réduire le bruit textuel, économiser des tokens

### Le “chunking structurel” devient un sujet de recherche à part entière

Une tendance nette depuis 2024‑2025 est de traiter le chunking de code comme un composant critique du RAG. **CodeRAG‑Bench** (benchmark public, NAACL/ACL Findings 2025) souligne que même si des contextes de qualité aident, **les retrievers peinent à ramener des contextes utiles** et les générateurs ont des limites pour les exploiter. citeturn9search0turn9search2

Côté chunking, un papier directement pertinent est **cAST: Chunking via Abstract Syntax Trees** (Findings EMNLP 2025) : il critique les heuristiques “line‑based” (qui peuvent couper une fonction ou fusionner des blocs sans lien) et propose un chunking **structure-aware** : on **split récursivement** des nœuds AST trop gros, puis on **merge** des nœuds frères pour maximiser la densité d’information sous une contrainte de taille. citeturn10search8turn10search4

Pour vous, cAST donne un cadre clair : **le chunking doit respecter les frontières sémantiques (fonctions/classes/blocs)**, et la taille doit être gérée par une logique “split/merge” plutôt que par des caractères/lignes arbitraires. citeturn10search0turn10search1  

### Relier cAST au biais textuel observé par SACL

SACL montre que les systèmes de retrieval peuvent devenir dépendants de docstrings/commentaires et favoriser le code “bien documenté” même si c’est non pertinent. citeturn2view0turn2view1  
Ils décrivent une normalisation qui peut inclure **la suppression de docstrings et commentaires** parmi les settings expérimentaux de normalisation (dans la section setup). citeturn2view1  

Donc votre chunking “intelligent” doit idéalement produire **deux représentations complémentaires** :

- **Représentation pour embeddings (anti‑biais, token‑efficient)** : code nettoyé (docstrings/commentaires supprimés/tronqués), normalisation d’espaces, éventuellement réduction de littéraux longs.  
- **Représentation pour affichage/contexte (fidèle)** : extrait original (ou presque), utilisé seulement quand l’agent décide de “lire” ou quand on doit patcher/éditer.

### Stratégie concrète de chunking “structure + débruitage”

Une stratégie robuste, compatible Tree‑sitter / multi‑langages, est :

**Segmentation sémantique primaire**
- Découper un fichier en unités : `import/module headers`, `class`, `function/method`, éventuellement `top-level statements` par blocs. Le pattern matching Tree‑sitter via queries est adapté à cette extraction (fonctions, classes, imports). citeturn7search18turn7search10  

**Contrôle de taille façon cAST**
- Si une unité dépasse votre budget (tokens/chars non‑whitespace), appliquer un split récursif sur les nœuds enfants (ex. bloc interne, sous-fonctions, grandes branches), puis merge adjacent siblings sous un seuil pour éviter de trop petits chunks. C’est exactement l’esprit “split/merge” décrit par cAST. citeturn10search8turn10search0  

**Nettoyage anti‑biais (embedding text)**
- Supprimer **docstrings/commentaires** ou les **tronquer** à une “première ligne” (résumé court) si vous souhaitez conserver un minimum d’indice (mais attention au retour du biais).
- Pour Python, LibCST est particulièrement adapté : il garde les commentaires/format et permet des transformations/filtrages sans perdre la structure. citeturn5search3turn5search7  
- Pour multi‑langages, Tree‑sitter voit souvent les commentaires comme nœuds dédiés ; vous pouvez les ignorer dans votre extraction ou les retirer dans une passe de reconstruction (selon pipeline). Le fait que Tree‑sitter construise un CST et permette des queries facilite l’extraction sélective. citeturn7search1turn7search18  

**Métadonnées structurelles en payload (au lieu de tokens)**
Plutôt que d’injecter de longs commentaires dans le texte embed, stocker en payload Qdrant : chemin, symboles, signature, liste d’imports, liste de calls (même non résolues), complexité approximative, etc. Cela permet des filtres et un “context shaping” sans brûler de tokens.

### Bonus “SACL‑style” : reranking sémantique sans docstrings

Une fois les chunks nettoyés, vous pouvez appliquer une logique de reranking inspirée de SACL :
- Au retrieval, chercher via embeddings “code nettoyé”.
- Pour les top‑k, générer une **description fonctionnelle** courte (“ce que fait la fonction” en 1‑2 phrases) et reranker avec une combinaison des scores “code” et “description”, comme illustré par SACL. citeturn2view2turn1view0

Cela vous donne une atténuation de biais “en deux temps” :  
(1) rendre l’index moins sensible aux docstrings ; (2) réintroduire de la sémantique via des descriptions contrôlées au rerank. citeturn2view0turn2view2  

### Attention aux “retrieval sources” : éviter le bruit

Le papier **What to Retrieve for Effective RACG?** (arXiv 2025) rapporte que **le code in‑context** et l’info **API potentielle** améliorent la performance, tandis que récupérer du “code similaire” peut ajouter du bruit et dégrader les résultats (jusqu’à ~15% dans leurs observations). citeturn8view0  
Conséquence : votre chunking et vos index devraient privilégier du **contexte structurel local** (dépendances, API surfaces, definitions) plutôt que du “nearest neighbor code snippet” purement vectoriel.


## Knowledge Graph pour le code : combiner Qdrant et Neo4j pour éviter de “lire aveuglément” des fichiers

### Pourquoi GraphRAG est pertinent pour le code

La doc Qdrant présente une approche **GraphRAG** combinant **vector search (Qdrant)** et **graph database (Neo4j)** afin de récupérer non seulement des chunks similaires, mais aussi des éléments **relationnellement connectés** (expansion de contexte via relations). citeturn1view2  
Le workflow décrit : d’abord une recherche sémantique, puis une **expansion contextuelle** via le graphe, ce qui aide sur des requêtes complexes nécessitant des liens non évidents dans du texte brut. citeturn1view2

Pour le code, c’est particulièrement naturel : un agent n’a pas besoin de relire tout un fichier si on peut lui fournir :
- le symbole cible (fonction/classe),
- ses dépendances (imports),
- ses callees/callers,
- les types/structures liées,
- le “chemin de dépendances” minimal pour comprendre le comportement.

### Relier GraphRAG à SACL (localisation + relations)

SACL, côté “localization”, cherche justement à aider à sélectionner les bons fichiers/segments via du contexte structurel enrichi (ex. résumés de fichiers) plutôt que via des noms de fichiers/docstrings. citeturn2view2turn1view0  
Et l’implémentation MCP SACL annonce explicitement des fonctions de “relationship analysis” et un stockage “knowledge graph” Neo4j/Graphiti. citeturn4view0turn1view3

En bref, une architecture “agent‑friendly” pour du code à grande échelle ressemble souvent à :
1) **Vector DB (Qdrant)** : retrouver vite “où regarder” (chunks/symboles).  
2) **Graph DB (Neo4j)** : décider “quoi charger autour” (relations minimales).  
3) **Rerank bias-aware (SACL)** : éviter docstrings/comments comme raccourcis trompeurs. citeturn1view2turn2view1turn2view2


## Exemples de serveurs MCP existants combinant Qdrant et/ou Neo4j pour une vue “Knowledge Graph” du code

Vous avez demandé des exemples existants ; voici ceux qui ressortent clairement et qui couvrent vos cas (code‑oriented, ou “graph+vector” réutilisable pour du code).

### Serveur MCP SACL (bias-aware code retrieval + Neo4j)

Le repo **ulasbilgen/sacl** se présente comme un **serveur MCP** implémentant SACL pour du **bias‑aware code retrieval**. Il annonce un **Knowledge Graph Graphiti/Neo4j**, de la “relationship analysis”, et des outils MCP comme `analyze_repository`, `query_code_with_context`, `update_file(s)` et `get_relationships`. citeturn4view0turn1view3  
Le README insiste sur le problème de sur‑dépendance aux docstrings/commentaires/noms de variables et sur l’objectif de prioriser la pertinence fonctionnelle. citeturn4view0turn1view3

### GraphRAG MCP Server (Neo4j + Qdrant) – “hybrid retrieval”

Le repo **rileylemm/graphrag_mcp** décrit un serveur MCP pour requêter un système hybride : **Neo4j (graph)** + **Qdrant (vector)**. Il met en avant la **graph-based context expansion** et une recherche hybride combinant similarité vectorielle et relations de graphe. citeturn11view1turn11view0  
Même si le repo parle de “documentation”, la structure est directement transposable à un knowledge graph de code (nœuds Symbol/File, relations CALLS/IMPORTS/DEFINES, etc.). citeturn11view1

### Qdrant + Neo4j + Crawl4AI MCP Server (agentic RAG, serveurs “montés”)

Le repo **BjornMelin/qdrant-neo4j-crawl4ai-mcp** est un serveur MCP “agentic RAG” combinant : **Qdrant (vector)**, **Neo4j (knowledge graph)** et une brique “web intelligence” Crawl4AI, avec orchestration. citeturn12view0  
Il décrit une architecture où un “gateway” MCP route vers des services vector/graph/web, ce qui correspond à une approche modulaire utile si vous voulez brancher un index “code KG” + un vector store. citeturn12view0

### Samaritan Memory MCP (Qdrant + Neo4j + reranker)

Le serveur **damanijb/samaritan-memory-mcp** propose explicitement un système mémoire hybride : **Qdrant** pour la recherche sémantique, **Neo4j** pour un graphe entités/relations/facts, et un **reranker** optionnel. citeturn13view0  
Il expose aussi des outils “hybrid” (`recall`/`record`) qui font chercher/écrire dans les deux systèmes en parallèle ou de façon atomique, pattern intéressant pour un agent “code-aware”. citeturn13view0

### MCP Memory Server with Qdrant Persistence (knowledge graph + semantic search)

Le repo **delorenj/mcp-qdrant-memory** implémente un “knowledge graph” (entités + relations) avec **semantic search via Qdrant** et synchronisation entre un stockage fichier (memory.json) et Qdrant. citeturn12view1  
C’est plutôt “mémoire générale”, mais utile comme base de “graph memory + vector search” côté agent. citeturn12view1

### Neo4j MCP Server (backend graph pur)

Le repo **mjftw/mcp_neo4j_knowledge_graph** fournit un serveur MCP qui utilise **Neo4j** comme backend pour stocker/chercher entités/relations, avec des outils de création, recherche, introspection de schéma, etc. citeturn15view0turn14view0  
Il peut servir de “brique graphe” que vous couplez avec Qdrant (via un autre MCP server, ou un service interne).

### NeoCoder (Neo4j + Qdrant, workflow “graph-guided”)

Le projet **Zpankz/neocoder** se décrit comme un serveur MCP combinant **Neo4j knowledge graphs** et **Qdrant vector databases**, orienté “workflow” et raisonnement hybride (graph‑first + vector‑enhanced). citeturn13view2  
Même si le focus est “workflow”, l’idée d’utiliser Neo4j comme “instruction manual” et mémoire structurée correspond bien à une stratégie où l’agent ne lit pas des fichiers entiers, mais suit des liens et récupère des preuves/contextes ciblés. citeturn13view2


## Synthèse opérationnelle pour un SACL‑like “code RAG” multi‑langages à latence faible

### Architecture recommandée en couches

Une architecture qui colle à vos 3 objectifs (multi‑langages, anti‑biais, KG pour éviter lecture aveugle) est :

**Ingestion incrémentale**
- Watcher (ex. watchfiles) déclenche sur changement. citeturn7search3turn7search11  
- Parsing Tree‑sitter (multi‑langages) + queries pour extraire unités sémantiques (fonctions/classes/imports). citeturn7search1turn7search18  
- Chunking structure-aware (cAST‑style split/merge). citeturn10search8turn10search0  
- Nettoyage anti‑biais (docstrings/comments) pour le texte d’embedding (LibCST côté Python). citeturn5search3turn2view1  
- Upsert Qdrant via `qdrant-client` en gRPC (`prefer_grpc=True`, port 6334). citeturn16search5turn16search1  

**Graphe de code**
- Construire/mettre à jour Neo4j (Symbol/File nodes, edges IMPORTS/CALLS/DEFINES/EXTENDS).  
- Laisser la résolution “exacte” (PyCG/importlab, ou LSP/indexers) en slow path asynchrone si nécessaire. citeturn6search1turn6search2  

**Retrieval & ranking**
- Retrieval primaire sur embeddings “nettoyés”.  
- Expansion contextuelle via Neo4j (GraphRAG : récupérer voisins pertinents). citeturn1view2  
- Reranking SACL : générer descriptions fonctionnelles des top‑k et combiner scores code+desc. citeturn2view2turn1view0  

### Lecture “non aveugle” pour l’agent

Au lieu de “donner un fichier complet”, renvoyer au modèle un **paquet de contexte minimal** :
- la définition (chunk) du symbole pressenti,
- 1 hop d’imports nécessaires,
- 1 hop de fonctions appelées “critiques” (ou stubs de signatures),
- éventuellement un résumé de fichier (SACL localization) si l’agent doit choisir un fichier. citeturn2view2turn1view0turn1view2  

C’est exactement l’esprit des architectures **Qdrant+Neo4j** et des MCP servers GraphRAG/mémoire hybride : vector → graph expansion → contexte ciblé. citeturn11view1turn13view0turn1view2  

### Limites réalistes de la contrainte <50ms

- **Tree‑sitter** (incrémental, parse local) est aligné avec une contrainte très basse latence. citeturn7search1turn5search0  
- **Qdrant gRPC** est conçu pour réduire l’overhead vs REST, et `prefer_grpc=True` est explicitement présenté comme “typiquement plus rapide” côté client Python. citeturn16search5turn16search1  
- Le **point le plus risqué** pour <50ms est l’**embedding** si vous dépendez d’une API distante ; une stratégie “local embeddings + cache + micro-batch” est souvent nécessaire (et cohérente avec l’existence d’intégrations embeddings côté Qdrant client). citeturn16search0turn16search12  

En pratique, viser “<50ms” implique souvent : (1) fast path strictement limitée au fichier modifié, (2) pré‑allocation/keep‑alive client DB, (3) embeddings locaux ou cache agressif, (4) upsert en batch minimal.


