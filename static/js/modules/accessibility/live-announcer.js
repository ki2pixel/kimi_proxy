/**
 * LiveAnnouncer - Gestion des annonces aria-live pour mises à jour dynamiques
 *
 * Implémente les standards WCAG 2.1 AA pour les annonces aux lecteurs d'écran :
 * - Région aria-live polie pour mises à jour normales
 * - Région assertive pour erreurs critiques
 * - Messages en français
 * - Gestion anti-redondance
 */

export class LiveAnnouncer {
    constructor() {
        this.lastAnnouncement = '';
        this.announcementTimeout = null;
        this.initRegions();
    }

    /**
     * Initialise les régions aria-live
     */
    initRegions() {
        this.createPoliteRegion();
        this.createAssertiveRegion();
    }

    /**
     * Crée la région aria-live polie pour annonces normales
     */
    createPoliteRegion() {
        let region = document.getElementById('live-region-polite');
        if (!region) {
            region = document.createElement('div');
            region.id = 'live-region-polite';
            region.setAttribute('aria-live', 'polite');
            region.setAttribute('aria-atomic', 'true');
            region.style.position = 'absolute';
            region.style.left = '-10000px';
            region.style.width = '1px';
            region.style.height = '1px';
            region.style.overflow = 'hidden';
            document.body.appendChild(region);
        }
        this.politeRegion = region;
    }

    /**
     * Crée la région aria-live assertive pour erreurs
     */
    createAssertiveRegion() {
        let region = document.getElementById('live-region-assertive');
        if (!region) {
            region = document.createElement('div');
            region.id = 'live-region-assertive';
            region.setAttribute('role', 'alert');
            region.setAttribute('aria-live', 'assertive');
            region.setAttribute('aria-atomic', 'true');
            region.style.position = 'absolute';
            region.style.left = '-10000px';
            region.style.width = '1px';
            region.style.height = '1px';
            region.style.overflow = 'hidden';
            document.body.appendChild(region);
        }
        this.assertiveRegion = region;
    }

    /**
     * Annonce un message de manière polie
     * @param {string} message - Message à annoncer
     * @param {boolean} force - Force l'annonce même si identique
     */
    announce(message, force = false) {
        if (!message || (!force && this.isDuplicate(message))) {
            return;
        }

        this.lastAnnouncement = message;

        // Clear timeout précédent
        if (this.announcementTimeout) {
            clearTimeout(this.announcementTimeout);
        }

        // Met à jour la région
        this.politeRegion.textContent = message;

        // Reset après un délai
        this.announcementTimeout = setTimeout(() => {
            this.politeRegion.textContent = '';
            this.lastAnnouncement = '';
        }, 1000);

        console.log('🔊 [LiveAnnouncer] Annonce polie:', message);
    }

    /**
     * Annonce une erreur de manière assertive
     * @param {string} message - Message d'erreur à annoncer
     */
    announceError(message) {
        if (!message) return;

        // Met à jour la région assertive
        this.assertiveRegion.textContent = message;

        // Reset après un délai plus long pour les erreurs
        setTimeout(() => {
            this.assertiveRegion.textContent = '';
        }, 3000);

        console.log('🚨 [LiveAnnouncer] Annonce erreur:', message);
    }

    /**
     * Vérifie si le message est un duplicata récent
     * @param {string} message - Message à vérifier
     * @returns {boolean} True si duplicata
     */
    isDuplicate(message) {
        return this.lastAnnouncement === message;
    }

    /**
     * Annonce une mise à jour de tokens
     * @param {number} tokens - Nombre de tokens
     * @param {number} percentage - Pourcentage d'usage
     */
    announceTokenUpdate(tokens, percentage) {
        const formattedTokens = new Intl.NumberFormat('fr-FR').format(tokens);
        const message = `Utilisation tokens: ${formattedTokens}, ${percentage.toFixed(1)} pour cent`;
        this.announce(message);
    }

    /**
     * Annonce un changement de statut de connexion
     * @param {boolean} connected - État de connexion
     */
    announceConnectionStatus(connected) {
        const message = connected ? 'Connexion WebSocket établie' : 'Connexion WebSocket perdue';
        this.announce(message, true); // Force pour les changements de statut
    }

    /**
     * Annonce un changement de session
     * @param {string} sessionName - Nom de la session
     */
    announceSessionChange(sessionName) {
        const message = `Session changée: ${sessionName}`;
        this.announce(message, true);
    }

    /**
     * Annonce une mise à jour de métriques
     * @param {Object} metrics - Données de métriques
     */
    announceMetricsUpdate(metrics) {
        if (metrics.total_tokens) {
            const message = `Métriques mises à jour: ${new Intl.NumberFormat('fr-FR').format(metrics.total_tokens)} tokens`;
            this.announce(message);
        }
    }

    /**
     * Annonce une alerte
     * @param {Object} alert - Données d'alerte
     */
    announceAlert(alert) {
        if (alert && alert.message) {
            const message = `Alerte: ${alert.message}`;
            this.announce(message, true);
        }
    }

    /**
     * Annonce le début d'une opération longue
     * @param {string} operation - Nom de l'opération
     */
    announceOperationStart(operation) {
        const message = `Début de l'opération: ${operation}`;
        this.announce(message, true);
    }

    /**
     * Annonce la fin d'une opération
     * @param {string} operation - Nom de l'opération
     * @param {boolean} success - Succès de l'opération
     */
    announceOperationEnd(operation, success = true) {
        const status = success ? 'terminée' : 'échouée';
        const message = `Opération ${operation} ${status}`;
        this.announce(message, true);
    }

    /**
     * Nettoie les ressources
     */
    destroy() {
        if (this.announcementTimeout) {
            clearTimeout(this.announcementTimeout);
        }

        // Supprime les régions du DOM
        if (this.politeRegion && this.politeRegion.parentNode) {
            this.politeRegion.parentNode.removeChild(this.politeRegion);
        }
        if (this.assertiveRegion && this.assertiveRegion.parentNode) {
            this.assertiveRegion.parentNode.removeChild(this.assertiveRegion);
        }

        console.log('🧹 [LiveAnnouncer] Nettoyage effectué');
    }
}

// Instance globale pour compatibilité
let liveAnnouncerInstance = null;

/**
 * Récupère l'instance globale du LiveAnnouncer
 * @returns {LiveAnnouncer}
 */
export function getLiveAnnouncer() {
    if (!liveAnnouncerInstance) {
        liveAnnouncerInstance = new LiveAnnouncer();
    }
    return liveAnnouncerInstance;
}