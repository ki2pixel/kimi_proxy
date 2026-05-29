# Schéma 2: Externalisation des Outputs Lourds

## TL;DR
Remplace les gros contenus par des handles/URIs éphémères (ResourceLinks MCP), ne transmettant que métadonnées courtes au contexte, réduisant drastiquement les tokens.

## Problème
Les outputs volumineux (logs, données, code) saturent la fenêtre de contexte de Cline, augmentant coûts et latence.

## Solution
Utiliser les ResourceLinks MCP pour externaliser les données lourdes vers stockage local/éphémère, renvoyant seulement un handle et métadonnées au LLM.

## Citations et Références
- @/home/kidpixel/kimi-proxy/research/deep-research-report-pptimisation-fenetre-contexte-MCP.md:9 - Section "Externalisation des gros outputs" - Pattern "handle, not payload", ResourceLinks / URIs éphémères pour réduire la quantité de texte observable.
- @/home/kidpixel/kimi-proxy/research/deep-research-report-pptimisation-fenetre-contexte-MCP.md:10 - Section "Filtrage/post-traitement" - Hooks gateway/proxy pour garde de longueur et redaction.

## Plan d'Action
1. **Analyser les outputs lourds** : Identifier types de contenus (>X tokens) à externaliser (ex. logs, dumps).
2. **Implémenter le système de handles** : Générer URIs éphémères uniques pour chaque output lourd.
3. **Développer stockage éphémère** : Cache local/session pour stocker les données réelles.
4. **Intégrer ResourceLinks MCP** : Remplacer outputs par liens + métadonnées (taille, type, résumé).
5. **Gérer la résolution** : Mécanisme pour récupérer données sur demande via handle.
6. **Tester compatibilité** : Vérifier que Cline peut accéder aux ressources via MCP.

## Trade-offs
- ✅ Réduction tokens drastique pour contenus volumineux.
- ❌ Complexité gestion stockage et résolution handles.
- ✅ Réutilise standards MCP existants.

## Golden Rule
Équilibrer accessibilité : handles doivent être résolubles rapidement pour éviter interruption workflow.