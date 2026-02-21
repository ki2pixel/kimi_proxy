/**
 * Tests unitaires pour SessionManager
 * Teste la gestion des sessions et la configuration proxy
 */

import { SessionManager } from '../static/js/modules/sessions.js';

// Mock fetch
global.fetch = jest.fn();

describe('SessionManager', () => {
    let sessionManager;

    beforeEach(() => {
        sessionManager = new SessionManager();
        jest.clearAllMocks();
    });

    test('should initialize with correct structure', () => {
        expect(sessionManager.activeSession).toBeNull();
        expect(sessionManager.sessionHistory).toEqual([]);
        expect(sessionManager.sessionProxyMap).toBeInstanceOf(Map);
    });

    test('should switch session atomically', async () => {
        const mockSession = {
            id: 'session-123',
            model: 'kimi-code',
            api_key: 'test-key'
        };

        // Mock API responses
        fetch.mockImplementation((url) => {
            if (url.includes('/api/sessions/session-123')) {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ session: mockSession })
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

        // Mock eventBus
        const mockEmit = jest.fn();
        const eventBus = { emit: mockEmit };
        require('../static/js/modules/sessions.js').eventBus = eventBus;

        const result = await sessionManager.switchSession('session-123');

        expect(result).toEqual(mockSession);
        expect(sessionManager.activeSession).toEqual(mockSession);
        expect(sessionManager.sessionHistory).toContain(mockSession);

        // Vérifie que l'événement a été émis
        expect(mockEmit).toHaveBeenCalledWith('sessionChanged', {
            oldSession: null,
            newSession: mockSession,
            proxyConfig: expect.any(Object)
        });
    });

    test('should extract provider correctly', () => {
        expect(sessionManager.extractProvider('kimi-code')).toBe('nvidia');
        expect(sessionManager.extractProvider('gpt-4')).toBe('openai');
        expect(sessionManager.extractProvider('claude-3')).toBe('anthropic');
        expect(sessionManager.extractProvider('mistral-7b')).toBe('mistral');
        expect(sessionManager.extractProvider('unknown-model')).toBe('unknown');
    });

    test('should get timeout for provider', () => {
        expect(sessionManager.getTimeoutForProvider('nvidia')).toBe(30);
        expect(sessionManager.getTimeoutForProvider('openai')).toBe(60);
        expect(sessionManager.getTimeoutForProvider('anthropic')).toBe(120);
        expect(sessionManager.getTimeoutForProvider('unknown')).toBe(30);
    });

    test('should check if session is active', () => {
        sessionManager.activeSession = { id: 'session-123' };

        expect(sessionManager.isSessionActive('session-123')).toBe(true);
        expect(sessionManager.isSessionActive('session-456')).toBe(false);
    });

    test('should cleanup old proxy configs', () => {
        // Ajoute plusieurs sessions
        for (let i = 1; i <= 12; i++) {
            sessionManager.sessionProxyMap.set(`session-${i}`, { config: `config-${i}` });
            sessionManager.sessionHistory.push({ id: `session-${i}` });
        }

        sessionManager.cleanupOldConfigs(10);

        expect(sessionManager.sessionHistory.length).toBe(10);
        expect(sessionManager.sessionProxyMap.has('session-1')).toBe(false);
        expect(sessionManager.sessionProxyMap.has('session-2')).toBe(false);
        expect(sessionManager.sessionProxyMap.has('session-12')).toBe(true);
    });
});
