# WebSocket Manager - Communication Temps Réel

## TL;DR
Module JavaScript centralisant la gestion WebSocket avec reconnexion automatique, filtrage par session et routage d'événements pour le dashboard temps réel Kimi Proxy.

## Problème
L'interface utilisateur nécessite des mises à jour temps réel pour afficher les métriques, alertes et changements de session sans rechargement de page, créant une complexité de synchronisation entre serveur et client.

## Architecture Modulaire
Le WebSocketManager fait partie de l'architecture frontend ES6 modules, dépendant des modules `utils.js`, `sessions.js` et communiquant via `eventBus`.

```
WebSocketManager ← eventBus ← Autres Modules (Charts, UI, Sessions)
```

## WebSocketManager Class
Classe principale pour la gestion centralisée des connexions WebSocket avec fonctionnalités avancées.

**Responsabilités :**
- Gestion de la connexion WebSocket avec reconnexion automatique
- Filtrage des messages par session active
- Queue des messages en cas de déconnexion
- Routage des événements vers les modules appropriés
- Gestion des métriques temps réel (proxy, logs, mémoire)

**Méthodes principales :**
- `connect()` - Établit la connexion WebSocket
- `disconnect()` - Ferme proprement la connexion
- `sendMessage(message)` - Envoie un message via WebSocket
- `setActiveSessionId(sessionId)` - Définit la session active pour filtrage
- `handleMessage(data)` - Route les messages entrants

## Gestion de Connexion

### ❌ Approche Naïve
```javascript
const ws = new WebSocket(url);
ws.onmessage = (event) => {
    // Logique directement dans le handler
    updateUI(JSON.parse(event.data));
};
```

### ✅ Approche WebSocketManager
```javascript
const wsManager = getWebSocketManager();
wsManager.connect();

// Les modules écoutent les événements
eventBus.on('metric:received', (metric) => {
    updateCharts(metric);
    updateUI(metric);
});
```

## Filtrage par Session
Le WebSocketManager filtre automatiquement les messages pour ne traiter que ceux de la session active, évitant les conflits entre onglets ou utilisateurs multiples.

```javascript
// Dans handleMessage
if (data.session_id && data.session_id !== this.activeSessionId) {
    console.log(`🚫 Message ignoré (session différente)`);
    return;
}
```

## Types de Messages Gérés
- `metric` - Métriques proxy temps réel
- `log_metric` - Métriques logs PyCharm/Continue
- `new_session` - Notification création session
- `memory_metrics_update` - Mise à jour métriques mémoire MCP
- `compression_event` - Événements compression
- `compaction_event` - Événements compaction
- `auto_session_created` - Création auto-session

## Patterns Système Appliqués
- **Pattern 1** : Architecture modulaire ES6 avec séparation des responsabilités
- **Pattern 2** : Communication via eventBus pour découplage
- **Pattern 14** : Gestion asynchrone des événements WebSocket

## Métriques Performance
- **Reconnexion automatique** : 3 secondes après déconnexion
- **Queue de messages** : Stockage des messages en attente de reconnexion
- **Filtrage session** : Traitement sélectif des messages
- **Types d'événements** : 15+ types d'événements routés

## Trade-offs
| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Classe centralisée | Cohérence, maintenabilité | Complexité initiale |
| eventBus global | Découplage, flexibilité | Debugging plus complexe |
| **Choix actuel** | **Temps réel robuste** | **Overhead coordination** |

## Golden Rule
**Tout message WebSocket doit être routé via WebSocketManager pour garantir le filtrage par session et la cohérence des événements temps réel.**

## Prochaines Évolutions
- [ ] Compression des messages WebSocket
- [ ] Authentification WebSocket
- [ ] Métriques de performance connexion
- [ ] Support WebRTC pour peer-to-peer

---
*Dernière mise à jour : 2026-02-22*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*