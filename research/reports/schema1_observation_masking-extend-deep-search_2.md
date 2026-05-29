# Observation masking pour optimiser la fenêtre de contexte dans des hôtes MCP type Cline

## Problématique et cadrage technique

Les agents de développement “dans l’IDE” (ex. Cline) accumulent naturellement des traces d’exécution : messages, lectures de fichiers, sorties de terminal, résultats d’outils (tool outputs). Or, dans Cline, ces éléments comptent explicitement dans la fenêtre de contexte : la documentation explique que le contexte inclut *la conversation*, *les contenus de fichiers lus/partagés* et *les sorties d’outils* (commandes, etc.). citeturn30view1turn30view0 La place occupée par ces “observations” (au sens des boucles agentiques : raisonner → agir → observer) devient vite dominante, ce qui augmente les coûts (tokens) et détériore la qualité quand le contexte grossit (“lost in the middle” / dilution du signal). citeturn4view1turn5view0

Dans ce rapport, **observation masking** = **masquer/neutraliser les observations anciennes** (principalement les *tool_results* et sorties verbeuses) **sans resentir l’historique complet à chaque tour**, tout en conservant au maximum la logique d’action (tool_use) et la “raison” (messages de l’agent). Cette définition correspond à la formulation JetBrains : l’observation masking cible l’observation (3ᵉ partie du tour) et préserve l’action et le raisonnement. citeturn4view1turn5view0

Côté protocole, **MCP** standardise l’exposition de **tools** par des serveurs, que des clients/hôtes invoquent (architecture JSON-RPC). citeturn3search0turn3search2 Le schéma MCP rappelle aussi que la manière de “rendre” certains contenus (ex. ressources intégrées) dépend du client : *“It is up to the client how best to render…”* — ce qui ouvre la porte à des politiques locales d’inclusion/omission pour la partie “contexte envoyé au modèle”. citeturn3search16 Autrement dit, **l’observation masking n’est pas une fonctionnalité MCP “serveur”** : c’est une **décision de l’hôte** (Cline/Roo/Kilo/mcphost, etc.) au moment de construire la requête LLM.

## Résultats empiriques et littérature mondiale

### Étude JetBrains et papier “The Complexity Trap” (référence empirique la plus directement alignée)

JetBrains Research a publié un travail centré exactement sur le dilemme **observation masking vs summarization** pour agents de type Software Engineering, sur des trajectoires longues (jusqu’à ~250 tours) et sur un benchmark standard **SWE-bench Verified**. citeturn4view1turn5view0turn27search0 Le billet de synthèse JetBrains décrit trois stratégies comparées : (1) pas de gestion (raw agent), (2) **observation masking** via fenêtre glissante et placeholders (“some details omitted for brevity”), (3) summarization par LLM. citeturn4view1turn5view0

Points empiriques saillants (hautement “load-bearing” pour votre TL;DR) :

- **Les deux approches “efficiency-first” coupent les coûts de >50%** vs laisser croître le contexte sans intervention (raw). citeturn4view1turn5view0  
- Dans l’exemple le plus parlant (Qwen3-Coder 480B), **l’observation masking est ~52% moins cher** que le raw agent tout en maintenant, voire améliorant légèrement, le solve rate sur SWE-bench Verified. citeturn4view1turn5view0turn27search0  
- Le papier explique *pourquoi* ça marche particulièrement bien en SE : les **tokens d’observation dominent la trajectoire**, et viser cette composante donne un excellent ratio gain/coût/complexité. citeturn5view0  
- Effet secondaire important : **la summarization peut “allonger” les trajectoires** (agents qui continuent plus longtemps), ce qui peut dégrader l’efficacité globale malgré un contexte borné. citeturn4view1turn5view0  
- Coût caché : les appels de summarization peuvent représenter une portion non triviale du coût et ont peu de réutilisation de cache (car chaque résumé traite une tranche unique d’historique). citeturn4view1turn5view0  

JetBrains publie également un repo associé et mentionne fournir code/données pour reproductibilité. citeturn27search3turn5view1turn5view0

### Autres axes académiques pertinents (au-delà SE agents “classiques”)

La littérature récente se structure autour de trois familles, utiles pour positionner l’opportunité “MCP host” :

- **Pruning adaptatif côté agent** pour le code : *SWE-Pruner* propose un framework de pruning “self-adaptive” inspiré du “skim” humain, ciblé agents de code. citeturn1search31  
- **Réduction de trajectoire à l’inférence** : des travaux proposent de réduire la trajectoire pour diminuer le coût token (logique proche de votre objectif “sans summarization LLM”), mais parfois avec des heuristiques plus riches que “fenêtre N tours”. citeturn1search19  
- **Pruning côté modèle (token-level / attention)** : *Dynamic Context Pruning* vise à supprimer des tokens du contexte au niveau transformer (requiert fine-tuning), ce qui est conceptuellement intéressant mais moins directement applicable à une extension VS Code. citeturn1search3  
- **Pruning par sélection de lignes pertinentes** dans des observations structurées (ex. agent web + AxTree) : *FocusAgent* illustre un trimming guidé par objectif sur une observation massive. citeturn1search27  

En synthèse : votre cible (masquage local, déterministe, sans appel LLM) est **cohérente avec la conclusion empirique JetBrains** (“la solution la plus simple est parfois la meilleure”) tout en restant compatible avec des extensions ultérieures (hybride, adaptatif). citeturn4view1turn5view0

## Panorama des solutions existantes (Cline, forks, hôtes MCP) et ce qu’elles font réellement

### Cline : gestion de contexte existante surtout “truncate/condense”, pas un masking pur par tours

Cline documente plusieurs stratégies orientées utilisateur : **Memory Bank**, commandes **/smol** (compression), **/newtask** (handoff vers une nouvelle tâche), et **Auto-Compact** (compression automatique). citeturn30view0turn30view1 L’objectif est bien de “libérer de la place” dans le contexte, mais ces mécanismes reposent soit sur **résumés**, soit sur redémarrage/hand-off, pas sur du “masking observation-only”.

Côté code, Cline implémente une **gestion programmatique de troncature** dans `ContextManager.ts`. La logique clé est : si la requête précédente a consommé un total de tokens (in/out + cache) au-delà d’un seuil lié à `maxAllowedSize`, alors Cline choisit de retirer une portion de l’historique (moitié ou 3/4 selon cas) tout en gardant la première paire user/assistant, puis calcule une “deleted range” et applique des modifications persistées par `contextHistoryUpdates`. citeturn20view0

Deux détails sont critiques pour toute implémentation d’observation masking “MCP-safe” dans Cline :

- Cline a déjà une fonction qui **répare/garantit l’invariant tool_use → tool_result** (`ensureToolResultsFollowToolUse`) et ajoute même des tool_results “missing” si nécessaire. citeturn20view0  
- Cline prend aussi soin de supprimer des **tool_results orphelins** après certaines troncatures (pour ne pas casser l’ordre attendu). citeturn20view0  

Cela indique que l’équipe Cline a déjà rencontré les mêmes contraintes fondamentales que vous allez affronter en masking : **on ne peut pas casser la structure tool calling** juste pour économiser des tokens.

Enfin, les retours utilisateurs montrent que la compression/summarization peut être vécue comme une perte de contexte (“perd des éléments critiques”, “résumés de résumés”), ce qui renforce l’intérêt d’une alternative “masking simple”. citeturn11search3turn11search24

### Roo Code & Kilo Code : sliding window + summarization (et parfois “fresh start”), plus proches mais pas identiques à l’observation masking ciblé

Des forks/alternatives open source (Roo Code, Kilo Code) ont une vraie infrastructure de “context management”. Kilo Code, par exemple, implémente une **troncature par fenêtre glissante** (retire une fraction des messages anciens, conserve le premier message et garde un nombre pair pour préserver l’alternance) et une **summarization optionnelle** (si activée), avec un **buffer** de 10% de la fenêtre de contexte. citeturn10view0turn10view1

Roo Code (dans une version miroir accessible) montre la même philosophie sliding-window : `truncateConversationIfNeeded` calcule un budget (fenêtre – buffer – tokens réservés à la réponse) et tronque en conservant le premier message et en retirant une fraction. citeturn19view0

Roo Code va plus loin côté condensing : le module de condensation convertit `tool_use`/`tool_result` en texte pour pouvoir résumer sans dépendre du paramètre `tools`, et **injecte des tool_results synthétiques** si des tool_calls sont “orphelins” (problème fréquent quand on modifie l’historique). citeturn19view1turn12view1

**Conclusion pratique** : Roo/Kilo prouvent qu’il est faisable de gérer le contexte “dans l’extension”, mais leur stratégie standard est plutôt **(a) troncature de messages** et/ou **(b) summarization**, pas un **masking observation-only** (remplacement sélectif des seules observations au-delà de N tours).

### MCPHost (CLI) et autres briques MCP : hooks et “host policy” déjà présents dans l’écosystème

Le projet **mark3labs/mcphost** (host CLI MCP) expose une approche intéressante pour votre objectif : il annonce une **fenêtre d’historique configurable** et, surtout, un **système de hooks** avec événements **PreToolUse** et **PostToolUse**. citeturn23view1turn22view2 Même sans être une extension VS Code, c’est un indicateur fort : *le bon niveau d’abstraction pour filtrer/masquer se situe côté host*, pas côté serveur MCP.

À côté, des outils comme **Portkey-AI/mcp-tool-filter** attaquent un autre poste de dépense : la **réduction du “tool context”** (listes de tools très longues) en ramenant 1000+ tools à 10–20 pertinents via embeddings. C’est complémentaire (moins de surcharge “outillage”), mais ce n’est pas du masking d’observations. citeturn2search29

## Hooks client-side : ce que l’écosystème montre (Claude Code, Cursor, contraintes tool_result) et implications

### Le pattern “hook avant/après tool” existe déjà — parfois explicitement pour MCP

Plusieurs environnements agentiques modernes intègrent des **hooks** capables d’inspecter/modifier le flot tool calling :

- **MCPHost** : hooks déclarés par événement (PreToolUse, PostToolUse, etc.). citeturn22view2  
- **Claude Code** : la documentation des hooks mentionne des fonctionnalités avancées, incluant des **MCP tool hooks** (dans la référence) et des exemples d’automatisation via PostToolUse. citeturn29search3turn29search17  
- **Claude Agent SDK (docs platform)** : les hooks exposent `tool_input` et `tool_response`, et peuvent même **injecter un systemMessage** dans la conversation (mécanisme directement exploitable pour “placeholder + pointer”). citeturn29search21  
- **Cursor** : sa doc “Agent Hooks” met explicitement en avant des usages de gouvernance : scanner des réponses d’outils/MCP **avant qu’elles n’atteignent le modèle**. citeturn29search15  

**Conséquence** : votre demande (“hooks client-side”, “post-tool”) n’est pas exotique ; c’est une direction déjà reconnue par plusieurs vendors/OSS, y compris dans des contextes MCP.

### Contrainte structurante : ne jamais casser l’ordre tool_use → tool_result

Dès qu’on touche à l’historique, on affronte une contrainte universelle : les API de tool calling imposent généralement que le **tool_result suive immédiatement** le tool_use correspondant, sinon erreurs ou corruption de conversation. Des issues OpenHands décrivent précisément des pannes lorsque la condensation insère un événement au mauvais endroit, brisant les paires action/observation ou des lots parallèles d’outils. citeturn29search2turn29search12

Même côté OpenAI, des discussions montrent que des implémentations bricolent des **placeholders** de tool_result (“rendered”) pour satisfaire les contraintes d’API, preuve que *le placeholder est un outil standard de compatibilité*. citeturn29search8 C’est exactement l’approche recommandée par JetBrains pour l’observation masking : remplacer par un texte court “omitted for brevity” au lieu de supprimer. citeturn4view1turn5view0

## Implémentations manuelles recommandées (TypeScript/JS) : de MCP TS SDK à un patch Cline

### Stratégie minimale viable : “masker” seulement les tool_results anciens, en conservant les IDs et la structure

L’approche la plus robuste (et la plus alignée avec JetBrains) est :

1. **Conserver l’intégralité des messages assistant** (raisonnements + tool_use) sur toute la session.  
2. Pour les **messages user contenant des `tool_result`**, remplacer le contenu des `tool_result` **au-delà d’une fenêtre de N tours** par un placeholder court (ex. “Observation masquée (tour X), disponible dans l’UI / logs locaux”).  
3. Ne jamais supprimer le bloc `tool_result` ni son `tool_use_id` : on préserve l’adjacence et la validation tool calling. (Les écueils OpenHands illustrent pourquoi.) citeturn29search2turn29search12  

Empiriquement, une fenêtre de **~10 tours** a été un bon compromis dans SWE-agent selon JetBrains, mais c’est un hyperparamètre qui devra être ajusté pour Cline (et peut être rendu configurable). citeturn4view1turn5view0

### Où l’intégrer dans Cline (sans proxy API) : `ContextManager` est déjà un point d’entrée

Cline possède déjà un mécanisme qui “altère” des blocs via `contextHistoryUpdates` et des helpers capables de lire/écrire du texte **dans des `tool_result` wrappers** (`getTextFromBlock` / `setTextInBlock`). citeturn20view0 C’est un point d’ancrage très favorable : vous pouvez implémenter une passe `applyObservationMasking(...)` **avant** de construire `truncatedConversationHistory`, en enregistrant des “updates” par `[messageIndex, blockIndex]` exactement comme les autres optimisations.

De plus, Cline exécute déjà une passe de correction `ensureToolResultsFollowToolUse`, ce qui peut rester comme filet de sécurité après masking (particulièrement si vous introduisez des exemptions). citeturn20view0

Un pseudo-code TypeScript (intentionnellement “host-level”, indépendant de MCP) :

```ts
type MaskPolicy = {
  windowTurns: number;          // ex: 5 ou 10
  keepErrors: boolean;          // ne pas masquer tool_result is_error
  keepLastKPerTool?: number;    // optionnel: conserver davantage pour certains tools
};

function maskOldToolResults(
  messages: Anthropic.Messages.MessageParam[],
  policy: MaskPolicy,
): Anthropic.Messages.MessageParam[] {
  // 1) Reconstituer les "tours" (assistant tool_use ↔ user tool_result).
  // 2) Identifier les tool_result plus vieux que windowTurns.
  // 3) Remplacer block.content par un petit texte placeholder, sans toucher tool_use_id.
  // 4) Ne rien supprimer (structure tool calling préservée).
  return messages;
}
```

**Exemptions recommandées** (pour limiter les régressions qualité) :  
- Conserver les `tool_result` marqués erreur (ou contenant patterns “stack trace”, “failed”, etc.). Roo/Kilo et même des outils de condensation montrent que les erreurs et les dernières lignes comptent plus que le “milieu” des logs. citeturn19view1turn10view0turn10view1  
- Conserver les observations récentes de type “état” (ex. résultat de tests final, statut git), car elles peuvent être une partie du signal d’arrêt — et JetBrains souligne que les summaries peuvent masquer ces signaux et allonger des trajectoires. citeturn4view1turn5view0  

### Variante “client MCP TypeScript SDK” : wrapper `callTool` + stockage local (si vous contrôlez un host MCP maison)

Si vous construisez un **host MCP** en TypeScript (hors Cline) avec le SDK officiel, vous avez un point de friction simple : `Client.callTool(...)` retourne un résultat que *vous* décidez d’injecter ou non dans la conversation LLM. citeturn3search2turn3search18turn0search13

Pattern recommandé en host maison :
- Stocker exhaustivement les résultats `callTool` (disque/DB) avec un identifiant stable.
- N’injecter dans le prompt LLM qu’un placeholder court + un identifiant (et éventuellement un hash).
- Exposer un tool local “rehydrate_observation(id)” si vous voulez permettre au modèle de redemander explicitement (au prix de tokens) — optionnel, mais utile pour éviter de devoir relancer des outils coûteux.

Ce pattern ressemble à ce que des systèmes à hooks permettent via “systemMessage injection” ou décisions PostToolUse. citeturn29search21turn22view2

## Lacunes observées et opportunités de développement “MCP observation masking” pour Cline

### Lacunes confirmées par la recherche multi-sources

Il existe aujourd’hui :
- Une **validation empirique solide** que l’observation masking peut réduire drastiquement les coûts tout en conservant (voire améliorant) le solve rate sur SWE-bench Verified dans des agents SE (SWE-agent), avec release code/données. citeturn5view0turn27search3turn4view1  
- Des **implémentations open source** de troncature par fenêtre glissante et/ou summarization dans des extensions type Cline (Roo/Kilo), ainsi qu’une gestion de cohérence tool_use/tool_result non triviale. citeturn10view0turn10view1turn19view1turn20view0  
- Des **hooks** (pré/post tool) documentés dans plusieurs écosystèmes (MCPHost, Claude Code, Cursor, Claude Agent SDK) montrant que l’interception côté host est un besoin établi, y compris pour MCP. citeturn22view2turn29search3turn29search15turn29search21  

Mais il manque, dans l’écosystème “Cline-like + MCP”, une implémentation **simple, isolée, configurable et open-source** de **masking observation-only** (par fenêtres de tours) qui :
- conserve la structure tool calling (IDs, adjacence),
- masque sélectivement les tool_results anciens (au lieu de couper des messages entiers),
- ne dépend pas d’un summarizer LLM (donc coût additionnel nul),
- s’intègre proprement aux pipelines existants (Cline ContextManager / Roo context-management).

C’est exactement votre “opportunité produit” : un module de politique de contexte (“Context Policy”) focalisé sur observations.

### Risques et points d’attention avant d’industrialiser

Le papier JetBrains liste des limites structurantes : l’observation masking est **agnostique à la pertinence** (fenêtre fixe) et peut garder des observations devenues obsolètes (ex. contenu d’un fichier après modification). citeturn5view0turn4view1 D’où l’intérêt d’évoluer ensuite vers un masking plus “state-aware” (hash de fichier, invalidation quand un fichier change, etc.).

Autre risque “engineering” : dès qu’on modifie l’historique, les erreurs de structure tool calling apparaissent (tool_use sans tool_result, tool_result orphelins, insertion au milieu d’un batch), comme illustré par OpenHands. citeturn29search2turn29search12 Le fait que Cline et Roo aient déjà du code de réparation (ou d’injection synthétique) est un signal que vos tests doivent inclure des scénarios adverses. citeturn20view0turn19view1

### Recommandations concrètes de développement et validation

Une feuille de route pragmatique, alignée sur les meilleures preuves disponibles :

- Implémenter un **flag expérimental** “Observation Masking (tool results only)” paramétrable en **nombre de tours** (N=5 par défaut pour votre objectif, N=10 comme valeur recommandée empirique initiale), avec exemptions sur erreurs. citeturn4view1turn5view0  
- Cibler d’abord **les bloc `tool_result`** (dont MCP tool results) : gain maximal car observations dominent souvent. citeturn5view0turn30view1  
- Utiliser systématiquement des **placeholders** (pas des suppressions) pour ne pas casser l’ordre tool calling. citeturn29search2turn29search12turn5view0  
- Mesurer avec des métriques simples et actionnables : tokens in/out, coût, longueur de trajectoire (nombre de tours), taux d’erreurs API tool calling, et (si possible) un proxy d’efficacité type “résolution de tâche”. JetBrains montre que ces métriques suffisent à révéler l’essentiel (coût, solve rate, trajectoire). citeturn4view1turn5view0  
- Validation empirique : réutiliser SWE-bench Verified comme benchmark externe (ou au moins un sous-ensemble) parce que c’est précisément le cadre où JetBrains a établi les ordres de grandeur et les effets secondaires (trajectory elongation, etc.). citeturn4view1turn5view0  

Enfin, gardez en tête que la doc Cline rappelle que “tool outputs” comptent dans le contexte : un masking ciblé sur observations est donc l’un des rares leviers **à coût marginal nul** qui s’attaque à une composante explicitement dans le budget. citeturn30view1turn30view0