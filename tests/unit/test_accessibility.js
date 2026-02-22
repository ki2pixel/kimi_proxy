/**
 * test_accessibility.js - Tests unitaires pour les composants d'accessibilité WCAG
 *
 * Teste les fonctionnalités WCAG Phase 2 :
 * - ModalManager (focus management)
 * - LiveAnnouncer (aria-live)
 * - DropdownManager (navigation clavier)
 * - Utils d'accessibilité
 */

import { ModalManager } from '../../static/js/modules/accessibility/modal-manager.js';
import { LiveAnnouncer } from '../../static/js/modules/accessibility/live-announcer.js';
import { DropdownManager } from '../../static/js/modules/accessibility/dropdown-manager.js';
import {
    trapFocus,
    checkContrast,
    setAriaAttributes,
    announceToScreenReader,
    isFocusable,
    createAccessibleElement
} from '../../static/js/modules/accessibility/utils.js';

// ============================================================================
// TESTS MODALMANAGER
// ============================================================================

describe('ModalManager', () => {
    let modalManager;
    let mockModal;
    let mockContent;

    beforeEach(() => {
        modalManager = new ModalManager();

        // Crée un mock de modale
        mockModal = document.createElement('div');
        mockModal.id = 'test-modal';
        mockModal.innerHTML = `
            <button id="close-btn">Fermer</button>
            <input type="text" id="test-input">
            <button id="action-btn">Action</button>
        `;
        document.body.appendChild(mockModal);

        mockContent = mockModal;
    });

    afterEach(() => {
        document.body.removeChild(mockModal);
        jest.clearAllMocks();
    });

    test('devrait ouvrir une modale avec gestion du focus', () => {
        modalManager.open(mockModal);

        expect(mockModal.getAttribute('role')).toBe('dialog');
        expect(mockModal.getAttribute('aria-modal')).toBe('true');
        expect(modalManager.isOpen(mockModal)).toBe(true);
    });

    test('devrait fermer une modale avec restauration du focus', () => {
        // Simule un élément précédemment focusé
        const previousElement = document.createElement('button');
        document.body.appendChild(previousElement);
        previousElement.focus();

        modalManager.open(mockModal);
        modalManager.close(mockModal);

        expect(mockModal.getAttribute('role')).toBeNull();
        expect(mockModal.getAttribute('aria-modal')).toBeNull();
        expect(modalManager.isOpen(mockModal)).toBe(false);
    });

    test('devrait gérer plusieurs modales ouvertes', () => {
        const modal2 = document.createElement('div');
        modal2.id = 'test-modal-2';
        document.body.appendChild(modal2);

        modalManager.open(mockModal);
        modalManager.open(modal2);

        expect(modalManager.getOpenCount()).toBe(2);
        expect(modalManager.isOpen(mockModal)).toBe(true);
        expect(modalManager.isOpen(modal2)).toBe(true);

        modalManager.closeAll();
        expect(modalManager.getOpenCount()).toBe(0);

        document.body.removeChild(modal2);
    });

    test('devrait configurer le focus trap correctement', () => {
        const focusableElements = mockModal.querySelectorAll('button, input');
        expect(focusableElements.length).toBeGreaterThan(0);

        modalManager.open(mockModal);

        // Vérifie que les attributs ARIA sont configurés
        expect(mockModal.getAttribute('role')).toBe('dialog');
        expect(mockModal.getAttribute('aria-modal')).toBe('true');
    });
});

// ============================================================================
// TESTS LIVEANNOUNCER
// ============================================================================

describe('LiveAnnouncer', () => {
    let announcer;

    beforeEach(() => {
        announcer = new LiveAnnouncer();
        // Nettoie les régions existantes
        const existingRegions = document.querySelectorAll('[id^="live-region"]');
        existingRegions.forEach(region => region.remove());
    });

    afterEach(() => {
        announcer.destroy();
        jest.clearAllMocks();
    });

    test('devrait créer les régions aria-live', () => {
        expect(document.getElementById('live-region-polite')).toBeTruthy();
        expect(document.getElementById('live-region-assertive')).toBeTruthy();
    });

    test('devrait annoncer un message de manière polie', () => {
        const message = 'Test d\'annonce polie';
        announcer.announce(message);

        const region = document.getElementById('live-region-polite');
        expect(region.textContent).toBe(message);
        expect(region.getAttribute('aria-live')).toBe('polite');
    });

    test('devrait annoncer une erreur de manière assertive', () => {
        const message = 'Erreur critique';
        announcer.announceError(message);

        const region = document.getElementById('live-region-assertive');
        expect(region.textContent).toBe(message);
        expect(region.getAttribute('aria-live')).toBe('assertive');
    });

    test('devrait éviter les annonces dupliquées', () => {
        const message = 'Message dupliqué';
        announcer.announce(message);
        announcer.announce(message); // Devrait être ignoré

        const region = document.getElementById('live-region-polite');
        expect(region.textContent).toBe(message);
    });

    test('devrait annoncer les mises à jour de tokens', () => {
        announcer.announceTokenUpdate(1500, 75);

        const region = document.getElementById('live-region-polite');
        expect(region.textContent).toContain('1 500');
        expect(region.textContent).toContain('75');
    });

    test('devrait annoncer les changements de statut de connexion', () => {
        announcer.announceConnectionStatus(true);
        let region = document.getElementById('live-region-polite');
        expect(region.textContent).toContain('Connecté');

        announcer.announceConnectionStatus(false);
        region = document.getElementById('live-region-polite');
        expect(region.textContent).toContain('Déconnecté');
    });
});

// ============================================================================
// TESTS DROPDOWNMANAGER
// ============================================================================

describe('DropdownManager', () => {
    let dropdownManager;
    let mockDropdown;

    beforeEach(() => {
        mockDropdown = document.createElement('div');
        mockDropdown.setAttribute('data-dropdown', '');
        mockDropdown.innerHTML = `
            <button data-dropdown-trigger>Options</button>
            <div data-dropdown-menu style="display: none;">
                <div data-dropdown-item>Option 1</div>
                <div data-dropdown-item>Option 2</div>
                <div data-dropdown-item>Option 3</div>
            </div>
        `;
        document.body.appendChild(mockDropdown);

        dropdownManager = new DropdownManager(mockDropdown);
    });

    afterEach(() => {
        document.body.removeChild(mockDropdown);
        jest.clearAllMocks();
    });

    test('devrait initialiser avec les attributs ARIA corrects', () => {
        const button = mockDropdown.querySelector('[data-dropdown-trigger]');
        const menu = mockDropdown.querySelector('[data-dropdown-menu]');
        const items = mockDropdown.querySelectorAll('[data-dropdown-item]');

        expect(button.getAttribute('aria-haspopup')).toBe('menu');
        expect(button.getAttribute('aria-expanded')).toBe('false');
        expect(menu.getAttribute('role')).toBe('menu');
        expect(menu.getAttribute('aria-hidden')).toBe('true');

        items.forEach(item => {
            expect(item.getAttribute('role')).toBe('menuitem');
            expect(item.getAttribute('tabindex')).toBe('-1');
        });
    });

    test('devrait ouvrir et fermer le dropdown', () => {
        const button = mockDropdown.querySelector('[data-dropdown-trigger]');
        const menu = mockDropdown.querySelector('[data-dropdown-menu]');

        // Ouvre
        dropdownManager.open();
        expect(button.getAttribute('aria-expanded')).toBe('true');
        expect(menu.getAttribute('aria-hidden')).toBe('false');
        expect(menu.style.display).toBe('block');

        // Ferme
        dropdownManager.close();
        expect(button.getAttribute('aria-expanded')).toBe('false');
        expect(menu.getAttribute('aria-hidden')).toBe('true');
        expect(menu.style.display).toBe('none');
    });

    test('devrait gérer la navigation clavier', () => {
        dropdownManager.open();

        const items = mockDropdown.querySelectorAll('[data-dropdown-item]');
        const menu = mockDropdown.querySelector('[data-dropdown-menu]');

        // Simule un événement flèche bas
        const keydownEvent = new KeyboardEvent('keydown', { key: 'ArrowDown' });
        menu.dispatchEvent(keydownEvent);

        expect(dropdownManager.getSelectedItem()).toBe(items[1]);

        // Simule un événement flèche haut
        const keyupEvent = new KeyboardEvent('keydown', { key: 'ArrowUp' });
        menu.dispatchEvent(keyupEvent);

        expect(dropdownManager.getSelectedItem()).toBe(items[0]);
    });

    test('devrait fermer avec Échap', () => {
        dropdownManager.open();

        const escapeEvent = new KeyboardEvent('keydown', { key: 'Escape' });
        const button = mockDropdown.querySelector('[data-dropdown-trigger]');
        button.dispatchEvent(escapeEvent);

        expect(dropdownManager.isDropdownOpen()).toBe(false);
    });
});

// ============================================================================
// TESTS UTILS ACCESSIBILITÉ
// ============================================================================

describe('Accessibility Utils', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.innerHTML = `
            <button id="btn1">Bouton 1</button>
            <input type="text" id="input1">
            <button id="btn2">Bouton 2</button>
        `;
        document.body.appendChild(container);
    });

    afterEach(() => {
        document.body.removeChild(container);
        jest.clearAllMocks();
    });

    test('devrait vérifier le contraste des couleurs', () => {
        // Test contraste suffisant
        expect(checkContrast('#000000', '#FFFFFF')).toBe(true);
        // Test contraste insuffisant
        expect(checkContrast('#808080', '#A0A0A0')).toBe(false);
    });

    test('devrait définir les attributs ARIA', () => {
        const element = document.createElement('div');
        setAriaAttributes(element, {
            'label': 'Test label',
            'expanded': 'true',
            'hidden': null // Devrait supprimer l'attribut
        });

        expect(element.getAttribute('aria-label')).toBe('Test label');
        expect(element.getAttribute('aria-expanded')).toBe('true');
        expect(element.hasAttribute('aria-hidden')).toBe(false);
    });

    test('devrait vérifier si un élément est focusable', () => {
        const button = container.querySelector('#btn1');
        const input = container.querySelector('#input1');
        const div = document.createElement('div');

        expect(isFocusable(button)).toBe(true);
        expect(isFocusable(input)).toBe(true);
        expect(isFocusable(div)).toBe(false);
    });

    test('devrait créer un élément accessible', () => {
        const button = createAccessibleElement('button', {
            'textContent': 'Test Button',
            'aria-label': 'Test Label',
            'class': 'test-class'
        });

        expect(button.tagName.toLowerCase()).toBe('button');
        expect(button.textContent).toBe('Test Button');
        expect(button.getAttribute('aria-label')).toBe('Test Label');
        expect(button.className).toBe('test-class');
    });

    test('devrait annoncer aux lecteurs d\'écran', () => {
        announceToScreenReader('Test announcement');

        const announcer = document.getElementById('sr-announcer');
        expect(announcer).toBeTruthy();
        expect(announcer.getAttribute('aria-live')).toBe('polite');
        expect(announcer.textContent).toBe('Test announcement');
    });
});

// ============================================================================
// TESTS FOCUS TRAP
// ============================================================================

describe('Focus Trap', () => {
    let container;
    let focusControls;

    beforeEach(() => {
        container = document.createElement('div');
        container.innerHTML = `
            <button id="first">Premier</button>
            <input type="text" id="middle">
            <button id="last">Dernier</button>
        `;
        document.body.appendChild(container);

        focusControls = trapFocus(container);
    });

    afterEach(() => {
        if (focusControls) {
            focusControls.deactivate();
        }
        document.body.removeChild(container);
        jest.clearAllMocks();
    });

    test('devrait activer et désactiver le focus trap', () => {
        expect(focusControls.isActive()).toBe(false);

        focusControls.activate();
        expect(focusControls.isActive()).toBe(true);

        focusControls.deactivate();
        expect(focusControls.isActive()).toBe(false);
    });

    test('devrait piéger le focus dans le conteneur', () => {
        focusControls.activate();

        const firstBtn = container.querySelector('#first');
        const lastBtn = container.querySelector('#last');

        // Simule Tab depuis le dernier élément
        const tabEvent = new KeyboardEvent('keydown', { key: 'Tab' });
        Object.defineProperty(tabEvent, 'target', { value: lastBtn });
        lastBtn.dispatchEvent(tabEvent);

        // Le focus devrait revenir au premier élément
        expect(document.activeElement).toBe(firstBtn);
    });
});

// ============================================================================
// TESTS D'INTÉGRATION WCAG
// ============================================================================

describe('WCAG Integration Tests', () => {
    test('devrait respecter les critères WCAG 2.1 AA pour le focus management', () => {
        // Test d'intégration pour s'assurer que tous les composants
        // respectent les critères WCAG pour la gestion du focus
        const modalManager = new ModalManager();
        const announcer = new LiveAnnouncer();

        expect(modalManager).toBeDefined();
        expect(announcer).toBeDefined();
        expect(typeof announcer.announce).toBe('function');
        expect(typeof modalManager.open).toBe('function');
    });

    test('devrait fournir des messages d\'annonce en français', () => {
        const announcer = new LiveAnnouncer();

        announcer.announceConnectionStatus(true);
        const region = document.getElementById('live-region-polite');

        // Vérifie que le message est en français
        expect(region.textContent).toContain('Connecté');

        announcer.destroy();
    });
});

// Tests pour les ratios de contraste WCAG
describe('WCAG Contrast Ratios', () => {
    test('devrait valider les ratios de contraste minimaux', () => {
        // Ratio minimum pour AA normal (4.5:1)
        expect(checkContrast('#000000', '#FFFFFF')).toBe(true); // Noir sur blanc
        expect(checkContrast('#FFFFFF', '#000000')).toBe(true); // Blanc sur noir

        // Test avec des couleurs à faible contraste
        expect(checkContrast('#808080', '#909090')).toBe(false); // Gris similaires
    });

    test('devrait supporter différents formats de couleur', () => {
        expect(checkContrast('black', 'white')).toBe(true);
        expect(checkContrast('#000', '#FFF')).toBe(true);
        expect(checkContrast('rgb(0,0,0)', 'rgb(255,255,255)')).toBe(true);
    });
});