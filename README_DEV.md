# README_DEV.md

## Objectif de ce document

Ce document décrit les conventions de développement, les choix d’architecture, les règles de maintenance et les principes d’évolution du projet `investing-pipeline`.

Il complète `README.md`, qui est centré sur :
- le fonctionnement global,
- l’installation,
- l’usage métier,
- les modes de sélection,
- le scoring snapshot + historique.

Ici, l’objectif est de répondre à des questions du type :
- comment le projet est structuré,
- où ajouter une nouvelle source de données,
- comment modifier le scoring sans casser le pipeline,
- comment brancher une nouvelle logique de sélection,
- comment exploiter les historiques StockAnalysis,
- comment tester et faire évoluer le projet proprement.

---

## Principes d’architecture

Le projet suit 6 principes directeurs.

### 1. Une seule source de vérité analytique
La source de vérité applicative est la **table normalisée produite par Python**.

Cela implique :
- Excel n’est qu’un export,
- les CSV sont des sorties dérivées,
- la watchlist n’est plus nécessairement la source primaire de découverte,
- la logique métier ne doit jamais vivre dans un tableur.

### 2. Séparation stricte des responsabilités
Chaque couche a un rôle précis :

- `config` : paramètres et validation légère
- `screening` : présélection de l’univers de titres
- `fetch` : accès aux providers / sources snapshot
- `history` : lecture et agrégation des historiques par ticker
- `transform` : normalisation tabulaire
- `validate` : contrôles de cohérence
- `scoring` : logique métier
- `export` : restitution

### 3. Les providers sont interchangeables
Les providers fundamentals et market data doivent être remplaçables sans modifier la logique métier centrale.

Le projet supporte explicitement :
- `fmp`
- `stockanalysis_screener`
- `marketdata_app` pour la couche market data

### 4. Les règles métier doivent rester explicites
Les règles de scoring et de sélection doivent rester lisibles dans du code clair.

À éviter :
- seuils cachés dans plusieurs endroits,
- logique métier disséminée dans `main.py`,
- transformations implicites impossibles à auditer.

### 5. Le pipeline est désormais data-first
Le paradigme a changé :
- **avant** : `watchlist.yaml` → fetch → score
- **maintenant** : screener bulk → pré-filtres → shortlist/watchlist → fetch → enrichissement historique → score

### 6. L’historique doit rester modulaire
Le scoring historique ne doit pas polluer la logique snapshot.

En pratique :
- les historiques sont lus dans `src/history/`
- leurs features sont mergées dans la table finale seulement avant le scoring
- le scoring snapshot et le scoring historique restent distinguables (`score_snapshot_total`, `score_historical_total`)

---

## Vue d’ensemble technique

### Flux cible actuel

```text
settings.yaml
   ↓
selection.source
   ↓
manual | screener | hybrid
   ↓
screening/* si source screener
   ↓
watchlist résolue
   ↓
fetch/*
   ↓
transform/normalize.py
   ↓
validate.py
   ↓
history/* si scoring.historical.enabled
   ↓
scoring/*
   ↓
export/*
```

### Flux simplifié du mode `screener` avec historique

```text
StockAnalysis bulk export
   ↓
stockanalysis_screener_client.py
   ↓
screening/stockanalysis_universe.py
   ↓
filtered candidates
   ↓
selected_watchlist
   ↓
fetch_all_fundamentals()
   ↓
normalize + validate
   ↓
history/stockanalysis_history.py
   ↓
features historiques par ticker
   ↓
compute_scores()
   ↓
apply_ranking()
   ↓
exports CSV / Excel
```

---

## Structure recommandée des modules

```text
src/
├─ main.py
├─ config.py
├─ utils/
├─ fetch/
├─ screening/
├─ history/
├─ transform/
├─ scoring/
└─ export/
```

### `main.py`

Point d’entrée orchestral.

Responsabilités :
- charger la config,
- résoudre la sélection (`manual`, `screener`, `hybrid`),
- enchaîner snapshot, validation, enrichissement historique, scoring et export,
- journaliser les grandes étapes.

Ne doit pas contenir :
- logique détaillée de provider,
- logique détaillée de scoring,
- règles de screening complexes,
- parsing spécifique des historiques.

### `config.py`

Responsable du chargement, du merge par défaut et de la validation de la configuration.

Fonctions actuelles importantes :
- `load_settings(...)`
- `load_watchlist(...)`

Évolutions récentes :
- support multi-provider,
- validation de `stockanalysis_screener.csv_path`,
- validation de `selection.source`,
- validation du nouveau bloc `scoring.historical`.

### `screening/`

Nouvelle couche introduite avec le paradigme data-first.

Responsabilité :
- filtrer un univers large,
- appliquer des critères d’éligibilité minimum,
- scorer les candidats restants,
- générer une shortlist / watchlist exploitable.

Module actuel :
- `stockanalysis_universe.py`

Fonction centrale :
- `build_screener_candidate_watchlist(settings)`

### `fetch/`

Contient uniquement l’accès aux sources snapshot.

Clients actuels :
- `fmp_client.py`
- `marketdata_client.py`
- `stockanalysis_screener_client.py`
- `providers.py` pour la factory provider

Règle :
- pas de scoring ici,
- pas de ranking,
- pas de logique d’export.

### `history/`

Nouvelle couche dédiée à la lecture des historiques exportés par ticker.

Module actuel :
- `stockanalysis_history.py`

Fonction publique :
- `build_history_features_dataframe(tickers, settings)`

Responsabilités :
- lire les fichiers annuels sous `data/stockanalysis_candidate_history/<TICKER>/...`
- exclure les lignes `TTM`
- limiter l’historique à `lookback_years`
- calculer des features robustes et simples

Features actuellement produites :
- `history_years_available`
- `history_roic_stability`
- `history_revenue_growth_consistency`
- `history_fcf_consistency`
- `history_share_count_cagr`
- `history_data_quality_flag`

### `transform/`

Rôle : transformer les payloads provider en schémas stables.

Module clé :
- `normalize.py`

Schémas actuels :
- fundamentals normalisés
- market data normalisées

### `validate.py`

Garde-fou minimal avant scoring.

Vérifie notamment :
- colonnes requises,
- dates valides,
- doublons ticker,
- présence minimale des champs critiques.

### `scoring/`

Cœur métier.

Modules :
- `rules.py`
- `score.py`
- `rank.py`

Le scoring est désormais séparé en :
- **snapshot**
- **historique**
- **agrégation finale**

### `export/`

Responsable des CSV et de l’Excel final.

Sorties actuelles possibles :
- `fundamentals_latest.csv`
- `history_features_latest.csv`
- `scores_latest.csv`
- `candidates_latest.csv`
- `selected_watchlist_latest.csv`
- `market_data_latest.csv`
- `fetch_failures_latest.csv`
- `investing_watchlist.xlsx`

---

## Providers et conventions d’intégration

## Fundamentals providers

### `fmp`

Convention attendue :
- `get_ratios(symbol)`
- `get_key_metrics(symbol)`

### `stockanalysis_screener`

Convention alignée sur le même contrat logique :
- `get_ratios(symbol)`
- `get_key_metrics(symbol)`

Spécificités :
- source = CSV exporté depuis Google Apps Script / Google Sheets
- parsing des nombres localisés (virgule décimale)
- calcul dérivé de `net_debt_ebitda`
- possibilité d’extraction bulk via `get_screening_records()`

### `providers.py`

Le rôle de `providers.py` est de centraliser la factory :
- `build_fundamentals_provider(settings)`
- `build_market_data_provider(settings)`

Objectif : éviter de disperser la logique provider dans `main.py`.

---

## Règles de transformation

`normalize.py` doit rester la couche qui absorbe les différences de schéma provider.

### Schéma interne snapshot à préserver

Colonnes fundamentals attendues :
- `ticker`
- `company_name`
- `sector`
- `currency`
- `priority`
- `note`
- `as_of_date`
- `roe`
- `roic`
- `net_debt_ebitda`
- `current_ratio`
- `interest_coverage`
- `earnings_yield`
- `fcf_yield`
- `pe_ratio`
- `pb_ratio`
- `p_fcf`
- `source_provider`
- `fetched_at`
- `data_quality_flag`

Les colonnes historiques sont ajoutées ensuite via merge.

Règle importante :
- les différences de noms provider sont absorbées ici,
- le scoring ne doit pas connaître les noms provider d’origine.

---

## Logique de scoring

### Score snapshot
Toujours basé sur :
- ROIC
- ROE
- Net Debt / EBITDA
- FCF Yield
- Earnings Yield
- valorisation secondaire

### Score historique (v1)
Calculé dans `score.py` à partir des features injectées par `history/`.

Sous-scores actuels :
- `score_history_roic_stability`
- `score_history_revenue_growth`
- `score_history_fcf_consistency`
- `score_history_dilution`

Totaux :
- `score_snapshot_total`
- `score_historical_total`
- `score_total`

### Convention importante
Quand vous ajoutez un nouveau sous-score historique :
1. ajoutez la feature dans `src/history/stockanalysis_history.py`
2. ajoutez sa règle et son poids dans `DEFAULT_SETTINGS`
3. ajoutez le calcul dans `src/scoring/score.py`
4. ajoutez un test dédié

---

## Historique StockAnalysis : conventions d’exploitation

### Source locale
Le pipeline consomme maintenant un dossier local de la forme :

```text
data/stockanalysis_candidate_history/<TICKER>/
├─ income_statement/
├─ balance_sheet/
├─ cash_flow_statement/
├─ ratios/
├─ revenue_history/
├─ market_cap_history/
└─ dividend_history/
```

### Règle actuelle
La v1 historique Python exploite uniquement :
- `ratios` annuel
- `income_statement` annuel
- `cash_flow_statement` annuel

Pourquoi :
- c’est suffisant pour un premier scoring multi-périodes robuste,
- cela limite la complexité,
- cela évite de surcharger `main.py` et `score.py` trop tôt.

### Datasets disponibles mais pas encore pleinement exploités
- `balance_sheet`
- `revenue_history`
- `market_cap_history`
- `dividend_history`
- les versions trimestrielles

Ces jeux restent très utiles pour les prochaines itérations.

---

## Google Apps Script historique

Le second script `stockanalysis_history.gs` sert à exporter les historiques ciblés par ticker.

### Frontière de responsabilité
- **Apps Script** : collecte et dépose du brut
- **Python** : normalise, agrège, score

### Point important
L’onglet `CandidateHistoryManifest` n’est pas encore la pièce la plus fiable du flux côté Google Sheets.
La vraie source utile pour Python est le contenu exporté sous Drive puis copié localement dans `data/stockanalysis_candidate_history/`.

---

## Gestion des données massives

Avec `stockanalysis_screener`, le volume de données augmente fortement.

### Conséquences
- impossible de raisonner uniquement en watchlist fixe,
- nécessité d’une couche screening dédiée,
- nécessité d’exports intermédiaires versionnés,
- nécessité d’un historique ciblé seulement pour les meilleurs candidats.

### Principe recommandé
- bulk export léger pour tout l’univers,
- historisation ciblée par ticker seulement pour les symboles retenus,
- éviter les fichiers monolithiques historiques non parsables.

---

## Journalisation

Les logs doivent permettre de comprendre :
- quel mode de sélection a été utilisé,
- combien de titres ont été filtrés puis retenus,
- quel provider a été utilisé,
- si l’enrichissement historique a été activé,
- où se situe un éventuel échec.

Exemples utiles :
- `INFO Starting pipeline`
- `INFO Screening produced ... candidates`
- `INFO Fetching fundamentals for ...`
- `INFO Validation fundamentals OK ...`
- `INFO Pipeline terminee avec succes ...`

---

## Gestion des erreurs

### Principes
- pas d’erreur silencieuse,
- messages explicites,
- distinction entre erreur bloquante et donnée partielle.

### Cas désormais importants
- export StockAnalysis absent,
- `selection.source` incohérente avec le provider fundamentals,
- présélection vide après application des filtres,
- ticker absent du CSV bulk,
- schéma du CSV bulk modifié,
- historique ticker absent ou partiel,
- nombre d’années insuffisant pour calculer certaines features.

---

## Configuration et secrets

### `.env`
Contient uniquement les secrets et tokens :
- `FMP_API_KEY`
- `MARKETDATA_API_TOKEN`

### `settings.yaml`
Contient :
- choix des providers,
- paramètres de sélection,
- seuils de scoring snapshot,
- seuils de scoring historique,
- chemins de fichiers,
- options d’export.

### `watchlist.yaml`
Contient désormais une shortlist manuelle ou un override humain, pas nécessairement la source primaire du pipeline.

---

## Tests

Le périmètre de test a évolué.

Tests actuels :
- `test_config.py`
- `test_fetch.py`
- `test_normalize.py`
- `test_score.py`
- `test_rank.py`
- `test_selection.py`
- `test_history.py`

### Nouveau point clé
`test_history.py` valide la construction des features historiques à partir d’un jeu minimal de fichiers annuels simulés.

### Commande recommandée

```bash
python3 -m pytest -q tests
```

Dernier état validé : **25 tests passants**.

---

## Évolution multi-provider

L’évolution future doit continuer à respecter cette règle :
- les providers divergent dans `fetch/`
- la cohérence est restaurée dans `transform/`
- l’enrichissement historique est concentré dans `history/`
- la logique métier reste stable dans `scoring/`
- la sélection est pilotée par `screening/`

Éviter absolument :

```python
if provider == "x":
    ...
elif provider == "y":
    ...
```

dans la logique métier centrale.

---

## Roadmap technique mise à jour

### Étape actuelle
- multi-provider opérationnel
- StockAnalysis screener intégré
- pipeline data-first opérationnel
- shortlist automatique fonctionnelle
- historique ciblé par ticker collecté via Apps Script
- scoring historique v1 intégré au pipeline Python

### Étape suivante probable
- enrichir les features historiques (marges, EPS, capital allocation)
- mieux séparer `screening score` et `investment score`
- améliorer la lisibilité des exports finaux de sous-scores historiques

### Étapes ultérieures
- SQLite / historisation structurée
- comparaison inter-runs
- dashboard
- CLI enrichie

---

## Règles pour modifier la sélection ou le scoring

Avant toute modification métier :
1. documenter la raison,
2. ajouter ou adapter un test,
3. vérifier l’impact sur quelques tickers connus,
4. préserver la lisibilité des seuils dans `settings.yaml`.

Si la logique métier change significativement, envisager de versionner le mode de scoring.

---

## Notes finales

Le projet n’est plus simplement un pipeline de score sur une petite watchlist.
Il devient progressivement un **moteur de présélection + scoring snapshot + scoring historique**.

Le risque principal n’est pas le manque de sophistication, mais la perte de lisibilité si :
- la sélection,
- le fetch,
- l’enrichissement historique,
- le scoring,
- et l’export
se mélangent trop.

La discipline d’architecture reste donc essentielle.
