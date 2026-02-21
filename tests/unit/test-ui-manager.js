/**
 * Tests unitaires pour UIManager
 * Teste la gestion dynamique des boutons UI selon les capacités des sessions
 */

import { UIManager } from '../static/js/modules/ui.js';

// Mock DOM
global.document = {
    getElementById: jest.fn(),
    querySelector: jest.fn()
};

describe('UIManager', () => {
    let uiManager;

    beforeEach(() => {
        uiManager = new UIManager();
        jest.clearAllMocks();
    });

    test('should initialize with correct structure', () => {
        expect(uiManager.buttonStates).toBeInstanceOf(Map);
        expect(uiManager.sessionCapabilities).toBeInstanceOf(Map);
    });

    test('should extract provider correctly', () => {
        expect(uiManager.extractProvider('kimi-code')).toBe('nvidia');
        expect(uiManager.extractProvider('gpt-4')).toBe('openai');
        expect(uiManager.extractProvider('claude-3')).toBe('anthropic');
        expect(uiManager.extractProvider('custom-model')).toBe('custom');
    });

    test('should check compaction support', () => {
        // Sessions avec compaction supportée
        expect(uiManager.isCompactionSupported({ model: 'gpt-4' })).toBe(true);
        expect(uiManager.isCompactionSupported({ model: 'claude-3' })).toBe(true);

        // Sessions sans compaction
        expect(uiManager.isCompactionSupported({ model: 'kimi-code' })).toBe(false);
        expect(uiManager.isCompactionSupported({ model: 'mistral-7b' })).toBe(false);
        expect(uiManager.isCompactionSupported({ model: 'kimi-code-2.5' })).toBe(false);

        // Session sans modèle
        expect(uiManager.isCompactionSupported({})).toBe(false);
    });

    test('should check warning support', () => {
        // Contexte volumineux avec provider compatible
        expect(uiManager.isWarningSupported({
            total_tokens: 15000,
            model: 'gpt-4'
        })).toBe(true);

        expect(uiManager.isWarningSupported({
            total_tokens: 15000,
            model: 'claude-3'
        })).toBe(true);

        // Contexte trop petit
        expect(uiManager.isWarningSupported({
            total_tokens: 5000,
            model: 'gpt-4'
        })).toBe(false);

        // Provider non compatible
        expect(uiManager.isWarningSupported({
            total_tokens: 15000,
            model: 'kimi-code'
        })).toBe(false);

        // Pas de tokens
        expect(uiManager.isWarningSupported({ model: 'gpt-4' })).toBe(false);
    });

    test('should check delete support', () => {
        expect(uiManager.isDeleteSupported({ id: 'session-1' })).toBe(true);
        expect(uiManager.isDeleteSupported({ id: 'session-1', is_system: false })).toBe(true);
        expect(uiManager.isDeleteSupported({ id: 'session-1', is_system: true })).toBe(false);
        expect(uiManager.isDeleteSupported({})).toBe(false);
    });

    test('should update button states', () => {
        const mockButton = {
            disabled: false,
            classList: { toggle: jest.fn() },
            setAttribute: jest.fn()
        };

        document.getElementById.mockImplementation((id) => {
            if (id === 'compaction-btn' || id === 'warning-btn' || id === 'delete-btn') {
                return mockButton;
            }
            return null;
        });

        const session = {
            id: 'session-123',
            model: 'gpt-4',
            total_tokens: 15000
        };

        const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

        uiManager.updateButtonStates(session);

        // Vérifie que les boutons ont été mis à jour
        expect(document.getElementById).toHaveBeenCalledWith('compaction-btn');
        expect(document.getElementById).toHaveBeenCalledWith('warning-btn');
        expect(document.getElementById).toHaveBeenCalledWith('delete-btn');

        // Vérifie le cache des états
        const cachedStates = uiManager.getButtonStates('session-123');
        expect(cachedStates).toEqual({
            'compaction-btn': true,  // Supporté pour GPT
            'warning-btn': true,     // Contexte volumineux + provider compatible
            'export-btn': true,      // Toujours supporté
            'delete-btn': true       // Supporté
        });

        consoleSpy.mockRestore();
    });

    test('should set button state correctly', () => {
        const mockButton = {
            disabled: false,
            classList: { toggle: jest.fn() },
            setAttribute: jest.fn()
        };

        const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

        // Désactiver le bouton
        uiManager.setButtonState(mockButton, false, 'test-btn');

        expect(mockButton.disabled).toBe(true);
        expect(mockButton.classList.toggle).toHaveBeenCalledWith('disabled', true);
        expect(mockButton.setAttribute).toHaveBeenCalledWith('aria-disabled', true);

        // Réactiver le bouton
        mockButton.disabled = true;
        uiManager.setButtonState(mockButton, true, 'test-btn');

        expect(mockButton.disabled).toBe(false);
        expect(mockButton.classList.toggle).toHaveBeenCalledWith('disabled', false);
        expect(mockButton.setAttribute).toHaveBeenCalledWith('aria-disabled', false);

        consoleSpy.mockRestore();
    });

    test('should get disabled tooltips', () => {
        expect(uiManager.getDisabledTooltip('compaction-btn'))
            .toContain('Compaction non supportée');

        expect(uiManager.getDisabledTooltip('warning-btn'))
            .toContain('Avertissements nécessitent');

        expect(uiManager.getDisabledTooltip('delete-btn'))
            .toContain('Suppression non autorisée');

        expect(uiManager.getDisabledTooltip('unknown-btn'))
            .toBe('Fonctionnalité non disponible');
    });

    test('should reset button states', () => {
        uiManager.buttonStates.set('session-123', { 'btn1': true, 'btn2': false });

        uiManager.resetButtonStates('session-123');

        expect(uiManager.getButtonStates('session-123')).toEqual({});
    });
});
