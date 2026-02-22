# Charts Manager - Gestion des Graphiques

## TL;DR
Module JavaScript centralisant la gestion de tous les graphiques Chart.js avec filtrage par session, mise à jour temps réel et optimisation des performances pour le dashboard Kimi Proxy.

## Problème
L'interface utilisateur nécessite des graphiques multiples (jauge, historique, compaction) avec synchronisation temps réel et filtrage par session, créant une complexité de gestion d'état et de performances.

## Architecture Modulaire
Le ChartManager fait partie de l'architecture frontend ES6 modules, dépendant du module `utils.js` et communiquant via `eventBus`.

```
ChartManager ← eventBus ← WebSocketManager (mises à jour temps réel)
```

## ChartManager Class
Classe principale pour la gestion centralisée de tous les graphiques Chart.js avec fonctionnalités avancées.

**Responsabilités :**
- Initialisation et configuration des graphiques Chart.js
- Mise à jour temps réel des données avec filtrage par session
- Gestion des buffers de données et optimisation des performances
- Nettoyage automatique lors des changements de session
- Support de trois types de graphiques : jauge, historique, compaction

**Méthodes principales :**
- `initGauge()` - Initialise la jauge de pourcentage
- `initHistoryChart()` - Initialise le graphique d'historique
- `initCompactionChart()` - Initialise le graphique de compaction
- `updateGauge(percentage, sessionId)` - Met à jour la jauge
- `updateHistoryChart(sessionMetrics, sessionId)` - Met à jour l'historique
- `updateCompactionChart(chartData, sessionId)` - Met à jour le graphique de compaction
- `handleSessionChange(event)` - Gère les changements de session

## Types de Graphiques

### Jauge (Gauge Chart)
Graphique en demi-cercle affichant le pourcentage d'usage du contexte avec code couleur dynamique.

**Caractéristiques :**
- Type : Doughnut Chart
- Couleurs : Vert → Jaune → Rouge selon pourcentage
- Animation : Rotation fluide
- Cutout : 75% pour effet jauge

### Graphique Historique (History Chart)
Graphique linéaire affichant l'évolution des tokens sur les dernières requêtes.

**Caractéristiques :**
- 3 datasets : Total, Prompt, Completion
- Tension : 0.4 pour courbes lisses
- Limite : 20 points maximum
- Interaction : Mode index pour tooltips synchronisés

### Graphique Compaction (Compaction Chart)
Graphique en barres affichant les économies de tokens via compaction.

**Caractéristiques :**
- Type : Bar chart
- Couleur : Vert pour économies
- Border radius : 4px
- Responsive avec maintien des proportions

## Gestion des Sessions
Le ChartManager filtre automatiquement les mises à jour selon la session active, garantissant que chaque onglet affiche uniquement les données de sa session.

```javascript
// Filtrage automatique
if (sessionId && sessionId !== this.sessionContext) {
    return; // Ignore la mise à jour
}
```

## Optimisations Performance

### ❌ Approche Naïve
```javascript
// Mise à jour directe à chaque métrique
function updateChart(data) {
    chart.data.datasets[0].data.push(data);
    chart.update(); // Recalcule tout à chaque fois
}
```

### ✅ Approche ChartManager
```javascript
// Mise à jour optimisée avec animation 'none'
chart.data.datasets[0].data = newData;
chart.update('none'); // Animation optimisée
```

## Patterns Système Appliqués
- **Pattern 1** : Architecture modulaire ES6 avec séparation des responsabilités
- **Pattern 2** : Communication via eventBus pour découplage
- **Pattern 14** : Gestion asynchrone des mises à jour graphiques

## Métriques Performance
- **3 types de graphiques** gérés de manière centralisée
- **Filtrage session** automatique pour multi-utilisateurs
- **Buffers de données** pour optimisation mémoire
- **Nettoyage automatique** lors des changements de session

## Trade-offs
| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Classe centralisée | Cohérence visuelle, maintenabilité | Complexité initiale |
| Tree-shaking Chart.js | Bundle optimisé, performances | Configuration avancée requise |
| **Choix actuel** | **Graphiques temps réel optimisés** | **Overhead gestion état** |

## Golden Rule
**Toute mise à jour graphique doit passer par ChartManager pour garantir le filtrage par session et la cohérence visuelle.**

## Prochaines Évolutions
- [ ] Support graphiques additionnels (mémoire, latence)
- [ ] Export PNG/PDF des graphiques
- [ ] Animations avancées de transition
- [ ] Mode sombre/clair dynamique
- [ ] Tooltips personnalisés avec métriques détaillées

---
*Dernière mise à jour : 2026-02-22*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*