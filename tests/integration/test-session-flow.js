/**
 * Tests d'intégration pour le flux de changement de session
 * Teste l'interaction entre tous les managers
 */

import { ChartManager } from '../static/js/modules/charts.js';
import { SessionManager } from '../static/js/modules/sessions.js';
import { WebSocketManager } from '../static/js/modules/websocket.js';
import { UIManager } from '../static/js/modules/ui.js';

// Mock dependencies
global.Chart = class Chart {
    constructor() {
        this.data = { datasets: [], labels: [] };
    }
    update(mode) {
        // Mock update
    }
    destroy() {
        // Mock destroy
    }
};

global.WebSocket = class WebSocket {
    constructor() {
        this.onopen = null;
        this.onmessage = null;
        this.onclose = null;
        this.onerror = null;
    }
    send() {}
    close() {}
};

global.document = {
    getElementById: jest.fn().mockReturnValue(null),
    querySelector: jest.fn()
};

global.fetch = jest.fn();

describe('Session Change Flow Integration', () => {
    let chartManager;
    let sessionManager;
    let wsManager;
    let uiManager;
    let mockEventBus;

    beforeEach(() => {
        // Initialize managers
        chartManager = new ChartManager();
        sessionManager = new SessionManager();
        wsManager = new WebSocketManager();
        uiManager = new UIManager();

        // Mock eventBus
        mockEventBus = { emit: jest.fn(), on: jest.fn() };
        require('../static/js/modules/charts.js').eventBus = mockEventBus;
        require('../static/js/modules/sessions.js').eventBus = mockEventBus;
        require('../static/js/modules/websocket.js').eventBus = mockEventBus;

        // Mock DOM elements for UI tests
        document.getElementById.mockImplementation((id) => {
            if (['compaction-btn', 'warning-btn', 'delete-btn'].includes(id)) {
                return {
                    disabled: false,
                    classList: { toggle: jest.fn() },
                    setAttribute: jest.fn()
                };
            }
            return null;
        });

        jest.clearAllMocks();
    });

    test('should handle complete session change flow', async () => {
        const newSession = {
            id: 'session-456',
            model: 'gpt-4',
            total_tokens: 15000,
            api_key: 'test-key'
        };

        // Mock API responses
        fetch.mockImplementation((url) => {
            if (url.includes('/api/sessions/session-456')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ session: newSession })
                });
            }
            if (url.includes('/api/proxy/config')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ success: true })
                });
            }
            return Promise.reject(new Error('Unknown URL'));
        });

        // Initialize charts
        document.getElementById.mockReturnValue({
            getContext: () => ({})
        });
        chartManager.initGauge();
        chartManager.initHistoryChart();

        // Add some initial data to charts
        const gaugeChart = chartManager.getChart('gauge');
        const historyChart = chartManager.getChart('history');

        gaugeChart.data.datasets[0].data = [75];
        historyChart.data.datasets[0].data = [100, 200];
        historyChart.data.labels = ['A', 'B'];

        // Perform session change
        await sessionManager.switchSession('session-456');

        // Verify session manager state
        expect(sessionManager.activeSession).toEqual(newSession);
        expect(sessionManager.sessionHistory).toContain(newSession);

        // Create session change event
        const sessionChangeEvent = {
            detail: {
                newSession: newSession
            }
        };

        // Handle session change in all managers
        chartManager.handleSessionChange(sessionChangeEvent);
        wsManager.setActiveSessionId(newSession.id);
        uiManager.updateButtonStates(newSession);

        // Verify chart manager reset
        expect(chartManager.sessionContext).toBe('session-456');
        expect(gaugeChart.data.datasets[0].data).toEqual([]);
        expect(historyChart.data.datasets[0].data).toEqual([]);
        expect(historyChart.data.labels).toEqual([]);

        // Verify WebSocket manager session tracking
        expect(wsManager.activeSessionId).toBe('session-456');

        // Verify UI manager button states
        const buttonStates = uiManager.getButtonStates('session-456');
        expect(buttonStates).toEqual({
            'compaction-btn': true,   // GPT-4 supporte la compaction
            'warning-btn': true,      // Contexte volumineux + provider compatible
            'export-btn': true,       // Toujours disponible
            'delete-btn': true        // Supporté
        });

        // Verify event emission
        expect(mockEventBus.emit).toHaveBeenCalledWith('sessionChanged', {
            oldSession: null,
            newSession: newSession,
            proxyConfig: expect.any(Object)
        });
    });

    test('should handle WebSocket message filtering after session change', () => {
        // Set active session
        wsManager.setActiveSessionId('session-456');

        // Mock message handlers
        wsManager.handleMetricMessage = jest.fn();
        wsManager.handleLogMetricMessage = jest.fn();

        // Message for active session - should be processed
        const activeSessionMessage = {
            type: 'metric',
            session_id: 'session-456',
            metric: { tokens: 1000 }
        };

        wsManager.handleMessage(activeSessionMessage);
        expect(wsManager.handleMetricMessage).toHaveBeenCalledWith(activeSessionMessage, expect.any(Number));

        // Reset mock
        wsManager.handleMetricMessage.mockClear();

        // Message for different session - should be filtered out
        const differentSessionMessage = {
            type: 'metric',
            session_id: 'session-123',
            metric: { tokens: 500 }
        };

        const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
        wsManager.handleMessage(differentSessionMessage);

        expect(wsManager.handleMetricMessage).not.toHaveBeenCalled();
        expect(consoleSpy).toHaveBeenCalledWith(
            expect.stringContaining('Message ignoré'),
            expect.stringContaining('session-123'),
            expect.stringContaining('session-456')
        );

        consoleSpy.mockRestore();
    });

    test('should handle session change with unsupported features', () => {
        const nvidiaSession = {
            id: 'session-nvidia',
            model: 'kimi-code',
            total_tokens: 5000
        };

        // Handle session change for Nvidia session
        uiManager.updateButtonStates(nvidiaSession);

        const buttonStates = uiManager.getButtonStates('session-nvidia');

        expect(buttonStates).toEqual({
            'compaction-btn': false,  // Nvidia ne supporte pas la compaction
            'warning-btn': false,     // Contexte trop petit + provider incompatible
            'export-btn': true,       // Toujours disponible
            'delete-btn': true        // Supporté
        });
    });

    test('should coordinate managers during complex session transitions', async () => {
        // Test multiple session changes
        const sessions = [
            { id: 'session-1', model: 'gpt-4', total_tokens: 20000 },
            { id: 'session-2', model: 'kimi-code', total_tokens: 10000 },
            { id: 'session-3', model: 'claude-3', total_tokens: 5000 }
        ];

        for (const session of sessions) {
            // Mock API for this session
            fetch.mockImplementationOnce(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ session })
            }));
            fetch.mockImplementationOnce(() => Promise.resolve({
                ok: true,
                json: () => Promise.resolve({ success: true })
            }));

            // Perform session change
            await sessionManager.switchSession(session.id);

            // Handle in all managers
            const event = { detail: { newSession: session } };
            chartManager.handleSessionChange(event);
            wsManager.setActiveSessionId(session.id);
            uiManager.updateButtonStates(session);

            // Verify state consistency
            expect(chartManager.sessionContext).toBe(session.id);
            expect(wsManager.activeSessionId).toBe(session.id);
            expect(sessionManager.activeSession).toEqual(session);

            const buttonStates = uiManager.getButtonStates(session.id);
            expect(buttonStates).toBeDefined();
            expect(typeof buttonStates['compaction-btn']).toBe('boolean');
        }
    });
});
