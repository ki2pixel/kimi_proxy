# Plan d'Action : Enrichissement Gestion Contexte Kimi Proxy Dashboard

**Date :** Février 2026  
**Audit basé sur :** Analyse du repo `docs/kimi-cli-main` (Kimi Code CLI)  
**Objectif :** Intégrer mécanismes avancés de gestion des fenêtres de contexte LLM

## Contexte de l'Audit

### Mécanismes Clés Identifiés dans Kimi CLI
- **Suivi fractionnaire** : `usage = token_count / max_context_size` avec mise à jour temps réel
- **Compaction automatique** : Trigger à `token_count + reserved >= max_context_size`
- **Stratégie SimpleCompaction** : Préservation N derniers messages + résumé LLM du reste
- **Gestion historique** : Checkpoints, fusion messages, persistance complète

### État Actuel Dashboard
- Suivi basique des tokens par session
- Jauges colorées vert/jaune/rouge par seuils fixes
- Export CSV/JSON des métriques
- Pas de gestion proactive du contexte

## Plan d'Action Priorisé

### Phase 1 : Infrastructure de Base (Priorité Haute)
#### 1.1 Étendre Modèle de Données
- Ajouter colonnes `reserved_tokens`, `compaction_count`, `last_compaction_at` à table sessions
- Créer table `compaction_history` pour tracer les compactages
- Migrer schéma SQLite avec script `scripts/migrate_compaction.sql`

#### 1.2 Service de Compaction
- Implémenter `SimpleCompaction` inspiré de Kimi CLI dans `src/kimi_proxy/features/compaction/`
- Configurable `max_preserved_messages` (défaut 2)
- Intégration avec Tiktoken pour calculs précis
- Tests unitaires pour logique compaction

#### 1.3 Métriques Temps Réel
- Étendre `StatusSnapshot` avec `context_usage_reserved`, `compaction_ready`
- WebSocket broadcasts pour mises à jour compaction
- Logging compaction avec tokens économisés

### Phase 2 : Fonctionnalités Utilisateur (Priorité Moyenne)
#### 2.1 UI Compaction Manuelle
- Bouton "Compresser Contexte" dans dashboard par session
- Modal confirmation avec preview impact (tokens avant/après)
- Indicateur loading pendant process asynchrone
- Feedback visuel succès/échec

#### 2.2 Triggers Automatiques
- Configuration seuils dans `config.toml` : `compaction_threshold` (ex: 0.8)
- Toggle auto-compaction par session
- Alertes WebSocket quand seuil atteint

#### 2.3 Visualisation Avancée
- Jauges multi-couches : usage actuel + réservé + seuil compaction
- Graphique historique compaction par session
- Tooltips détaillés avec tokens utilisés/réduits

### Phase 3 : Optimisations Avancées (Priorité Basse)
#### 3.1 Gestion Sessions Améliorée
- Checkpoints dashboard pour rollback contextuel (restauration historique conversationnel uniquement - modifications fichiers/commandes non restaurées)
- Détection conflits multi-source intelligente
- Stats cumulatives par provider avec tendances

#### 3.2 Intégration MCP
- **Connecteurs MCP pour analyse contexte externe** :
  - **Qdrant MCP** (`github.com/qdrant/mcp-server-qdrant`) : Similarité sémantique, détection redondances (<50ms)
  - **SACL MCP** (`github.com/ulasbilgen/sacl`) : Scoring importance bias-aware, amélioration rappel +12%
  - **Token Counter Server** (`github.com/Intro0siddiqui/token-counter-server`) : Surveillance économie tokens, compatibilité tiktoken
  - **Context Compression MCP** (`github.com/rsakao/context-compression-mcp-server`) : Compression zlib 20-80%, stockage SQLite persistant

**Analyse Compatibilité (15 février 2026)** :
- **SACL MCP** : Recherche code bias-aware avec Neo4j. Compatibilité moyenne - réduction biais textuels +12% Recall@1, mais overhead élevé et dépendances externes. Utile pour analyse sémantique avancée, mais complexité vs bénéfices actuels.
- **Context Compression MCP** : Stockage contexte compressé FastMCP Python. Compatibilité élevée - compression zlib identique à approche actuelle, API simple. Idéal pour archivage contextes hors fenêtre principale.
- **Qdrant MCP** : Mémoire vectorielle sémantique. Compatibilité moyenne-élevée - recherche <50ms, persistance vectorielle. Parfait pour phase 2 (mémoire MCP) avec balises `<mcp-memory>`.
- **Token Counter Server** : Comptage tokens TypeScript. Compatibilité faible - redondant avec Tiktoken intégré, stack différente.

**Recommandation** : Priorité Context Compression + Qdrant. Reporter SACL (complexité) et Token Counter (redondance). Évaluation benchmarks avant déploiement.
- Mémoire standardisée pour contextes fréquents
- Routing provider basé sur capacité contexte restante

#### 3.3 Performance
- Compaction asynchrone non-bloquante
- Cache tokens pour messages répétitifs
- Monitoring impact mémoire sessions volumineuses

## Critères de Succès

### Métriques Fonctionnelles
- ✅ Réduction moyenne 60% tokens après compaction
- ✅ Temps compaction < 5s pour sessions typiques
- ✅ 0% perte données lors compaction
- ✅ Compatibilité tous providers supportés

### Métriques Utilisateur
- ✅ Interface intuitive pour déclenchement manuel
- ✅ Alertes proactives sans spam
- ✅ Visualisation claire usage vs limites
- ✅ Performance dashboard inchangée

## Risques et Mitigation

### Risques Techniques
- **Perte de contexte** : Tests exhaustifs compaction, backups automatiques
- **Performance** : Profiling mémoire/CPU, optimisation requêtes DB
- **Compatibilité providers** : Tests multi-provider avant déploiement

### Risques Fonctionnels
- **Complexité UI** : Design simple, tests utilisateurs
- **Configuration** : Valeurs par défaut conservatrices
- **Maintenance** : Logs détaillés pour debugging

## Livrables

### Code
- `src/kimi_proxy/features/compaction/` : Module compaction complet
- `src/kimi_proxy/core/models.py` : Modèles étendus
- `static/index.html` : UI enrichie compaction
- Tests unitaires/integration pour toutes fonctionnalités

### Documentation
- Guide utilisateur compaction dans `docs/deployment/usage.md`
- Documentation développeur dans `docs/development/guides/`
- Exemples configuration dans `config.toml`

### Tests
- Suite de tests compaction avec scénarios edge cases
- Tests E2E workflow complet
- Benchmarks performance

## Timeline Estimée

- **Phase 1** : 2-3 semaines (infrastructure)
- **Phase 2** : 2-3 semaines (UI/fonctionnalités)
- **Phase 3** : 1-2 semaines (optimisations)
- **Tests/Validation** : 1 semaine
- **Total** : 6-9 semaines

## Ressources Requises

- **Équipe** : 1 développeur backend, 1 frontend, 1 QA
- **Dépendances** : Aucune nouvelle (utilise Tiktoken existant)
- **Environnements** : Dev, staging, prod avec monitoring

---

*Plan établi suite à audit technique du 15 février 2026*
