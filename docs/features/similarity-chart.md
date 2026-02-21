# Similarity Chart Module - Visualisations Similarité Mémoire

## TL;DR
Module JavaScript spécialisé dans les visualisations Chart.js pour les résultats de recherche de similarité mémoire, avec rendu scatter plot interactif, distribution des scores, et codage couleur intelligent pour l'analyse visuelle des patterns MCP.

## Problème
Les résultats de recherche de similarité nécessitent des visualisations spécialisées pour comprendre les patterns de proximité sémantique, avec navigation interactive et codage visuel des scores de similarité.

## Architecture Modulaire
Le module similarity-chart.js constitue la couche visualisation pour les fonctionnalités mémoire avancées, dépendant de `utils.js` pour l'eventBus, et intégré aux modals de recherche de similarité.

## Composants Principaux

### SimilarityChartService Class
Service centralisé pour la gestion des graphiques de similarité.

**Responsabilités :**
- Création et destruction d'instances Chart.js
- Rendu scatter plot pour résultats individuels
- Rendu bar chart pour distribution des scores
- Codage couleur selon niveaux de similarité
- Nettoyage mémoire automatique

**Instance globale :**
```javascript
export const similarityChartService = new SimilarityChartService();
```

### Scatter Plot - Carte de Similarité
Visualisation interactive des résultats individuels :

**Configuration Chart.js :**
```javascript
this.chartInstance = new Chart(ctx, {
    type: 'scatter',
    data: {
        datasets: [{
            label: 'Score de Similarité',
            data: scatterData.map((mem, idx) => ({
                x: idx,
                y: mem.similarity_score,
                memory: mem,
                label: mem.title || `Mémoire ${idx + 1}`
            })),
            backgroundColor: data.map(point => getColorForScore(point.y)),
            borderColor: data.map(point => getBorderColorForScore(point.y)),
            pointRadius: 8,
            pointHoverRadius: 10
        }]
    }
});
```

**Codage Couleur :**
```javascript
getColorForScore(score) {
    if (score >= 0.9) return 'rgba(34, 197, 94, 0.8)';    // Vert - excellente
    if (score >= 0.8) return 'rgba(59, 130, 246, 0.8)';   // Bleu - bonne
    if (score >= 0.7) return 'rgba(251, 191, 36, 0.8)';   // Jaune - moyenne
    return 'rgba(239, 68, 68, 0.8)';                       // Rouge - faible
}
```

### Bar Chart - Distribution des Scores
Analyse statistique des résultats groupés :

**Calcul distribution :**
```javascript
calculateScoreDistribution(results) {
    const ranges = [
        { range: '0.9-1.0', min: 0.9, max: 1.0, label: '90-100%' },
        { range: '0.8-0.9', min: 0.8, max: 0.9, label: '80-90%' },
        { range: '0.7-0.8', min: 0.7, max: 0.8, label: '70-80%' },
        // ... autres plages
    ];
    
    return ranges.map(range => ({
        ...range,
        count: results.filter(r => 
            r.similarity_score >= range.min && 
            r.similarity_score < range.max
        ).length
    }));
}
```

### Tooltips Interactifs
Informations détaillées au survol :

**Configuration tooltips :**
```javascript
tooltip: {
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    callbacks: {
        title: (context) => point?.label || 'Mémoire inconnue',
        label: (context) => [
            `Score: ${(point.y * 100).toFixed(1)}%`,
            `ID: ${point.memory.id || 'N/A'}`,
            `Type: ${point.memory.type || 'inconnu'}`
        ],
        afterLabel: (context) => {
            const preview = point.memory.content_preview;
            return preview ? `Aperçu: ${preview.substring(0, 100)}...` : '';
        }
    }
}
```

## Gestion Performance

### Optimisations Mémoire
Nettoyage automatique des instances Chart.js :

```javascript
setupEventListeners() {
    eventBus.on('memory:similarity:hide', () => {
        this.destroyChart();
    });
    
    window.addEventListener('beforeunload', () => {
        this.destroyChart();
    });
}

destroyChart() {
    if (this.chartInstance) {
        this.chartInstance.destroy();
        this.chartInstance = null;
    }
}
```

### Mise à Jour Dynamique
Animation fluide pour updates de données :

```javascript
updateChart(results) {
    const scatterData = results.map((mem, idx) => ({
        x: idx, y: mem.similarity_score, memory: mem
    }));
    
    this.chartInstance.data.datasets[0].data = scatterData;
    // Update couleurs selon nouveaux scores
    this.chartInstance.data.datasets[0].backgroundColor = 
        scatterData.map(point => this.getColorForScore(point.y));
    
    this.chartInstance.update('active'); // Animation active
}
```

## Patterns Système Appliqués

### Pattern 1 - Singleton avec Convenience Exports
Accès simplifié aux fonctionnalités :

```javascript
// Instance globale
export const similarityChartService = new SimilarityChartService();

// Exports convenience
export function renderSimilarityChart(canvasId, results) {
    return similarityChartService.renderSimilarityChart(canvasId, results);
}
```

### Pattern 2 - Color Coding Sémantique
Représentation visuelle des niveaux de similarité :

```javascript
// Mapping sémantique : score → couleur → signification
0.9-1.0 → Vert    → Excellente similarité
0.8-0.9 → Bleu    → Bonne similarité  
0.7-0.8 → Jaune   → Similarité moyenne
0.6-0.7 → Orange  → Similarité faible
0.5-0.6 → Rouge   → Très faible
0.0-0.5 → Bordeaux → Quasi nulle
```

### Pattern 3 - Responsive Tooltips
Informations contextuelles adaptatives :

```javascript
// Tooltips qui s'adaptent au contenu disponible
title: (context) => point?.label || 'Mémoire inconnue',
label: (context) => [
    `Score: ${(point.y * 100).toFixed(1)}%`,
    `ID: ${point.memory.id || 'N/A'}`,
    `Type: ${point.memory.type || 'inconnu'}`
],
afterLabel: (context) => {
    const preview = point.memory.content_preview;
    return preview ? `Aperçu: ${preview.substring(0, 100)}...` : '';
}
```

## Gestion Erreurs et Résilience

### Validation Canvas
Vérification de la disponibilité du DOM :

```javascript
renderSimilarityChart(canvasId, results) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        console.error(`Canvas ${canvasId} non trouvé`);
        return;
    }
    
    this.destroyChart(); // Cleanup avant création
    // ... création chart
}
```

### Gestion Données
Validation des résultats avant rendu :

```javascript
renderSimilarityChart(canvasId, results) {
    // Validation implicite : results doit être array
    const scatterData = results.map((mem, idx) => ({
        x: idx,
        y: mem.similarity_score, // Suppose format correct
        memory: mem,
        label: mem.title || `Mémoire ${idx + 1}`
    }));
    // ... rendu
}
```

## Métriques Performance

### Métriques Actuelles
- **2 types de graphiques** : scatter + bar chart
- **6 niveaux de couleur** pour codage sémantique
- **Responsive tooltips** avec aperçu contenu
- **Memory cleanup** automatique

### Optimisations
- **Single instance** : Un seul chart actif à la fois
- **Lazy rendering** : Charts créés à la demande
- **Efficient updates** : Animation sélective
- **DOM validation** : Échec gracieux si canvas manquant

## Trade-offs

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Chart.js intégré | Flexibilité, écosystème | Taille bundle, dépendance |
| Canvas natif | Léger, contrôle total | Complexité développement |
| **Choix actuel** | **Rapidité développement** | **Overhead bibliothèque** |

## Golden Rule
**Chaque graphique de similarité doit utiliser un codage couleur sémantique cohérent pour permettre l'interprétation intuitive des niveaux de proximité sémantique.**

## Prochaines Évolutions
- [ ] Animation transitions entre datasets
- [ ] Clustering visuel des résultats similaires
- [ ] Export PNG/PDF des visualisations
- [ ] Mode comparaison côte à côte
- [ ] Intégration D3.js pour interactions avancées

---
*Dernière mise à jour : 2026-02-21*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*</content>
<parameter name="path">/home/kidpixel/kimi-proxy/docs/features/similarity-chart.md