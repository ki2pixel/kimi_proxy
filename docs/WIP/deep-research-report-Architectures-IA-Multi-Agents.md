# Architectures hybrides multi‑agents (Cloud + Local) pour le développement assisté par IA sans surcoût API

## Cadre du problème et contraintes réelles de facturation

Le point clé, en 2026, est qu’il existe **plusieurs “surfaces” OpenAI** qui ne se facturent pas de la même manière : l’**API OpenAI Platform** (facturation à l’usage), **ChatGPT** (abonnement avec limites d’usage), et **Codex** (agent de dev accessible depuis plusieurs clients, avec authentification soit “ChatGPT”, soit “API key”). D’un point de vue “coût API”, il est crucial de distinguer ces chemins.

Sur la facturation, OpenAI est explicite : **les APIs sont facturées séparément des abonnements ChatGPT** (Plus/Pro/Business/Enterprise/Edu). citeturn1search8turn1search10turn1search1  
Donc, si une extension/outil consomme l’API OpenAI “classique” (Platform), vous ne pourrez pas “faire passer” cela sur l’abonnement ChatGPT. citeturn1search8turn1search4  

En revanche, **Codex** introduit précisément une voie “abonnement” utilisable dans des clients locaux (CLI/IDE extension) : la doc OpenAI côté développeurs indique que **Codex supporte deux méthodes de connexion** :
- **Se connecter avec ChatGPT** (accès “subscription”)  
- **Se connecter avec une API key** (accès “usage-based”)  
et précise que **Codex cloud requiert une connexion via ChatGPT** (alors que CLI/IDE supportent les deux). citeturn21view0  

Côté Help Center, OpenAI indique que **Codex est inclus avec les plans ChatGPT Plus/Pro/Business/Enterprise/Edu** (et temporairement aussi Free/Go), et qu’on peut l’utiliser depuis **terminal, IDE, app Codex, et web**. citeturn21view1turn21view2  

Enfin, attention à la tentation de “piloter ChatGPT web” par automatisation (scraping, extraction programmée d’outputs, contournement de limites). Les Conditions d’utilisation OpenAI (1er janvier 2026) interdisent notamment **l’extraction automatique/programmatique de données ou d’Output**, et le fait de **contourner des limitations**. citeturn10view0  
Cela ne vous empêche pas d’utiliser des workflows hybrides, mais favorise les voies **officielles** (Codex, ou API) plutôt que des bricolages d’automatisation du site.

## Patterns d’architecture “Multi‑Agents Hybrides” pour gérer le contexte

Votre objectif (“un modèle local = Context Manager / Summarizer, puis un agent principal cloud”) correspond à une famille de patterns de **context engineering** et de **gestion de mémoire**.

### Deux stratégies dominantes (et leur hybride)

Une synthèse très utile (JetBrains Research, 12/2025) décrit deux grandes approches d’optimisation du contexte pour agents :  
- **LLM summarization** : un modèle produit des résumés des tours passés (raisonnement/actions/observations) pour compacter l’historique. citeturn11view0  
- **Observation masking** : on **masque/retire surtout les “observations” volumineuses** (ex. logs, gros outputs de tools, lectures de fichiers), tout en gardant davantage les décisions/raisonnements. citeturn11view0turn12search0  

JetBrains décrit aussi une approche hybride : **masking d’abord**, puis **summarization en dernier recours** sur de gros lots/trajectoires. citeturn11view0  

### Pourquoi le local est pertinent pour “nettoyer” avant le cloud

Dans un workflow dev réel, la majorité du “gras” vient de : sorties de tests, logs, dumps JSON, fichiers longs, etc. JetBrains note que les trajectoires d’agents SE sont souvent très “skew” vers l’observation, ce qui rend le masking particulièrement efficace. citeturn11view0  

Donc, un **Context Manager local** peut combiner :
- **Heuristiques non‑LLM** (troncature intelligente, déduplication, extraction de sections “ERROR”, “stack trace”, “diff”, etc.) ⇒ coût nul et souvent très efficace.  
- **Résumé LLM local** (Ollama/vLLM) uniquement quand nécessaire (ex. fichier énorme mais besoin d’une vue structurelle).  
- **Sortie “Context Pack”** ultra compacte (= prompt structuré + références précises vers fichiers/sections).

Voici un schéma type (Cloud + Local), compatible avec une utilisation Codex/ChatGPT “abonnement” :

```
Repo local + logs/tests
   │
   ├─ (A) Pré-tri non‑LLM : masking, dédup, extraction erreurs
   ├─ (B) Résumé local (Ollama/vLLM) : compaction ciblée
   └─ (C) Index local (embeddings) : retrieval de snippets pertinents
        ↓
   "Context Pack" (≤ N tokens) + pointeurs (paths, lignes, commits)
        ↓
Agent principal cloud (Codex via login ChatGPT / ou ChatGPT UI)
        ↓
Actions (patch/diff, commandes, décisions)
        ↓
Mise à jour de mémoire (fichiers de synthèse, tickets, notes)
```

## Outils et extensions existants (hors Continue.dev et Cline) qui s’approchent de ce design

### La réponse la plus “alignée” avec votre contrainte “pas de frais d’API”

Si votre contrainte est **“je veux un agent IDE/CLI qui compte sur l’abonnement ChatGPT, pas sur l’API”**, alors **Codex** est central : la doc OpenAI décrit explicitement la connexion “Sign in with ChatGPT for subscription access” vs “API key for usage-based access”. citeturn21view0turn21view1  

Ensuite, des outils tiers se branchent sur ce backend (ou un catalogue “Codex”).

### Exemples concrets pertinents

| Outil | Peut fonctionner “sur abonnement ChatGPT” (pas facturé à l’API Platform) | Local (Ollama/vLLM) possible | Mécanisme de compression/contexte notable | Peut utiliser un modèle *différent* pour résumer vs agent principal |
|---|---|---|---|---|
| **Roo Code (VS Code)** | Oui via provider **“OpenAI – ChatGPT Plus/Pro”** (OAuth “Sign in to OpenAI Codex”, “No API Costs”) citeturn18view0 | Oui (provider Ollama, et “OpenAI Compatible”) citeturn22view0turn22view2 | **Intelligent Context Condensing** + réserve de fenêtre + recovery sur erreurs de fenêtre citeturn7view0 | **Non** : le condensing “utilise toujours le modèle/provider actif” citeturn7view0 |
| **Codex CLI / IDE extension (OpenAI)** | Oui : “Sign in with ChatGPT” recommandé pour plans Plus/Pro/etc citeturn21view3turn21view0 | Extensible via outils (MCP) ; le local dépend de vos serveurs/outils MCP citeturn21view3turn21view0 | MCP pour outils/context externe; possibilité d’architecture outillée (pré‑résumeurs) citeturn21view3turn21view0 | Dépend de votre design (ex. MCP “summarize-local”) |
| **Goose (Block, CLI/Desktop)** | Généralement via providers (coûts selon provider), mais supporte aussi local (Ollama = $0) citeturn2view0turn24view0 | Oui (exemple explicite avec `GOOSE_PROVIDER=ollama`) citeturn24view0 | **Auto‑compaction** à ~80% + résumés d’outputs d’outils citeturn2view0turn6view0 | Multi‑modèle possible (lead/worker), mais compaction = logique interne citeturn4view0turn2view0 |
| **Aider (CLI)** | Par défaut plutôt API/clé (selon provider), mais très “hybride” en modèles citeturn9view0 | Oui (Ollama et endpoints OpenAI‑compatibles) citeturn23view0turn23view1 | Repo map (sélection sous budget) + summarization d’historique citeturn23view2turn23view3 | **Oui** : hiérarchie **main/weak/editor**, weak utilisé pour summarization citeturn9view0 |
| **AiderDesk (desktop app autour d’Aider)** | Pas son cœur, mais offre un **handoff** très pratique vers ChatGPT web via clipboard citeturn14view0 | Selon modèle configuré (peut être local) ; compaction dépend du modèle configuré citeturn14view1 | `/clear-logs`, `/compact`, `/copy-context` (paster dans ChatGPT/Claude) citeturn14view0turn14view1 | Dépend du mode et du profil “compact” en agent mode citeturn14view1 |
| **OpenHands (agent/plateforme)** | Plutôt API/cloud selon usage, mais design agent complet citeturn13view0 | Oui : docs “Local LLMs” et endpoints OpenAI‑compatibles via Ollama/vLLM/SGLang citeturn13view1turn12search4 | “Context condenser” (résume anciens events, garde récents) citeturn13view0 | Potentiellement (selon config interne), mais dépend de l’implémentation |

**Conclusion pragmatique pour votre besoin précis** :  
- Si vous ciblez **“GPT‑4/équivalent via IDE/CLI sans token billing API”**, la voie la plus propre est **Codex avec login ChatGPT**, soit via clients officiels, soit via intégrations comme **Roo Code “ChatGPT Plus/Pro”**. citeturn21view0turn18view0  
- Si vous ciblez **“local summarizer → cloud agent”**, vous le ferez soit via un **système multi‑modèle natif** (Aider main/weak), soit via un **système d’outillage** (MCP) au-dessus de Codex. citeturn9view0turn21view3  
- Si vous ciblez **“ChatGPT web pur”**, AiderDesk est intéressant car il formalise le **copy/paste de contexte** + nettoyage de logs. citeturn14view0  

## Goose : “Smart Context Management” et compaction automatique

Goose documente une gestion du contexte structurée en **deux étages** :  
1) **Auto‑compaction** : résume proactivement la conversation quand on approche une limite de tokens. citeturn2view0turn6view0  
2) **Context strategies** : stratégie de secours si la limite est encore dépassée (summarize / truncate / clear / prompt selon mode). citeturn2view0  

### Déclenchement et paramétrage

La doc Goose indique que l’auto‑compaction est déclenchée par défaut vers **80%** de la limite (Desktop + CLI), avec une variable d’environnement pour ajuster le seuil. citeturn2view0  
Goose permet aussi de **personnaliser la manière de résumer** lors de la compaction via un template `compaction.md`. citeturn2view0  

### Gestion spécifique des “tool outputs” (souvent la vraie source de bloat)

Un point très aligné avec votre cas “nettoyage de logs” : Goose indique qu’il **résume en arrière‑plan les outputs d’outils plus anciens**, tout en gardant les récents en détail, avec un comportement par défaut quand il y a **>10 tool calls** (tunable). citeturn2view0  

### Multi‑modèle (lead/worker) = hybride coût/qualité

Goose a un mode **lead/worker** où un modèle “lead” fait les premiers tours (planification), puis un “worker” exécute, avec retour au lead si échecs. citeturn4view0  
Ce pattern est exactement une architecture “multi‑agents hybrides”, même si ce n’est pas *uniquement* un summarizer : c’est plutôt **raisonneur vs exécutant**.

### Local (Ollama) pour une partie ou la totalité

Goose montre explicitement une exécution locale via Ollama (`GOOSE_PROVIDER=ollama`), et décrit des workflows locaux/offline. citeturn24view0turn2view0  
Dans sa vue coûts, Goose précise que les déploiements locaux (ex. Ollama) affichent un coût estimé à **$0.00** (logique). citeturn2view0  

**Lecture “deep research” pour votre besoin** : Goose est excellent si vous voulez un agent outillé qui **auto‑résume** et traite le bloat “tool outputs”. En revanche, si votre exigence est “résumer en local mais exécuter sur GPT‑4 via ChatGPT sans API”, Goose ne résout pas à lui seul la partie “abonnement ChatGPT” ; il est surtout un framework d’agent multi‑provider. citeturn2view0turn4view0  

## Aider (et AiderDesk) : repo map + hiérarchie de modèles + compaction/handoff

Aider est un cas particulièrement pertinent pour “context management” en codebase, parce qu’il combine **compaction algorithmique** (sans LLM) et **résumé LLM** (quand nécessaire).

### Repository map : compression “structurelle” sous budget

Aider injecte à chaque requête une **repo map** : liste de fichiers + symboles clés + signatures/sections critiques, pour donner une vue globale sans ouvrir tous les fichiers. citeturn23view2  
Pour les gros dépôts, il **optimise la map** en sélectionnant les portions les plus pertinentes via un **algorithme de ranking sur graphe de dépendances**, afin de tenir dans un budget de tokens (paramètre `--map-tokens`, par défaut ~1k). citeturn23view2  
C’est un excellent mécanisme pour votre objectif “lire gros fichiers / réduire contexte” car une partie de la “compression” est faite **sans coût LLM** (analyse structurelle, ranking), puis seulement les snippets nécessaires sont envoyés.

### Résumé automatique de l’historique pour éviter overflow

Au niveau conversation, DeepWiki (basé sur le code) indique que la classe `ChatSummary` gère une **summarization automatique de l’historique** quand on approche des limites, pour conserver la continuité. citeturn23view3  

### Le point décisif pour une architecture “local summarizer → cloud main” : main/weak/editor

Aider a une hiérarchie de **trois modèles** :
- **Main model** : chat principal et génération/édition  
- **Weak model** : tâches “légères” (dont **summarization**) et messages de commit  
- **Editor model** : tâches d’édition “architect”/format spécifique  
citeturn9view0  

Cela veut dire que, *en théorie d’architecture*, vous pouvez configurer :  
- **weak model = local** (Ollama/vLLM via endpoint OpenAI‑compatible),  
- **main model = cloud** (OpenAI API, ou autre provider),  
et obtenir exactement le pattern “un modèle moins cher ou local fait les résumés/compactions”. citeturn9view0turn23view1  

Sur le support local, la doc Aider indique explicitement : **Ollama** et plus généralement **tout endpoint OpenAI‑compatible**. citeturn23view0turn23view1  

### AiderDesk : “context manager” orienté UI + handoff vers ChatGPT web

AiderDesk ajoute des fonctionnalités très alignées avec votre demande “nettoyer logs / compacter / passer à l’agent principal via UI web” :
- `/clear-logs` : retire uniquement les logs (info/warn/error) tout en gardant la conversation. citeturn14view0  
- `/compact` : génère un résumé structuré (intent, concepts, messages utilisateurs, fichiers modifiés, erreurs/résolutions, next step) et remplace l’historique par ce résumé. citeturn14view1  
- `/copy-context` : copie le contexte au format Markdown pour le **coller dans ChatGPT ou Claude web**. citeturn14view0  

C’est probablement l’un des rares outils qui assume explicitement le workflow “je prépare un contexte propre, puis je colle dans une UI web”.

Enfin, AiderDesk dispose d’un **serveur MCP intégré** exposant des actions (ajouter/retirer fichiers de contexte, run prompt, etc.) à des clients MCP. citeturn20view0  
Cela ouvre un pattern avancé : **Codex (ou autre agent MCP‑capable) appelle AiderDesk comme sous‑agent/local context manager**.

## Roo Code : condensation intelligente + provider “ChatGPT Plus/Pro” (Codex) + limites importantes

Roo Code mérite une analyse séparée car il coche deux cases qui vous intéressent fortement : (a) un agent VS Code assez “autonome”, (b) une connexion possible via abonnement ChatGPT (donc sans billing API Platform).

### Provider “OpenAI – ChatGPT Plus/Pro” : le chaînon manquant “sans coûts API”

Roo Code documente un provider **“OpenAI – ChatGPT Plus/Pro”** avec un quickstart clair : sélectionner le provider, cliquer “Sign in to OpenAI Codex”, compléter l’OAuth, puis choisir un modèle. citeturn18view0  
Le point central pour votre contrainte budget est explicitement écrit : **“No API Costs: Usage through this provider counts against your ChatGPT subscription, not separately billed API usage.”** citeturn18view0  

Roo Code précise aussi les limites de ce mode :  
- vous ne pouvez pas appeler **arbitrairement** “tous les modèles API OpenAI” ; ce provider n’expose que les modèles du **catalogue Codex** de Roo. citeturn18view0  

En parallèle, OpenAI confirme côté documentation Codex que l’auth “ChatGPT” donne un accès “subscription”, tandis que l’API key tombe sur de la facturation standard API. citeturn21view0  

### Intelligent Context Condensing : comment Roo gère les limites de tokens

La fonctionnalité “Intelligent Context Condensing” est décrite comme un mécanisme qui **résume les parties anciennes** de la conversation quand on approche la limite de fenêtre de contexte, plutôt que de supprimer brutalement les messages. citeturn7view0  
Roo ajoute : configuration d’un seuil (pourcentage), déclenchement auto, prompt de condensation personnalisable, déclenchement manuel, et un “audit trail” (tokens avant/après, coût, résumé consultable). citeturn7view0  

Roo décrit aussi une **récupération automatique sur erreurs de dépassement** : détection d’erreur “context window exceeded”, réduction automatique du contexte (25%), retry, continuité. citeturn7view0  

### Limite majeure vis‑à‑vis de votre pattern “local summarizer / cloud main”

Roo Code répond presque textuellement à votre question : dans l’implémentation, **la condensation utilise toujours le modèle/provider actif** et Roo explique pourquoi il ne permet pas de choisir un autre modèle pour condenser. citeturn7view0  

Donc, si vous utilisez Roo Code + provider “ChatGPT Plus/Pro” (Codex), la condensation consomme aussi cette surface (donc vos quotas/limites d’abonnement). Cela ne coûte pas “API Platform”, mais ce n’est pas “gratuit” en quota.

### Local models (Ollama) et endpoints OpenAI‑compatibles

Roo Code supporte des modèles locaux via **Ollama** et **LM Studio**, avec les avantages “privacy/offline/cost savings”. citeturn22view1turn22view0  
Il documente aussi l’usage de providers **OpenAI‑compatibles** (endpoints personnalisés), et précise un point technique important : Roo Code exige le **native tool calling** (pas de fallback XML), donc votre modèle/endpoint doit supporter l’équivalent du schéma tools OpenAI. citeturn22view2  

### Hybride possible (mais sur un autre axe) : embeddings/indexing séparés

Même si Roo ne permet pas un “condense model” séparé, il existe un autre levier hybride : l’indexation (embeddings) peut être branchée sur différents providers, y compris **Ollama**, pour du retrieval sémantique. citeturn16search4  
Cela peut réduire la nécessité d’injecter de gros fichiers en contexte, en préférant “retriever → snippets”.

## Recommandations d’architecture adaptées à votre objectif “optimiser le contexte sans payer l’API”

### Choisir une surface Cloud “sans coût API” et la rendre extensible

Si votre objectif est “GPT‑4/équivalent dans un IDE sans payer l’API Platform”, utilisez **Codex avec login ChatGPT** (officiel) ou une intégration IDE qui s’y connecte (ex. Roo Code “ChatGPT Plus/Pro”). citeturn21view0turn18view0turn21view3  
Cela respecte le modèle économique : vous n’essayez pas de “détourner” ChatGPT web, vous utilisez une voie documentée (OAuth ChatGPT). citeturn21view0turn10view0  

### Mettre le “Context Manager” en local via outils plutôt que via “condense model”

Comme Roo Code (et beaucoup d’agents) lient la condensation au modèle actif, le pattern le plus robuste est : **ne pas condenser “dans l’agent”**, mais **avant** ou **à côté**, via outillage local.

Deux options très compatibles avec Codex :

1) **Observation masking local (sans LLM)** en première ligne. C’est souvent le meilleur ROI : remplacer les gros outputs par un placeholder + pointeur (fichier, commande, timestamp, lignes). JetBrains montre que le masking peut être aussi efficace que la summarization, voire mieux sur l’efficience globale. citeturn11view0turn12search0  

2) **Résumé LLM local en second rideau** (Ollama/vLLM) quand il faut une compréhension “sémantique” d’un gros bloc. Là, vous payez en compute local, pas en quota cloud.

### Utiliser MCP pour brancher le local au cloud (architecture “multi‑agents” propre)

Codex CLI supporte explicitement les **serveurs MCP**. citeturn21view3turn21view0  
Cela vous permet de construire un vrai pattern “hybride multi‑agents” : l’agent cloud (Codex) appelle une tool MCP “summarize_log”, “summarize_file”, “compress_context”, qui tourne en local et s’appuie sur Ollama/vLLM.

AiderDesk propose justement un **serveur MCP intégré** (et expose des tools comme “run_prompt”, gestion de fichiers de contexte). citeturn20view0  
Donc, sans même développer votre serveur, vous pouvez envisager un montage où **AiderDesk joue le rôle de context manager** et **Codex/Roo** celui de “principal agent”.

### Quand vous restez sur ChatGPT web : privilégier le “handoff” explicite

Si vous tenez à “agent principal = ChatGPT web”, le workflow le plus propre (et explicitement supporté par certains outils) est le **handoff manuel** : générer le “context pack” en local et coller dans ChatGPT.  
AiderDesk est très aligné ici via `/copy-context` (format Markdown optimisé pour ChatGPT/Claude web) et `/clear-logs` (nettoyage des logs). citeturn14view0  

### Un mot de prudence sur l’automatisation “web UI”

Évitez les solutions qui automatisent l’extraction d’outputs ou le pilotage de ChatGPT web de manière programmatique : les Conditions d’utilisation OpenAI prohibent explicitement l’extraction automatique d’Output et le contournement de restrictions. citeturn10view0  
À la place, pour un IDE agentique “abonnement”, appuyez-vous sur Codex (OAuth ChatGPT) ou assumez l’API.

### “Checklist” de conception d’un Context Pack très efficace

En pratique, les meilleurs “prompts ultra‑optimisés” pour agent principal ressemblent à un artefact structuré :
- Objectif/contrainte (1–3 lignes)  
- État actuel (ce qui est vrai maintenant)  
- Ce qui a été tenté / ce qui échoue (erreur + 20 lignes autour)  
- Fichiers concernés (paths + sections/lignes)  
- Hypothèses/risques  
- Actions demandées (liste courte, vérifiable)  

Cette philosophie rejoint les recommandations générales de “context engineering” : viser le **minimum de tokens à fort signal** pour maximiser la probabilité d’un bon résultat. citeturn0search15  

En combinant : (a) Codex via abonnement ChatGPT, citeturn21view0turn21view1 (b) masking + summarization local, citeturn11view0turn23view0 et (c) éventuellement MCP pour brancher les tools locales à l’agent cloud, citeturn21view3turn20view0 vous obtenez une architecture “Multi‑Agents Hybrides (Cloud + Local)” qui colle très bien à votre contrainte “optimiser le contexte sans payer de frais d’API supplémentaires”.