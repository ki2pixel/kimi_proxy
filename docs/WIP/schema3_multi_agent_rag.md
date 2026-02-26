# Schéma 3: Architecture Multi-Agent avec RAG Intégré

## TL;DR
Coordonne des agents spécialisés via MCP, utilisant RAG pour retrieval contextuelle avec embeddings nettoyés et expansion graph (Qdrant + Neo4j), permettant contexte intelligent et scalable sous <50ms.

## Problème
Tâches complexes (développement, analyse) nécessitent vastes contextes, surchargeant la fenêtre de Cline et augmentant latence/coûts.

## Solution
Implémenter architecture multi-agent où un agent RAG gère retrieval via embeddings nettoyés + expansion graph, compressant le contexte avant transmission.

## Citations et Références
- @/home/kidpixel/kimi-proxy/research/deep-research-report-Architectures-IA-Multi-Agents.md - Rapport Architectures IA Multi-Agents: Coordination d'agents spécialisés pour distribuer tâches et réduire charge globale.
- @/home/kidpixel/kimi-proxy/research/deep-research-report-Recherche-sur-RAG-et-AST.md:218 - Rapport RAG et AST: "Retrieval & ranking" - Retrieval primaire sur embeddings nettoyés, expansion contextuelle via Neo4j (GraphRAG), reranking SACL pour combiner scores code+desc.
- @/home/kidpixel/kimi-proxy/research/deep-research-report-Recherche-sur-RAG-et-AST.md:233 - Rapport RAG et AST: Limites réalistes <50ms avec Qdrant gRPC et embeddings locaux/cache.

## Plan d'Action
1. **Setup infrastructure RAG** : Installer Qdrant (vector DB) et Neo4j (graph DB) en local/éphémère.
2. **Préparer embeddings** : Nettoyer code, générer embeddings locaux (cache agressif pour <50ms).
3. **Développer agents MCP** : Agent retrieval (récupération), agent analysis (traitement), avec orchestration.
4. **Implémenter expansion graph** : Utiliser Neo4j pour récupérer voisins pertinents via GraphRAG.
5. **Ajouter reranking SACL** : Générer descriptions fonctionnelles des top-k, combiner scores.
6. **Intégrer avec Cline** : Exposer via serveurs MCP, tester coordination agents.
7. **Optimiser latence** : Pré-allocation clients DB, batch upsert, mesurer <50ms.

## Trade-offs
- ✅ Contexte intelligent et scalable pour tâches complexes.
- ❌ Setup complexe (Qdrant/Neo4j), latence critique.
- ✅ Réutilise serveurs MCP existants (ex. Qdrant MCP).

## Golden Rule
Valider empiriquement : mesurer impact sur tâches réelles, ajuster seuil latence pour éviter interruption.