/**
 * Tests unitaires pour WebSocketManager
 * Teste la gestion WebSocket avec filtrage de session
 */

import { WebSocketManager } from '../static/js/modules/websocket.js';

// Mock WebSocket
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

describe('WebSocketManager', () => {
    let wsManager;
    let mockEventBus;

    beforeEach(() => {
        wsManager = new WebSocketManager();
        mockEventBus = { emit: jest.fn() };

        // Mock eventBus
        require('../static/js/modules/websocket.js').eventBus = mockEventBus;
    });

    test('should initialize with correct structure', () => {
        expect(wsManager.ws).toBeNull();
        expect(wsManager.isConnected).toBe(false);
        expect(wsManager.activeSessionId).toBeNull();
        expect(wsManager.messageQueue).toEqual([]);
    });

    test('should set active session ID', () => {
        const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

        wsManager.setActiveSessionId('session-123');

        expect(wsManager.activeSessionId).toBe('session-123');
        expect(consoleSpy).toHaveBeenCalledWith(
            expect.stringContaining('Session active changée')
        );

        consoleSpy.mockRestore();
    });

    test('should filter messages by session ID', () => {
        wsManager.activeSessionId = 'session-123';

        // Mock handlers
        wsManager.handleMetricMessage = jest.fn();
        wsManager.handleLogMetricMessage = jest.fn();

        // Message avec session matching
        const matchingMessage = {
            type: 'metric',
            session_id: 'session-123',
            metric: { tokens: 100 }
        };

        wsManager.handleMessage(matchingMessage);
        expect(wsManager.handleMetricMessage).toHaveBeenCalled();

        // Reset mock
        wsManager.handleMetricMessage.mockClear();

        // Message avec session différente - devrait être filtré
        const differentMessage = {
            type: 'metric',
            session_id: 'session-456',
            metric: { tokens: 200 }
        };

        const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
        wsManager.handleMessage(differentMessage);

        expect(wsManager.handleMetricMessage).not.toHaveBeenCalled();
        expect(consoleSpy).toHaveBeenCalledWith(
            expect.stringContaining('Message ignoré')
        );

        consoleSpy.mockRestore();
    });

    test('should queue messages when disconnected', () => {
        wsManager.isConnected = false;

        wsManager.sendMessage({ type: 'test', data: 'test' });

        expect(wsManager.messageQueue).toHaveLength(1);
        expect(wsManager.messageQueue[0]).toEqual({ type: 'test', data: 'test' });
    });

    test('should process message queue on connect', () => {
        wsManager.isConnected = false;
        wsManager.messageQueue = [{ type: 'queued', data: 'data' }];

        const sendSpy = jest.spyOn(wsManager, 'sendMessage');

        wsManager.processMessageQueue();

        expect(sendSpy).toHaveBeenCalledWith({ type: 'queued', data: 'data' });
        expect(wsManager.messageQueue).toHaveLength(0);
    });

    test('should disconnect properly', () => {
        wsManager.ws = { close: jest.fn() };
        wsManager.isConnected = true;
        wsManager.activeSessionId = 'session-123';
        wsManager.messageQueue = [{ type: 'test' }];

        wsManager.disconnect();

        expect(wsManager.ws).toBeNull();
        expect(wsManager.isConnected).toBe(false);
        expect(wsManager.activeSessionId).toBeNull();
        expect(wsManager.messageQueue).toEqual([]);
    });
});
