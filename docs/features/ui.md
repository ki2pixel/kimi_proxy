# UI Module - Gestion Interface Utilisateur

## TL;DR
Module JavaScript centralisant la manipulation DOM, la gestion d'état des boutons UI et les mises à jour d'interface en temps réel pour le dashboard Kimi Proxy.

## Problème
L'interface utilisateur du dashboard nécessite une gestion d'état complexe des boutons selon les capacités des sessions actives, avec des mises à jour temps réel et une séparation claire entre logique métier et affichage.

## Architecture Modulaire
Le module UI fait partie de l'architecture frontend ES6 modules, dépendant des modules `utils.js`, `charts.js`, `sessions.js` et `modals.js`.

## Composants Principaux

### UIManager Class
Classe principale pour la gestion centralisée de l'état des boutons UI.

**Responsabilités :**
- Gestion de l'état des boutons selon capacités session
- Mise à jour temps réel des éléments d'interface
- Coordination avec les autres modules pour cohérence UI

**Méthodes clés :**
- `updateButtonStates(session)` - Met à jour tous les boutons selon session active
- `isCompactionSupported(session)` - Vérifie support compactage
- `isCompressionSupported(session)` - Vérifie support compression
- `isMemorySupported(session)` - Vérifie support fonctionnalités mémoire

### Fonctions d'Update UI
- `updateSessionDisplay(session)` - Met à jour affichage session courante
- `updateContextDisplay(metrics)` - Met à jour jauge et indicateurs contexte
- `updateProviderDisplay(provider)` - Met à jour affichage provider actif
- `updateModelDisplay(model)` - Met à jour affichage modèle actif

## Patterns Système Appliqués

### Pattern 1 - Séparation Responsabilités
```javascript
// ❌ Mauvaise approche - Logique métier mélangée à DOM
function updateUI(data) {
    document.getElementById('context').innerHTML = calculatePercentage(data);
    // Logique calcul directement dans UI
}

// ✅ Bonne approche - Séparation claire
import { calculateStats } from './sessions.js';

function updateContextDisplay(metrics) {
    const stats = calculateStats(metrics);
    document.getElementById('context').innerHTML = formatPercentage(stats.percentage);
}
```

### Pattern 2 - Event Bus Communication
```javascript
// Communication découplée entre modules
eventBus.on('sessionChanged', (session) => {
    uiManager.updateButtonStates(session);
    updateSessionDisplay(session);
});
```

## Gestion État Boutons

### États Dynamiques
Les boutons changent d'état selon :
- **Session active** : Présence d'une session en cours
- **Capacités session** : Support compactage, compression, mémoire
- **Contexte actuel** : Niveau remplissage (vert/jaune/rouge)
- **Permissions** : Droits d'accès aux fonctionnalités

### Transitions d'État
- **Enabled** → **Disabled** : Quand fonctionnalité non supportée
- **Visible** → **Hidden** : Quand session inactive
- **Normal** → **Warning** : Quand seuil critique atteint

## Intégration WebSocket

### Mises à Jour Temps Réel
```javascript
// Réception événements WebSocket
websocket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    switch(data.type) {
        case 'session_activated':
            updateSessionDisplay(data.session);
            break;
        case 'compaction_event':
            updateCompactionUI(data.compaction);
            break;
    }
};
```

## Métriques Performance

### Optimisations DOM
- **Batch updates** : Regroupement modifications DOM
- **Virtual DOM approach** : Comparaison état avant update
- **Lazy loading** : Chargement composants à la demande

### Métriques Actuelles
- **107 fonctions utilitaires** pour manipulation DOM
- **Complexité moyenne** : B (8-12)
- **Coverage événements** : 15+ types d'événements gérés

## Trade-offs

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Classe centralisée | Cohérence, maintenabilité | Complexité initiale |
| Modules séparés | Flexibilité, testabilité | Coordination requise |
| **Choix actuel** | **Équilibre maintenabilité** | **Overhead coordination** |

## Golden Rule
**Chaque changement d'état doit être propagé via UIManager pour garantir la cohérence de l'interface utilisateur.**

## Prochaines Évolutions
- [ ] Animation transitions d'état
- [ ] Thèmes dynamiques
- [ ] Accessibilité améliorée
- [ ] Tests E2E complets

---
*Dernière mise à jour : 2026-02-21*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*</content>
<parameter name="path">/home/kidpixel/kimi-proxy/docs/features/ui.md