# **Optimisation de la Fenêtre de Contexte par le Masking d'Observations dans les Écosystèmes de l'Agentic AI et du Model Context Protocol**

L'essor des agents autonomes fondés sur les grands modèles de langage (LLM) a transformé le paradigme de l'ingénierie logicielle, passant de simples assistants de complétion de code à des entités capables de raisonner, de planifier et d'interagir avec des environnements complexes via des outils. Cependant, cette autonomie repose sur une architecture itérative, souvent désignée sous le terme de boucle ReAct (Reason-Act), où chaque action génère une observation qui est ensuite réinjectée dans la fenêtre de contexte pour le tour suivant.1 Cette accumulation systématique de données, particulièrement les résultats d'outils ou « observations », crée une croissance linéaire de l'historique qui finit par saturer les capacités de traitement des modèles les plus performants. Il est observé que les observations environnementales constituent environ 84 % de la consommation de tokens dans une trajectoire d'agent typique.2 Sans une gestion proactive, cette prolifération entraîne non seulement une explosion des coûts opérationnels, mais également une dégradation de la performance cognitive du modèle, un phénomène documenté sous le nom de « perte au milieu » (lost-in-the-middle) ou « pourriture de contexte » (context rot).1

Le problème central identifié dans les extensions de type MCP (Model Context Protocol), telles que Cline, réside dans l'absence de mécanismes de filtrage local des observations. Cline, en tant que client MCP, orchestre des appels d'outils dont les résultats sont stockés intégralement dans l'historique de la conversation.5 Pour des tâches complexes nécessitant des dizaines de tours de parole, le coût des tokens d'entrée devient prohibitif, doublant parfois le prix par instance de résolution de bug sans gain de performance proportionnel.2 Les solutions traditionnelles basées sur la summarisation sémantique par le LLM lui-même, bien que populaires, introduisent une complexité supplémentaire et des risques de perte d'informations critiques.3 À l'inverse, des recherches récentes, notamment l'étude de JetBrains publiée en 2025, suggèrent qu'une stratégie plus simple de « masking d'observations » (observation masking) permet de réduire les coûts de plus de 52 % tout en égalant, voire dépassant, les taux de succès des méthodes de compression plus complexes.1

## **La Crise du Contexte dans les Flux de Travail Agentiques**

La gestion de la fenêtre de contexte est devenue le goulet d'étranglement critique de l'IA agentique. Contrairement à un chatbot classique, un agent comme Cline doit maintenir une connaissance précise de l'état du système de fichiers, des résultats des tests et de l'historique des modifications.6 Chaque fois qu'un agent lit un fichier volumineux ou exécute une commande shell générant des logs exhaustifs, ces données s'ancrent dans la mémoire de travail du modèle pour toute la durée de la tâche.10

### **Dynamique de l'Explosion de Tokens**

L'analyse des trajectoires d'agents sur des benchmarks industriels comme SWE-bench démontre une corrélation directe entre la longueur de la trajectoire et l'inefficacité économique. Dans un scénario sans gestion de contexte, le modèle est contraint de relire l'intégralité du préambule système et de l'historique des outils à chaque nouvelle prédiction.3 Pour une tâche de 50 tours, l'agent finit par payer 50 fois pour les mêmes données initiales, ce qui rend l'utilisation de modèles frontières comme Claude 3.5 Sonnet ou GPT-4o extrêmement coûteuse pour les développeurs individuels.3

| Stratégie de Gestion | Réduction des Coûts (%) | Impact sur le Taux de Résolution | Complexité d'Implémentation |
| :---- | :---- | :---- | :---- |
| Agent Brut (Baseline) | 0% | Baseline | Faible |
| Summarisation LLM | 50% \- 52% | Stable ou Déclin Léger | Élevée |
| Masking d'Observations | 52% \- 54% | Amélioration Légère | Modérée |
| AgentDiet (Réflexion) | 21% \- 36% | Stable | Élevée |

Le tableau ci-dessus synthétise les performances comparées des différentes approches de gestion de trajectoire. Il apparaît que le masking d'observations offre le meilleur compromis entre économie de tokens et maintien de la capacité de raisonnement.1

### **Phénoménologie de la Dégradation Cognitive**

L'impact de la saturation du contexte ne se limite pas aux coûts. La recherche indique que la capacité d'un LLM à suivre des instructions et à récupérer des informations spécifiques diminue drastiquement lorsque la fenêtre de contexte dépasse un certain seuil d'efficacité, souvent bien inférieur à la limite technique annoncée.3 Ce phénomène de « confusion de contexte » se manifeste par des erreurs où l'agent applique des contraintes issues d'une tâche précédente ou se laisse distraire par des informations non pertinentes (bruit) présentes dans les observations d'outils passées.14

Un exemple frappant est celui de la summarisation sémantique qui, en tentant de condenser les échecs de tests, finit par « lisser » la réalité technique. L'agent, lisant un résumé atténué, peut ne pas percevoir la gravité d'une erreur de segmentation ou d'une fuite de mémoire et persister dans une stratégie de résolution erronée, un effet connu sous le nom d'élongation de trajectoire.3

## **Fondements Théoriques du Masking d'Observations**

Le masking d'observations est une technique d'ingénierie de contexte qui consiste à remplacer les sorties d'outils volumineuses par des jetons de substitution (placeholders) ou des références compactes, tout en préservant l'intégralité du raisonnement interne (Thought) et des commandes émises (Action) de l'agent.16 Cette approche repose sur le postulat que l'utilité d'une observation brute décroît exponentiellement une fois qu'elle a été traitée par le modèle pour prendre une décision.15

### **Le Mécanisme de Substitution**

Dans une mise en œuvre standard, la fonction de masking identifie les observations plus anciennes qu'une fenêtre fixe ![][image1] et les remplace par un texte minimal tel que \[Observation omise pour des raisons de brièveté\] ou \`\`.17 Ce mécanisme permet de conserver la trace de l'existence de l'action, ce qui est crucial pour que l'agent comprenne où il se situe dans son plan de résolution, sans pour autant encombrer la mémoire de travail avec des données déjà analysées.3

L'efficacité du masking est particulièrement visible lors de l'utilisation de modèles comme Qwen3-Coder 480B. L'étude de JetBrains montre qu'un simple masking à ![][image2] (conservation des 10 dernières observations) permet non seulement de réduire les coûts de 52 %, mais augmente également le taux de résolution de 2,6 % par rapport à un agent brut.1 Cette amélioration s'explique par la réduction du bruit, permettant au modèle de focaliser son attention sur les éléments les plus récents et pertinents de l'environnement.1

### **Analyse de l'AgentDiet et de la Réduction de Trajectoire**

Au-delà du masking statique, des approches plus dynamiques comme AgentDiet proposent une réduction de trajectoire basée sur la réflexion.13 AgentDiet insère un module de réflexion après chaque étape de la boucle de l'agent pour identifier les informations inutiles, redondantes ou expirées.12 Par exemple, si un agent a listé un répertoire pour localiser un fichier et qu'il a maintenant ouvert ce fichier, la liste complète des fichiers du répertoire devient une information « expirée » qui peut être supprimée de la trajectoire sans dommage.13

Les évaluations montrent qu'AgentDiet peut réduire les tokens d'entrée de 39,9 % à 59,7 %, ce qui se traduit par une réduction du coût de calcul final de 21,1 % à 35,9 %.13 Cependant, contrairement au masking simple, cette méthode nécessite un appel supplémentaire au LLM pour la phase de réflexion, ce qui peut augmenter la latence par tour.13

## **Le Model Context Protocol (MCP) : Infrastructure et Opportunités**

Le Model Context Protocol (MCP) s'est imposé comme le standard ouvert pour connecter les agents IA à des sources de données et des outils externes.21 Son architecture client-serveur offre des points d'insertion idéaux pour implémenter des solutions locales de masking d'observations.

### **Rôle du Client MCP et Hooks de Middleware**

Dans l'écosystème MCP, le client (tel que Cline) gère la communication avec les serveurs via des transports comme stdio ou SSE.21 Chaque interaction avec un outil suit un cycle de requête-réponse JSON-RPC.21 C'est à ce niveau que le client peut agir en tant que middleware de filtrage.22

Le SDK TypeScript de MCP permet de définir des clients capables d'intercepter les résultats de callTool avant qu'ils ne soient transmis à l'interface utilisateur ou au moteur de l'agent.24 Une implémentation manuelle de masking peut être conçue en enveloppant l'appel à l'outil :

TypeScript

// Exemple conceptuel de hook client-side pour le masking  
async function callToolWithMasking(client: Client, name: string, args: any) {  
    const response \= await client.callTool({ name, arguments: args });  
      
    // Logique de filtrage local  
    if (response.content.some(c \=\> c.type \=== 'text' && c.text.length \> THRESHOLD)) {  
        const originalText \= response.content.text;  
        const maskedText \= \`\`;  
        return {...response, content: };  
    }  
    return response;  
}

Cette approche permet de transformer des résultats d'outils potentiellement massifs en métadonnées gérables, préservant ainsi la fenêtre de contexte pour le raisonnement logique.15

### **Échantillonnage (Sampling) et Contrôle de Contexte**

L'une des fonctionnalités les plus puissantes de MCP pour l'optimisation du contexte est le « sampling ».26 Le sampling permet aux serveurs de demander des complétions LLM via le client, lequel conserve le contrôle total sur les permissions et le contexte inclus.26 Le client peut décider d'inclure le contexte de « tous les serveurs », de « ce serveur uniquement » ou de « aucun », permettant une isolation stricte des données et une réduction drastique du « bruit » contextuel.26

De plus, le client peut modifier les prompts de système demandés par le serveur ou filtrer les résultats générés avant de les renvoyer au serveur.26 Ce mécanisme de « boucle de révision » (human-in-the-loop) agit comme un pare-feu contextuel, garantissant que seules les informations nécessaires circulent entre les composants du système.26

## **Analyse Comparative des Solutions Existantes : Cline vs Roo Code**

Le marché des assistants de codage IA pour VS Code est actuellement dominé par deux approches divergentes en matière de gestion de contexte : l'approche structurée de Cline et l'approche flexible de Roo Code.

### **Cline : Sécurité et Fragmentation du Contexte**

Cline se distingue par une séparation claire entre les modes « Plan » et « Act », et par une exigence de validation humaine à chaque étape cruciale.29 Sa gestion de contexte repose sur un algorithme de compaction et de troncature de l'historique qui intervient lorsque la limite de tokens est approchée.5

Toutefois, Cline souffre de lacunes importantes signalées par la communauté :

* **Limites de fichiers rigides :** Une limite de lecture de fichiers de 300 Ko est codée en dur, provoquant des erreurs irrécupérables si l'agent tente d'ouvrir accidentellement des fichiers binaires ou des logs massifs.10  
* **Explosion de tokens post-compaction :** Des utilisateurs rapportent que même après compaction, le contexte peut gonfler massivement si de nombreux onglets sont ouverts ou si l'indexation se déclenche de manière intempestive.5  
* **Absence de Masking d'Observations :** Bien que Cline utilise la compaction, il ne propose pas de masking granulaire des sorties d'outils passées, ce qui entraîne une perte de précision lors de la suppression de blocs entiers de l'historique.20

### **Roo Code : Personnalisation et Instabilité Mémoire**

Roo Code, un fork de Cline, a introduit des innovations telles que les modes personnalisés et une indexation plus agressive du codebase.11 Roo Code utilise un mécanisme de « condensation de contexte » pour gérer les grandes quantités d'informations.33

Cependant, cette complexité accrue s'accompagne de problèmes de stabilité. Des rapports indiquent que Roo Code peut consommer des quantités excessives de mémoire, provoquant des plantages de l'extension lorsque la taille de la conversation dépasse 100 Mo.33 Comparativement, Cline est souvent perçu comme plus économe en tokens pour des tâches identiques, réduisant le contexte à environ 50-70 % de la limite pour maintenir des coûts d'appel API bas.33

| Caractéristique | Cline | Roo Code |
| :---- | :---- | :---- |
| Gestion du Contexte | Troncature simple / Compaction | Condensation / Tâches "Boomerang" |
| Stabilité | Élevée (Moins de plantages) | Modérée (Problèmes de mémoire à \>100Mo) |
| Efficacité des Tokens | Optimisée pour Anthropic | Plus verbeuse / Consommation élevée |
| Support MCP | Standard | Avancé (Marketplace de modes) |

## **Implémentations Manuelles et Stratégies de Développement**

Pour combler le fossé entre les besoins des développeurs et les capacités actuelles de Cline, plusieurs stratégies d'implémentation de masking d'observations peuvent être envisagées au niveau du code source TypeScript de l'extension.

### **Architecture de "Smart Filtering"**

L'implémentation d'un agent de raffinage de prompt (Prompt Refiner Agent) a été proposée au sein de la communauté Cline pour agir comme un filtre intelligent avant l'appel à l'API principale.20 Cet agent intermédiaire traiterait le contexte brut (historique complet, règles .clinerules, détails de l'environnement) pour générer un prompt condensé et focalisé.20

Les étapes clés d'une telle implémentation incluraient :

1. **Collecte du contexte total :** Rassemblement de tous les éléments (système, historique, fichiers mentionnés).20  
2. **Invocation du Refiner :** Utilisation d'un modèle rapide et peu coûteux (ex: GPT-4o-mini ou Gemini 1.5 Flash) pour identifier les observations à masquer.20  
3. **Application du Masking :** Remplacement des blocs d'observations identifiés par des jetons de substitution contenant des métadonnées structurelles.17  
4. **Appel au LLM Principal :** Envoi du prompt optimisé pour l'exécution de la tâche.20

### **Règles d'Exemption et Seuils de Masking**

Un système de masking efficace ne doit pas être appliqué de manière uniforme. Des règles d'exemption critiques sont nécessaires pour garantir que l'agent ne perde pas les informations vitales à sa progression.15

* **Règle des N tours :** Les observations des ![][image3] derniers tours (généralement ![][image4] à ![][image5]) doivent toujours être conservées intégralement pour maintenir la cohérence immédiate.15  
* **Exemption des Erreurs :** Toute observation contenant des messages d'erreur critiques (ex: stack traces, erreurs de compilation) doit rester visible jusqu'à ce que l'agent ait émis une action corrective validée.1  
* **Troncature 20/80 :** Inspirée par les outils de Google Gemini CLI, une stratégie consiste à conserver les premiers 20 % et les derniers 80 % d'une sortie volumineuse, privilégiant ainsi la fin du message où se trouvent généralement les résultats finaux et les erreurs.34

### **Gestion de l'État Scoped au Workspace**

Une autre opportunité d'optimisation réside dans la refonte du stockage de l'état de l'extension. Actuellement, Cline partage son état globalement, ce qui peut polluer le contexte lors du passage d'un projet à un autre.35 Le passage à un stockage « workspace-scoped » via l'API workspaceState de VS Code permettrait de ségréguer l'historique des tâches et les instructions spécifiques au projet, réduisant ainsi la charge cognitive globale imposée au modèle.35

## **Études de Cas Techniques : Problèmes de Tooling et Résolutions**

L'analyse des issues GitHub de Cline et de ses forks révèle des défis techniques concrets liés à la gestion des observations qui pourraient être résolus par un masking intelligent.

### **Le Problème des ToolResult Orphelins sur Bedrock**

Un bug critique identifié sur le modèle Claude 3.5 Sonnet via Amazon Bedrock survient lorsque le nombre de blocs toolResult dépasse le nombre de blocs toolUse du tour précédent.36 Cela arrive souvent lors de changements de mode ou d'interruptions d'exécution. Un mécanisme de validation au niveau du client MCP, capable de détecter et de convertir ces blocs orphelins en texte brut (une forme de masking fonctionnel), est nécessaire pour éviter l'échec total de la conversation.36

### **Conflits de Noms et Réservations API**

Lors de l'utilisation de Claude Code OAuth, certains noms d'outils comme read\_file sont réservés par l'API d'Anthropic, provoquant des échecs de requête si l'extension tente d'exposer ses propres outils sous ces noms.37 La solution adoptée consiste à préfixer dynamiquement les noms des outils (ex: read\_file devient roo\_read\_file).37 Ce type de transformation de métadonnées est un précurseur nécessaire à tout système de masking complexe, assurant que les références de masking restent uniques et valides au sein du protocole.

### **Fusion de Messages pour la Compatibilité OpenAI**

Pour les fournisseurs compatibles OpenAI (vLLM, Ollama), la séquence stricte assistant \-\> tool \-\> user est souvent imposée. Roo Code a dû implémenter une option mergeToolResultText pour fusionner les textes de feedback (comme les détails d'environnement) directement dans le dernier message d'outil afin d'éviter la création de messages utilisateurs séparés qui violeraient le protocole de certains modèles.38 Cette technique de fusion peut être vue comme une forme de compactage structurel du contexte, réduisant le nombre total de messages dans la fenêtre.38

## **Optimisation de la Performance et Expérience Développeur**

Au-delà de la réduction pure du nombre de tokens, l'ingénierie de contexte vise à améliorer l'efficacité temporelle et la stabilité des systèmes agentiques.

### **Latence et Préremplissage du Cache KV**

La latence d'un agent est fortement influencée par la taille de son contexte, car le modèle doit effectuer une phase de préremplissage (prefill) avant de générer le premier token.39 Le masking d'observations, en maintenant la fenêtre de contexte à une taille constante et réduite, maximise le taux de réussite du cache KV (Key-Value).40

Pour optimiser ce cache, il est recommandé de :

* **Maintenir un préambule stable :** Placer les instructions système et les définitions d'outils au tout début du prompt et ne jamais les modifier.40  
* **Éviter les variables dynamiques en début de prompt :** L'insertion d'horodatages précis à la seconde au début du prompt invalide l'intégralité du cache pour chaque appel.40  
* **Utiliser des points d'arrêt de cache explicites :** Certains fournisseurs permettent de marquer des sections du contexte comme persistantes, ce qui est idéal pour les bibliothèques de définitions d'outils MCP.40

### **Stratégies d'Architecture au-delà du Prompt**

Parfois, la meilleure façon de gérer le contexte n'est pas de le compresser, mais de modifier l'architecture de l'agent lui-même. Anthropic suggère deux patterns majeurs :

1. **Récupération Juste-à-Temps (JIT) :** Au lieu de charger tous les fichiers dans le contexte, donner à l'agent des outils pour explorer l'environnement (ex: ls, grep) et ne lire que les fragments nécessaires.3  
2. **Architectures de Sous-Agents :** Déléguer des tâches complexes à des sous-agents spécialisés qui travaillent dans une fenêtre de contexte vierge et ne renvoient qu'un résumé succinct au parent.3 Cette isolation empêche la "pollution" de la mémoire de l'agent principal par les détails de bas niveau d'une sous-tâche exploratoire.3

| Technique d'Optimisation | Cible | Bénéfice Principal |
| :---- | :---- | :---- |
| Masking d'Observations | Historique des outils | Réduction des coûts d'entrée |
| Cache KV stable | Preremplissage (Prefill) | Réduction drastique de la latence |
| Sous-Agents | Complexité de la tâche | Isolation et focus cognitif |
| JIT Retrieval | Volume de données | Évite le "Context Bloat" initial |

## **Vers un Framework de Gestion Autonome du Contexte**

L'avenir de l'IA agentique réside dans le développement de mécanismes de gestion de contexte autonomes capables de compresser et de curer l'historique des interactions de manière proactive.42

### **Vers le "Context-Aware Decoding"**

Une approche avancée, utilisée par des agents comme Manus, consiste à gérer la disponibilité des outils non pas en les supprimant du prompt, mais en masquant les logits de tokens pendant le décodage.40 Cela permet d'empêcher l'agent d'appeler des outils qui ne sont plus pertinents dans l'état actuel de la tâche, sans pour autant perdre l'historique de leur existence.40 Cette forme de masking algorithmique représente l'évolution ultime du masking d'observations, passant d'une gestion de texte à une gestion de probabilités.

### **Recommandations pour le Développement de Forks Cline**

Pour les développeurs souhaitant implémenter un masking d'observations efficace dans un fork de Cline ou une extension similaire, la feuille de route suivante est préconisée :

1. **Implémenter des Hooks de Middleware MCP :** Utiliser le SDK TypeScript pour intercepter les réponses des serveurs MCP. Si une observation dépasse un certain seuil (ex: 2000 tokens), elle doit être stockée dans une base de données locale (RefID) et remplacée par un placeholder enrichi de métadonnées.20  
2. **Développer un "Episodic Memory Manager" :** Créer un module capable de suivre l'importance relative de chaque tour de parole. Les observations liées à des succès mineurs peuvent être masquées rapidement, tandis que celles liées à des échecs ou des décisions architecturales doivent être conservées plus longtemps.3  
3. **Intégrer des Visualiseurs de Tokens :** Fournir aux utilisateurs une transparence totale sur la consommation de tokens, décomposée par sections (système, outils, historique, observations masquées). Cela permet aux développeurs de comprendre la "pression contextuelle" et d'ajuster leurs instructions en conséquence.3  
4. **Adopter une Approche Hybride :** Utiliser le masking d'observations par défaut pour l'économie, et ne déclencher la summarisation LLM qu'en dernier recours lorsque la fenêtre de contexte est critiquement pleine malgré le masking.3

En conclusion, bien que les agents comme Cline aient ouvert la voie à l'ingénierie logicielle assistée par IA, leur viabilité économique et technique à grande échelle dépend de leur capacité à gérer intelligemment la mémoire de travail. Le masking d'observations, soutenu par la rigueur du Model Context Protocol et les découvertes empiriques de 2025, s'impose comme la pierre angulaire de cette nouvelle ère de l'ingénierie de contexte.3 En privilégiant la simplicité et la fidélité de la trace d'action sur la complexité sémantique, les développeurs peuvent bâtir des agents plus rapides, moins coûteux et fondamentalement plus capables de résoudre les problèmes complexes du monde réel.

#### **Sources des citations**

1. Simple Observation Masking Is as Efficient as LLM Summarization, consulté le février 26, 2026, [https://arxiv.org/pdf/2508.21433?](https://arxiv.org/pdf/2508.21433)  
2. Simple Observation Masking Is as Efficient as LLM Summarization, consulté le février 26, 2026, [https://arxiv.org/pdf/2508.21433](https://arxiv.org/pdf/2508.21433)  
3. Context Length Management in LLM Applications \- Medium, consulté le février 26, 2026, [https://medium.com/softtechas/context-length-management-in-llm-applications-89bfc210489f](https://medium.com/softtechas/context-length-management-in-llm-applications-89bfc210489f)  
4. Context windows \- Claude API Docs, consulté le février 26, 2026, [https://platform.claude.com/docs/en/build-with-claude/context-windows](https://platform.claude.com/docs/en/build-with-claude/context-windows)  
5. Cline reporting context usage vs actual context usage mismatch., consulté le février 26, 2026, [https://github.com/cline/cline/issues/8857](https://github.com/cline/cline/issues/8857)  
6. VS Code extension Cline: AI-automated scripting and CLI ... \- 4sysops, consulté le février 26, 2026, [https://4sysops.com/archives/vs-code-extension-cline-ai-automated-scripting-and-cli-administration-a-powershell-example/](https://4sysops.com/archives/vs-code-extension-cline-ai-automated-scripting-and-cli-administration-a-powershell-example/)  
7. Simple Observation Masking Is as Efficient as LLM Summarization, consulté le février 26, 2026, [https://arxiv.org/html/2508.21433v1](https://arxiv.org/html/2508.21433v1)  
8. JetBrains-Research/the-complexity-trap · Datasets at Hugging Face, consulté le février 26, 2026, [https://huggingface.co/datasets/JetBrains-Research/the-complexity-trap](https://huggingface.co/datasets/JetBrains-Research/the-complexity-trap)  
9. MCP best practices and Live Debugger boost developer experience, consulté le février 26, 2026, [https://www.dynatrace.com/news/blog/mcp-best-practices-cline-live-debugger-developer-experience/](https://www.dynatrace.com/news/blog/mcp-best-practices-cline-live-debugger-developer-experience/)  
10. Improve Context Window Management and Large File Handling ..., consulté le février 26, 2026, [https://github.com/cline/cline/issues/4389](https://github.com/cline/cline/issues/4389)  
11. cline vs cursor vs roo code vs claude code \- GitHub, consulté le février 26, 2026, [https://github.com/cline/cline/issues/9174](https://github.com/cline/cline/issues/9174)  
12. Improving the Efficiency of LLM Agent Systems through Trajectory, consulté le février 26, 2026, [https://arxiv.org/pdf/2509.23586](https://arxiv.org/pdf/2509.23586)  
13. Improving the Efficiency of LLM Agent Systems through Trajectory, consulté le février 26, 2026, [https://arxiv.org/html/2509.23586v1](https://arxiv.org/html/2509.23586v1)  
14. context-degradation | Skills Marketp... \- LobeHub, consulté le février 26, 2026, [https://lobehub.com/ru/skills/panaversity-agentfactory-context-degradation](https://lobehub.com/ru/skills/panaversity-agentfactory-context-degradation)  
15. context-optimization | Skills Market... · LobeHub, consulté le février 26, 2026, [https://lobehub.com/ko/skills/panaversity-agentfactory-context-optimization](https://lobehub.com/ko/skills/panaversity-agentfactory-context-optimization)  
16. Cutting Through the Noise: Smarter Context Management for LLM, consulté le février 26, 2026, [https://blog.jetbrains.com/research/2025/12/efficient-context-management/](https://blog.jetbrains.com/research/2025/12/efficient-context-management/)  
17. Why Simple Observation Masking Beats LLM Summarisation \- Medium, consulté le février 26, 2026, [https://medium.com/@balajibal/agent-context-management-why-simple-observation-masking-beats-llm-summarisation-4961cb67be89](https://medium.com/@balajibal/agent-context-management-why-simple-observation-masking-beats-llm-summarisation-4961cb67be89)  
18. Overview of the context management strategies evaluated in, consulté le février 26, 2026, [https://www.researchgate.net/figure/Overview-of-the-context-management-strategies-evaluated-in-our-work-Box-heights-indicate\_fig2\_395126021](https://www.researchgate.net/figure/Overview-of-the-context-management-strategies-evaluated-in-our-work-Box-heights-indicate_fig2_395126021)  
19. Improving the Efficiency of LLM Agent Systems through Trajectory, consulté le février 26, 2026, [https://chatpaper.com/chatpaper/paper/193196](https://chatpaper.com/chatpaper/paper/193196)  
20. Implement Prompt Refiner Agent \#2552 \- cline cline \- GitHub, consulté le février 26, 2026, [https://github.com/cline/cline/discussions/2552](https://github.com/cline/cline/discussions/2552)  
21. Model Context Protocol (MCP) Client Development Guide \- GitHub, consulté le février 26, 2026, [https://github.com/cyanheads/model-context-protocol-resources/blob/main/guides/mcp-client-development-guide.md](https://github.com/cyanheads/model-context-protocol-resources/blob/main/guides/mcp-client-development-guide.md)  
22. Code execution with MCP: building more efficient AI agents \\ Anthropic, consulté le février 26, 2026, [https://www.anthropic.com/engineering/code-execution-with-mcp](https://www.anthropic.com/engineering/code-execution-with-mcp)  
23. @redocly/mcp-typescript-sdk \- npm, consulté le février 26, 2026, [https://www.npmjs.com/package/@redocly/mcp-typescript-sdk](https://www.npmjs.com/package/@redocly/mcp-typescript-sdk)  
24. MCP Tracing (TypeScript) \- Phoenix \- Arize AI, consulté le février 26, 2026, [https://arize.com/docs/phoenix/integrations/typescript/mcp/mcp-tracing-typescript](https://arize.com/docs/phoenix/integrations/typescript/mcp/mcp-tracing-typescript)  
25. typescript-sdk/docs/client.md at main \- GitHub, consulté le février 26, 2026, [https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/client.md](https://github.com/modelcontextprotocol/typescript-sdk/blob/main/docs/client.md)  
26. Sampling \- Model Context Protocol, consulté le février 26, 2026, [https://modelcontextprotocol.io/legacy/concepts/sampling](https://modelcontextprotocol.io/legacy/concepts/sampling)  
27. Understanding MCP clients \- Model Context Protocol, consulté le février 26, 2026, [https://modelcontextprotocol.io/docs/learn/client-concepts](https://modelcontextprotocol.io/docs/learn/client-concepts)  
28. Sampling \- Model Context Protocol, consulté le février 26, 2026, [https://modelcontextprotocol.io/specification/2025-06-18/client/sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)  
29. Roo Code vs Cline: Best AI Coding Agents for VS Code (2026) \- Qodo, consulté le février 26, 2026, [https://www.qodo.ai/blog/roo-code-vs-cline/](https://www.qodo.ai/blog/roo-code-vs-cline/)  
30. \[Developing with Alpha\] From Cursor to Settling on VS Code's Cline, consulté le février 26, 2026, [https://medium.com/@fstory97/developing-with-alpha-from-cursor-to-settling-on-vs-codes-cline-218be9b4bae2](https://medium.com/@fstory97/developing-with-alpha-from-cursor-to-settling-on-vs-codes-cline-218be9b4bae2)  
31. Context Window and Response Truncation Issue (Claude Code), consulté le février 26, 2026, [https://github.com/Kilo-Org/kilocode/issues/1224](https://github.com/Kilo-Org/kilocode/issues/1224)  
32. 5 Must-Know Roo Code Features That Make It Better Than Cline, consulté le février 26, 2026, [https://www.youtube.com/watch?v=rg\_g3BPv4uQ](https://www.youtube.com/watch?v=rg_g3BPv4uQ)  
33. Significant observations of Roo vs Cline (Token Usage, Task ..., consulté le février 26, 2026, [https://github.com/RooVetGit/Roo-Code/issues/2700](https://github.com/RooVetGit/Roo-Code/issues/2700)  
34. \[Preview\] New Feature: Automatic Shell Output Truncation \#8297, consulté le février 26, 2026, [https://github.com/google-gemini/gemini-cli/discussions/8297](https://github.com/google-gemini/gemini-cli/discussions/8297)  
35. Cline Workspace threads and not global \#2550 \- GitHub, consulté le février 26, 2026, [https://github.com/cline/cline/discussions/2550](https://github.com/cline/cline/discussions/2550)  
36. \[BUG\] Unknown API error \#10216 \- RooCodeInc/Roo-Code \- GitHub, consulté le février 26, 2026, [https://github.com/RooCodeInc/Roo-Code/issues/10216](https://github.com/RooCodeInc/Roo-Code/issues/10216)  
37. \[BUG\] Claude Code OAuth API fails when a tool is named read\_file, consulté le février 26, 2026, [https://github.com/RooCodeInc/Roo-Code/issues/10867](https://github.com/RooCodeInc/Roo-Code/issues/10867)  
38. \[BUG\] Local vllm devstral2 \-\> OpenAI completion error \#10684, consulté le février 26, 2026, [https://github.com/RooCodeInc/Roo-Code/issues/10684](https://github.com/RooCodeInc/Roo-Code/issues/10684)  
39. Monitor your MCP server | Speakeasy, consulté le février 26, 2026, [https://www.speakeasy.com/mcp/monitoring-mcp-servers](https://www.speakeasy.com/mcp/monitoring-mcp-servers)  
40. Context Engineering for AI Agents: Lessons from Building Manus, consulté le février 26, 2026, [https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)  
41. Agent Skills for Context Engineering Are Here — Ready for Claude, consulté le février 26, 2026, [https://medium.com/@gbx1220max/agent-skills-for-context-engineering-are-here-ready-for-claude-code-codex-garnering-2-3k-00d720ec55bd](https://medium.com/@gbx1220max/agent-skills-for-context-engineering-are-here-ready-for-claude-code-codex-garnering-2-3k-00d720ec55bd)  
42. Awesome Issue Resolution \- GitHub Pages, consulté le février 26, 2026, [https://deepsoftwareanalytics.github.io/Awesome-Issue-Resolution/](https://deepsoftwareanalytics.github.io/Awesome-Issue-Resolution/)  
43. Deep Dive into Context Engineering for Agents \- Galileo AI, consulté le février 26, 2026, [https://galileo.ai/blog/context-engineering-for-agents](https://galileo.ai/blog/context-engineering-for-agents)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABUAAAAYCAYAAAAVibZIAAABOklEQVR4Xu2TPSwFQRSFT/wVXhAtNSUFFYWSoBKJaESheAWFkqDRCBKJQuu1Co1WopAgNFqlkGipFEQ415l5mZkdOoVkv+TL7sy5M29n9z6g5F/STy/pO/2kD3FcYBKqM+/oQRzHHNILqLglyTyddBWq2UmyLLd0BVrQk2SeWboG1YwlWYE+WqMz0ILRKBVTtJue0VfaGsdFlukcHYA2rcYx2ui0u77R0zjOc0K7aAe06VYcf7+WRjoO5etxXKSZXgXjJ3oUjOehExjb0KbD9fQHRuhuMD6nN+6+QheDzH78hTYFc1k2od7z1Oizu1+ATmK0Q7187Ma/cg0t8GxAR7ROsK7wTLj5pWAuyyC9hz6Cx7ogt9j+OTbfm8zXsc3sCT+gQvs4/hUMQS3T4MZ79NHV+dp9l5WU/BVfKrw/RABl4xEAAAAASUVORK5CYII=>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAEIAAAAYCAYAAABOQSt5AAACZElEQVR4Xu2WTYiNURjH/z7zETILySysWFhQQ5FZSPkKpaRkIwvTWIzyXSMUNkKUJErNFSULG0vKQj4iHzXyURL5ntWwsTBp5v+8zzn3nvPc977dZuEl51e/5r7P/9x37vt0znkPkEgk/gOm0BZbdIymR+ht+oSepOOjEf84I+gs2kFf0l1xXOUqvQJtyDh6A9qUXObR+3SADtIPcVzHWug48TU9F8d/hGv0Lr0M/R15jVgHzaYFtTmutjCo1dFD70EHjjWZZyrdDx1zwmRlsAiNG3GJ9pmazIzf0GdoyDPaDb2xTLs8NtED0DGrTFYGRY3opa9skfTTm7bomUsrdCP0xiujVFlPW6Fr7CedEMelUNSI79BmWL7Rt7bo2Uk30/nQG2+LY0yiG9zfX/RWHDdkOmr7SbOuyL7ZHEWNkHpeIz7TT7bokd10BvRVJDc4FsfZkhlFV0Pzg3FcGkWNkFmb1whpwjtbFMbQB8H1F+iu7NkCnSnCceg/bq+m5eIbsdsG0Lffc1skX6FnijqWQA8anjv0kfs8kXYFmTRM1p7svn8DRY14St/YIvmBBkv7KPRs4KlAd1ZhK3TGCJOhZ43r7roZhrNHLMu+2Ry+EXtsQC6i9hwe2eBlvF36GQ+hD+k5BB0sbxB5m3jWuPr2oFY2vhF7bUCWQ7OZQU0OUlJrC2oZC+h76EbokbdH3gPLCVLqs029TJZCf9NhGzhkyZ8KruUkeiG4zhogM0FOWXIj2SD98lgMXUMj3fVp+tGN82PPuKwsdtAXqP1+8TE9Hw6CPkMnPQtdKvtcLZFIJBKJxPAYAkiJnfh49N4cAAAAAElFTkSuQmCC>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAYCAYAAAD3Va0xAAABBElEQVR4XmNgGAUDBqyAeDcQ3wfi/0B8AlUaDHYA8W8GiPwzIG5ElUYFO4H4AQNEsRmqFBgUAfF8dEF0wA3E14E4gQFi0HoUWQiYAsRO6ILowA2IJwExGwPCVerICoDgFANEHi/oBuIAKLuYAWIQyGAYkAfirUh8nOAMEPNB2TxA/AaIPwGxAFQsjQESRniBOBAfQhNrY4C4CuQ6EFgJxAYIaewgCohr0MQkgPgbED8FYl4gvoEqjR3MYYCkJXQwgwHiqsVQTBBcA2IWdEEg0GCAGATCiWhyGMALiM8DMSO6BBSsZoAYJI0uAQM2DJCYgtn4AIjtkBVAgSUQX0IXHAWjAAgA8tMw5+vmET0AAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAYCAYAAABa1LWYAAABzElEQVR4Xu2VTShFQRiGPyUpP7EQZSFKpJQoRUISJQtrpdiwJwtlw0LJRrKwIMpComwoUhZWEvkN2bgboiykWJB4v/PNuDNzkauc7q3z1NM95/3mdOfMmR+igICAKEmDc/ASrsIpWGI2iEcWYIdxvwWfYL6RfVINN+EVfIc7dtljHb6S1G/gkF3+d3JI/vvUyPpVNmxkEWzAEEnDSrvk0Qtn3dAn+KXu4J6RDZD0ddTILFLgOewkabhiVYVJ2OCGPpIFk437JZK+1huZRROcgEkU/lpFZgOwS1KPBVrhC+xxCyZjsE1d95G8FL+kJg+uGfc/oed/NPKg/oZSuAwfSDYOnmHfwnM1XV2nwnv4CDNU1k2ypmIF3t734TGF+2iRDbedbIRkBPmrMYuwLFyOCXhmcR/nnNyjHQ46GU+hZ3hNMioXdtl3EkkGlX81BSQv9UZfTMNpkrPKhU9sfmhe+Vv+sqYavSe/Z5ykHa99TaHK2Ewj9zgjewQ0xRR+qMup+Q0PPPeDl4WmWWW8K1u0wAOY4BYU+izIdQs+UwFvYbm65zOLNzdeInW6UY0K9ZcIwVpdNKgi2WFigXp4BA/hCZyhyLM0ICAgICD++QCH4HKiiS1XVwAAAABJRU5ErkJggg==>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAWCAYAAAD5Jg1dAAAAxUlEQVR4XuXRPQtBYRjG8ZvBIBbZFcloNpBYKaMPoExmi6+AzcKofASbpKSMPgJlYMBgkvg/zov7nCwmg6t+w7nO1dN5Efl50mgioroCeur6lRIePgfk9cikjB322GCIjGdhx5w48pefUpQvhhN0McURfQTU5pUctkja1ymc0XYXdqJI+LoxLog7hTl+jhWCTkk6Yn2mllOEcMcVYacU63nNsKI6WSOrC7Fe6oSYLqsYyPtE8/tuaLgLlTpmWGCJmvf2P+YJP44j2u0MJQkAAAAASUVORK5CYII=>