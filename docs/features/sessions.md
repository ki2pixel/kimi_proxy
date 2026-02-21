# Sessions Module - Gestion des Sessions et Métriques

## TL;DR
Module JavaScript centralisant la gestion des sessions LLM, métriques de tokens temps réel, et fusion intelligente des sources de données (proxy/logs) pour le dashboard Kimi Proxy.

## Problème
L'application nécessite une gestion d'état complexe des sessions avec métriques temps réel, fusion de sources de données multiples, et calculs statistiques pour l'affichage du dashboard.

## Architecture Modulaire
Le module sessions.js fait partie du cœur métier frontend, dépendant des modules `api.js` et `utils.js`, et servant de base de données en mémoire pour l'état global de l'application.

## Composants Principaux

### SessionManager Class
Classe principale pour la gestion centralisée des sessions et leur configuration proxy.

**Responsabilités :**
- Changement atomique de session avec rollback possible
- Configuration automatique du routage proxy par provider
- Cache des configurations proxy pour performance
- Extraction automatique du provider depuis les modèles

**Méthodes clés :**
- `switchSession(sessionId, existingMetrics)` - Changement de session atomique
- `loadSession(sessionId)` - Chargement session depuis API
- `updateProxyConfig(session)` - Configuration proxy pour session
- `extractProvider(model)` - Extraction provider depuis nom modèle

### Gestion Métriques Temps Réel
Système de métriques avec calcul de deltas et fusion de sources.

**Fonctionnalités :**
- Buffer circulaire de métriques (max 100 entrées)
- Calcul automatique des deltas de tokens (nouveau contenu)
- Mise à jour avec tokens réels post-traitement
- Détection du bruit token (ratio historique > 70%)

**Fonctions clés :**
- `addMetric(metric, sessionId)` - Ajout métrique avec calcul delta
- `updateMetricWithRealTokens(metricId, realTokens)` - Correction post-API
- `calculateTokenDelta(currentMetric)` - Calcul delta intelligent

### Fusion Sources de Données
Stratégie de fusion intelligente entre données proxy et logs.

**Priorité des sources :**
- `compile_chat`: 4 (Données officielles Continue.dev)
- `api_error`: 3 (Informations critiques)
- `proxy`: 2 (Données temps réel)
- `logs`: 1 (Données secondaires)

**Logique de fusion :**
```javascript
// Si les deux sources ont des données proches (< 20% diff), création hybride
if (diff / avg < 0.2 && diff > 100) {
    source = 'hybrid';
    bestData = { tokens: Math.max(proxyTokens, logTokens), ... };
}
```

### Calculs Statistiques
Fonctions de calcul pour KPIs du dashboard.

**Métriques calculées :**
- Nombre total de requêtes
- Tokens maximum/par requête
- Moyenne tokens/requête
- Total prompt/completion séparés
- Précision estimation Tiktoken vs réel

**Fonctions clés :**
- `calculateStats()` - Statistiques globales session
- `calculateAccuracy()` - Précision estimation tokens

## Patterns Système Appliqués

### Pattern 1 - Singleton pour SessionManager
```javascript
// Instance globale pour cohérence d'état
let sessionManagerInstance = null;

export function getSessionManager() {
    if (!sessionManagerInstance) {
        sessionManagerInstance = new SessionManager();
    }
    return sessionManagerInstance;
}
```

### Pattern 2 - Event-Driven Architecture
```javascript
// Propagation des changements via eventBus
eventBus.emit('sessionChanged', {
    oldSession: previousSession,
    newSession: newSession,
    proxyConfig: this.getProxyConfig(newSession)
});
```

### Pattern 3 - Cache LRU pour Configurations Proxy
```javascript
// Map avec nettoyage automatique
this.sessionProxyMap.set(session.id, routingConfig);

cleanupOldConfigs(maxHistory = 10) {
    if (this.sessionHistory.length > maxHistory) {
        const oldSessions = this.sessionHistory.splice(0, this.sessionHistory.length - maxHistory);
        oldSessions.forEach(session => this.sessionProxyMap.delete(session.id));
    }
}
```

## Gestion État Global

### Variables d'État Partagées
```javascript
let currentSessionId = null;
let sessionMetrics = [];
let currentMaxContext = 262144;
let currentMemoryMetrics = { memory_tokens: 0, chat_tokens: 0, ... };
```

### Getters/Setters Pattern
- `getCurrentSessionId()` / `setCurrentSessionId(id)`
- `getSessionMetrics()` / `addMetric(metric)`
- `getCurrentMaxContext()` / `setCurrentMaxContext(context)`

## Métriques Performance

### Optimisations
- **Buffer circulaire** : Limitation mémoire métriques (max 100)
- **Lazy loading** : Rechargement données à la demande
- **Cache proxy config** : Réutilisation configurations similaires
- **Calculs différés** : Deltas calculés seulement si nécessaire

### Métriques Actuelles
- **45 fonctions utilitaires** pour gestion sessions/métriques
- **Complexité moyenne** : B (8-12)
- **Buffer métriques** : 100 entrées max avec rotation

## Trade-offs

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Instance globale | Cohérence, simplicité | Testabilité réduite |
| Cache local | Performance, offline | Synchronisation manuelle |
| **Choix actuel** | **Performance maintenabilité** | **Complexité état global** |

## Golden Rule
**Toute modification de session doit passer par SessionManager.switchSession() pour garantir la cohérence de l'état proxy et l'émission des événements appropriés.**

## Prochaines Évolutions
- [ ] Migration complète vers SessionManager (legacy cleanup)
- [ ] Persistence métriques localStorage
- [ ] Calculs statistiques temps réel
- [ ] Support sessions multi-utilisateurs

---
*Dernière mise à jour : 2026-02-21*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*</content>
<parameter name="path">/home/kidpixel/kimi-proxy/docs/features/sessions.md