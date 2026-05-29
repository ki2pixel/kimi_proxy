# Schéma 4: Compression Hybride AST + Multi-Agent

## TL;DR
Combine analyse AST via Tree-sitter pour parser/compresser code en chunks minimaux (définition + 1 hop imports/fonctions) avec architecture multi-agent pour orchestration, assurant précision maximale sous <50ms.

## Problème
Code volumineux et historique complexe (multi-fichiers, dépendances) saturent la fenêtre de contexte de Cline, rendant inefficaces les méthodes simples.

## Solution
Utiliser AST pour extraction ciblée de contexte (non aveugle), intégrée dans multi-agent pour compression hybride et traitement distribué.

## Citations et Références
- @/home/kidpixel/kimi-proxy/research/deep-research-report-Recherche-sur-RAG-et-AST.md:223 - Rapport RAG et AST: Section "Lecture 'non aveugle' pour l'agent" - Renvoi paquet contexte minimal (chunk symbole pressenti, 1 hop imports nécessaires, 1 hop fonctions appelées critiques), résumé fichier si choix nécessaire.
- @/home/kidpixel/kimi-proxy/research/deep-research-report-Architectures-IA-Multi-Agents.md - Rapport Architectures IA Multi-Agents: Coordination agents spécialisés pour distribuer tâches complexes.
- @/home/kidpixel/kimi-proxy/research/deep-research-report-Recherche-sur-RAG-et-AST.md:233 - Rapport RAG et AST: Section "Limites réalistes de la contrainte <50ms" - Tree-sitter (incrémental, parse local) aligné avec faible latence.

## Plan d'Action
1. **Intégrer Tree-sitter** : Setup parseur AST pour langages cibles (JS, Python, etc.), incremental pour modifications.
2. **Développer extracteur contexte** : Parser code pour extraire chunks minimaux (définition symbole, 1 hop imports/fonctions), stubs signatures.
3. **Combiner avec multi-agent** : Agent parsing AST, agent orchestration, agent compression.
4. **Implémenter filtrage observation masking** : Intégrer schéma 1 pour historique.
5. **Tester sur codebases** : Valider compression sur projets réels, mesurer réduction tokens.
6. **Optimiser performance** : Pré-allocation, fast path fichier modifié uniquement, vérifier <50ms.
7. **Intégrer MCP** : Exposer via serveurs MCP pour compatibilité Cline.

## Trade-offs
- ✅ Précision maximale, aligné contraintes <50ms.
- ❌ Développement intensif, dépendances AST/multi-agent.
- ✅ Extension naturelle des schémas 1+3.

## Golden Rule
Prioriser validation technique : prouver faisabilité <50ms avant déploiement, ajuster granularité chunks selon feedback empirique.