/**
 * DropdownManager - Gestion centralisée des dropdowns avec navigation clavier
 *
 * Implémente les standards WCAG 2.1 AA pour la navigation clavier :
 * - Navigation flèches haut/bas dans les menus
 * - Fermeture avec Échap
 * - Focus trap dans le menu ouvert
 * - Sélection avec Entrée/Espace
 * - Attributs ARIA appropriés
 */

export class DropdownManager {
    constructor(dropdown) {
        this.dropdown = dropdown;
        this.button = dropdown.querySelector('[data-dropdown-trigger]');
        this.menu = dropdown.querySelector('[data-dropdown-menu]');
        this.items = [...dropdown.querySelectorAll('[data-dropdown-item]')];
        this.isOpen = false;
        this.currentIndex = -1;

        if (this.button && this.menu) {
            this.init();
        } else {
            console.warn('DropdownManager: Éléments requis non trouvés', dropdown);
        }
    }

    /**
     * Initialise le dropdown avec les attributs ARIA et les écouteurs
     */
    init() {
        // Configure les attributs ARIA
        this.button.setAttribute('aria-haspopup', 'menu');
        this.button.setAttribute('aria-expanded', 'false');
        this.menu.setAttribute('role', 'menu');
        this.menu.setAttribute('aria-hidden', 'true');

        // Configure les items du menu
        this.items.forEach((item, index) => {
            item.setAttribute('role', 'menuitem');
            item.setAttribute('tabindex', '-1');
            item.setAttribute('aria-selected', 'false');
        });

        // Écouteurs d'événements
        this.button.addEventListener('click', () => this.toggle());
        this.button.addEventListener('keydown', (e) => this.handleButtonKeydown(e));
        document.addEventListener('click', (e) => {
            if (!this.dropdown.contains(e.target)) this.close();
        });

        console.log('🔽 [DropdownManager] Initialisé avec', this.items.length, 'items');
    }

    /**
     * Bascule l'état du dropdown (ouvert/fermé)
     */
    toggle() {
        this.isOpen ? this.close() : this.open();
    }

    /**
     * Ouvre le dropdown
     */
    open() {
        if (this.isOpen) return;

        this.isOpen = true;
        this.button.setAttribute('aria-expanded', 'true');
        this.menu.setAttribute('aria-hidden', 'false');
        this.menu.style.display = 'block';

        // Focus sur le premier item
        this.currentIndex = 0;
        if (this.items[0]) {
            this.items[0].focus();
            this.items[0].setAttribute('aria-selected', 'true');
        }

        // Écouteur pour la navigation clavier dans le menu
        this.menu.addEventListener('keydown', (e) => this.handleMenuKeydown(e));

        console.log('🔽 [DropdownManager] Dropdown ouvert');
    }

    /**
     * Ferme le dropdown
     */
    close() {
        if (!this.isOpen) return;

        this.isOpen = false;
        this.button.setAttribute('aria-expanded', 'false');
        this.menu.setAttribute('aria-hidden', 'true');
        this.menu.style.display = 'none';

        // Remet à jour les attributs aria-selected
        this.items.forEach(item => {
            item.setAttribute('aria-selected', 'false');
        });

        // Focus retour sur le bouton
        this.button.focus();
        this.currentIndex = -1;

        console.log('🔽 [DropdownManager] Dropdown fermé');
    }

    /**
     * Gère les événements clavier sur le bouton
     * @param {KeyboardEvent} e - Événement clavier
     */
    handleButtonKeydown(e) {
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.open();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.open();
                // Focus sur le dernier item si ouverture avec flèche haut
                if (this.items.length > 0) {
                    this.currentIndex = this.items.length - 1;
                    this.items[this.currentIndex].focus();
                    this.updateAriaSelected();
                }
                break;
            case 'Escape':
                this.close();
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                this.toggle();
                break;
        }
    }

    /**
     * Gère les événements clavier dans le menu
     * @param {KeyboardEvent} e - Événement clavier
     */
    handleMenuKeydown(e) {
        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.navigateDown();
                break;
            case 'ArrowUp':
                e.preventDefault();
                this.navigateUp();
                break;
            case 'Escape':
                this.close();
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                this.selectCurrentItem();
                break;
            case 'Tab':
                // Si Tab sans shift, ferme le dropdown
                if (!e.shiftKey) {
                    this.close();
                }
                break;
        }
    }

    /**
     * Navigue vers l'item suivant
     */
    navigateDown() {
        if (this.items.length === 0) return;

        this.currentIndex = (this.currentIndex + 1) % this.items.length;
        this.items[this.currentIndex].focus();
        this.updateAriaSelected();
    }

    /**
     * Navigue vers l'item précédent
     */
    navigateUp() {
        if (this.items.length === 0) return;

        this.currentIndex = this.currentIndex <= 0 ? this.items.length - 1 : this.currentIndex - 1;
        this.items[this.currentIndex].focus();
        this.updateAriaSelected();
    }

    /**
     * Met à jour les attributs aria-selected
     */
    updateAriaSelected() {
        this.items.forEach((item, index) => {
            item.setAttribute('aria-selected', index === this.currentIndex ? 'true' : 'false');
        });
    }

    /**
     * Sélectionne l'item actuellement focusé
     */
    selectCurrentItem() {
        if (this.currentIndex >= 0 && this.currentIndex < this.items.length) {
            const selectedItem = this.items[this.currentIndex];

            // Déclenche l'événement click sur l'item
            selectedItem.click();

            // Ferme le dropdown après sélection
            this.close();
        }
    }

    /**
     * Sélectionne un item par sa valeur ou son texte
     * @param {string} value - Valeur de l'item à sélectionner
     */
    selectItem(value) {
        const itemIndex = this.items.findIndex(item =>
            item.textContent.trim() === value ||
            item.getAttribute('data-value') === value
        );

        if (itemIndex >= 0) {
            this.currentIndex = itemIndex;
            this.selectCurrentItem();
        }
    }

    /**
     * Récupère l'item actuellement sélectionné
     * @returns {HTMLElement|null} Item sélectionné ou null
     */
    getSelectedItem() {
        return this.currentIndex >= 0 && this.currentIndex < this.items.length
            ? this.items[this.currentIndex]
            : null;
    }

    /**
     * Vérifie si le dropdown est ouvert
     * @returns {boolean} True si ouvert
     */
    isDropdownOpen() {
        return this.isOpen;
    }

    /**
     * Nettoie les ressources et supprime les écouteurs
     */
    destroy() {
        if (this.button) {
            this.button.removeEventListener('click', this.toggle);
            this.button.removeEventListener('keydown', this.handleButtonKeydown);
        }

        document.removeEventListener('click', this.close);

        console.log('🧹 [DropdownManager] Nettoyage effectué');
    }

    // ==================================================
    // MÉTHODES STATIQUES
    // ==================================================

    /**
     * Initialise automatiquement tous les dropdowns sur la page
     * Recherche tous les éléments avec data-dropdown
     */
    static initAll() {
        const dropdowns = document.querySelectorAll('[data-dropdown]');
        dropdowns.forEach(dropdown => {
            if (!dropdown._dropdownManager) {
                dropdown._dropdownManager = new DropdownManager(dropdown);
            }
        });

        console.log('🔽 [DropdownManager] Initialisé', dropdowns.length, 'dropdowns');
    }

    /**
     * Recherche et retourne le DropdownManager pour un élément donné
     * @param {HTMLElement} element - Élément dans le dropdown
     * @returns {DropdownManager|null} Manager du dropdown ou null
     */
    static getManagerFor(element) {
        const dropdown = element.closest('[data-dropdown]');
        return dropdown ? dropdown._dropdownManager : null;
    }

    /**
     * Ferme tous les dropdowns ouverts
     */
    static closeAll() {
        const dropdowns = document.querySelectorAll('[data-dropdown]');
        dropdowns.forEach(dropdown => {
            if (dropdown._dropdownManager && dropdown._dropdownManager.isOpen) {
                dropdown._dropdownManager.close();
            }
        });
    }
}

// Instance globale pour compatibilité
let dropdownManagerInstances = new Map();

/**
 * Récupère ou crée un DropdownManager pour un élément
 * @param {HTMLElement} dropdown - Élément dropdown
 * @returns {DropdownManager}
 */
export function getDropdownManager(dropdown) {
    if (!dropdownManagerInstances.has(dropdown)) {
        dropdownManagerInstances.set(dropdown, new DropdownManager(dropdown));
    }
    return dropdownManagerInstances.get(dropdown);
}

/**
 * Initialise tous les dropdowns sur la page
 */
export function initAllDropdowns() {
    DropdownManager.initAll();
}