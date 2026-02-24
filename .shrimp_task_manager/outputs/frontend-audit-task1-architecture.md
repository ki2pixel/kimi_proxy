# Audit frontend - Task 1 - Architecture (ES6 modules, couplage, globals)

Scope: cartographier l'architecture actuelle sous static/js, identifier les points de couplage HTML<->JS (onclick, window.*), la coherence EventBus, et les duplications (scripts inline vs modules). Ce document ne propose pas de refactor immediat: il liste des constats et des recommandations de migration progressive.

## 1) Cartographie des modules (static/js/modules)

Source: arborescence static/js/modules (fast_get_directory_tree) et lecture des fichiers.

### Point d'entree
- static/js/main.js
  - Role: orchestration (initApp), initialisation des managers, branchement EventBus, exposition de fonctions globales pour le HTML.

### Utilitaires et contrats transverses
- static/js/modules/utils.js
  - Role: constantes (MAX_CONTEXT, WS_URL), EventBus (eventBus.on/off/emit), helpers (escapeHtml, debounce, throttle, formatters, showNotification).
  - Couplage: WS_URL depend de window.location.host.

### UI / rendu / DOM
- static/js/modules/ui.js
  - Role: cache d'elements DOM, mise a jour UI (updateDisplay/updateStats/renderLogs/addLogEntry), indicateurs source, alertes, statut WebSocket.
  - Dependances: utils.js (eventBus + helpers), charts.js (updateGauge/updateHistoryChart), sessions.js (state + calculs), modals.js (showMemoryModal), accessibility/live-announcer.js.

### Sessions / metriques / state
- static/js/modules/sessions.js
  - Role: gestion des sessions et metriques.
  - Observations:
    - Deux paradigmes coexistent:
      1) SessionManager (classe) + getSessionManager() (singleton module)
      2) variables globales module-scope "legacy" (currentSessionId, sessionMetrics, lastProxyData, lastLogData, currentMaxContext, currentMemoryMetrics)

### WebSocket temps reel
- static/js/modules/websocket.js
  - Role: WebSocketManager (connexion, reconnexion, parsing, routage par type, filtrage par session_id), emission d'evenements EventBus.
  - Dependances: utils.js (WS_URL/eventBus/showNotification), sessions.js (getCurrentSessionId/addMetric/setLastProxyData/setLastLogData/...)

### Graphiques
- static/js/modules/charts.js
  - Role: ChartManager (gauge/history/compaction), destruction, gestion de contexte session.
  - Contrainte: Chart.js est charge globalement via CDN (index.html -> chart.umd.min.js). Aucun import ES6 de Chart.

### Modales
- static/js/modules/modals.js
  - Role: modales "Nouvelle session", modales memoire (compression/similarite), modales compaction preview/result.
  - Dependances: api.js, utils.js, sessions.js, charts.js, memory-service.js, similarity-chart.js, accessibility/modal-manager.js.
  - Couplage notable: generation HTML par templates (strings) + insertion (innerHTML/insertAdjacentHTML) pour des sections importantes.

### MCP status / memoire
- static/js/modules/mcp.js
  - Role: recuperation statuts MCP Phase 3/4, stats avancees, memoires frequentes, appels similarity/compress/store.
  - Dependances: api.js (apiRequest), utils.js (eventBus/throttle).
  - Couplage notable: setInterval 30s, et usage de window.currentSessionId (non observe comme etant defini dans les fichiers lus).

### Services memoire
- static/js/modules/memory-service.js
  - Role: services WebSocket (preview/execute compression, similarite) avec correlation requestId->Promise, cache LRU (similarite).
  - Dependances: utils.js (eventBus).

### Auto-session
- static/js/modules/auto-session.js
  - Role: toggle auto-session, persistance localStorage, event handlers.
  - Couplage: exposition globale window.toggleAutoSession via exposeAutoSessionGlobals().

### Accessibilite
- static/js/modules/accessibility/*
  - Role: focus trap modal, live announcer, dropdown manager.
  - Exemple: accessibility/modal-manager.js appelle window.closeNewSessionModal / window.closeCompactPreviewModal / window.closeCompactResultModal sur Escape.

## 2) Graphe de dependances simplifie

Source: rg '^import ' sous static/js/*.js.

- main.js
  -> modules/utils.js
  -> modules/api.js
  -> modules/charts.js
  -> modules/sessions.js
  -> modules/websocket.js
  -> modules/ui.js
  -> modules/modals.js
  -> modules/compaction.js
  -> modules/mcp.js
  -> modules/auto-session.js
  -> modules/accessibility/dropdown-manager.js

- modules/ui.js
  -> modules/utils.js
  -> modules/charts.js
  -> modules/sessions.js
  -> modules/modals.js
  -> modules/accessibility/live-announcer.js

- modules/websocket.js
  -> modules/utils.js
  -> modules/sessions.js

- modules/modals.js
  -> modules/api.js
  -> modules/utils.js
  -> modules/sessions.js
  -> modules/charts.js
  -> modules/memory-service.js
  -> modules/similarity-chart.js
  -> modules/accessibility/modal-manager.js

- modules/compaction.js
  -> modules/api.js
  -> modules/utils.js
  -> modules/charts.js
  -> modules/sessions.js

- modules/mcp.js
  -> modules/utils.js
  -> modules/api.js

- modules/sessions.js
  -> modules/api.js
  -> modules/utils.js

- modules/charts.js
  -> modules/utils.js

- modules/memory-service.js
  -> modules/utils.js

- modules/auto-session.js
  -> modules/api.js
  -> modules/utils.js

Note: ce graphe confirme un noyau de dependances centralise sur utils.js (EventBus + helpers).

## 3) Couplage HTML <-> JS (onclick, window.*)

### 3.1 Attributs inline (onclick/oninput/onkeypress)

Source: rg "on(click|input|change|keypress)=" dans static/*.html.

- static/index.html contient de nombreux onclick/oninput/onkeypress (exemples):
  - onclick="toggleSessionSelector()"
  - onclick="showCompactPreviewModal()"
  - onclick="toggleAutoSession()"
  - onclick="showNewSessionModal()"
  - oninput="filterModels(this.value)"
  - onclick="createNewSessionWithProvider()"
  - onclick="refreshMCPStatus()"
  - onclick="window.showMemoryModal('similarity')" / "window.showMemoryModal('compress')"
  - onclick="showMemoryStoreModal()"
  - onkeypress="if(event.key==='Enter') executeMCPSearch()"
  - onclick="executeMCPSearch()"
  - onclick="executeMCPCompression()"
  - onclick="executeStoreMemory()"

- static/memory-section.html contient aussi du onclick lie a eventBus et aux modales.

Impact architecture:
- Necessite d'exposer une surface globale window.* ou des fonctions globales, reduit la modularite.
- Rend la migration CSP plus difficile (scripts inline et handlers inline).

### 3.2 Exposition via window.*

Source: rg '\bwindow\.' dans static/js.

- static/js/main.js expose un grand nombre de fonctions (exposeGlobals):
  - window.showNewSessionModal / window.closeNewSessionModal / window.createNewSessionWithProvider
  - window.showCompactPreviewModal / window.closeCompactPreviewModal / window.closeCompactResultModal / window.executeCompaction / window.toggleAutoCompaction
  - window.exportData
  - window.clearLogs
  - window.toggleSelectAll / window.updateBulkDeleteButton / window.deleteSelectedSessions / window.deleteSession
  - window.refreshMCPStatus
  - window.searchSimilar / window.compressContent (wrappers dynamiques import('./modules/mcp.js'))
  - window.showMemoryModal / window.hideMemoryModal
  - window.showMemoryStoreModal / window.closeMemoryStoreModal / window.executeStoreMemory
  - window.toggleSessionSelector

- static/js/modules/modals.js expose aussi:
  - window.selectModel, window.filterModels, window.showMemoryModal

- static/js/modules/auto-session.js expose:
  - window.toggleAutoSession

- static/js/modules/accessibility/modal-manager.js depend explicitement de window.closeNewSessionModal / closeCompactPreviewModal / closeCompactResultModal.

Impact architecture:
- L'API publique du frontend n'est pas formalisee (pas de "namespace" unique ni de contrat de stabilite).
- Risque de collisions et d'incoherence (plusieurs modules exposent des fonctions proches).

## 4) Duplications et sources de verite multiples

### 4.1 Modale "Mémoriser": duplication index.html vs main.js

Source: rg showMemoryStoreModal/executeStoreMemory.
- static/index.html definit showMemoryStoreModal(), closeMemoryStoreModal(), executeStoreMemory() dans un <script> inline.
- static/js/main.js definit aussi showMemoryStoreModal(), closeMemoryStoreModal(), executeStoreMemory(), puis les expose via window.*.

Risque:
- Divergence de comportements (deux implementations paralleles).
- Debug difficile (quelle version est appelee depend de l'ordre de chargement et du scope global).

### 4.2 MCP search/compress: logique UI inline dans index.html

- static/index.html definit executeMCPSearch() et executeMCPCompression() inline.
- main.js expose window.searchSimilar/window.compressContent comme wrappers de modules/mcp.js.

Risque:
- Frontiere floue entre "UI" et "service": index.html gere le rendu (templates HTML) et les erreurs; mcp.js gere appels API + rendu partiel (innerHTML genere).

### 4.3 Export: duplication api.js vs main.js

- modules/api.js fournit exportData(format).
- main.js implemente exportData(format) aussi.

Risque:
- Divergence et duplication d'erreurs/notifications.

## 5) Conformite aux standards internes (constats architecture)

Standards pertinents (codingstandards.md): Vanilla JS, ES6 modules, EventBus, eviter global state, pas d'export default.

Conformites observees:
- ES6 modules: imports/exports nommes largement utilises.
- EventBus present et central (modules/utils.js) et utilise pour decoupler la plupart des flux (WS -> UI, session, alerts).
- Separation de modules: api/websocket/sessions/ui/charts/modals existent.

Ecarts / points a surveiller:
- Usage intensif de window.* et de handlers inline dans HTML (couplage fort).
- Presence de "singletons" module-scope (getUIManager/getChartManager/getWebSocketManager/getSessionManager/getModalManager) et d'etat module-scope legacy (sessions.js). Cela correspond a du "global state" au sens du navigateur.
- Scripts inline dans index.html (executeMCPSearch/executeMCPCompression/showMemoryStoreModal/etc.) introduisent une deuxieme couche de logique applicative hors modules.

## 6) Recommandations priorisees (migration progressive)

P0 (risque eleve / dette structurante)
1) Eliminer les sources de verite multiples (index.html inline vs main.js/modules):
   - Choisir une seule implementation pour showMemoryStoreModal/executeStoreMemory (idealement dans un module), et supprimer l'autre.
   - Deplacer executeMCPSearch/executeMCPCompression vers un module UI (et attacher les events via addEventListener).
2) Formaliser une API publique unique pour l'UI (ex: window.KimiDashboard = {...}) au lieu de multiples window.*.
   - Objectif: minimiser collisions, clarifier la retro-compatibilite.

P1 (maintenabilite)
3) Unifier les appels HTTP via modules/api.js (apiRequest + fonctions specialisees) et supprimer les fetch() dupliques.
4) Clarifier le modele de state sessions:
   - Migrer progressivement vers SessionManager (classe) OU consolider legacy state, mais eviter le mix durable.

P2 (qualite et extensibilite)
5) EventBus: considerer une structure Map + fonctions utilitaires (once, clear), et outillage (liste des events) pour eviter accumulation de handlers.
6) Encapsuler les "managers" avec un cycle de vie explicite (init/destroy) et limiter les singletons si possible.

## 7) Annexes - preuves rapides

- main.js: exposition window.* (rg window. -> main.js:299-346, 497+).
- modals.js: exposition window.selectModel/filterModels/showMemoryModal (vers la fin, initModalListeners()).
- index.html: handlers inline et scripts inline (executeMCPSearch/executeMCPCompression/showMemoryStoreModal/executeStoreMemory).
- accessibility/modal-manager.js: depend de window.closeNewSessionModal etc.
