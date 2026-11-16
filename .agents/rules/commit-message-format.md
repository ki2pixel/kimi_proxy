---
trigger: model_decision
description: Format des messages de commit Git (Conventional Commits, anglais, body à puces).
---

# Règles de Format des Messages de Commit Git

## 1. Format Canonique (Conventional Commits)
```text
<Prefix>(<scope>): <Summary (impératif, court, sans point final)>

- Changement 1 (puce descriptive)
- Changement 2 (puce descriptive)

Refs: #<Numéro d'issue> (optionnel)
BREAKING CHANGE: <détail rupture de compatibilité> (optionnel)
```

## 2. Spécification de Langue & Préfixes
- **Langue du message** : Anglais (`language = "en"`). Le résumé et le corps sont rédigés en anglais.
- **Préfixes autorisés** :
  - `feat`: Nouvelle fonctionnalité
  - `fix`: Correction de bug
  - `refactor`: Refactoring sans modification de comportement
  - `perf`: Amélioration de performance
  - `test`: Ajout ou ajustement de tests
  - `docs`: Documentation
  - `build`: Changements liés au build ou aux dépendances
  - `ci`: Configuration d'intégration continue
  - `chore`: Tâches diverses, maintenance, outillage
  - `style`: Formatage, espaces, virgules (sans impact logique)
  - `revert`: Annulation de commit

## 3. Ligne de Résumé (Première Ligne)
- Rédigée au présent de l'impératif, concise (< 50 caractères).
- Pas de point final.
- Doit résumer fidèlement le diff effectif (`git diff` / `git diff --cached`).

## 4. Corps du Message (Bullet Points)
- Liste à puces démarrant par `- `.
- Énumère les modifications réelles, le périmètre d'impact, les risques ou migrations éventuelles.
- Les termes techniques restent en anglais.

## 5. Pied de Page (Footer)
- Références : `Refs: #123` ou `Closes: #123`.
- `BREAKING CHANGE:` explicite en cas d'incompatibilité descendante.

## 6. Pratiques Proscrites
- ❌ Résumés vagues ou vides de sens (`update`, `fix bug`, `changes`).
- ❌ Corps sous forme de paragraphe indigeste sans listes à puces.
- ❌ Commits désactivant silencieusement les linters ou tests sans résolution de fond.
