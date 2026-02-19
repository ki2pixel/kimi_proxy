---
name: kimi-proxy-frontend-architecture
description: Expert Frontend Vanilla JavaScript & WebSockets for Kimi Proxy Dashboard. Use when working with the real-time dashboard, ES6 modules, Chart.js visualizations, or WebSocket-based live updates. Covers modular frontend architecture and performance optimization.
license: Complete terms in LICENSE.txt
alwaysApply: false
---

# Kimi Proxy Frontend Architecture

This skill provides comprehensive frontend development guidance for Kimi Proxy Dashboard.

## ES6 Modular Architecture

### Module Structure

```
static/js/
├── main.js              # Entry point, orchestration
└── modules/
    ├── utils.js         # Event bus, utilities
    ├── api.js           # API client, HTTP requests
    ├── charts.js        # Chart.js integration
    ├── sessions.js      # Session state management
    ├── websocket.js     # WebSocket connection
    ├── ui.js            # DOM manipulation, cache
    ├── modals.js        # Modal management
    └── compaction.js    # Compaction features
```

### Event Bus Pattern

```javascript
// modules/utils.js - Central event coordination
export const EventBus = {
    events: new Map(),
    
    on(event, callback) {
        if (!this.events.has(event)) {
            this.events.set(event, new Set());
        }
        this.events.get(event).add(callback);
    },
    
    emit(event, data) {
        if (this.events.has(event)) {
            this.events.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Event handler error for ${event}:`, error);
                }
            });
        }
    },
    
    off(event, callback) {
        if (this.events.has(event)) {
            this.events.get(event).delete(callback);
        }
    }
};

// Usage in modules
EventBus.emit('sessionCreated', sessionData);
EventBus.on('metricUpdate', (data) => updateChart(data));
```

### Module Import Pattern

```javascript
// main.js - Module orchestration
import { EventBus } from './modules/utils.js';
import { API } from './modules/api.js';
import { WebSocketManager } from './modules/websocket.js';
import { ChartManager } from './modules/charts.js';
import { UIManager } from './modules/ui.js';

class Dashboard {
    constructor() {
        this.initializeModules();
        this.setupEventListeners();
    }
    
    initializeModules() {
        this.api = new API();
        this.ws = new WebSocketManager();
        this.charts = new ChartManager();
        this.ui = new UIManager();
    }
    
    setupEventListeners() {
        EventBus.on('sessionCreated', (session) => {
            this.ui.updateSessionDisplay(session);
            this.charts.addSession(session);
        });
        
        EventBus.on('metricUpdate', (metric) => {
            this.charts.updateMetrics(metric);
            this.ui.updateGauge(metric.total_tokens);
        });
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
```

## WebSocket Integration

### Real-time Updates

```javascript
// modules/websocket.js
export class WebSocketManager {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
    }
    
    async connect() {
        try {
            this.ws = new WebSocket(`ws://${window.location.host}/ws`);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                EventBus.emit('websocketConnected');
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                EventBus.emit('websocketError', error);
            };
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.scheduleReconnect();
        }
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'metric':
                EventBus.emit('metricUpdate', data.data);
                break;
            case 'session':
                EventBus.emit('sessionUpdate', data.data);
                break;
            case 'alert':
                this.showAlert(data.data);
                break;
            default:
                console.warn('Unknown message type:', data.type);
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            setTimeout(() => {
                this.reconnectAttempts++;
                this.connect();
            }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts));
        }
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }
}
```

### Connection Management

```javascript
// Enhanced WebSocket with heartbeat
export class RobustWebSocketManager extends WebSocketManager {
    constructor() {
        super();
        this.heartbeatInterval = null;
        this.heartbeatTimeout = null;
    }
    
    onopen() {
        super.onopen();
        this.startHeartbeat();
    }
    
    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            this.send({ type: 'ping' });
            this.heartbeatTimeout = setTimeout(() => {
                console.warn('Heartbeat timeout, reconnecting...');
                this.ws.close();
            }, 5000);
        }, 30000);
    }
    
    handleMessage(data) {
        if (data.type === 'pong') {
            clearTimeout(this.heartbeatTimeout);
            return;
        }
        super.handleMessage(data);
    }
    
    onclose() {
        clearInterval(this.heartbeatInterval);
        clearTimeout(this.heartbeatTimeout);
        super.onclose();
    }
}
```

## Chart.js Integration

### Dynamic Charts

```javascript
// modules/charts.js
import { EventBus } from './utils.js';

export class ChartManager {
    constructor() {
        this.charts = new Map();
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            minute: 'HH:mm',
                            hour: 'HH:mm'
                        }
                    }
                }
            }
        };
    }
    
    createTokenChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                datasets: [{
                    label: 'Tokens par minute',
                    data: [],
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.1
                }]
            },
            options: {
                ...this.defaultOptions,
                scales: {
                    ...this.defaultOptions.scales,
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Tokens'
                        }
                    }
                }
            }
        });
        
        this.charts.set(canvasId, chart);
        return chart;
    }
    
    updateChart(chartId, newData) {
        const chart = this.charts.get(chartId);
        if (!chart) return;
        
        chart.data.datasets[0].data.push(...newData);
        
        // Keep only last 100 data points
        if (chart.data.datasets[0].data.length > 100) {
            chart.data.datasets[0].data = chart.data.datasets[0].data.slice(-100);
        }
        
        chart.update('none'); // No animation for real-time updates
    }
    
    createSourceDistributionChart(canvasId) {
        const ctx = document.getElementById(canvasId).getContext('2d');
        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Proxy', 'Logs', 'CompileChat', 'Erreur'],
                datasets: [{
                    data: [0, 0, 0, 0],
                    backgroundColor: [
                        'rgba(54, 162, 235, 0.8)',   // Blue
                        'rgba(34, 197, 94, 0.8)',    // Green  
                        'rgba(168, 85, 247, 0.8)',   // Purple
                        'rgba(239, 68, 68, 0.8)'     // Red
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
        
        this.charts.set(canvasId, chart);
        return chart;
    }
}
```

### Real-time Data Streaming

```javascript
// Efficient chart updates with throttling
export class StreamingChartManager extends ChartManager {
    constructor() {
        super();
        this.updateThrottle = 100; // ms
        this.pendingUpdates = new Map();
        this.updateTimer = null;
    }
    
    addDataPoint(chartId, timestamp, value, source = 'proxy') {
        if (!this.pendingUpdates.has(chartId)) {
            this.pendingUpdates.set(chartId, []);
        }
        
        this.pendingUpdates.get(chartId).push({
            x: timestamp,
            y: value,
            source: source
        });
        
        this.scheduleUpdate();
    }
    
    scheduleUpdate() {
        if (this.updateTimer) return;
        
        this.updateTimer = setTimeout(() => {
            this.flushUpdates();
            this.updateTimer = null;
        }, this.updateThrottle);
    }
    
    flushUpdates() {
        for (const [chartId, updates] of this.pendingUpdates) {
            const chart = this.charts.get(chartId);
            if (!chart) continue;
            
            // Batch update all pending points
            chart.data.datasets[0].data.push(...updates);
            
            // Limit data points
            if (chart.data.datasets[0].data.length > 200) {
                chart.data.datasets[0].data = chart.data.datasets[0].data.slice(-200);
            }
            
            chart.update('none');
        }
        
        this.pendingUpdates.clear();
    }
}
```

## API Client Architecture

### HTTP Client

```javascript
// modules/api.js
export class API {
    constructor() {
        this.baseURL = window.location.origin;
        this.cache = new Map();
        this.cacheTimeout = 30000; // 30 seconds
    }
    
    async request(endpoint, options = {}) {
        const cacheKey = `${endpoint}:${JSON.stringify(options)}`;
        
        // Check cache first
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }
        
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Cache successful responses
            this.cache.set(cacheKey, {
                data,
                timestamp: Date.now()
            });
            
            EventBus.emit('apiRequest', { endpoint, data });
            return data;
        } catch (error) {
            EventBus.emit('apiError', { endpoint, error });
            throw error;
        }
    }
    
    // Specific API methods
    async getSessions() {
        return this.request('/api/sessions');
    }
    
    async createSession(sessionData) {
        return this.request('/api/sessions', {
            method: 'POST',
            body: JSON.stringify(sessionData)
        });
    }
    
    async getActiveSession() {
        return this.request('/api/sessions/active');
    }
    
    async exportSession(format = 'csv') {
        return this.request(`/api/export/${format}`);
    }
    
    async getProviders() {
        return this.request('/api/providers');
    }
    
    async getMemoryStats() {
        return this.request('/api/memory/stats');
    }
}
```

### Error Handling

```javascript
// Robust error handling with retry
export class RobustAPI extends API {
    constructor() {
        super();
        this.maxRetries = 3;
        this.retryDelay = 1000;
    }
    
    async requestWithRetry(endpoint, options = {}, retryCount = 0) {
        try {
            return await this.request(endpoint, options);
        } catch (error) {
            if (retryCount >= this.maxRetries) {
                EventBus.emit('apiError', { endpoint, error, final: true });
                throw error;
            }
            
            // Don't retry on client errors
            if (error.message.includes('HTTP 4')) {
                throw error;
            }
            
            console.warn(`Retrying ${endpoint} (${retryCount + 1}/${this.maxRetries})`);
            await new Promise(resolve => setTimeout(resolve, this.retryDelay * (retryCount + 1)));
            
            return this.requestWithRetry(endpoint, options, retryCount + 1);
        }
    }
}
```

## UI Management

### DOM Caching

```javascript
// modules/ui.js
export class UIManager {
    constructor() {
        this.cache = new Map();
        this.throttleTime = 16; // ~60fps
        this.pendingUpdates = new Map();
    }
    
    cacheElement(selector) {
        const element = document.querySelector(selector);
        if (element && !this.cache.has(selector)) {
            this.cache.set(selector, element);
        }
        return element || this.cache.get(selector);
    }
    
    updateGauge(tokenCount, maxTokens = 262144) {
        const gauge = this.cacheElement('#context-gauge');
        if (!gauge) return;
        
        const percentage = (tokenCount / maxTokens) * 100;
        const color = this.getGaugeColor(percentage);
        
        // Throttle updates
        this.scheduleUpdate('gauge', () => {
            gauge.style.width = `${Math.min(percentage, 100)}%`;
            gauge.className = `gauge-fill ${color}`;
            gauge.setAttribute('aria-valuenow', percentage);
        });
    }
    
    getGaugeColor(percentage) {
        if (percentage < 70) return 'green';
        if (percentage < 85) return 'yellow';
        return 'red';
    }
    
    scheduleUpdate(key, updateFn) {
        if (!this.pendingUpdates.has(key)) {
            this.pendingUpdates.set(key, updateFn);
            requestAnimationFrame(() => {
                const fn = this.pendingUpdates.get(key);
                if (fn) {
                    fn();
                    this.pendingUpdates.delete(key);
                }
            });
        }
    }
    
    showNotification(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto-remove
        setTimeout(() => {
            notification.classList.add('notification-hiding');
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, duration);
    }
}
```

### Modal Management

```javascript
// modules/modals.js
export class ModalManager {
    constructor() {
        this.activeModal = null;
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                this.closeModal();
            }
        });
        
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-backdrop')) {
                this.closeModal();
            }
        });
    }
    
    showModal(content, options = {}) {
        if (this.activeModal) {
            this.closeModal();
        }
        
        const modal = document.createElement('div');
        modal.className = 'modal-backdrop';
        modal.innerHTML = `
            <div class="modal-content ${options.size || ''}">
                <div class="modal-header">
                    <h3>${options.title || ''}</h3>
                    <button class="modal-close" aria-label="Close">&times;</button>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        this.activeModal = modal;
        
        // Focus management
        const closeButton = modal.querySelector('.modal-close');
        closeButton?.focus();
        
        // Event listeners
        modal.querySelector('.modal-close').addEventListener('click', () => {
            this.closeModal();
        });
        
        return modal;
    }
    
    closeModal() {
        if (this.activeModal) {
            this.activeModal.classList.add('modal-hiding');
            setTimeout(() => {
                document.body.removeChild(this.activeModal);
                this.activeModal = null;
            }, 300);
        }
    }
}
```

## Performance Optimization

### Lazy Loading

```javascript
// Lazy load modules and components
class LazyDashboard {
    constructor() {
        this.loadedModules = new Set();
        this.intersectionObserver = new IntersectionObserver(
            this.handleIntersection.bind(this)
        );
    }
    
    async handleIntersection(entries) {
        for (const entry of entries) {
            if (entry.isIntersecting) {
                const moduleType = entry.target.dataset.module;
                if (!this.loadedModules.has(moduleType)) {
                    await this.loadModule(moduleType);
                    this.loadedModules.add(moduleType);
                }
            }
        }
    }
    
    async loadModule(type) {
        switch (type) {
            case 'charts':
                await import('./modules/charts.js');
                break;
            case 'advanced':
                await import('./modules/advanced.js');
                break;
        }
    }
}
```

### Memory Management

```javascript
// Prevent memory leaks in charts
export class MemoryEfficientChartManager extends ChartManager {
    constructor() {
        super();
        this.maxDataPoints = 100;
        this.cleanupInterval = setInterval(() => {
            this.cleanupOldCharts();
        }, 60000); // Every minute
    }
    
    createChart(canvasId, config) {
        const chart = super.createChart(canvasId, config);
        
        // Store chart reference for cleanup
        chart.canvasId = canvasId;
        chart.createdAt = Date.now();
        
        return chart;
    }
    
    cleanupOldCharts() {
        const now = Date.now();
        const maxAge = 300000; // 5 minutes
        
        for (const [canvasId, chart] of this.charts) {
            if (now - chart.createdAt > maxAge) {
                chart.destroy();
                this.charts.delete(canvasId);
            }
        }
    }
    
    destroy() {
        clearInterval(this.cleanupInterval);
        for (const chart of this.charts.values()) {
            chart.destroy();
        }
        this.charts.clear();
    }
}
```

## Responsive Design

### Mobile Optimization

```javascript
// Responsive chart configuration
export class ResponsiveChartManager extends ChartManager {
    constructor() {
        super();
        this.setupResponsiveHandlers();
    }
    
    setupResponsiveHandlers() {
        const resizeObserver = new ResizeObserver(
            this.handleResize.bind(this)
        );
        
        // Observe all chart containers
        document.querySelectorAll('.chart-container').forEach(container => {
            resizeObserver.observe(container);
        });
    }
    
    handleResize(entries) {
        for (const entry of entries) {
            const chart = this.charts.get(entry.target.querySelector('canvas').id);
            if (chart) {
                chart.resize();
            }
        }
    }
    
    getMobileOptions() {
        return {
            ...this.defaultOptions,
            plugins: {
                ...this.defaultOptions.plugins,
                legend: {
                    display: window.innerWidth > 768,
                    position: window.innerWidth > 768 ? 'top' : 'bottom'
                }
            },
            scales: {
                ...this.defaultOptions.scales,
                x: {
                    ...this.defaultOptions.scales.x,
                    ticks: {
                        maxTicksLimit: window.innerWidth > 768 ? 10 : 5
                    }
                }
            }
        };
    }
}
```

### Touch Support

```javascript
// Touch-friendly interactions
export class TouchUIManager extends UIManager {
    constructor() {
        super();
        this.setupTouchHandlers();
    }
    
    setupTouchHandlers() {
        let touchStartX = 0;
        let touchStartY = 0;
        
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
        });
        
        document.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            
            // Handle swipe gestures
            if (Math.abs(deltaX) > Math.abs(deltaY)) {
                if (deltaX > 50) {
                    this.handleSwipeRight();
                } else if (deltaX < -50) {
                    this.handleSwipeLeft();
                }
            }
        });
    }
    
    handleSwipeRight() {
        // Navigate to previous session/view
        EventBus.emit('navigatePrevious');
    }
    
    handleSwipeLeft() {
        // Navigate to next session/view
        EventBus.emit('navigateNext');
    }
}
```
