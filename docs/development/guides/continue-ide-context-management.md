# **Étude Architecturale de la Gestion du Contexte et de la Visibilité des Tokens dans les Environnements Continue pour VS Code et JetBrains**

La gestion de la fenêtre de contexte représente le pivot central de l'efficacité des assistants de codage basés sur les grands modèles de langage (LLM). Dans l'écosystème de l'extension Continue, disponible sur Visual Studio Code et les environnements de développement intégrés (IDE) de JetBrains, la question de la visibilité de la progression de cette fenêtre — à savoir la capacité à quantifier les tokens utilisés, restants et disponibles — a évolué d'une simple requête utilisateur vers une fonctionnalité architecturale majeure.1 Cette étude analyse en profondeur les mécanismes de monitoring du contexte, les implémentations spécifiques aux IDE, et les stratégies de régulation thermique du flux de tokens pour optimiser les interactions homme-machine dans le développement logiciel.

## **L'Architecture du Contexte dans les Assistants de Codage Modernes**

La fenêtre de contexte est définie comme la quantité de données historiques et environnementales qu'un LLM peut traiter simultanément lors d'une seule requête.3 Dans le cadre de Continue, cette fenêtre ne se limite pas aux messages échangés lors d'une session de chat, mais englobe également le code sélectionné, les fichiers ouverts, les structures de dépôt et les métadonnées système.4 La complexité de cette gestion réside dans la nature finie des ressources computationnelles : chaque modèle possède une limite stricte de tokens, et dépasser cette limite entraîne inévitablement des erreurs de troncature ou des échecs de génération.6

L'architecture de Continue repose sur une séparation claire entre le cœur logique (core), les extensions spécifiques aux IDE et l'interface utilisateur graphique (GUI).5 Cette structure permet une gestion centralisée du contexte tout en autorisant des variations dans la restitution visuelle de la progression des tokens. Le cœur est responsable du chargement de la configuration utilisateur, de la gestion des fournisseurs de contexte et de la communication avec les modèles.5 L'interface, quant à elle, doit traduire ces données brutes en indicateurs compréhensibles pour le développeur, afin d'éviter le phénomène de "saturation cognitive" où l'utilisateur perd le fil de ce que l'IA "voit" réellement de son projet.1

| Composant Architectural | Rôle dans la Gestion du Contexte | Impact sur la Visibilité des Tokens |
| :---- | :---- | :---- |
| Core (TypeScript) | Calcul de la tokenisation et gestion de l'historique | Source unique de vérité pour le décompte des tokens 5 |
| Extension (Node.js/Kotlin) | Interfaçage avec les API de l'IDE (VS Code/JetBrains) | Transmission des métriques de contexte vers l'UI 5 |
| GUI (React/Redux) | Affichage de l'interface de chat et des barres d'outils | Restitution visuelle de la progression (Barres, Tooltips) 1 |
| Context Providers | Extraction de données (fichiers, terminal, docs) | Définition dynamique de la charge de tokens entrante 4 |

## **Évolution de la Transparence des Tokens : De l'Opacité à l'Indicateur Visuel**

Pendant une phase prolongée du développement de Continue, les utilisateurs ont exprimé des difficultés à situer leur consommation de contexte en temps réel.1 L'absence d'indicateur clair forçait les développeurs à deviner le moment opportun pour réinitialiser une session, souvent après avoir rencontré une erreur de type Token limit reached.6 Cette opacité nuisait non seulement à l'expérience utilisateur, mais entraînait également une inefficacité économique pour les utilisateurs d'API payantes et une surcharge de mémoire pour ceux utilisant des modèles locaux via Ollama ou Jan.ai.6

Le tournant majeur dans la visibilité du contexte a été marqué par l'Issue \#3876 sur le dépôt GitHub de Continue, intitulée "Context Window Fill Visual indicator".2 Ouverte en janvier 2025, cette requête visait à introduire une jauge visuelle simple montrant le taux d'occupation de la fenêtre de contexte.2 Après plusieurs mois de développement et de discussions au sein de la communauté Discord de Continue, cette fonctionnalité a été officiellement intégrée et clôturée comme "complétée" le 11 août 2025\.2 Cette mise à jour a apporté une réponse directe à la question de savoir s'il est possible de connaître la progression du contexte lors d'une session de chat.

L'implémentation de cette visibilité repose sur un système d'alertes subtiles et de barres de progression. Lorsqu'une session approche de sa limite, un élément de la barre d'outils change de couleur, passant généralement du vert à l'orange puis au rouge, reflétant l'état de saturation.1 Un survol de cet indicateur (tooltip) permet d'afficher les métriques exactes : le nombre de tokens actuellement utilisés par rapport au plafond total autorisé par le modèle configuré.1 Cette approche s'aligne sur les standards ergonomiques établis par d'autres outils comme Goose ou VS Code Copilot, tout en conservant la flexibilité propre à Continue.3

## **Implémentation Spécifique dans Visual Studio Code**

Visual Studio Code bénéficie de l'intégration la plus poussée en termes de monitoring du contexte, grâce à la flexibilité de son API d'extension et à l'utilisation d'une console de diagnostic dédiée.12 Pour les utilisateurs souhaitant une vision exhaustive de la progression des tokens, plusieurs couches d'information sont disponibles.

### **La Console Continue : Le Tableau de Bord du Contexte**

Au-delà de la barre de progression visuelle dans l'interface de chat, Continue propose une "Continue Console" dans VS Code, spécifiquement conçue pour le suivi des prompts et de l'analytique.12 Pour y accéder, le développeur doit activer le paramètre Continue: Enable Console dans les réglages de l'IDE, puis utiliser la commande Continue: Focus on Continue Console View via la palette de commandes.12 Cette console affiche :

1. Le décompte précis des tokens pour chaque prompt envoyé au modèle.13  
2. La structure détaillée du contexte inclus (fichiers référencés via @, historique de session, instructions système).5  
3. Les mesures de performance et les métriques de génération (tokens par seconde).13

Cette visibilité est cruciale lors de l'utilisation de fonctionnalités complexes comme l'autocomplétion ou l'édition en ligne (Ctrl+I), où le volume de tokens peut augmenter de manière exponentielle sans action explicite de l'utilisateur.7 Par exemple, une erreur fréquente de type "File/range likely too large for this edit" peut être anticipée en observant la montée en charge dans la console avant de valider une modification.7

### **Indicateurs de l'Interface de Chat VS Code**

L'interface de chat dans VS Code intègre désormais des éléments de contrôle de la fenêtre de contexte qui imitent les meilleures pratiques du marché.11 Bien que le design reste propre à Continue, la logique de remplissage est similaire à celle de Copilot : une barre ombrée progresse dans la zone de saisie au fur et à mesure que l'historique s'accumule.11

| Caractéristique UI | Description de l'Indicateur dans VS Code |
| :---- | :---- |
| Jauge de Remplissage | Barre de progression située en bas ou sur le côté du champ de saisie 1 |
| Tooltip de Données | Affiche le ratio Tokens Utilisés / Limite Totale au survol 1 |
| Alertes de Seuil | Changement de couleur de l'icône de statut (Vert \< 50%, Orange 50-85%, Rouge \> 85%) 3 |
| Notifications de Pruning | Message informant que la session va être élaguée pour continuer 1 |

## **La Problématique JetBrains : Contraintes de l'Interface et Solutions de Monitoring**

L'implémentation de Continue sur les IDE de JetBrains (IntelliJ IDEA, PyCharm, WebStorm, etc.) présente des défis distincts en raison de l'architecture Swing sur laquelle reposent ces outils, moins flexible que l'environnement Electron de VS Code.16 Historiquement, les utilisateurs de JetBrains ont rapporté une visibilité moindre des métriques de tokens directement dans l'interface graphique.16

### **Accès aux Données via les Logs Système**

Pour pallier l'absence potentielle d'indicateurs visuels en temps réel dans certaines versions de l'extension JetBrains, le monitoring s'effectue via les journaux système.12 Le fichier \~/.continue/logs/core.log constitue la source de données la plus fiable pour connaître l'état de la fenêtre de contexte.12 En examinant les dernières entrées de ce fichier, le développeur peut identifier :

* Le paramètre contextLength réellement utilisé par le modèle (qui peut parfois différer de la configuration si le serveur local impose ses propres limites).16  
* Le volume de données envoyé lors de la dernière requête de chat.12  
* Les erreurs de dépassement de mémoire vive, fréquentes lors de l'utilisation de modèles volumineux sur des machines locales.6

### **Évolution vers une Interface Native JetBrains**

Des efforts sont en cours pour aligner l'expérience utilisateur de JetBrains sur celle de VS Code. Les versions récentes cherchent à intégrer des tooltips et des indicateurs de progression qui respectent les directives de design de JetBrains (IntelliJ UI/UX guidelines).17 L'objectif est de fournir un panneau latéral de chat qui inclut non seulement l'interaction textuelle, mais aussi un affichage dynamique de la consommation de "crédits" ou de tokens, particulièrement important lors de l'utilisation de fournisseurs tiers comme Anthropic ou OpenAI via des clés API personnelles.19

## **L'Interface en Ligne de Commande (CLI) : Précision Statistique**

Pour les utilisateurs avancés, Continue propose une interface en ligne de commande nommée cn.21 Ce mode, particulièrement utilisé pour les tâches de refactorisation complexes ou l'automatisation, offre la visibilité la plus granulaire sur la fenêtre de contexte via la commande slash /info.21

Invoquer /info au sein d'une session TUI (Terminal User Interface) retourne un tableau complet de statistiques :

* **Utilisation des Tokens** : Décomposition entre tokens d'entrée (prompt), tokens de sortie (générés) et tokens de cache.21  
* **Coût de la Session** : Estimation financière basée sur les tarifs du fournisseur configuré.21  
* **État du Contexte** : Pourcentage d'occupation de la fenêtre de contexte totale.21

Cette approche "data-first" permet de contourner les limitations graphiques des IDE et offre un moyen rapide de vérifier si une session de chat est devenue trop volumineuse pour être efficace. La commande /info est ainsi le complément indispensable à la barre de progression visuelle pour les environnements de production.21

## **Configuration et Paramétrage du Contexte via YAML**

La connaissance de la progression du contexte est indissociable de la capacité à configurer les limites de ce dernier. Le fichier config.yaml (situé dans \~/.continue/) est le centre de contrôle où l'utilisateur définit les paramètres qui régiront l'affichage de la progression.23

### **Paramètres de Régulation des Tokens**

Un développeur peut influencer la manière dont le contexte est géré (et donc visualisé) en ajustant plusieurs clés critiques dans sa configuration.

| Paramètre YAML | Fonctionnalité | Influence sur la Fenêtre de Contexte |
| :---- | :---- | :---- |
| contextLength | Limite absolue du modèle | Définit le "100%" de l'indicateur de progression 6 |
| maxTokens | Limite de génération | Réserve une portion du contexte pour la réponse de l'IA 7 |
| maxPromptTokens | Seuil d'entrée | Limite la taille du prompt pour éviter la saturation précoce 14 |
| maxChunkSize | Taille des fragments | Contrôle la densité des données récupérées via @codebase 8 |

Une mauvaise configuration, par exemple une valeur de maxTokens trop proche de contextLength, peut saturer l'indicateur de progression dès le premier message, ne laissant aucune place à la réponse du modèle.6 La visibilité de ces métriques permet donc d'ajuster dynamiquement ces valeurs pour optimiser le rapport entre la longueur de l'historique et la capacité de réponse.

## **Analyse Comparative : Continue face à l'Écosystème des Extensions IA**

Pour comprendre la valeur de la visibilité du contexte dans Continue, il convient de la comparer aux solutions concurrentes qui ont fait de la transparence des tokens un argument de vente.

### **VS Code Copilot : Le Standard Industriel**

Le mécanisme de "Context window control" de GitHub Copilot est souvent cité comme la référence. Il affiche une barre ombrée proportionnelle à l'usage actuel. Au survol, l'utilisateur obtient une fraction exacte (ex: 15K/128K) et une répartition par catégorie (code, historique, système).11 Continue a largement convergé vers ce modèle suite aux demandes de la communauté (Issue \#6640).1

### **Cline et Roo Code : L'Approche Budgétaire**

Des extensions comme Cline ou son fork Roo Code vont plus loin en intégrant un compteur de coût monétaire en temps réel.24 Roo Code propose une barre ContextWindowProgress qui distingue l'espace utilisé, l'espace réservé pour la sortie de l'IA et l'espace libre.25 Il propose également un bouton "Condense Context" qui permet de déclencher manuellement une réduction de la charge de tokens, une fonctionnalité que Continue adresse via la commande slash /compact.21

### **Claude Code : La Précision du CLI**

L'outil Claude Code d'Anthropic utilise une approche similaire à la CLI de Continue, avec des commandes comme /stats et une ligne d'état configurable affichant context\_window.used\_percentage.28 Cette convergence montre que la visibilité de la fenêtre de contexte n'est plus une option, mais une exigence pour tout outil de développement professionnel.

## **Stratégies d'Optimisation du Contexte et Actions Utilisateur**

Savoir que la fenêtre de contexte est à 90% de sa capacité est inutile si l'utilisateur ne dispose pas de leviers pour agir. Continue propose plusieurs mécanismes pour "nettoyer" la fenêtre de contexte une fois la progression identifiée comme critique.

### **La Commande /compact : Résumé et Compression**

Inspirée des mécanismes de "Auto-Compaction" de Goose, la commande /compact dans Continue demande au modèle de résumer la conversation en cours pour en extraire l'essence technique tout en libérant une part significative de tokens.3 C'est la réponse privilégiée lorsque la barre de progression passe au rouge mais que l'utilisateur souhaite poursuivre le même fil de réflexion.

### **La Gestion Intelligente du Contexte (Smart Context Management)**

L'utilisation des fournisseurs de contexte (Context Providers) permet de limiter préventivement le remplissage de la fenêtre. Par exemple, au lieu d'utiliser @codebase qui peut indexer un volume massif de données, un développeur averti utilisera @file ou @symbol pour n'injecter que les tokens strictement nécessaires à la résolution du problème actuel.4

La formule simplifiée de l'occupation du contexte peut être représentée ainsi :

![][image1]  
L'objectif de la visibilité est de permettre à l'utilisateur de minimiser ![][image2] et ![][image3] pour maximiser la place disponible pour la réflexion du modèle (![][image4]).30

## **Facteurs Exogènes Affectant la Fenêtre de Contexte**

La progression visible des tokens peut parfois être trompeuse en raison de facteurs techniques liés aux modèles et aux infrastructures.

### **L'Impact de la Pensée Étendue (Extended Thinking)**

Avec l'introduction de modèles comme Claude 3.7 ou GPT-o1, une nouvelle catégorie de tokens est apparue : les tokens de réflexion (reasoning tokens).31 Ces tokens consomment de l'espace dans la fenêtre de contexte durant la génération, mais ne sont pas toujours comptabilisés dans l'historique de chat permanent.31 Dans Continue, la gestion de ces blocs de pensée via des "thinking tags" peut affecter la perception de la progression du contexte, car la barre peut bondir durant la génération avant de se stabiliser une fois la pensée finalisée.31

### **Tokenisation et Ratios Modèles**

Le nombre de tokens n'est pas strictement équivalent au nombre de caractères ou de mots. Chaque fournisseur (OpenAI, Anthropic, Ollama) utilise son propre tokenizer (ex: Tiktoken pour OpenAI).33 Continue doit donc traduire en interne les données brutes pour afficher un indicateur de progression cohérent, quel que soit le modèle utilisé. Cette complexité explique pourquoi les outils de monitoring comme "Copilot Token Tracker" ou la console Continue sont essentiels pour obtenir une mesure fidèle à la facturation ou aux limites physiques du modèle.34

## **Cas d'Usage : Monitoring du Contexte en Environnement Local**

L'utilisation de modèles locaux (via Ollama sur JetBrains ou VS Code) rend la visibilité du contexte encore plus critique. Contrairement au cloud, où le dépassement de limite entraîne une erreur API, en local, cela peut provoquer un crash de l'application ou un ralentissement extrême du système dû au "swap" mémoire.6

Un développeur travaillant sur un projet Java massif dans IntelliJ avec un modèle Qwen-32B local devra surveiller étroitement son core.log ou son indicateur de progression.7 Si la barre de progression indique que le contexte approche des 32k tokens (limite typique pour de nombreuses configurations locales), il est impératif de lancer un /clear ou un /compact pour éviter de saturer la VRAM de la carte graphique.6 Cette dimension "gestion des ressources" transforme l'indicateur de tokens en un véritable manomètre de santé système.

## **Perspectives Futures : Vers une Gestion Cognitive du Contexte**

L'évolution de Continue suggère que la simple barre de progression pourrait bientôt être remplacée par des systèmes de gestion plus autonomes. L'objectif ultime, tel que discuté dans les issues GitHub, est de "cacher cette complexité à l'utilisateur" en effectuant des actions en arrière-plan (compaction automatique, sélection dynamique de la pertinence) avant même que l'utilisateur ne se sente limité.1

Cependant, tant que les modèles resteront limités par des fenêtres de contexte finies, la possibilité de connaître la progression des tokens restera une exigence fondamentale pour les développeurs professionnels. La transparence permet une "hygiène de chat" rigoureuse, essentielle pour maintenir la qualité des raisonnements produits par l'IA sur le long terme.27

## **Synthèse des Méthodes de Monitoring dans Continue**

En conclusion, il est tout à fait possible de connaître la progression de la fenêtre de contexte dans Continue, bien que les méthodes diffèrent selon l'environnement et le niveau de précision requis.

1. **Indicateur Visuel (GUI)** : Disponible sur VS Code (et en cours de déploiement généralisé sur JetBrains) via des barres de progression colorées et des tooltips affichant le ratio de tokens.1  
2. **Continue Console (Diagnostic)** : La méthode de référence sur VS Code pour un audit détaillé des tokens de prompt et de génération.12  
3. **Logs Système (Backend)** : La solution ultime pour JetBrains via le fichier core.log, permettant de voir les limites réelles et les volumes de données échangés.12  
4. **Commandes Slash (Interactif)** : L'utilisation de /info dans le CLI ou l'observation des métriques après un /compact pour valider la libération d'espace.21

Cette capacité de suivi, intégrée officiellement en août 2025, transforme Continue d'un simple outil de chat en un environnement de développement assisté par IA mature, capable de gérer des sessions de travail complexes sur des bases de code étendues tout en offrant au développeur le contrôle nécessaire sur ses ressources.2

#### **Sources des citations**

1. Understanding tokens and Context · Issue \#6640 · continuedev/continue \- GitHub, consulté le février 13, 2026, [https://github.com/continuedev/continue/issues/6640](https://github.com/continuedev/continue/issues/6640)  
2. Context Window Fill Visual indicator · Issue \#3876 · continuedev/continue \- GitHub, consulté le février 13, 2026, [https://github.com/continuedev/continue/issues/3876](https://github.com/continuedev/continue/issues/3876)  
3. Smart Context Management | goose \- GitHub Pages, consulté le février 13, 2026, [https://block.github.io/goose/docs/guides/sessions/smart-context-management/](https://block.github.io/goose/docs/guides/sessions/smart-context-management/)  
4. Context Providers \- Continue Docs, consulté le février 13, 2026, [https://docs.continue.dev/customize/deep-dives/custom-providers](https://docs.continue.dev/customize/deep-dives/custom-providers)  
5. Continue • continuedev/vscode, consulté le février 13, 2026, [https://www.continue.dev/continuedev/vscode](https://www.continue.dev/continuedev/vscode)  
6. Context window when using a ollama · Issue \#5123 · continuedev/continue \- GitHub, consulté le février 13, 2026, [https://github.com/continuedev/continue/issues/5123](https://github.com/continuedev/continue/issues/5123)  
7. Error streaming edit diffs: Token limit reached. File/range likely too large for this edit · Issue \#7544 · continuedev/continue \- GitHub, consulté le février 13, 2026, [https://github.com/continuedev/continue/issues/7544](https://github.com/continuedev/continue/issues/7544)  
8. config.yaml Reference \- Continue, consulté le février 13, 2026, [https://docs.continue.dev/reference](https://docs.continue.dev/reference)  
9. Continue.dev \- Jan.ai, consulté le février 13, 2026, [https://www.jan.ai/docs/server-examples/continue-dev](https://www.jan.ai/docs/server-examples/continue-dev)  
10. Setup Extension with AskCodi API \- Continue.dev, consulté le février 13, 2026, [https://www.askcodi.com/documentation/integrations/continue/setup-continue-dev-ext-with-askcodi-api](https://www.askcodi.com/documentation/integrations/continue/setup-continue-dev-ext-with-askcodi-api)  
11. Manage context for AI \- Visual Studio Code, consulté le février 13, 2026, [https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context](https://code.visualstudio.com/docs/copilot/chat/copilot-chat-context)  
12. Troubleshooting \- Continue Docs, consulté le février 13, 2026, [https://docs.continue.dev/troubleshooting](https://docs.continue.dev/troubleshooting)  
13. Telemetry \- Continue Docs, consulté le février 13, 2026, [https://docs.continue.dev/customize/telemetry](https://docs.continue.dev/customize/telemetry)  
14. Prompt tokens for autocompletion are too few · Issue \#5586 · continuedev/continue \- GitHub, consulté le février 13, 2026, [https://github.com/continuedev/continue/issues/5586](https://github.com/continuedev/continue/issues/5586)  
15. GitHub Copilot in VS Code cheat sheet, consulté le février 13, 2026, [https://code.visualstudio.com/docs/copilot/reference/copilot-vscode-features](https://code.visualstudio.com/docs/copilot/reference/copilot-vscode-features)  
16. Continue Plugin for JetBrains IDEs, consulté le février 13, 2026, [https://plugins.jetbrains.com/plugin/22707-continue](https://plugins.jetbrains.com/plugin/22707-continue)  
17. \[FEATURE\] IntelliJ IDEA plugin for Claude Code (like VS Code extension) \#13120 \- GitHub, consulté le février 13, 2026, [https://github.com/anthropics/claude-code/issues/13120](https://github.com/anthropics/claude-code/issues/13120)  
18. Adding AI to IntelliJ IDEA using Continue and Generative APIs | Scaleway Documentation, consulté le février 13, 2026, [https://www.scaleway.com/en/docs/generative-apis/reference-content/adding-ai-to-intellij-using-continue/](https://www.scaleway.com/en/docs/generative-apis/reference-content/adding-ai-to-intellij-using-continue/)  
19. AI Chat | AI Assistant Documentation \- JetBrains, consulté le février 13, 2026, [https://www.jetbrains.com/help/ai-assistant/ai-chat.html](https://www.jetbrains.com/help/ai-assistant/ai-chat.html)  
20. Implement a progress bar of AI usage after 80% of the volume is used : LLM-1960, consulté le février 13, 2026, [https://youtrack.jetbrains.com/projects/LLM/issues/LLM-1960/Implement-a-progress-bar-of-AI-usage-after-80-of-the-volume-is-used?backToIssues=false](https://youtrack.jetbrains.com/projects/LLM/issues/LLM-1960/Implement-a-progress-bar-of-AI-usage-after-80-of-the-volume-is-used?backToIssues=false)  
21. Continue CLI Quick Start, consulté le février 13, 2026, [https://docs.continue.dev/cli/quick-start](https://docs.continue.dev/cli/quick-start)  
22. How to Use Continue CLI (cn), consulté le février 13, 2026, [https://docs.continue.dev/guides/cli](https://docs.continue.dev/guides/cli)  
23. How to Configure Continue, consulté le février 13, 2026, [https://docs.continue.dev/customize/deep-dives/configuration](https://docs.continue.dev/customize/deep-dives/configuration)  
24. cline/CHANGELOG.md at main \- GitHub, consulté le février 13, 2026, [https://github.com/cline/cline/blob/main/CHANGELOG.md](https://github.com/cline/cline/blob/main/CHANGELOG.md)  
25. Intelligent Context Condensing | Roo Code Documentation, consulté le février 13, 2026, [https://docs.roocode.com/features/intelligent-context-condensing](https://docs.roocode.com/features/intelligent-context-condensing)  
26. An Awesome List of AI Assisted Development Tools \- Vlad Iliescu, consulté le février 13, 2026, [https://vladiliescu.net/ai-assisted-dev-tools/](https://vladiliescu.net/ai-assisted-dev-tools/)  
27. Manage costs effectively \- Claude Code Docs, consulté le février 13, 2026, [https://code.claude.com/docs/en/costs](https://code.claude.com/docs/en/costs)  
28. Customize your status line \- Claude Code Docs, consulté le février 13, 2026, [https://code.claude.com/docs/en/statusline](https://code.claude.com/docs/en/statusline)  
29. Use Claude Code in VS Code \- Claude Code Docs, consulté le février 13, 2026, [https://code.claude.com/docs/en/vs-code](https://code.claude.com/docs/en/vs-code)  
30. how are you guys not burning 100k+ tokens per claude code session?? \- Reddit, consulté le février 13, 2026, [https://www.reddit.com/r/ClaudeCode/comments/1r26miw/how\_are\_you\_guys\_not\_burning\_100k\_tokens\_per/](https://www.reddit.com/r/ClaudeCode/comments/1r26miw/how_are_you_guys_not_burning_100k_tokens_per/)  
31. Building with extended thinking \- Claude API Docs, consulté le février 13, 2026, [https://platform.claude.com/docs/en/build-with-claude/extended-thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)  
32. Changelog \- Continue.dev, consulté le février 13, 2026, [https://changelog.continue.dev/](https://changelog.continue.dev/)  
33. My extension for token counting got a bit more fancier : r/vscode \- Reddit, consulté le février 13, 2026, [https://www.reddit.com/r/vscode/comments/1okbm5t/my\_extension\_for\_token\_counting\_got\_a\_bit\_more/](https://www.reddit.com/r/vscode/comments/1okbm5t/my_extension_for_token_counting_got_a_bit_more/)  
34. GitHub Copilot Token Tracker \- Visual Studio Marketplace, consulté le février 13, 2026, [https://marketplace.visualstudio.com/items?itemName=RobBos.copilot-token-tracker](https://marketplace.visualstudio.com/items?itemName=RobBos.copilot-token-tracker)  
35. I added Table of Contents, Prompt count and Token count to ChatGPT using this extension\!\!, consulté le février 13, 2026, [https://www.reddit.com/r/ChatGPT/comments/1m4l8p4/i\_added\_table\_of\_contents\_prompt\_count\_and\_token/](https://www.reddit.com/r/ChatGPT/comments/1m4l8p4/i_added_table_of_contents_prompt_count_and_token/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAmwAAAAjCAYAAAApBFa1AAAHnUlEQVR4Xu3cZ6xtRRXA8SWIoiKoiAULBGNDwS5YuSJi1CjRIMUQRYMae1fsqFgjWMGCwlMsERNFNKDwgadigURBjd0YI9b4wRY1SIjOP2smZ85w+7v3npvL/5es7L3nnHfemZl996w9e+8TIUmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSJEmSNqV9SryhxK9L/KjEM0q8u8Qh/Ztm7PIS/yvxzRI/qOt/KPGbEl+dvG2mto0F8+B7X1PiohL/LHF1ie/Wsod175ulg8eCBWz2/thKaN9/l/h6Xf9HiSvq+vW790mStqgzS7xgKGMAOH8om7U+eXx9iad128/p1mfpwrFgsHu3vmvkALwZHT4WzOPkbn2z9sdW0ffHXGSS1uzfrUuStqgXxvTBv/eSsWCGrjdsby+xd7f9iG59lpg1W8zTu/VHxXTb36hbn7VHjwUD+uNr3fb22Jz9sVV8vFt/S0zvN0v1lSRpC+DAv5kSs+V4bCycZM7aUglb71uxeeuxkiRgM/fHVsSl8++PhZKkrY2B9j5j4YBZoV3Gwuq4saDz17Fgjbw9djxBOLTEXcbCVXh/5HdZKBbDvWuXDWW/LPHZoeymJW43lDVrUQfcJq793ftgNnAha9EfoE9WYq3qPp8vDNskSD8ZynbEjuw3vH7KWLjO7lTisLGwM7bXSi12jJEkRR78x0txN47pmaLFbiB/zVjQWWwWYBygxlgMr188Fq4QN/uvxwCxkhk26jEOgj8uce+hbCF7xfrUASuZYVuL/gB9slzrWff5fDGm79GbpatK3HAsXGf8La/nAzGLHWMkSZH3If2+235oXDthmKvLt3ZlPEXIzA83zuNDdfnIusTR3fpaIkEY75H6ZIkDIp+gIwF9Vi1/dl3etS7b7BU3yeO2Jb5dYqcSZ5R4ZYmflbhl5FOpr4uVzfwsN2HbN+Z/LwPjHiV+G/nk7gklnllfY/15JX5V4hYl3lbL8dMSNylxamQdnlLiZiX+E/nE79geS1lpwjb2B/Ugofph5AMsrQ7Mut4j8qlSHFmX6PuEGUX6hJm/+9dyvhNPRaKve4998sWR++Nc5NO3d4xMckgqb1/id/W9Tyzx6sh2YwaplbOv0MZoM1lX1uWXI2cbqc+JkZ/Nv20JK30E+mc9kDTyNHePNtqvxK0jH0Cgj08r8fwSZ0fWse0PtD3bPAnetuk7+urTkfv9B0p8PjIpbubbV5vWXrQH9zE+sMT7Im+14ITu8ZF/k1zK5QTlUyWOKfG5mOwXc3UpSVoAg+nxkZfmOGA/derVPKi3s/n/duVHRR6IweDKwRg8xAA+d8+6vlYYNC6JTBB4urKf3ftIZOLJYM+gzYwIGLBw58jBtiUIc3XJDdzfiRwEH1LiDpEDGhjkGXhfXreXY7GBDQyCvIfvSj34GRX+z+a5dfmvyGSY9m8393P5mXo/oG6TjDTtqUwSNgbcD3av8RljeyxlOQnby2Lh/mj1wONi8rMTvJc2/Xvd7k8C5uqSPnljTCcmt4rJyQH6uveYHebz5yKTgl9Enji0fnlnic/UdRI2EriWEPIaXhvZjvTV1bWMJAN/ikws2f/pt/GkhD762FC2Fkh0qAMJON+JhKvp27Dt+0+I/IkZ+oHv2e8PbLfkGNtLvDky8dwt8ljAiVu/D/TvH7X2oo+OqGXfqOu0L58N+v5BJf4YeWzgpOSeMX2MkSStEskLB1MOyu0eHgZTXBB5kL9v5AGaAza/w/WeyMF8Ix9maElVSxi5tMi9eSRdzJD9LXIwp5zBCCQEHy3x0sgZBuq1e11Hm8X5c0wG86W0wX81+hmNJ0W2I23IbAXJ5Jfqa8x+gN8/ow4kQyTNaAlZn1xzr1ffHsvBLN9q8QQpMz44OXKGrzkwctbqVZEziCSsJHqtT6gLfQL6gXq9qMR7axn/jve2us+n/Ybc9yJnwEhumBXDWZGzTcwksc9iW13S92AWj/+37df7lrhbZH+0xJeEDX3ixP5DH7WEeqNQp4bvTV+DpPjmkScx/f7Adn8bBDPKeFddfqUufx6ZiO0U+X7abT6tvdDuyfxE5N/dzjFJztsJXpuNP6/EY2L6GCNJWiUGeQZcBj7O5E8vcVJ9jcsZ7RIbCU0702bA5NLoRh6AXxE54DBAgMHg0sjZAxIhvjuzJA+OTNy4tHRI5MDNgMfsIvfoPDwm2gwDA38/C7Ze2oCGcyNnR46NSaJGe74pJokdMy7UAedE3vxP3dprDQlU3x4bgcSRBIZLZDeI3GfazNaFJQ6KHOQZ4OmD1idgm6SOPgH7FJ+1LbJPeG9f9xGXRPnR53vVbS7DctkTnGBwvxTte/dadr+Y/t04Zg1JksF+TeJ+RuR+/Y7IGcwTIvc1Prvhdfqo1XOjkIBx6Z59AyRcJMpccuR7kzj1+wPbPRJT2pi/cXBJHSTFzIiBffHJdX3U2ov2+Estu7jEhyM/m1lOPr/hc0+KfFCBRLw/xkiSrmO43MVlRweBvAR1XWqPK8cCzQyJ+/FjoSRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRJkiRtsP8DSAJ0ZRAbpzkAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADgAAAAYCAYAAACvKj4oAAACxklEQVR4Xu2XWajOURTFl3nK8IDMQzIl4tEUiTxRhjI9iHhBRCmUKSFziuQFIRKJKFMSUvJASEjpZnjwZAohsdZd5/Qdx5dy63K/61v1q3v2/s7//9/77LPPuUBZZZVV1l/QZPKdfCOPyCXyPti+kpvkavDLNtzTSkdnyUrSMrFdhIPpmdgGkI+kdWKr8WpBzmW2xnAgTzK7dD831HTNItMz2xh49XZn9iZw+ZaUVIKNMtt6OEDtzVQNSd/MVpK6AQfYKnfUBjWHO+et3BE0Ft6bR3NHkOY/Jh1zRxGNIr1yY3VrHLx6G3NHoj1kQW4Mqkvmkjq5o4ju4R8cOTvhAEfnjkQPyMDc+IdqA5+1DXJHdesO+QQfFcXUjrwjy8hauKvWD75JZB9ZGsZR6tSr4K7cHm5iWr2X8Pw+4XdqYCfINnKKDIJLWPMOkS3kGJka7MvJ8cqZrpiHpG0YF1U3ePV+dxRMIbdRuBQ8I13hI2QOXJ4KMqo3/FGS9q2OIGkDfLmI6kRekH5hPIGcgRPZhXwmPcgV+D3z4cRUhN8rOZr/i1QqCkgoowpQPA22zoWfVmoXmRf+lu8DvNpqLuq6F+CPi9IxpFLUx6bHjq5/I5PxJnIkGesZd+F3KKl50mVfQraGsRJ7suCuuvTSmOWFcImoLNRcOpBX8O0olkp3MoSsg0tfSWhG3sKJ0bWvHrlGZoc50ma4VCUldXXii7oMd2LpAFlRcFVNWu3nyfg8mUh2wB+9GG5SyvhQ+OVv4ACaws1J+3UYuQ5Le1O2/SjcqBS0AlZVSLoextJOVQEfR3q2tkoMtsrSEaLNHrUXbgaxZKeR02RNGCshaijaR4fhlZT0QSq5mWREsGl/KWEKWM+MNyYl5zWcwFxqMkqMyv8L/Nxao/5kcPh7EfzvXK2SOvJ2eO+rq4//2V36UkBqPAfJjMz3/+gHLL2GwzAkm34AAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHkAAAAYCAYAAADeUlK2AAAEtElEQVR4Xu2ZZ6hdRRSFl733XmKCBbtgR0WMEtGgsWBDI0ZFEQtix957SRQ1xBZ7wUSxYgWJYsE/lggqQf1hQVEQCSoooutjz3Anw7svktx38T3ng8U7Z885c2dm79kzc57UaDQajUaj0egrh1p/W39Zn1mvWXOT7U/rPWtWKse2e7zWGE68YF1irVTYXlU4dJPCto31m7V6YWsMA1a0XqpsSyucOaeyw+za0Pjvc5x1VGXbWzGL76zsyyhSeWOYQTpeqrJdo3Aya3XJktbmla0xTHlb4eSV64LGyGAFxY76/bpgCGHJWKI2LgC9qqdXMJafW+vVBeYg60trWl3QDyYoZvF1dcEQsbbiuLawzulVPb1kUetEa5G6IPGwdXRt7Ae3KZw8ri4YIg6xXq6NC0Cv6ukXOP4na0xl7wsfWL8rjlEDQQq6xZpq3WttmOxsyGamsmesba1NrUes6dZp1nnWG9aO6Z3nra+tT9J1hmfZ2d9uTUy2Pa3HrcesC60zFXVDt3oGYnFFliIgTrautF601lcEyoPWFdb9irroAxxgPW1NUbSD/cp21o3WjPQM/bs7XVMX/T433cNqitl7h3WP9VVRxu/z7vWKNjD+g7WH52n7pdapyfavGKOYxd2OSUTf6+oM/MfWEYof/MbaMtkPVjTofGtdRdDslMrIFDgo85Y1trjnHRoPW1g3W4tZ9yUb6e1N6zDrw2SDup5ucDzcWfEVLx8d+RB0k3VBss1WOJF206d9rU+t5dLzkxUOvdrazPoi2VnqCHCOmicoUjWOBlI3+5x8YqEOHA7rWO8o1m6eIwBYfrq1Bx6ytra2UnyNHJQ1FE5F3yqcjNgUYBvVeVT7KJxJQ0puUMywDE7+yFrTOlDzfmzBQdiAhs9V5wjHFzfumR0MIBGKjd/Lm5dbFU4pqesZDIJueetXdZ4na5CV6CuzrK4fBzDrMziILENwn5XugSC4TJHtaNMrirEA+syY5vWZYDgpXV9lvat4l5m5W7J3aw/cpfAXWYkg6RnMsBx9JTju+OIeJ5G2gb+kV+Bz6C+KQV5FMUNy1ljL2tX6Lt13g9kwNl0T7VDXMz/20LzZigE+Nl2TnfbqFGlZRdBvXNh4Pgcqx828f5lk7ZCuCaYfFF8UCXYcSeoFgvZnxVJHH1guyiAqqdsDBBABdoois5LtegaOzOkH6Nx4xXqRUx+OxOlEM+CUXdL1MYqO0mjeIx1dq5hRF1mjrR8V6yawrp+hSElzFBHLP0lIhwxOXovqeuYHqZY9BbAkkOpZEqj/D0X9JaTjnEnYG5SBzuzcQLGGktEyLEksTSxnzEz6wUcm2F+xHm+vGFPWYjICcDpgRvN73dqDY89J12dbpxdlCw0RmDcCpBA6QPrZSLGRIdWQhvJXMQaudNp+io0XZ0Pew4nPKTrKQMFE6wGFE3AcKZD6cQSDyGaL90mvZTDU9QzGU4qZTB9I/2yIgOArZ3iGTdeTitRIQDO7M7Q3Ly1kp8yR1rPW5el+VUXqpQ84lM0bKZdZycSgXrLeo+r8l69be5gsbOjImCw1jPP/Dgbh4gF0eCr/Xu0/aSMajiCk/sYIhc3QE4qZTDptNEYG/wCnI/V3W9oiYwAAAABJRU5ErkJggg==>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADMAAAAYCAYAAABXysXfAAAChUlEQVR4Xu2WSaiPURjGn8zKlCGzbkmGpGTBRoYoQilk2BiisKAslKkuhQWFMmyQIlOxMESmQiKKBQulJBIrFsJC4nk879c9nf637v3fu/hu/k/9uud73/P/7nnPec/7fkBNNdX032sh+UN+k9fkNvkWtl/kCbkfftkm+2fl1DWyg/RMbLfghY9IbOPID9I3sZVKPciNzNYFXvSbzC69zA1l0kqyLLPNhE/lSGbvCqdgaaU06pzZdsPB6C6l6kRGZ7bS6xEcTK/c0dbUHa5gT3NHK0gp3TE3VqHhZEZurKR58KnszR0t1AC43LdGMIfJ1txYSYfgYJoUeTO0gNzMjVXqOZrY616Qn3B5riT1ohPw7pwly8OuFLqIhk1YROpjfJV8IK9i3AE+eQW3juwi18kQMopsIZf//RJoRx7CLWQxeQCvT1VVz42qDj6VxsqvFnGPrInn3uQrvEuTyBmyJHwXknmSFjQ1xir9E+Evi6ItqGnvIxvgiln0MzVqbUShWWh8fegHO8VHOBjxNmxDG6ZiDvxiBSUpGM0dT9qTT6RP+N6TsTFWVdR9KVrAINKNfE9s6mnH4f+3iewP+ypyLsaSAlbgLZb6z6nkeS55FuPp5E6M68gXOGilR7qb/ePvlMQmPSYrYnwXfp+kADeioU0UJ6xCos2sWtqlY8mzPoOUBtLqxLeWXCGzyQT4DuyBT2FbzNlMjsZ4DLxIna70jgyGm7QyRCmp6qX7o/uiLxGlp+5X1dLLdYHr4cs/P/ENhBck3074Ah8Mn9JQwWkzhoXtEnwyShnNK9JT2k5OwpX1ADlNpoVP4/VwgSmNPqPEX9/N0UhU/iJvc1IlOw+fzNLMV1Ohv6ydfR1iFWR9AAAAAElFTkSuQmCC>