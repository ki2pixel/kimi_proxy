---
name: kimi-proxy-frontend-architecture
description: Expert Frontend Vanilla JavaScript & WebSockets for Kimi Proxy Dashboard. Use when working with the real-time dashboard, ES6 modules, Chart.js visualizations, or WebSocket-based live updates. Covers modular frontend architecture and performance optimization.
license: Complete terms in LICENSE.txt
---

# Kimi Proxy Frontend Architecture

**TL;DR**: The current frontend is a vanilla ES6 module application centered on `static/js/main.js`, a lowercase `eventBus`, WebSocket-driven updates, and focused feature modules such as `sessions.js`, `websocket.js`, `memory-service.js`, `mcp.js`, and `compaction.js`. Document and extend the modules that actually ship; do not present optional example classes as if they were production components.

## Source of Truth

Current frontend behavior is primarily implemented in:

- `static/js/main.js`
- `static/js/modules/utils.js`
- `static/js/modules/api.js`
- `static/js/modules/sessions.js`
- `static/js/modules/websocket.js`
- `static/js/modules/ui.js`
- `static/js/modules/modals.js`
- `static/js/modules/charts.js`
- `static/js/modules/memory-service.js`
- `static/js/modules/mcp.js`
- `static/js/modules/auto-session.js`
- `static/js/modules/compaction.js`
- `static/js/modules/accessibility/modal-manager.js`

## Current Architecture

### ✅ Real module pattern

```javascript
// static/js/main.js
import { eventBus } from './modules/utils.js';
import { loadInitialData } from './modules/api.js';
import { WebSocketManager } from './modules/websocket.js';
import { getSessionManager } from './modules/sessions.js';
```

The event bus exported by the real codebase is `eventBus`, not `EventBus`.

### Real responsibilities by module

- `utils.js`: `eventBus`, formatting helpers, throttle/debounce, UI notifications
- `sessions.js`: session state, metrics state, session switching, memory metrics
- `websocket.js`: message routing from `/ws`, broadcast event translation
- `ui.js`: DOM updates, gauges, badges, alerts, log rendering hooks
- `memory-service.js`: WebSocket-backed compression/similarity workflows
- `mcp.js`: MCP dashboard state, server status, advanced memory stats
- `compaction.js`: auto-compaction polling and compaction UI actions

## Event Bus Integration

The frontend uses event-driven coordination instead of direct cross-module coupling.

### ✅ Real event names in current code

```javascript
import { eventBus } from './utils.js';

eventBus.emit('sessionChanged', { oldSession, newSession, proxyConfig: null });
eventBus.emit('memory:updated', memoryMetrics);
eventBus.emit('compaction:event', data);
eventBus.emit('notification:show', {
    message: 'Mémoire stockée avec succès',
    type: 'success'
});
```

Common integration points already in use:

- Session lifecycle: `sessionChanged`, `session:loaded`, `session:new`, `session:deleted`
- WebSocket state: `websocket:connected`, `websocket:disconnected`, `websocket:error`, `websocket:status`
- Metrics: `metric:received`, `metric:added`, `metric:updated`, `metrics:loaded`, `metrics:cleared`
- Memory / MCP: `memory:updated`, `memory:compress:show`, `memory:similarity:show`, `mcp:statusUpdate`
- Compaction: `compaction:event`, `compaction:alert`, `compaction:auto_toggled`

## WebSocket Architecture

`static/js/modules/websocket.js` is the real WebSocket integration point.

It translates incoming backend messages into frontend events, including:

- metric updates
- memory metrics updates
- compaction events and alerts
- auto-session / session lifecycle events
- similarity results and Cline usage refreshes

When documenting or extending WebSocket behavior, prefer the current `WebSocketManager` flow over hypothetical wrapper classes.

## SessionManager Notes

### `updateProxyConfig()` is deprecated

`static/js/modules/sessions.js` still contains `SessionManager.updateProxyConfig()`, but it is explicitly deprecated.

```javascript
async updateProxyConfig(session) {
    console.warn('⚠️ [SessionManager] updateProxyConfig() est déprécié - le routing gère la configuration automatiquement');
}
```

Reason: backend routing now derives provider/model behavior automatically. New frontend code should not depend on explicit proxy reconfiguration calls.

## Mobile and Responsive Support

There is **no standalone `TouchUIManager` class in production code** today.

Current mobile/responsive behavior is handled through:

- responsive Chart.js configuration already embedded in chart modules
- DOM-level controls in `ui.js`
- modal accessibility helpers in `modules/accessibility/modal-manager.js`
- CSS/layout behavior from the dashboard shell

If a dedicated touch layer is added later, it should publish navigation or gesture events through `eventBus` rather than bypassing existing modules.

## Memory, MCP, and Compaction Integration

The current frontend is richer than the older skill version suggested.

### Memory flows

- `memory-service.js` emits WebSocket requests such as `memory_compress_preview`, `memory_compress_execute`, and `memory_similarity_search`
- `main.js` wires memory modal events and memory store UX
- `mcp.js` renders MCP status, frequent memories, and advanced stats panels

### Compaction flows

- `main.js` starts compaction polling
- `websocket.js` handles `compaction_event`, `compaction_alert`, and `auto_compaction_toggled`
- `api.js` exposes session-level compaction endpoints for stats, history, preview, and auto-toggle

## Security and Coding Standards

Frontend changes must stay compatible with the project rules:

- ES6 modules only
- vanilla JS only
- named exports only
- prefer `textContent`, DOM APIs, and escaped content for new UI work
- do not introduce fresh `innerHTML`-heavy patterns without careful review

### ❌ Avoid documenting optional example classes as current architecture

- `RobustWebSocketManager`
- `StreamingChartManager`
- `ResponsiveChartManager`
- `TouchUIManager`

These are acceptable idea patterns for future work; they are not the current production abstraction layer.

## Golden Rule

**Document the modules, event names, and deprecations that actually exist in `static/js` today.** If you add a new frontend abstraction, wire it through `eventBus` and update this skill only after the code lands.