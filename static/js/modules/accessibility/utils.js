/**
 * utils.js - Utilitaires d'accessibilité WCAG 2.1 AA
 *
 * Fournit des fonctions utilitaires réutilisables pour l'accessibilité :
 * - Focus trap générique
 * - Skip links pour navigation rapide
 * - Vérification contraste des couleurs
 * - Gestion des attributs ARIA
 * - Navigation clavier
 */

/**
 * Focus Trap - Piège le focus dans un élément conteneur
 * Utile pour les modales, dropdowns, et autres composants isolés
 * @param {HTMLElement} container - Élément conteneur
 * @param {Function} onEscape - Callback optionnel pour la touche Échap
 * @returns {Object} Contrôles pour activer/désactiver le focus trap
 */
export function trapFocus(container, onEscape = null) {
    if (!container) return null;

    const focusableElements = container.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    if (focusableElements.length === 0) return null;

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    let isActive = false;

    function handleTabKey(e) {
        if (!isActive || e.key !== 'Tab') return;

        if (e.shiftKey) {
            // Shift + Tab sur le premier élément → dernier élément
            if (document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
        } else {
            // Tab sur le dernier élément → premier élément
            if (document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        }
    }

    function handleEscapeKey(e) {
        if (!isActive || e.key !== 'Escape') return;
        if (onEscape) {
            onEscape();
        }
    }

    function activate() {
        if (isActive) return;
        isActive = true;
        container.addEventListener('keydown', handleTabKey);
        container.addEventListener('keydown', handleEscapeKey);
        console.log('🔒 Focus trap activé sur', container);
    }

    function deactivate() {
        if (!isActive) return;
        isActive = false;
        container.removeEventListener('keydown', handleTabKey);
        container.removeEventListener('keydown', handleEscapeKey);
        console.log('🔓 Focus trap désactivé sur', container);
    }

    return { activate, deactivate, isActive: () => isActive };
}

/**
 * Ajoute un skip link pour la navigation clavier
 * Permet aux utilisateurs de clavier de sauter directement au contenu principal
 * @param {string} targetId - ID de l'élément cible (défaut: 'main-content')
 * @param {string} text - Texte du lien (défaut: 'Aller au contenu principal')
 */
export function addSkipLink(targetId = 'main-content', text = 'Aller au contenu principal') {
    // Vérifie si le skip link existe déjà
    if (document.getElementById('skip-link')) return;

    const skipLink = document.createElement('a');
    skipLink.id = 'skip-link';
    skipLink.href = `#${targetId}`;
    skipLink.textContent = text;
    skipLink.className = 'sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 bg-blue-600 text-white px-4 py-2 rounded-lg z-50 focus:outline-none focus:ring-2 focus:ring-blue-300';

    // Styles pour les lecteurs d'écran uniquement (sr-only)
    const style = document.createElement('style');
    const cssRules = `
        .sr-only {
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }
        .sr-only.focus:not(.sr-only) {
            position: fixed;
            top: 1rem;
            left: 1rem;
            width: auto;
            height: auto;
            padding: 0.5rem 1rem;
            margin: 0;
            overflow: visible;
            clip: auto;
            white-space: normal;
            background: #2563eb;
            color: white;
            border-radius: 0.5rem;
            z-index: 9999;
            text-decoration: none;
            font-weight: 600;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }
    `;
    style.textContent = cssRules;
    document.head.appendChild(style);

    // Gestion du focus
    skipLink.addEventListener('click', (e) => {
        const target = document.getElementById(targetId);
        if (target) {
            target.focus();
            target.scrollIntoView({ behavior: 'smooth' });
        }
    });

    document.body.insertBefore(skipLink, document.body.firstChild);
    console.log('⏭️ Skip link ajouté:', text);
}

/**
 * Vérifie le contraste entre deux couleurs selon WCAG 2.1 AA
 * @param {string} color1 - Première couleur (format hex, rgb, hsl)
 * @param {string} color2 - Seconde couleur (format hex, rgb, hsl)
 * @param {number} minRatio - Ratio minimum requis (défaut: 4.5 pour AA normal)
 * @returns {boolean} True si le contraste est suffisant
 */
export function checkContrast(color1, color2, minRatio = 4.5) {
    try {
        // Convertit les couleurs en RGB
        const rgb1 = parseColor(color1);
        const rgb2 = parseColor(color2);

        if (!rgb1 || !rgb2) return false;

        // Calcule la luminance relative
        const lum1 = getRelativeLuminance(rgb1);
        const lum2 = getRelativeLuminance(rgb2);

        // Calcule le ratio de contraste
        const lighter = Math.max(lum1, lum2);
        const darker = Math.min(lum1, lum2);
        const ratio = (lighter + 0.05) / (darker + 0.05);

        return ratio >= minRatio;
    } catch (error) {
        console.warn('Erreur vérification contraste:', error);
        return false;
    }
}

/**
 * Parse une couleur en format RGB
 * @param {string} color - Couleur à parser
 * @returns {Object|null} Objet RGB ou null si invalide
 */
function parseColor(color) {
    if (!color) return null;

    // Format hex (#RGB, #RRGGBB)
    const hexMatch = color.match(/^#([a-f\d]{3}|[a-f\d]{6})$/i);
    if (hexMatch) {
        const hex = hexMatch[1];
        const rgb = hex.length === 3
            ? hex.split('').map(c => parseInt(c + c, 16))
            : [hex.substr(0, 2), hex.substr(2, 2), hex.substr(4, 2)].map(c => parseInt(c, 16));
        return { r: rgb[0], g: rgb[1], b: rgb[2] };
    }

    // Format rgb/rgba
    const rgbMatch = color.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)$/i);
    if (rgbMatch) {
        return {
            r: parseInt(rgbMatch[1], 10),
            g: parseInt(rgbMatch[2], 10),
            b: parseInt(rgbMatch[3], 10)
        };
    }

    // Format nommé (basic)
    const namedColors = {
        'black': { r: 0, g: 0, b: 0 },
        'white': { r: 255, g: 255, b: 255 },
        'red': { r: 255, g: 0, b: 0 },
        'green': { r: 0, g: 128, b: 0 },
        'blue': { r: 0, g: 0, b: 255 },
        'gray': { r: 128, g: 128, b: 128 },
        'grey': { r: 128, g: 128, b: 128 }
    };

    return namedColors[color.toLowerCase()] || null;
}

/**
 * Calcule la luminance relative d'une couleur RGB
 * @param {Object} rgb - Objet RGB {r, g, b}
 * @returns {number} Luminance relative (0-1)
 */
function getRelativeLuminance(rgb) {
    const { r, g, b } = rgb;

    // Convertit en sRGB linéaire
    const toLinear = (c) => {
        c = c / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    };

    const rLinear = toLinear(r);
    const gLinear = toLinear(g);
    const bLinear = toLinear(b);

    // Calcule la luminance
    return 0.2126 * rLinear + 0.7152 * gLinear + 0.0722 * bLinear;
}

/**
 * Définit les attributs ARIA pour un élément
 * @param {HTMLElement} element - Élément cible
 * @param {Object} attributes - Attributs ARIA à définir
 */
export function setAriaAttributes(element, attributes) {
    if (!element || !attributes) return;

    Object.entries(attributes).forEach(([key, value]) => {
        const ariaKey = key.startsWith('aria-') ? key : `aria-${key}`;
        if (value === null || value === undefined) {
            element.removeAttribute(ariaKey);
        } else {
            element.setAttribute(ariaKey, String(value));
        }
    });
}

/**
 * Gère la navigation clavier pour une liste d'éléments
 * @param {HTMLElement} container - Conteneur des éléments
 * @param {string} selector - Sélecteur CSS pour les éléments navigables
 * @param {Object} options - Options de configuration
 * @returns {Object} Contrôles de navigation
 */
export function setupKeyboardNavigation(container, selector, options = {}) {
    const {
        onSelect = null,
        loop = true,
        activateOnFocus = false,
        orientation = 'vertical' // 'vertical' | 'horizontal'
    } = options;

    let currentIndex = -1;
    const items = Array.from(container.querySelectorAll(selector));
    let isActive = false;

    function getNavigationKeys() {
        return orientation === 'horizontal'
            ? { prev: 'ArrowLeft', next: 'ArrowRight' }
            : { prev: 'ArrowUp', next: 'ArrowDown' };
    }

    function focusItem(index) {
        if (index < 0 || index >= items.length) return;

        currentIndex = index;
        items[index].focus();

        if (activateOnFocus && onSelect) {
            onSelect(items[index], index);
        }

        // Met à jour les attributs ARIA
        items.forEach((item, i) => {
            setAriaAttributes(item, {
                'selected': i === index ? 'true' : 'false'
            });
        });
    }

    function handleKeydown(e) {
        if (!isActive) return;

        const { prev, next } = getNavigationKeys();

        switch (e.key) {
            case prev:
                e.preventDefault();
                const prevIndex = loop && currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
                focusItem(prevIndex);
                break;

            case next:
                e.preventDefault();
                const nextIndex = loop && currentIndex >= items.length - 1 ? 0 : currentIndex + 1;
                focusItem(nextIndex);
                break;

            case 'Enter':
            case ' ':
                e.preventDefault();
                if (onSelect && currentIndex >= 0) {
                    onSelect(items[currentIndex], currentIndex);
                }
                break;

            case 'Home':
                e.preventDefault();
                focusItem(0);
                break;

            case 'End':
                e.preventDefault();
                focusItem(items.length - 1);
                break;
        }
    }

    function activate() {
        if (isActive) return;
        isActive = true;
        container.addEventListener('keydown', handleKeydown);
        console.log('⌨️ Navigation clavier activée');
    }

    function deactivate() {
        if (!isActive) return;
        isActive = false;
        container.removeEventListener('keydown', handleKeydown);
        currentIndex = -1;
        console.log('🚫 Navigation clavier désactivée');
    }

    function updateItems() {
        const newItems = Array.from(container.querySelectorAll(selector));
        if (newItems.length !== items.length) {
            items.splice(0, items.length, ...newItems);
            if (currentIndex >= items.length) {
                currentIndex = items.length - 1;
            }
        }
    }

    return {
        activate,
        deactivate,
        focusItem,
        updateItems,
        getCurrentIndex: () => currentIndex,
        isActive: () => isActive
    };
}

/**
 * Annonce un message aux lecteurs d'écran via un élément aria-live
 * @param {string} message - Message à annoncer
 * @param {string} priority - Priorité ('polite' ou 'assertive')
 */
export function announceToScreenReader(message, priority = 'polite') {
    if (!message) return;

    // Crée ou récupère l'élément d'annonce
    let announcer = document.getElementById('sr-announcer');
    if (!announcer) {
        announcer = document.createElement('div');
        announcer.id = 'sr-announcer';
        announcer.setAttribute('aria-live', 'polite');
        announcer.setAttribute('aria-atomic', 'true');
        announcer.style.position = 'absolute';
        announcer.style.left = '-10000px';
        announcer.style.width = '1px';
        announcer.style.height = '1px';
        announcer.style.overflow = 'hidden';
        document.body.appendChild(announcer);
    }

    // Met à jour l'attribut aria-live selon la priorité
    announcer.setAttribute('aria-live', priority);

    // Annonce le message
    announcer.textContent = message;

    // Reset après un délai
    setTimeout(() => {
        announcer.textContent = '';
    }, 1000);

    console.log('Annonce lecteur d\'écran:', message);
}

/**
 * Vérifie si un élément est focusable
 * @param {HTMLElement} element - Élément à vérifier
 * @returns {boolean} True si focusable
 */
export function isFocusable(element) {
    if (!element) return false;

    const tagName = element.tagName.toLowerCase();
    const hasHref = element.hasAttribute('href');
    const hasTabindex = element.hasAttribute('tabindex');
    const tabindex = element.getAttribute('tabindex');

    // Éléments naturellement focusables
    const focusableTags = ['input', 'select', 'textarea', 'button', 'a', 'area'];

    if (focusableTags.includes(tagName)) {
        // Pour les liens, vérifie href
        if (tagName === 'a' && !hasHref) return false;
        // Pour les inputs, vérifie type
        if (tagName === 'input' && element.type === 'hidden') return false;
        return true;
    }

    // Éléments avec tabindex positif ou zéro
    if (hasTabindex && (tabindex === '0' || parseInt(tabindex, 10) > 0)) {
        return true;
    }

    return false;
}

/**
 * Trouve le prochain élément focusable dans une direction donnée
 * @param {HTMLElement} currentElement - Élément actuel
 * @param {string} direction - Direction ('next' ou 'previous')
 * @returns {HTMLElement|null} Prochain élément focusable ou null
 */
export function findNextFocusable(currentElement, direction = 'next') {
    if (!currentElement) return null;

    const focusableElements = Array.from(
        document.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
    );

    const currentIndex = focusableElements.indexOf(currentElement);
    if (currentIndex === -1) return null;

    if (direction === 'next') {
        return currentIndex < focusableElements.length - 1 ? focusableElements[currentIndex + 1] : null;
    } else {
        return currentIndex > 0 ? focusableElements[currentIndex - 1] : null;
    }
}

/**
 * Crée un élément avec les attributs d'accessibilité appropriés
 * @param {string} tagName - Nom de la balise
 * @param {Object} attributes - Attributs HTML et ARIA
 * @returns {HTMLElement} Élément créé
 */
export function createAccessibleElement(tagName, attributes = {}) {
    const element = document.createElement(tagName);

    Object.entries(attributes).forEach(([key, value]) => {
        if (key.startsWith('aria-')) {
            element.setAttribute(key, String(value));
        } else if (key === 'class') {
            element.className = value;
        } else if (key === 'textContent' || key === 'innerText') {
            element.textContent = value;
        } else {
            element.setAttribute(key, String(value));
        }
    });

    return element;
}