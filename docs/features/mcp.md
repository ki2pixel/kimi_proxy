# MCP Module - Gestion Serveurs MCP Phase 3 & Phase 4

## TL;DR
Module JavaScript orchestrant l'interface frontend pour les fonctionnalités MCP avancées, gérant les serveurs MCP externes avec monitoring temps réel, recherche sémantique, compression et stockage mémoire standardisé.

## Problème
L'application nécessite une interface unifiée pour interagir avec les serveurs MCP externes, avec monitoring d'état et gestion d'erreurs.

## Architecture

### Phase 3 - Serveurs dans le Proxy
- **Qdrant MCP**: Recherche sémantique et clustering
- **Context Compression MCP**: Compression contextuelle
- **Emplacement**: Serveurs intégrés au proxy Kimi

### Phase 4 - Serveurs dans Continue.dev
- **Task Master MCP**: Gestion de tâches (14 outils)
- **Sequential Thinking MCP**: Raisonnement séquentiel (1 outil)
- **Fast Filesystem MCP**: Opérations fichiers (25 outils)
- **JSON Query MCP**: Requêtes JSON (3 outils)
- **Emplacement**: Serveurs locaux dans Continue.dev (processus séparés)

## Composants Principaux

### État Global MCP
Gestion centralisée de l'état des serveurs MCP actifs.

**Structure d'état :**
```javascript
let mcpState = {
    servers: [],           // Tous serveurs (Phase 3 + 4)
    phase3Servers: [],     // Qdrant, Context Compression
    phase4Servers: [],     // Task Master, Sequential Thinking, Fast Filesystem, JSON Query
    allConnected: false,
    connectedCount: 0,
    totalCount: 0,
    lastCheck: null,
    memoryStats: null,
    frequentMemories: [],
    isLoading: false
};
```

**Serveurs gérés :**
- **Phase 3 (Proxy intégré)**: 2 serveurs, fonctionnalités mémoire
- **Phase 4 (Continue.dev)**: 4 serveurs, outils avancés dans IDE
- **Total**: Interface unifiée pour tous les serveurs MCP

### API Operations
Fonctions pour toutes les opérations MCP via backend.

**Statuts serveurs :**
```javascript
async function fetchServerStatuses() {
    // Récupère statuts Phase 3 + Phase 4
    // Fallback vers anciens endpoints si nécessaire
    // Émission événement statusUpdate
}
```

**Recherche et compression :**
```javascript
async function searchSimilar(query, limit = 5, scoreThreshold = 0.7)
async function compressContent(content, algorithm, targetRatio)
async function storeMemory(sessionId, content, memoryType, metadata)
```

**Statistiques mémoire :**
```javascript
async function fetchAdvancedMemoryStats(sessionId = null)
async function fetchFrequentMemories(sessionId, minAccessCount, limit)
```

### Rendu UI
Fonctions de rendu pour l'affichage des statuts et données MCP.

**Panneau statuts serveurs :**
```javascript
function renderMCPStatusPanel() {
    // Groupage par phase (P3/P4)
    // Indicateurs connexion temps réel
    // Badges nombre d'outils
}
```

**Mémoires fréquentes :**
```javascript
function renderFrequentMemoriesPanel() {
    // Cartes par type (frequent/episodic/semantic)
    // Métriques accès et tokens
    // Tri par fréquence utilisation
}
```

**Statistiques avancées :**
```javascript
function renderAdvancedStats() {
    // KPIs: mémoires totales, tokens stockés
    // Compteurs par type
    // Indicateurs fonctionnalités (Qdrant, Compression)
}
```

## Patterns Système Appliqués

### Pattern 1 - État Centralisé avec Events
Communication découplée via eventBus pour cohérence UI :
```javascript
// Mise à jour état → Émission événement → Rendu automatique
mcpState.servers = response.all;
eventBus.emit('mcp:statusUpdate', mcpState);

// Modules UI s'abonnent automatiquement
eventBus.on('mcp:statusUpdate', renderMCPStatusPanel);
```

### Pattern 2 - Fallback API Progressif
Migration douce vers nouveaux endpoints :
```javascript
try {
    // Nouvel endpoint unifié
    return await apiRequest('/api/memory/all-servers');
} catch (error) {
    // Fallback vers endpoint Phase 3 seulement
    return await apiRequest('/api/memory/servers');
}
```

### Pattern 3 - Refresh Périodique
Monitoring continu avec throttling :
```javascript
setInterval(() => {
    fetchServerStatuses();
    fetchAdvancedMemoryStats(sessionId);
    fetchFrequentMemories(sessionId);
}, 30000); // 30 secondes
```

## Gestion Erreurs et Résilience

### Gestion Erreurs API
Chaque fonction API wrappée avec gestion d'erreurs :
```javascript
async function searchSimilar(query, limit, scoreThreshold) {
    try {
        const response = await apiRequest('/api/memory/similarity', {
            method: 'POST',
            body: JSON.stringify({ query, limit, score_threshold: scoreThreshold })
        });
        return response;
    } catch (error) {
        console.error('❌ Erreur recherche sémantique:', error);
        return { results: [], results_count: 0 }; // Valeur par défaut
    }
}
```

### Indicateurs Visuels d'État
Rendu conditionnel selon statut connexion :
```javascript
const statusColor = server.connected ? 'text-emerald-400' : 'text-rose-400';
const statusIcon = server.connected ? 'check-circle' : 'x-circle';
const latencyText = server.connected ? `${server.latency_ms.toFixed(0)}ms` : 'N/A';
```

## Métriques Performance

### Métriques Actuelles
- **43 outils MCP** exposés via 4 serveurs Phase 4
- **6 serveurs** monitorés (Phase 3 + 4)
- **30 secondes** intervalle refresh
- **Complexité moyenne** : C (11-15)

### Optimisations
- **Lazy loading** : Données chargées à la demande
- **Cache implicite** : État local évite rechargements inutiles
- **Batch updates** : Rendu groupé pour performance UI
- **Error boundaries** : Échecs isolés n'arrêtent pas l'ensemble

## Trade-offs

| Approche | Avantages | Inconvénants |
|----------|-----------|---------------|
| Monitoring temps réel | Visibilité immédiate | Trafic réseau continu |
| État centralisé | Cohérence garantie | Complexité synchronisation |
| **Choix actuel** | **Monitoring complet** | **Overhead réseau modéré** |

## Golden Rule
**Chaque opération MCP doit émettre un événement approprié pour permettre aux modules UI de se mettre à jour automatiquement sans couplage direct.**

## Prochaines Évolutions
- [ ] Streaming temps réel pour gros volumes
- [ ] Cache localStorage pour statuts
- [ ] Alertes configurables par serveur
- [ ] Métriques performance par outil
- [ ] Support serveurs MCP dynamiques

---
*Dernière mise à jour : 2026-02-21*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*</content>
<parameter name="path">/home/kidpixel/kimi-proxy/docs/features/mcp.md