/**
 * ModalManager - Gestion centralisée du focus pour les modales
 *
 * Implémente les standards WCAG 2.1 AA pour la gestion du focus :
 * - Focus trap dans les modales ouvertes
 * - Restauration du focus à la fermeture
 * - Support de la touche Échap pour fermer
 * - Attributs ARIA appropriés
 */

export class ModalManager {
    constructor() {
        this.openModals = new Set();
        this.previouslyFocused = null;
    }

    /**
     * Ouvre une modale avec gestion du focus
     * @param {HTMLElement} modal - Élément modale à ouvrir
     */
    open(modal) {
        if (!modal) return;

        const focusable = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        // Sauvegarde l'élément précédemment focusé
        this.previouslyFocused = document.activeElement;

        // Ajoute la modale à la liste des modales ouvertes
        this.openModals.add(modal);

        // Configure les attributs ARIA
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');

        // Focus sur le premier élément focusable
        setTimeout(() => {
            if (focusable.length > 0) {
                focusable[0].focus();
            }
        }, 100);

        // Configure le focus trap
        this.setupFocusTrap(modal, focusable);

        console.log('🔄 [ModalManager] Modale ouverte avec gestion du focus');
    }

    /**
     * Ferme une modale avec restauration du focus
     * @param {HTMLElement} modal - Élément modale à fermer
     */
    close(modal) {
        if (!modal) return;

        // Supprime la modale de la liste des modales ouvertes
        this.openModals.delete(modal);

        // Supprime les attributs ARIA
        modal.removeAttribute('role');
        modal.removeAttribute('aria-modal');

        // Restaure le focus sur l'élément précédemment focusé
        if (this.previouslyFocused && document.contains(this.previouslyFocused)) {
            setTimeout(() => {
                this.previouslyFocused.focus();
            }, 100);
        }

        console.log('🔄 [ModalManager] Modale fermée avec restauration du focus');
    }

    /**
     * Configure le focus trap pour une modale
     * @param {HTMLElement} modal - Élément modale
     * @param {NodeList} focusable - Éléments focusables dans la modale
     */
    setupFocusTrap(modal, focusable) {
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        const handleKeydown = (e) => {
            if (e.key !== 'Tab') return;

            // Shift + Tab sur le premier élément → focus sur le dernier
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            }
            // Tab sur le dernier élément → focus sur le premier
            else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        };

        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                // Trouve la fonction de fermeture appropriée selon le type de modale
                const modalId = modal.id;
                if (modalId === 'newSessionModal') {
                    if (window.closeNewSessionModal) {
                        window.closeNewSessionModal();
                    }
                } else if (modalId === 'compactPreviewModal') {
                    if (window.closeCompactPreviewModal) {
                        window.closeCompactPreviewModal();
                    }
                } else if (modalId === 'compactResultModal') {
                    if (window.closeCompactResultModal) {
                        window.closeCompactResultModal();
                    }
                } else if (modal.classList.contains('memory-modal')) {
                    // Pour les modales mémoire, cherche le bouton de fermeture
                    const closeBtn = modal.querySelector('.memory-modal-close');
                    if (closeBtn) {
                        closeBtn.click();
                    }
                }
            }
        };

        // Ajoute les écouteurs d'événements
        modal.addEventListener('keydown', handleKeydown);
        modal.addEventListener('keydown', handleEscape);

        // Stocke les références pour pouvoir les supprimer plus tard
        modal._focusTrapHandlers = { handleKeydown, handleEscape };
    }

    /**
     * Vérifie si une modale est actuellement ouverte
     * @param {HTMLElement} modal - Élément modale à vérifier
     * @returns {boolean} True si la modale est ouverte
     */
    isOpen(modal) {
        return this.openModals.has(modal);
    }

    /**
     * Ferme toutes les modales ouvertes
     */
    closeAll() {
        const modals = Array.from(this.openModals);
        modals.forEach(modal => this.close(modal));
    }

    /**
     * Obtient le nombre de modales actuellement ouvertes
     * @returns {number} Nombre de modales ouvertes
     */
    getOpenCount() {
        return this.openModals.size;
    }
}

// Instance globale pour compatibilité
let modalManagerInstance = null;

/**
 * Récupère l'instance globale du ModalManager
 * @returns {ModalManager}
 */
export function getModalManager() {
    if (!modalManagerInstance) {
        modalManagerInstance = new ModalManager();
    }
    return modalManagerInstance;
}