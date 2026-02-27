---
description: Docs Updater, Standard Tools, Cloc Radon, Quality Context
---

# Workflow: Docs Updater — Standardized & Metric-Driven

> Ce workflow harmonise la documentation Kimi Proxy en utilisant l'analyse statique standard (`cloc`, `radon`, `tree`) pour la précision technique et les modèles de référence pour la qualité éditoriale, adapté à l'architecture 5 couches et aux patterns système.

## 🚨 Protocoles Critiques
1.  **Outils autorisés** : MCP fast-filesystem (`fast_read_file`, `fast_list_directory`, `fast_search_files`, `edit_file`), MCP ripgrep (`search`, `advanced-search`, `count-matches`), et `bash` limité aux audits (`tree`, `cloc`, `radon`, `ls`).
2.  **Contexte** : Initialiser le contexte en appelant l'outil fast_read_file du serveur fast-filesystem pour lire UNIQUEMENT activeContext.md. Ne lire les autres fichiers de la Memory Bank que si une divergence majeure est détectée lors du diagnostic.
3.  **Source de Vérité** : Le Code (analysé par outils) > La Documentation existante > La Mémoire.
4.  **Sécurité Memory Bank** : Utilisez les outils fast-filesystem (fast_*) pour accéder aux fichiers memory-bank avec des chemins absolus dans `/home/kidpixel/kimi-proxy/memory-bank/`.

## Étape 1 — Audit Structurel et Métrique
Lancer les commandes suivantes pour ignorer les dossiers de données (ex: "sessions.db", "__pycache__", "node_modules") et cibler le cœur applicatif selon l'architecture 5 couches.

1.  **Cartographie (Filtre Bruit)** :
    - `bash "tree -L 3 -I '__pycache__|venv|node_modules|.git|*.db|*.backup|logs|debug|assets|*_output|test*|mcp|shrimp_data|.shrimp_task_manager'"`
    - *But* : Visualiser l'architecture 5 couches (`src/kimi_proxy/{api,services,features,proxy,core}`).
2.  **Volumétrie (Code Source)** :
    - `bash "cloc src/kimi_proxy --md --exclude-dir=__pycache__,tests,mcp,shrimp_data,.shrimp_task_manager"`
    - *But* : Quantifier le code réel par couche (API/Services/Features/Proxy/Core).
4.  **Sessions Développement (Nouvelles Fonctionnalités)** :
    - `find_by_name docs/development/sessions/ -name "*.md" | head -10`
    - *But* : Détecter les nouvelles fonctionnalités documentées dans les sessions de développement récentes.
    - **Règle** : Intégrer les nouvelles features dans la documentation principale si elles ne sont pas encore référencées.
5.  **Analyse APIs (Endpoints & Routes)** :
    - `grep_search Query="@app\.(get|post|put|delete|patch)" SearchPath=src/kimi_proxy/api`
    - *But* : Détecter tous les endpoints API et vérifier leur documentation dans `docs/api/`.
    - **Règle** : Tout endpoint DOIT avoir une doc API correspondante.
6.  **Analyse Frontend (Modules & Éléments UI)** :
    - `grep_search Query="class.*\{|function.*\(|const.*=.*\(" SearchPath=static/js/modules`
    - `grep_search Query="<.*id=|class=" SearchPath=static`
    - *But* : Détecter les modules JavaScript et éléments HTML pour vérifier la cohérence avec `docs/ui/` et `docs/features/`.
7.  **Analyse Base de Données (Migrations & Schémas)** :
    - `list_dir DirectoryPath=src/kimi_proxy/core`
    - `grep_search Query="CREATE TABLE|ALTER TABLE|INSERT INTO|UPDATE|DELETE FROM" SearchPath=src/kimi_proxy/core`
    - *But* : Détecter les changements de schéma et vérifier la documentation des entités dans `docs/core/`.
8.  **Analyse Configuration (Nouveaux Providers/Paramètres)** :
    - `grep_search Query="providers\[|models\[|config\." SearchPath=src/kimi_proxy`
    - *But* : Détecter les nouveaux providers/modèles et vérifier leur documentation dans `docs/features/multi-provider-support.md`.
9.  **Analyse Métriques & Monitoring** :
    - `grep_search Query="METRICS|LOGGING|ALERT" SearchPath=src/kimi_proxy`
    - *But* : Détecter les nouveaux systèmes de métriques et vérifier leur documentation.

## Étape 2 — Analyse Comparative Code vs Docs
Générer un plan de modification avant d'appliquer :

```markdown
## 📝 Plan de Mise à Jour Documentation
### Audit Métrique
- **Cible** : `src/kimi_proxy/services/websocket_manager.py`
- **Métriques** : 320 LOC, Complexité max C (11), Pattern 2 (DI) appliqué.

### Modifications Proposées
#### 📄 docs/development/services/websocket-manager.md
- **Type** : [API | Services | Features | Proxy | Core]
- **Diagnostic** : [Obsolète | Incomplet | Manquant]
- **Correction** :
  ```markdown
  [Contenu proposé respectant les patterns système Kimi Proxy]
  ```

## Étape 5 — Application et Finalisation
1.  **Exécution** : Après validation, utiliser `edit_file` ou `edit_files`.
2.  **Mise à jour Memory Bank** :
    - Mettre à jour la Memory Bank en utilisant EXCLUSIVEMENT l'outil edit_file avec timestamps [YYYY-MM-DD HH:MM:SS].

### Sous-protocole Rédaction — Application de documentation/SKILL.md

#### 5.1 Point d'Entrée Explicite
- **Mode Rédaction** : Déclenché après validation du plan de mise à jour.
- **Lecture obligatoire** : `.windsurf/skills/documentation/SKILL.md`.
- **Modèle à appliquer** : Spécifié dans le plan (article deep-dive, README, fiche technique, etc.).

#### 5.2 Checkpoints Obligatoires
**Avant rédaction** :
- [ ] TL;DR présent (section 1 du skill)
- [ ] Problem-first opening (section 2 du skill)

**Pendant rédaction** :
- [ ] Comparaison ❌/✅ (section 4 du skill)
- [ ] Trade-offs table si applicable (section 7 du skill)
- [ ] Golden Rule (section 8 du skill)
- [ ] Éviter les artefacts AI (section 6 du skill)
- [ ] Patterns système Kimi Proxy référencés (Pattern 1-19)

**Après rédaction** :
- [ ] Validation checklist « Avoiding AI-Generated Feel »
- [ ] Vérification ponctuation (remplacer " - " par ;/:/—)
- [ ] Conformité architecture 5 couches

#### 5.3 Traçabilité
Dans la proposition de mise à jour (Étape 4), ajouter :
#### Application du skill
- **Modèle** : [Article deep-dive | README | Technique]
- **Éléments appliqués** : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔
- **Patterns système** : [Pattern 1, Pattern 6, Pattern 14, etc.]

#### 5.4 Hook d'Automation
- **Validation Git** : Commentaire de commit « Guidé par documentation/SKILL.md — sections: [liste] »
- **Blocking** : Le workflow ne peut pas se terminer si les checkpoints ne sont pas cochés
- **Audit trail** : Chaque fichier modifié contient une note de validation interne
- **Memory Bank sync** : Mise à jour automatique de `progress.md` et `decisionLog.md`