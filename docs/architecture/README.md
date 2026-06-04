# 🏛️ Architecture Système : Les Fondations Techniques

**TL;DR**: C'est comme une maison à 5 étages où chaque niveau a sa fonction - API pour accueillir, Services pour gérer, Features pour les fonctionnalités spéciales, Proxy pour router, et Core pour les fondations.

Cette section explique comment j'ai construit cette maison, pourquoi chaque étage est important, et comment ils communiquent entre eux.

## L'histoire de cette architecture

J'ai commencé avec un fichier monolithique de 3,073 lignes. C'était comme vivre dans un studio de 10m² - tout était mélangé, impossible à trouver quoi que ce soit, et chaque modification risquait de tout casser.

Après des mois de frustration, j'ai tout démantelé et reconstruit étage par étage. Le résultat? 52 fichiers organisés logiquement, chaque module ayant une seule responsabilité.

## Ce que vous trouverez ici

### [Architecture Modulaire v2.0](./modular-architecture-v2.md) ⭐ **Le cœur du système**
- Pourquoi j'ai tout démantelé
- Les 5 étages de la maison (API/Services/Features/Proxy/Core)
- Comment les modules communiquent
- Mes patterns préférés (Factory, Context Managers, DI)
- La migration qui m'a pris une semaine

### Cline (local) (import lecture seule)

Si tu utilises Cline en local, Kimi Proxy peut importer des métriques d’usage depuis un unique ledger allowlisté, puis les exposer via l’API et le dashboard.

- Doc feature : `docs/features/cline.md`
- Emplacement dans l’architecture 5 couches : voir la section “Feature exemple : Cline (local)” dans `modular-architecture-v2.md`

### [Système Proxy](./proxy-system.md)
- Comment le routage multi-provider fonctionne
- La gestion des clés API et sécurité
- La protection anti-boucle et injection headers

### [Schéma Base de Données](./database-schema.md)
- Les tables principales (sessions, metrics, providers)
- Les extensions Phase 2 (memory_metrics, compression_log)
- Comment les migrations fonctionnent

### [Endpoints API](./api-endpoints.md)
- L'API REST complète avec exemples
- Les WebSocket temps réel
- Les endpoints spécialisés (sanitizer, MCP, compression)

## Pourquoi cette structure?

### La règle d'or : Une seule raison de changer
Chaque module ne fait qu'une chose :
- `core/tokens.py` ne fait QUE compter des tokens
- `features/sanitizer.py` ne fait QUE masquer du contenu
- `proxy/router.py` ne fait QUE router vers les providers

Quand j'ai besoin de modifier quelque chose, je sais exactement où aller. Pas de chasse au trésor.

### Les dépendances contrôlées
```
Core peut importer personne
Config peut importer Core seulement
Features peuvent importer Core + Config
Proxy peut importer Core + Config
Services peuvent importer tout sauf API
API peut importer tout le monde
```

### Tests qui ont du sens
- Tests unitaires par module (rapides, isolés)
- Tests d'intégration entre modules
- Tests E2E pour les workflows complets

## L'analogie de la maison

Pensez à cette architecture comme une maison :

- **Rez-de-chaussée (API)** : La porte d'entrée, ce que voient les invités
- **1er étage (Services)** : Les pièces communes (salon, cuisine) partagées par tous
- **2ème étage (Features)** : Les chambres spécialisées, chacune avec sa fonction
- **3ème étage (Proxy)** : Le standard téléphonique qui connecte au monde extérieur
- **Fondations (Core)** : Ce qui supporte tout le reste, invisible mais essentiel

Chaque étage peut être rénové sans effondrer la maison. Je peux changer la décoration d'une chambre sans perturber le salon.

## Métriques Actuelles (2026-06-04)

### Volumétrie Code Source
- **87 fichiers Python** de production (dans `src/` et `scripts/`)
- **14 177 lignes de code** (hors commentaires/vides)
- **Complexité moyenne** : A (3.95)

### Distribution par Couche
| Couche | Fichiers | LOC | Complexité Moyenne |
| ------ | --------- | --- | ---------------- |
| Core | 7 | 1 632 | A (2.62) |
| Features | 45 | 6 587 | A (4.11) |
| Proxy | 9 | 1 468 | B (5.79) |
| Services | 4 | 252 | A (2.14) |
| API | 13 | 2 378 | A (4.24) |

### Points Chauds Identifiés
- **_proxy_to_provider()** (API/routes/proxy.py) : Score F (41) — routage et transformation des requêtes LLM
- **maybe_prune_jsonrpc_response()** (Features/mcp_tool_pruning/engine.py) : Score F (44) — analyse et élagage des réponses d'outils volumineuses
- **_tool_prune_text()** (Features/mcp_pruner/server.py) : Score E (40) — moteur algorithmique d'élagage de texte
- **reconstruct_complex_json()** (Proxy/tool_utils.py) : Score E (38) — réparation structurelle de JSON corrompus ou tronqués
- **fix_malformed_json_arguments()** (Proxy/tool_utils.py) : Score E (31) — normalisation d'arguments JSON mal formés

### Documentation Créée
- ✅ **proxy-layer.md** : Architecture couche proxy avec patterns système
- ✅ **log-watcher.md** : Monitoring temps réel PyCharm
- 📋 **Mise à jour README** : Intégration métriques actuelles

## Pour qui cette documentation?

- **Développeurs qui veulent contribuer** : Comprendre comment tout s'articule
- **Architectes logiciels** : Voir un exemple concret de modularisation
- **Moi-même dans 6 mois** : Me souvenir de pourquoi j'ai fait ces choix
- **Curieux techniques** : Comment on transforme un monolithe en architecture modulaire

---

*Navigation : [← Retour à l'index](../README.md) | [Architecture Modulaire →](./modular-architecture-v2.md)*
