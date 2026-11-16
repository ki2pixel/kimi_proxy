---
trigger: always_on
description: Memory Bank Protocol (Version Filesystem-Agent MCP-Optimized)
globs: 
---

# Protocole Memory Bank (Optimisé MCP)

## 1. Initialisation Sélective (Obligatoire au Premier Tour)
- **Déclenchement** : `first_interaction` | **Priorité** : Immédiate.
- **Action Requise** :
  1. Appeler systématiquement `fast_read_file(path="/home/kidpixel/kimi-proxy/memory-bank/activeContext.md")` (utiliser le chemin absolu du projet actif).
  2. Vérifier les bloqueurs, le focus courant et les prochaines étapes.
  3. **Préfixe Obligatoire** : Débuter impérativement la réponse par `[MEMORY BANK: ACTIVE (MCP-PULL)]`.
- **Règles Strictes de Chargement** :
  - Ne **JAMAIS** charger `productContext.md` ou `systemPatterns.md` sans besoin architectural explicite.
  - Ne charger qu'**un seul fichier à la fois**.
  - **Chemins absolus stricts** : Tout appel `fast_*` doit utiliser un chemin absolu sous `/home/kidpixel/...`. L'usage de `"."`, `"./..."` ou de chemins relatifs est strictement interdit (serveur partagé multi-projets).
  - En cas d'inaccessibilité du MCP `fast-filesystem`, le signaler et poursuivre sans contexte.
  - Si un résultat contient le contenu d'un autre projet, s'arrêter immédiatement et le signaler.

## 2. Structure des 5 Fichiers de Base
- `activeContext.md` : État courant, décisions actives et bloqueurs.
- `progress.md` : Suivi d'avancement des tâches (terminées, en cours, à venir).
- `decisionLog.md` : Décisions d'architecture durables et arbitrages techniques.
- `systemPatterns.md` : Patrons de conception, architecture et patterns de test.
- `productContext.md` : Périmètre global et objectifs du projet.

## 3. Protocole de Mise à Jour & Archivage
- **Format d'horodatage** : `[YYYY-MM-DD HH:MM:SS] - [Résumé]` obligatoire pour chaque entrée.
- **Mise à jour chirurgicale** : Effectuée via `edit_file` en fin de session ou sur commande.
- **Archivage** : Conserver 90 jours de détail dans `decisionLog.md` et `progress.md`. Déplacer les entrées antérieures vers `memory-bank/archives/*.md` via `fast_write_file`.
- **Restriction** : `fast_write_file` est réservé à l'archivage ou à l'initialisation des 5 fichiers de base. Interdiction de créer d'autres fichiers à la racine de `memory-bank/`.

## 4. Commande Spéciale : Update Memory Bank (UMB)
- **Déclencheur** : `^(Update Memory Bank|UMB)$`.
- **Procédure** :
  1. Répondre par `[MEMORY BANK: UPDATING]`.
  2. Auditer la session (décisions, changements, validations).
  3. Mettre à jour `progress.md` et `activeContext.md` via `edit_file`.
  4. Consigner uniquement les deltas de la session courante sans recopier l'historique global.
