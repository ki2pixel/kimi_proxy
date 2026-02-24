---
name: kimi-proxy-frontend-architecture
description: Real-time dashboard, ES6 modules, Chart.js, WebSocket architecture
---

# Kimi Proxy Frontend Architecture

## Overview

Modern frontend architecture for real-time dashboard with ES6 modules, Chart.js visualizations, and WebSocket connectivity.

## Core Architecture

### ES6 Modules Structure

```
static/js/
├── modules/
│   ├── ui.js           # UI management and DOM operations
│   ├── api.js          # API communication and data fetching
│   ├── websocket.js    # WebSocket connection management
│   ├── charts.js       # Chart.js visualizations
│   └── session.js      # Session data management
├── app.js              # Main application initialization
└── config.js           # Configuration constants
```

### Key Components

#### WebSocket Manager

```javascript
// modules/websocket.js
export class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.eventListeners = new Map();
    }

    connect() {
        return new Promise((resolve, reject) => {
            try {
                this.socket = new WebSocket(this.url);

                this.socket.onopen = () => {
                    console.log('WebSocket connected');
                    this.reconnectAttempts = 0;
                    resolve();
                };

                this.socket.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleMessage(data);
                    } catch (error) {
                        console.error('Failed to parse WebSocket message:', error);
                    }
                };

                this.socket.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.attemptReconnect();
                };

                this.socket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    reject(error);
                };

            } catch (error) {
                reject(error);
            }
        });
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

            setTimeout(() => {
                console.log(`Attempting WebSocket reconnect ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
                this.connect();
            }, delay);
        }
    }

    sendMessage(type, data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const message = { type, data, timestamp: Date.now() };
            this.socket.send(JSON.stringify(message));
        }
    }

    onMessage(type, callback) {
        if (!this.eventListeners.has(type)) {
            this.eventListeners.set(type, []);
        }
        this.eventListeners.get(type).push(callback);
    }

    handleMessage(message) {
        const listeners = this.eventListeners.get(message.type) || [];
        listeners.forEach(callback => callback(message.data));
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}
```

#### API Manager

```javascript
// modules/api.js
export class APIManager {
    constructor(baseURL = '/api') {
        this.baseURL = baseURL;
        this.requestQueue = [];
        this.maxConcurrentRequests = 3;
        this.activeRequests = 0;
        this.requestTimeout = 30000;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            method: options.method || 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (config.method !== 'GET' && options.data) {
            config.body = JSON.stringify(options.data);
        }

        // Queue management for rate limiting
        if (this.activeRequests >= this.maxConcurrentRequests) {
            await this.waitForQueue();
        }

        this.activeRequests++;

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.requestTimeout);

            const response = await fetch(url, {
                ...config,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }

            return await response.text();

        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            throw error;
        } finally {
            this.activeRequests--;
            this.processQueue();
        }
    }

    async waitForQueue() {
        return new Promise(resolve => {
            this.requestQueue.push(resolve);
        });
    }

    processQueue() {
        if (this.requestQueue.length > 0 && this.activeRequests < this.maxConcurrentRequests) {
            const resolve = this.requestQueue.shift();
            resolve();
        }
    }

    // Convenience methods
    get(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'GET' });
    }

    post(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'POST', data });
    }

    put(endpoint, data, options = {}) {
        return this.request(endpoint, { ...options, method: 'PUT', data });
    }

    delete(endpoint, options = {}) {
        return this.request(endpoint, { ...options, method: 'DELETE' });
    }

    // Streaming support for large responses
    async *streamRequest(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const response = await fetch(url, options);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                yield chunk;
            }
        } finally {
            reader.releaseLock();
        }
    }
}
```

#### Chart Manager

```javascript
// modules/charts.js
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
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    display: true,
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                }
            },
            animation: {
                duration: 300,
                easing: 'easeInOutQuad'
            }
        };
    }

    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`Canvas with id '${canvasId}' not found`);
            return null;
        }

        const ctx = canvas.getContext('2d');

        // Destroy existing chart if it exists
        if (this.charts.has(canvasId)) {
            this.charts.get(canvasId).destroy();
        }

        const chart = new Chart(ctx, {
            ...config,
            options: {
                ...this.defaultOptions,
                ...config.options
            }
        });

        this.charts.set(canvasId, chart);
        return chart;
    }

    updateChart(canvasId, data, options = {}) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.data = data;
            if (options) {
                chart.options = { ...chart.options, ...options };
            }
            chart.update('active');
        }
    }

    destroyChart(canvasId) {
        const chart = this.charts.get(canvasId);
        if (chart) {
            chart.destroy();
            this.charts.delete(canvasId);
        }
    }

    destroyAll() {
        for (const [canvasId, chart] of this.charts) {
            chart.destroy();
        }
        this.charts.clear();
    }

    // Specialized chart types
    createTokenChart(canvasId, tokenData) {
        return this.createChart(canvasId, {
            type: 'line',
            data: {
                labels: tokenData.labels,
                datasets: [{
                    label: 'Token Usage',
                    data: tokenData.values,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Tokens'
                        }
                    }
                }
            }
        });
    }

    createProviderChart(canvasId, providerData) {
        return this.createChart(canvasId, {
            type: 'doughnut',
            data: {
                labels: providerData.labels,
                datasets: [{
                    data: providerData.values,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 205, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)'
                    ],
                    borderWidth: 2
                }]
            },
            options: {
                plugins: {
                    legend: {
                        position: 'right'
                    }
                }
            }
        });
    }
}
```

## Real-time Updates

### Session Manager

```javascript
// modules/session.js
export class SessionManager {
    constructor(apiManager, websocketManager, chartManager) {
        this.api = apiManager;
        this.ws = websocketManager;
        this.charts = chartManager;
        this.currentSession = null;
        this.sessions = new Map();
        this.updateInterval = null;
        this.setupWebSocketHandlers();
    }

    setupWebSocketHandlers() {
        this.ws.onMessage('session_update', (data) => {
            this.handleSessionUpdate(data);
        });

        this.ws.onMessage('token_update', (data) => {
            this.handleTokenUpdate(data);
        });

        this.ws.onMessage('error', (data) => {
            this.handleError(data);
        });
    }

    async loadSessions() {
        try {
            const response = await this.api.get('/sessions');
            this.sessions.clear();

            response.sessions.forEach(session => {
                this.sessions.set(session.id, session);
            });

            return Array.from(this.sessions.values());
        } catch (error) {
            console.error('Failed to load sessions:', error);
            throw error;
        }
    }

    async loadSession(sessionId) {
        try {
            const response = await this.api.get(`/sessions/${sessionId}`);
            this.currentSession = response.session;
            this.sessions.set(sessionId, response.session);
            return response.session;
        } catch (error) {
            console.error(`Failed to load session ${sessionId}:`, error);
            throw error;
        }
    }

    handleSessionUpdate(data) {
        if (data.session) {
            this.sessions.set(data.session.id, data.session);

            if (this.currentSession && this.currentSession.id === data.session.id) {
                this.currentSession = data.session;
                this.updateUI();
            }
        }
    }

    handleTokenUpdate(data) {
        if (this.currentSession && data.sessionId === this.currentSession.id) {
            this.currentSession.tokenCount = data.tokenCount;
            this.updateTokenDisplay();
        }
    }

    handleError(data) {
        console.error('WebSocket error:', data.message);
        // Show user-friendly error message
        this.showError(data.message);
    }

    updateUI() {
        if (!this.currentSession) return;

        // Update session info display
        this.updateSessionInfo();

        // Update charts if they exist
        this.updateCharts();
    }

    updateSessionInfo() {
        const infoElement = document.getElementById('session-info');
        if (infoElement && this.currentSession) {
            infoElement.innerHTML = `
                <div class="session-header">
                    <h3>${this.currentSession.name || 'Unnamed Session'}</h3>
                    <span class="session-status status-${this.currentSession.status || 'unknown'}">
                        ${this.currentSession.status || 'Unknown'}
                    </span>
                </div>
                <div class="session-meta">
                    <span>Created: ${new Date(this.currentSession.createdAt).toLocaleString()}</span>
                    <span>Messages: ${this.currentSession.messageCount || 0}</span>
                </div>
            `;
        }
    }

    updateTokenDisplay() {
        if (!this.currentSession) return;

        const tokenCount = this.currentSession.tokenCount || 0;
        const maxTokens = this.currentSession.maxTokens || 262144;

        // Update gauge
        this.updateTokenGauge(tokenCount, maxTokens);

        // Update text display
        const displayElement = document.getElementById('token-display');
        if (displayElement) {
            displayElement.textContent = `${tokenCount.toLocaleString()} / ${maxTokens.toLocaleString()}`;
        }
    }

    updateTokenGauge(tokenCount, maxTokens) {
        const percentage = (tokenCount / maxTokens) * 100;
        const gaugeElement = document.getElementById('token-gauge');

        if (gaugeElement) {
            gaugeElement.style.width = `${Math.min(percentage, 100)}%`;

            // Color coding
            gaugeElement.className = 'token-gauge-fill';
            if (percentage < 70) {
                gaugeElement.classList.add('gauge-green');
            } else if (percentage < 85) {
                gaugeElement.classList.add('gauge-yellow');
            } else {
                gaugeElement.classList.add('gauge-red');
            }
        }
    }

    updateCharts() {
        if (!this.currentSession || !this.currentSession.tokenHistory) return;

        const tokenData = {
            labels: this.currentSession.tokenHistory.map((_, i) => `T${i + 1}`),
            values: this.currentSession.tokenHistory
        };

        this.charts.updateChart('token-chart', {
            labels: tokenData.labels,
            datasets: [{
                label: 'Token Usage',
                data: tokenData.values,
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                tension: 0.4,
                fill: true
            }]
        });
    }

    showError(message) {
        const errorElement = document.getElementById('error-display');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';

            setTimeout(() => {
                errorElement.style.display = 'none';
            }, 5000);
        }
    }

    startPeriodicUpdates(interval = 30000) {
        this.updateInterval = setInterval(async () => {
            try {
                await this.loadSessions();
            } catch (error) {
                console.error('Failed to update sessions:', error);
            }
        }, interval);
    }

    stopPeriodicUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
}
```

## Error Handling & Resilience

### Retry Logic

```javascript
// modules/api.js (continued)
export class APIManager {
    // ... existing code ...

    async requestWithRetry(endpoint, options = {}, maxRetries = 3) {
        let lastError;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                return await this.request(endpoint, options);
            } catch (error) {
                lastError = error;

                if (attempt < maxRetries && this.isRetryableError(error)) {
                    const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
                    console.log(`Request failed, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries + 1})`);
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay * (retryCount + 1)));
                    
                    return this.requestWithRetry(endpoint, options, retryCount + 1);
                }
            }
        }

        throw lastError;
    }

    isRetryableError(error) {
        // Retry on network errors, timeouts, 5xx server errors
        return error.message.includes('network') ||
               error.message.includes('timeout') ||
               error.message.includes('HTTP 5');
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