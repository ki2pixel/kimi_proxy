# **Architectures de Compression Adaptative et Stratégies d'Intégration de SWE-Pruner pour l'Optimisation du Contexte dans l'Extension Cline**

L'émergence des agents de développement logiciel autonomes a radicalement transformé le paradigme de l'ingénierie assistée par ordinateur. Dans ce contexte, l'extension Cline s'est imposée comme une solution de référence en permettant une interaction directe entre les modèles de langage de pointe et l'environnement de développement local. Cependant, l'efficacité de ces systèmes est intrinsèquement liée à la gestion de la fenêtre de contexte, un espace mémoire limité où sont stockés l'historique des conversations, les fichiers sources et les sorties des outils de diagnostic.1 Bien que des modèles contemporains comme Claude 3.5 Sonnet proposent des fenêtres s'étendant jusqu'à un million de jetons, l'augmentation brute de la capacité ne résout pas le problème de la densité d'information.3 En réalité, l'inclusion de contextes massifs mais bruyants induit souvent une dégradation des capacités de raisonnement de l'agent, phénomène documenté sous le terme d'amnésie contextuelle ou de fragmentation cognitive.5 Pour pallier ces limitations, le cadre SWE-Pruner propose une approche de réduction adaptative et sémantique, simulant le comportement de lecture sélective des développeurs humains.7 L'intégration de SWE-Pruner au sein de Cline représente une opportunité majeure pour optimiser la consommation de jetons tout en préservant l'intégrité structurelle du code nécessaire à la résolution de tâches complexes.

## **Analyse Comparative des Mécanismes de Gestion de Contexte**

La gestion de la mémoire de travail au sein de Cline repose sur une architecture multicouche conçue pour équilibrer la fidélité des informations et les contraintes techniques des API de modèles de langage. Le composant central, ContextManager, orchestre l'historique des interactions en appliquant des stratégies de troncature sélective lorsque la limite de jetons est approchée.2 Contrairement aux approches de compression classiques, Cline privilégie la conservation des instructions système initiales et des derniers échanges, tout en éliminant les messages intermédiaires par paires utilisateur-assistant pour maintenir la cohérence structurelle de la conversation.2

Cependant, cette approche de troncature temporelle s'avère insuffisante lors de la manipulation de bases de code volumineuses. L'analyse des limitations techniques révèle que Cline impose une restriction de lecture de 300 Ko par fichier, une barrière qui déclenche souvent des erreurs de type HTTP 413 ou des échecs de lecture silencieux, même lorsque le modèle dispose d'une fenêtre de contexte théoriquement suffisante.5 C'est ici que l'approche de SWE-Pruner diverge fondamentalement. Plutôt que de s'appuyer sur des métriques statistiques comme la perplexité (PPL), SWE-Pruner utilise un "skimmer" neural léger de 0,6 milliard de paramètres pour identifier les lignes de code sémantiquement cruciales en fonction d'un objectif spécifique.10

### **Performance et Efficience des Méthodes de Compression**

| Méthodologie | Unité de Granularité | Critère de Sélection | Réduction des Jetons | Impact sur le Succès |
| :---- | :---- | :---- | :---- | :---- |
| Troncature Cline (Standard) | Message | Temporel / FIFO | Variable | Risque de perte de contexte |
| LongLLMLingua | Token | Perplexité Statistique | 30-40% | Rupture possible de la syntaxe |
| RAG Classique | Chunk / Fragment | Similarité Cosinus | 20-30% | Perte de la structure logique |
| **SWE-Pruner** | **Ligne de Code** | **Objectif de Tâche (Task-Aware)** | **23-54%** | **Maintien de la performance** |
| Auto-compact (Cline) | Session | Résumé par LLM | 15-20% | Coût en jetons d'inférence |

Les données indiquent que SWE-Pruner surpasse les techniques conventionnelles en atteignant des taux de compression allant jusqu'à 14,84x sur des tâches de lecture de code à long contexte (LongCodeQA), tout en minimisant la dégradation des performances de l'agent.7 Cette efficacité découle de sa capacité à fonctionner comme un middleware intelligent, filtrant les données à la source avant qu'elles n'atteignent le modèle de langage principal.7

## **Architecture Technique de SWE-Pruner et le Concept de Skimming Neural**

Le fonctionnement de SWE-Pruner repose sur deux étapes distinctes mais interdépendantes : la formulation d'un objectif de focalisation (Goal Hint) et le filtrage adaptatif par le skimmer neural.7 L'agent, confronté à une tâche de débogage ou d'implémentation, génère une instruction décrivant son besoin immédiat, telle que "se concentrer sur la logique de résolution MRO" ou "analyser la gestion des exceptions dans le module de parsing".7

Le modèle de skimmer (0,6B paramètres) traite ensuite le contexte brut. Contrairement aux modèles massifs, cette taille réduite permet une inférence locale rapide, évitant ainsi d'ajouter une latence significative au flux de travail de l'agent.7 Le modèle a été entraîné sur un jeu de données synthétiques de 61 000 exemples, lui permettant de comprendre comment les modifications apportées à une partie du code peuvent influencer d'autres sections, préservant ainsi les dépendances logiques essentielles.7

La réduction s'opère au niveau de la ligne, ce qui garantit que les structures syntaxiques du langage de programmation restent valides. En éliminant les branches conditionnelles non pertinentes, les attributs de classe inutilisés ou les fonctions utilitaires sans rapport avec la tâche, SWE-Pruner permet à l'agent de se concentrer sur une version "distillée" du code.12 Cette méthode de "Semantic Highlighting" agit comme un masque dynamique, où l'agent peut toujours demander la récupération des lignes masquées s'il juge que le filtrage a été trop agressif, assurant ainsi une boucle de rétroaction robuste.12

## **Exploration des Points d'Insertion dans l'Infrastructure Cline**

L'intégration de SWE-Pruner dans Cline nécessite une analyse des points d'extension disponibles dans l'architecture de l'extension. Cline repose sur un système de boucle ReAct (Reasoning and Acting) où l'agent planifie des actions, exécute des outils et vérifie les résultats.13 Trois voies d'intégration principales se dégagent de l'étude des capacités actuelles de Cline : l'utilisation du Model Context Protocol (MCP), l'exploitation du système de Hooks (v3.36) et la modification directe du noyau de gestion des outils.

### **Intégration via le Model Context Protocol (MCP)**

Le protocole MCP représente la méthode la plus modulaire et la plus conforme à la philosophie de Cline pour introduire SWE-Pruner.15 Cline agit comme un client MCP capable de se connecter à des serveurs tiers fournissant des outils, des ressources et des modèles de contexte.17 Un serveur MCP "Pruner" pourrait être implémenté pour remplacer ou compléter les outils de lecture de fichiers natifs.

Dans cette configuration, l'agent Cline n'appellerait plus directement read\_file, mais un outil personnalisé read\_file\_optimized exposé par le serveur MCP.16 Ce serveur exécuterait localement le modèle de skimmer SWE-Pruner. Le flux de travail serait alors le suivant : l'agent fournit le chemin du fichier et son objectif actuel ; le serveur MCP lit le fichier sur le disque, applique le pruning via le modèle 0,6B et renvoie uniquement le contenu filtré à Cline.7 Cette approche présente l'avantage majeur de contourner les limites de taille de fichier de Cline, car le serveur MCP lit le fichier complet localement avant de transmettre une version réduite, compatible avec les limites de l'extension, au modèle de langage.5

### **Optimisation via les Hooks de Workflow (v3.36)**

L'introduction des Hooks dans la version 3.36 de Cline offre une opportunité d'intercepter les opérations de l'agent sans modifier les outils eux-mêmes.19 Les scripts de hooks, placés dans \~/Documents/Cline/Rules/Hooks/, reçoivent un contexte d'opération au format JSON via l'entrée standard et peuvent influencer le déroulement de la tâche.19

Le hook PreToolUse est particulièrement pertinent. Il se déclenche après que l'IA a décidé d'utiliser un outil (comme read\_file) mais avant son exécution.19 Bien que les hooks ne puissent pas encore réécrire directement la sortie d'un outil pour le tour actuel, ils peuvent utiliser le champ contextModification pour injecter des instructions ou des résumés dans la requête API suivante.19 Pour SWE-Pruner, un hook pourrait analyser les paramètres de read\_file, extraire l'objectif de l'agent à partir de l'historique récent et préparer le skimmer pour traiter le contenu dès qu'il est disponible, ou même forcer l'agent à utiliser une version compressée si le fichier dépasse un certain seuil de jetons.19

### **Modification du Handler d'Outils read\_file**

Pour une intégration native et transparente, la modification du code source de Cline, spécifiquement les classes gérant la lecture de fichiers, est la solution la plus directe. Le fichier ReadFileToolHandler.ts (ou son équivalent dans la structure src/core/task/tools/handlers/) définit la logique d'extraction du contenu des fichiers.20 Actuellement, Cline renvoie le contenu brut sans annotation de ligne, ce qui rend les discussions sur des lignes spécifiques sujettes aux erreurs de calcul du modèle.22

L'intégration de SWE-Pruner au niveau du noyau permettrait d'injecter une étape de prétraitement systématique. Lors de l'appel à extractFileContent(), le système pourrait vérifier si un objectif a été formulé par l'agent. Si tel est le cas, le contenu extrait passerait par le skimmer neural avant d'être formaté pour le modèle.7 Cette modification permettrait également d'ajouter systématiquement des numéros de lignes au contenu pruné, facilitant ainsi les éditions ultérieures via des outils de type "diff" comme replace\_in\_file.13

## **Dynamique de Formulation des "Goal Hints"**

Le succès de l'élagage contextuel repose sur la précision de l'indice d'objectif fourni au skimmer. Dans l'écosystème Cline, la génération de ces indices peut être automatisée en s'appuyant sur la structure bifocale de l'agent : le mode "Plan" et le mode "Act".23

En mode "Plan", Cline explore la base de code et définit une stratégie sans modifier de fichiers.13 Les sorties de cette phase constituent une source primaire riche pour les "Goal Hints". Par exemple, si le plan stipule "analyser les schémas de base de données dans models.py", cette directive peut être automatiquement extraite et transmise à SWE-Pruner lors de la lecture subséquente du fichier models.py.7

En mode "Act", les indices peuvent être dérivés des instructions de l'utilisateur ou de l'état actuel de la chaîne de réflexion (CoT) de l'agent.14 Un modèle de langage plus petit ou une règle heuristique pourrait analyser le dernier message de l'agent pour en extraire l'intention.12 Si l'agent déclare "Je vais lire utils.ts pour voir comment les erreurs sont loguées", l'indice d'objectif devient "logique de journalisation des erreurs".7

### **Sources Potentielles pour l'Extraction d'Objectifs**

| Source d'Information | Méthode d'Extraction | Fiabilité de l'Objectif |
| :---- | :---- | :---- |
| Planification de Tâche | Parsing des étapes du plan | Très Élevée |
| Prompt de l'Utilisateur | Analyse sémantique de la requête | Moyenne |
| Historique des Outils | Corrélation entre search\_files et read\_file | Élevée |
| Instructions .clinerules | Correspondance de motifs sur les chemins | Déterministe |

L'utilisation de fichiers .clinerules permet de définir des priorités de pruning spécifiques par projet ou par répertoire.25 Par exemple, une règle pourrait spécifier que pour tout fichier dans un répertoire de tests, le pruning doit prioriser les assertions et les configurations de setup, tout en ignorant les données de test volumineuses intégrées.6

## **Analyse d'Impact Opérationnel : Latence et Économies**

L'introduction de SWE-Pruner dans le flux de travail de Cline modifie la structure des coûts et de la performance. Bien que l'inférence du modèle de 0,6B paramètres nécessite des ressources de calcul locales, l'impact global sur la latence est souvent positif en raison de la réduction drastique du volume de données traitées par le LLM distant.7

### **Modélisation de la Latence et de l'Efficience**

Considérons ![][image1], le temps total de réponse de l'agent pour un tour donné. Sans pruning, ce temps est dominé par ![][image2], le temps de traitement du LLM qui croît linéairement (ou de manière quadratique pour certaines architectures d'attention) avec la longueur du contexte ![][image3].

![][image4]  
Avec l'intégration de SWE-Pruner, nous ajoutons un temps d'inférence local ![][image5], mais nous réduisons significativement ![][image3] à ![][image6], où ![][image7].

![][image8]  
Étant donné que ![][image5] pour un modèle de 0,6B sur une architecture moderne est de l'ordre de quelques millisecondes, et que ![][image9] peut représenter plusieurs secondes pour des contextes de 100 000 jetons, l'économie de temps est substantielle.7 De plus, la réduction de la charge cognitive sur le modèle principal réduit le risque de réponses générées incorrectes ou d'hallucinations d'outils, évitant ainsi des tours de correction coûteux.7

### **Tableau des Gains de Performance Observés (Benchmarks)**

| Benchmark | Modèle de Base | Réduction de Jetons | Amélioration du Temps de Cycle |
| :---- | :---- | :---- | :---- |
| SWE-Bench Verified | Claude 3.5 Sonnet | 38% | 26% |
| LongCodeQA | GPT-4o | 14.84x | 65% |
| Mini SWE Agent | GLM 4.6 | 23% | 18% |

L'analyse des trajectoires d'agents montre que SWE-Pruner permet non seulement d'économiser des jetons, mais réduit également le nombre de "rounds" ou de tours nécessaires pour accomplir une tâche.7 En filtrant les informations redondantes, l'agent localise les problèmes plus précisément et prend des décisions plus directes, évitant les lectures exploratoires répétées de fichiers volumineux.7

## **Défis de Sécurité, de Robustesse et de Confidentialité**

L'intégration d'un modèle supplémentaire et d'un mécanisme de filtrage dynamique soulève des questions de sécurité, notamment en ce qui concerne les attaques par injection de prompts et la confidentialité des données. Cline est déjà identifié comme vulnérable aux injections via les fichiers .clinerules malveillants.5 L'ajout de SWE-Pruner pourrait complexifier cette surface d'attaque.

### **Risques liés au Filtrage et Attaques par Injection**

Un attaquant pourrait concevoir un code source qui, lorsqu'il est traité par le skimmer, manipule l'indice d'objectif ou force l'omission de lignes de sécurité critiques. Si le skimmer est influencé pour masquer des mécanismes de validation, l'agent Cline pourrait introduire des vulnérabilités lors de ses éditions.5 Il est donc crucial que le processus de pruning soit transparent et que l'utilisateur puisse vérifier les sections supprimées.

### **Souveraineté des Données et Inférence Locale**

L'un des avantages majeurs de l'utilisation d'un modèle de 0,6B paramètres pour SWE-Pruner est la possibilité de réaliser l'inférence entièrement en local.7 Cela garantit que les données sensibles de l'entreprise ou les secrets contenus dans le code source ne sont jamais transmis à un tiers pour le processus de compression.12 Cette architecture "Local-First" renforce l'attrait de Cline pour les environnements avec des exigences de conformité strictes.5

## **Implémentation de Stratégies de Récupération (Recovery)**

Le pruning agressif comporte le risque de supprimer des informations vitales. Pour assurer la robustesse du système, une stratégie de récupération à deux niveaux est recommandée. Premièrement, le contenu pruné doit inclure des marqueurs visuels ou sémantiques indiquant où des lignes ont été supprimées, par exemple : //... \[35 lignes prunées pour focus sur la gestion des erreurs\]....12

Deuxièmement, l'agent doit être instruit via son prompt système de la possibilité de demander une lecture non filtrée d'une plage spécifique s'il suspecte un manque d'information.12 Cette approche transforme le pruner en un outil d'exploration dynamique plutôt qu'en un filtre destructif définitif. L'agent peut ainsi naviguer dans le code à différents niveaux de fidélité, optimisant son propre contexte de manière itérative.12

## **Vers une Gestion de Contexte Auto-Adaptive Intégrée**

L'intégration de SWE-Pruner dans Cline marque une transition vers des systèmes de gestion de contexte auto-adaptatifs. Actuellement, Cline s'appuie sur des mécanismes réactifs (troncature après dépassement) ou manuels (mentions @ par l'utilisateur).4 En devenant "context-aware" au niveau du prétraitement, Cline peut proactivement ajuster la densité d'information envoyée au modèle.

### **Perspectives Futures : Au-delà du Code Source**

Le succès du pruning sur le code source ouvre la voie à son application sur d'autres types de données contextuelles dans Cline. Les sorties de terminaux lors de l'exécution de commandes complexes, qui peuvent générer des milliers de lignes de logs, bénéficieraient grandement d'un filtrage intelligent basé sur les erreurs ou les avertissements pertinents à la tâche.6 De même, les résultats de recherche web ou les documentations techniques volumineuses pourraient être distillés par un skimmer neural avant d'être intégrés à la fenêtre de travail de l'agent.14

L'architecture MCP Apps, qui permet d'intégrer des interfaces interactives dans Cline, pourrait également servir de panneau de contrôle pour le pruner, permettant à l'utilisateur de visualiser en temps réel ce qui est conservé ou supprimé et d'ajuster l'objectif de l'IA manuellement si nécessaire.18

## **Synthèse et Recommandations Stratégiques**

L'analyse exhaustive des méthodes et solutions pour l'intégration de SWE-Pruner dans Cline révèle un potentiel significatif d'amélioration de l'efficience des agents de codage. Le pruning task-aware résout la tension entre la nécessité d'une vision holistique du projet et les contraintes de coût et de performance liées aux longs contextes.

### **Recommandations pour le Développement et l'Intégration**

1. **Architecture Middleware MCP** : Il est recommandé de prioriser l'implémentation d'un serveur MCP dédié. Cela offre la plus grande flexibilité, permet une mise à jour indépendante du modèle de skimmer et assure la compatibilité avec d'autres clients MCP comme Cursor ou Claude Desktop.15  
2. **Automatisation des Goal Hints** : L'intégration doit exploiter la phase de planification de Cline pour générer des indices d'objectifs sans intervention utilisateur, maximisant ainsi l'autonomie de l'agent.13  
3. **Transparence du Pruning** : Le système doit inclure des annotations de numéros de lignes et des marqueurs de suppression clairs pour éviter toute confusion de la part de l'agent ou de l'utilisateur final.12  
4. **Inférence Locale Optimisée** : L'utilisation de bibliothèques comme ONNX Runtime ou l'intégration via un service local léger (ex: via le SDK MCP en Python) garantit une latence minimale et une sécurité des données optimale.8

En conclusion, l'adoption de SWE-Pruner comme méthode d'optimisation de la fenêtre de contexte transforme Cline en un outil plus précis, plus économique et capable de traiter des tâches d'ingénierie d'une complexité accrue. Cette évolution s'inscrit dans la tendance plus large des agents de "Software Engineering 3.0", où la gestion intelligente de l'information devient aussi cruciale que la capacité de génération de code elle-même.28

#### **Sources des citations**

1. The End of Context Amnesia: Cline's Visual Solution to Context Management \- Cline Blog, consulté le février 26, 2026, [https://cline.bot/blog/understanding-the-new-context-window-progress-bar-in-cline](https://cline.bot/blog/understanding-the-new-context-window-progress-bar-in-cline)  
2. Dissecting Cline — Cline Context Management | by balaji bal ..., consulté le février 26, 2026, [https://medium.com/@balajibal/dissecting-cline-cline-context-management-260aec3d84cb](https://medium.com/@balajibal/dissecting-cline-cline-context-management-260aec3d84cb)  
3. Two Ways to Advantage of Claude Sonnet 4's 1M Context Window in Cline \- Ghost, consulté le février 26, 2026, [https://cline.ghost.io/two-ways-to-advantage-of-claude-sonnet-4s-1m-context-window-in-cline/](https://cline.ghost.io/two-ways-to-advantage-of-claude-sonnet-4s-1m-context-window-in-cline/)  
4. Context Window Guide \- Cline Documentation, consulté le février 26, 2026, [https://docs.cline.bot/model-config/context-windows](https://docs.cline.bot/model-config/context-windows)  
5. Google Antigravity vs Cline: Agent-First Development vs Open-Source Control for Teams, consulté le février 26, 2026, [https://www.augmentcode.com/tools/google-antigravity-vs-cline](https://www.augmentcode.com/tools/google-antigravity-vs-cline)  
6. Context Management : r/CLine \- Reddit, consulté le février 26, 2026, [https://www.reddit.com/r/CLine/comments/1i6oevd/context\_management/](https://www.reddit.com/r/CLine/comments/1i6oevd/context_management/)  
7. SWE-Pruner: Self-Adaptive Context Pruning for Coding Agents \- arXiv.org, consulté le février 26, 2026, [https://arxiv.org/html/2601.16746v1](https://arxiv.org/html/2601.16746v1)  
8. Ayanami1314/swe-pruner \- GitHub, consulté le février 26, 2026, [https://github.com/Ayanami1314/swe-pruner](https://github.com/Ayanami1314/swe-pruner)  
9. GPT-5 is restricted from reading files beyond the project folder \#5487 \- GitHub, consulté le février 26, 2026, [https://github.com/cline/cline/issues/5487](https://github.com/cline/cline/issues/5487)  
10. (PDF) SWE-Pruner: Self-Adaptive Context Pruning for Coding Agents \- ResearchGate, consulté le février 26, 2026, [https://www.researchgate.net/publication/400071923\_SWE-Pruner\_Self-Adaptive\_Context\_Pruning\_for\_Coding\_Agents](https://www.researchgate.net/publication/400071923_SWE-Pruner_Self-Adaptive_Context_Pruning_for_Coding_Agents)  
11. SWE-Pruner: Self-Adaptive Context Pruning for Coding Agents \- Takara TLDR, consulté le février 26, 2026, [https://tldr.takara.ai/p/2601.16746](https://tldr.takara.ai/p/2601.16746)  
12. SWE-Pruner: Reduce your Coding Agent's token cost by 40% with "Semantic Highlighting" (Open Source) : r/ClaudeAI \- Reddit, consulté le février 26, 2026, [https://www.reddit.com/r/ClaudeAI/comments/1qvdsdm/swepruner\_reduce\_your\_coding\_agents\_token\_cost\_by/](https://www.reddit.com/r/ClaudeAI/comments/1qvdsdm/swepruner_reduce_your_coding_agents_token_cost_by/)  
13. Chapter 4: System Prompt Advanced \- Cline, consulté le février 26, 2026, [https://cline.ghost.io/system-prompt-advanced/](https://cline.ghost.io/system-prompt-advanced/)  
14. Inside Cline: How Its Agentic Chat System Really Works | by Flora Lan | Jan, 2026 | Medium, consulté le février 26, 2026, [https://medium.com/@floralan212/inside-cline-how-its-agentic-chat-system-really-works-3d582935efa5](https://medium.com/@floralan212/inside-cline-how-its-agentic-chat-system-really-works-3d582935efa5)  
15. MCP Server Development Protocol \- Cline, consulté le février 26, 2026, [https://docs.cline.bot/mcp/mcp-server-development-protocol](https://docs.cline.bot/mcp/mcp-server-development-protocol)  
16. Model Context Protocol (MCP) Server: A Deep Dive into the Cline-MCP-Example for AI Engineers \- Skywork.ai, consulté le février 26, 2026, [https://skywork.ai/skypage/en/Model-Context-Protocol-(MCP)-Server:-A-Deep-Dive-into-the-Cline-MCP-Example-for-AI-Engineers/1972125087999037440](https://skywork.ai/skypage/en/Model-Context-Protocol-\(MCP\)-Server:-A-Deep-Dive-into-the-Cline-MCP-Example-for-AI-Engineers/1972125087999037440)  
17. How to use MCP in Cline and Cursor \- DEV Community, consulté le février 26, 2026, [https://dev.to/webdeveloperhyper/how-to-use-mcp-in-cline-and-cursor-54hg](https://dev.to/webdeveloperhyper/how-to-use-mcp-in-cline-and-cursor-54hg)  
18. SettleMint Model Context Provider (MCP), consulté le février 26, 2026, [https://console.settlemint.com/documentation/blockchain-platform/release-notes/2025/2025-03-11-settlemint-mcp](https://console.settlemint.com/documentation/blockchain-platform/release-notes/2025/2025-03-11-settlemint-mcp)  
19. Cline v3.36: Hooks \- Inject Custom Logic Into Cline's Workflow \- Ghost, consulté le février 26, 2026, [https://cline.ghost.io/cline-v3-36-hooks/](https://cline.ghost.io/cline-v3-36-hooks/)  
20. Decimates sourcefiles during editing · Issue \#6769 · cline/cline, consulté le février 26, 2026, [https://github.com/cline/cline/issues/6769](https://github.com/cline/cline/issues/6769)  
21. Cline attempts to use str\_replace\_editor instead of replace\_in\_file when using VSCode LM API with Claude Sonnet · Issue \#4027 \- GitHub, consulté le février 26, 2026, [https://github.com/cline/cline/issues/4027](https://github.com/cline/cline/issues/4027)  
22. Can't simply count line numbers \- can't have discussions about "the code on line XXX" · Issue \#7821 · cline/cline \- GitHub, consulté le février 26, 2026, [https://github.com/cline/cline/issues/7821](https://github.com/cline/cline/issues/7821)  
23. Prompt Engineering for AI Agents \- PromptHub, consulté le février 26, 2026, [https://www.prompthub.us/blog/prompt-engineering-for-ai-agents](https://www.prompthub.us/blog/prompt-engineering-for-ai-agents)  
24. Cline VS Code Guide: AI Agent Setup & Deployment \- DeployHQ, consulté le février 26, 2026, [https://www.deployhq.com/guides/cline](https://www.deployhq.com/guides/cline)  
25. Rules \- Cline Documentation, consulté le février 26, 2026, [https://docs.cline.bot/customization/cline-rules](https://docs.cline.bot/customization/cline-rules)  
26. Using MCP Tools with Claude and Cline \- Scott Spence, consulté le février 26, 2026, [https://scottspence.com/posts/using-mcp-tools-with-claude-and-cline](https://scottspence.com/posts/using-mcp-tools-with-claude-and-cline)  
27. MCP Apps \- Model Context Protocol, consulté le février 26, 2026, [https://modelcontextprotocol.io/docs/extensions/apps](https://modelcontextprotocol.io/docs/extensions/apps)  
28. Autonomous-Agents/README.md at main \- GitHub, consulté le février 26, 2026, [https://github.com/tmgthb/Autonomous-Agents/blob/main/README.md](https://github.com/tmgthb/Autonomous-Agents/blob/main/README.md)  
29. eltociear/awesome-AI-driven-development \- GitHub, consulté le février 26, 2026, [https://github.com/eltociear/awesome-AI-driven-development](https://github.com/eltociear/awesome-AI-driven-development)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACgAAAAYCAYAAACIhL/AAAAB+klEQVR4Xu2V3SveYRjHrwzzElvhQAyNrS0lHE9eIkeKyIETmfIH7EAt2dkmRGntkHGiFKUoolbe1nIilJTaEQd2ttY4WGu+l+t6eu6u/Txv9Tyeg9+3PnXf3+v61fW7r/uFyJcvXxGpC/wDf8Ep2AS/1PsDvoEtjbNXJ58lTqtgGDxyvA2SYp45XhW4AvmOF3flgjXjZZAUcmZ81rE14q0+0GO8FpLV+2T8TJL2J1TcwofGe09SIO9NV+ngpfHuRXskBT62gWRQDsnJ3bcBR03guTXvUKS5pSTb56sNWLWRrN6IDTg6osivmmhyB8GkNa2mSApstgFVAckdmWYDHooml8XXXac1rQ7ANclVY8WHh1fkgqQdL9Tng7MIJsAyqAmR2whmwBgYB2/VTwW/QZ7OPVVGsnqhrpIPJJd6QMXgHFTqvAOs6NjmPgU/QInOv4BuHb8i+aH/xG3gghj+Wy6Q+a7ek2DqrfjZa3Dmo2DemXOBhzq2uXyvzuo4BVyCQp3zSobdf+GUDX6StJ+fuwdgG7x2crh13Gqv3F3Qr3nV4ITkJeMHYB20ayxmcRt2dPyOZN98puBLxIVwwXxVeeUugVb1uPVz4A2oINl/RerHrCyStveCevXKSf6ei+ADEnhpvHJrwUcwBAbAAskWYXHuNEmxvnwljW4AaL5m6VGjjrUAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB8AAAAYCAYAAAACqyaBAAABrklEQVR4Xu2VPShFYRjH/74ZfCRfhVAMFotNlMRok7BRLBaKRCgDwuRrIAYZFCWiFJNBZCBZlGIykEWKIvF/PG+d472X4Z57L4Nf/eo9//ec+5734zwX+OefX6COvtM3ekH36KPJXukR3Tf9klXoY8Fhmw7QZFe2Cx2oyJWV0Cea5so8kUR3rCweOsillQvnduCFZtpkZTXQWc9aeQJ0S4KGLGuclQ1DB5ez4CaWFltZ0DmADp5id4SaROgJP7Y7PFIOndSP1EJnPWp3eCQDvtvowyR08Gq7Ixyc0mfo5+aPPDpPJ+ggXTV5AZ2iy7SLjpt2tLnepFXmXr/kQ2f93ecUQ8/gLN8QnTbtHmjxeYBTmOR3umkp9EXks/5COvQm8QY6uHhlslznVjSYPMJcr9FG086BbpX7xaUgdUJX8R46VsDIIVwy7Uh6S7Nplsn6oVshSOV8oYW0nm7QTGitCIgOaAESKuk1dElbTLYFZyXaoOdCWIdu1Ri0SgZEKp2hfbSdrtA5aDGSlbiji3SE9tIofeyzTC9Aty0kyD/eiR2Gi1borMNOGT00Svvv8wGzaFPYtBxajgAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA0AAAAYCAYAAAAh8HdUAAAAsklEQVR4XmNgGAVYgRUQ7wbiV0D8H4i/A/EZIJ6HrAgXWM8A0WSMLoELMDFAbLqBLoEPWDBAbJmMLoEP1DBANAWhS+ADh4D4FxDzo0vgAiCFfxkgGokGICeBnNaELgEFxUAsji44hQGiyRldAgiEgPgouiAIXAfin0DMjSbOCMQLgTgbTZxBnQFiCyhFIANOIJ4ExJ8ZkALHjgGi8AIDRNMzKP8cEH+AioHwMpiGUUB3AADC8SRQwDvm9gAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAjCAYAAAApBFa1AAAEdklEQVR4Xu3cW6htUxzH8b/7LdfInSJyeCCXyK2dax6UBxwUzjmhJJI39xMRD5RbkttRiAcSSnInl3LnRZQXUaTcQpL4//qP0R7nv9ZcZ2777L3mqe+n/s0x/3OuPcdY+2H9G3PMaQYAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABbZLTnR4RmPrXISAAAAC2tvj41zssPxHi/mJAAAmL5/Pb7weKm0//Z4w+Mfj2Oa86bpdBvt53sW/VR7KP3ssoHHQzk5xh0ef3h8ZDGuXz1eL23l5+pSj7dS7kib/Q4/sNF+He6xWcoBAIApam9/berxVbM/JC807dzPz5v2UG3i8VxOJid5XNPsq6Cq9vd4vNnvS39jx5x061sUv11eyQkAADA9y5v2iR73NPtDmmU5p2nnfmq2aOhUZK6pYHvQY49mvy3YTva4rtnv6+ecKI7wuCsnG7/kBAAAGIa3PbbJyQFaV/rZ6lOwtbawuC06X13r0d702DonG22xCAAABmJLi7Vr2XE50eg6tqct3KxXVz/nYyeP73KyJz1V2VXcfGJxrCtunD11xCket+VkDypmW0+kfVGhpvWJk3SNCQAATJEWu4/7kf4tJ4odrPuYPJ8TjXqtrpikq5/zdVlO9HSFxwM5OcZcZ9g+tlj3Nl/jZtjuttHvMBd6+TgAABgA/UCPmxW7tmx38zigtFV43Nwc28tm116d6XG0x2dlf20b189XPS702M7jVIvrr7BYWH+Yx3oW6950zmkWff3L4zWPCyxm2A60cF7ZvmPx+fstxvdDyeta8r7Hhhb92a/kJplLwXa+jRZMG3l8Wtp17ZnG+qHFE6iaMTvEVl+TKD+mfWm/Q61TvNNGb4/W8QIAgAHQTFl9xUP9Id+9OT5Ttrc2ORUOeqXGTNmvDwCowNnZ40qP20tubVG/cj+rbyyKJxVsB1kUNxqXqFBSsabiUsWkLLXVP6/9aqZs37VY5H+UxfhWWYzv+3JcBaF8W7Zr0qdgO8GiX39ajLF9+vUsj69L++yyvcFiXPrOdb6uUcddKb+ktI+12e9Qt4Drq0NycSjP5gQAABgmzVSJiqGHS3t7i3Vk9d1eOvZUaat40C3C3z12LbnFcG/Z1ld/1GKqPll6btmqYNPaMBVCKuKqurj/Kotz9U43jUOF3/UW49NTmhrfIx77WhRHCl2rfWJ1kkNzYg4u97jJoqDUTJquqyc5d/F41GK27WmLwrp9ulfFc52Z62sfi/8rAABYB2xucXtO9LZ8zThpkb1opqYeO9jjao+LLAoGHdMrKhaLZq5WWtzulG0t+lL3NTOm24i6/anboz9ZPIVZaYZOVKzVfqtAfcyieNP49Hn9zSfLcY1Ta8H00tmLS24hafZQ17vE4z6Lp2S/tFg/d0Y5R4WjZuJaKirrzFxfq3ICAAAA/8+ynJhgZU50eNmiUAcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADMt/rgbL8kOU8L8AAAAASUVORK5CYII=>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAYCAYAAAC8/X7cAAACPklEQVR4Xu2WW4iNURTH/+6U2xRymxpFY168MSGFeJgkLx7woCikRDTGpZnxIJdcEiUyLgl584KI5JZLHqjxopTU5IUnKRoS/7//OnM+u+OFU3M+nX/9ap21v2+ftfdae+0PqKqqqv4LLSU/yHfyitwmn8L3jTwl92Ncvjl+rXJ0jbSRERnfLTjYKRnfNPKZjMr4el3DyY3ENxgO9HXil16mjt7WKrIi8S2Ed/944h8Cl1dFSSUyKPHtgRegs5HVQNKQ+CpSj+AFjEwH8qBhcOd5lg7kRYvh3d+XDuRFR+EFLEgH8qIX5AvcSlNNIsfIBdJMDoTdn2yE2/FWcorcJH3IVLKDXIHVlzyE23c9uUjOkg2khdwl0+NZaSI8335yHqXj6lEdvPt/apXb4EvsI4oXnJ5dTtaTE/CfKXtv4GC1MHWuwv2hy7Ar7O1kPLxhM8KnCtgc9jjymEyA5+ogY2OsR6PhIMQ7eAFCAchXW3z0124ouOwCFdg6uGN1krmZMUnvbyGH4vdqcjnsMWQJfr9IH4RP2k2ekF2kncwuPPQvaoUnk1QGX8lkeGe6UTrFd8j8sE+TTSi26MNkZ9iF7A4lNeQ6nNmy6ipcMtJacjDsZeRe2KnewmWgi1CZbUQxaLXrmWGvhOtci22Cy1HZkwbAmdA8fy3V4XtyhuyFD2e/GNPk+iAsJWVNB1X1fQQ++PPgdz/ATUBaBB/ik3ADUEbOwVm6hDJ8BesAPk+dedIaePdzqVlwRxCyqyqHfgKAYm6vPUSPgAAAAABJRU5ErkJggg==>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAYCAYAAAD3Va0xAAAA6ElEQVR4Xu2SMetBURjGXzYZlEVZ/wO7RZSUb+ADGBksymryETArJasPYFM2yeRvVwaTkkSJ5/QedTwdXfb7q99wn+eet3PuuSIhHtJwA4tc/EoDPmCWC0MBzuBB9KULXMKh+5JlDOccMlPRQTkuHHawzqFLVHRHWy4c/uAZJrhwyYvups+FQ038x32jIzqoyoVDC5Y5ZMwHvEnAtoMwi+/yxW0EYY5jjtXlwtKGKQ59DEQHVbgASbjg8BP/8ArjlEfgCDYp95IR3Y35s11isAdPEnABJdHFa9FBe/u8gkebGSevBSEhxBOEEiyLNhQ8RgAAAABJRU5ErkJggg==>

[image7]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFIAAAAYCAYAAABp76qRAAADeUlEQVR4Xu2YWahOURTH/2TIkPFBPH1ChjKXOW6GJ0UoPMiYecgUJdyIxAOFUKTMHoREmecxQmR6ULeEDCFClFh/6xzWt+455/suty/l/Or/cP5r73P3Wd/ea+99gZSUlJQsGonui7r7QIHoKtovOic6K+qZFY1ngqiDea4pWinqbLyCMlH0XdTCBwpAF9FTUafgua/os6j3rxbxnIKO22q7qIpt9Ld0E50QvYT+AQ7uhmirbRSwU3TemwXiumit83aJDjkvitOiW6K3omOiGdnhLCZB8xEmnH0uimbaRkkcgHbs6AOGJ9BlUmiaQcc2zfnFoveiSs73nBRlvJlARWgCn4uqulgi7MgZ+dAHDE1EH0W1faAADIMmcoTzZwV+L+d7OMMy3kygHfS9m3wgF6w/7LjOBwwjEb3co6gvOgJ95wfRNdEiRNck/ogLvOmYDX0XE2qZGvhjne9hIseIDopui25CN6445kHfO9QHcrEQ2nGwDxhYI4q8GcMG0RboYLnsOGN2QD+gvWlHpoumOM8Tjs8nkvWMPjfBJA6LlplnTpgSUT3jWY5D38sJUSa4gXxF+S3bvd4IGCd6Ba1Z3DiuQo8yuerQfEQnMjxF8L1JtHHPLaH9ljuf1IDm4rIP5ILJ+4by3Y1ZY+KoJRoFXer9kHujIOOhHz7c+ZzJuVZSFEwW+931AWEA4pOcCAfBjkt9IGCOqIE384BLlrVpN7Q+RdXHkP7ecAyBjnG08zk2+kXOt/D7XiC73lWA9uMG61kDjfGcGsUqb4Ssh3bs4wPQGnLJm3nAwbMezoW+l7/uBVEP2yiApwFbv6LIQMfoz3IroOfeOs63LIH2LTYe29O7YryQO6Ivouo+AF1Bq70Z8gDakdPdwl9tG3RnLCuchf59TaEHesZ4G+E1jUlkjcznpsR2m53Hw/g+5/GIxEtGyCDo361sPP6gTORi4xFegemfcT5h8rnjt/YB0hzakUvQUg26GfDo8icbEDeHOAaKHok+QW8Z9qOTaCx6DP1Y0kr0BvoNIeExjofpEE6Io/h9r+Zxi7s4JxC/0xLWYtZvS0PoiiqVYF72mTxmmB2fBc9cju8Cj+Ls+ZfgzOVS3SPaKGqbHf5Zy1+j9MRgIjibeefmVZP37LomzhsT+5RAv/te8Mx/0LB0hPmYHLRPSUlJSUlJSfkf+QGN+8Hd0netuwAAAABJRU5ErkJggg==>

[image8]: <data:image/png;base64,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>

[image9]: <data:image/png;base64,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>