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

## Métriques Actuelles (2026-02-19)

### Volumétrie Code Source
- **69 fichiers Python** analysés
- **7,336 lignes de code** (hors commentaires/vides)
- **Complexité moyenne** : C (16.93)

### Distribution par Couche
| Couche | Fichiers | LOC | Complexité Moyenne |
| ------ | --------- | --- | ---------------- |
| Core | 8 | ~1,200 | B |
| Features | 15 | ~2,100 | C |
| Proxy | 6 | ~800 | D |
| Services | 4 | ~600 | B |
| API | 36 | ~2,636 | C |

### Points Chauds Identifiés
- **proxy_chat()** (API) : Score F - gestion multi-provider + streaming
- **_proxy_to_provider()** (API) : Score D - 311 LOC routing
- **_extract_standard_metrics()** (Features) : Score D - parsing robuste
- **_parse_compile_chat_block()** (Features) : Score C - parsing PyCharm

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
