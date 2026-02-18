/**
 * utils.js - Fonctions utilitaires génériques
 * 
 * Pourquoi : Centralise les fonctions utilitaires pour éviter la duplication
 * et faciliter la maintenance des helpers communs.
 */

// ============================================================================
// CONSTANTES GLOBALES
// ============================================================================

export const MAX_CONTEXT = 262144;
export const WS_URL = `ws://${window.location.host}/ws`;

export const ALERT_THRESHOLDS = {
    caution: { level: 80, color: '#eab308', bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
    warning: { level: 90, color: '#f97316', bg: 'bg-orange-500/20', text: 'text-orange-400' },
    critical: { level: 95, color: '#ef4444', bg: 'bg-red-500/20', text: 'text-red-400' }
};

// ============================================================================
// BUS D'ÉVÉNEMENTS CENTRALISÉ
// ============================================================================

/**
 * Pourquoi : Un bus d'événements permet une communication découplée entre modules.
 * Évite les dépendances circulaires et facilite l'extension des fonctionnalités.
 */
export const eventBus = {
    events: {},
    
    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    },
    
    off(event, callback) {
        if (!this.events[event]) return;
        this.events[event] = this.events[event].filter(cb => cb !== callback);
    },
    
    emit(event, data) {
        if (!this.events[event]) return;
        this.events[event].forEach(callback => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Erreur dans le handler de l'événement ${event}:`, error);
            }
        });
    }
};

// ============================================================================
// FONCTIONS UTILITAIRES
// ============================================================================

/**
 * Échappe les caractères HTML pour éviter les injections XSS
 * Pourquoi : Sécurité - évite l'exécution de code malveillant dans les previews
 * @param {string} text - Texte à échapper
 * @returns {string} Texte échappé
 */
export function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Affiche une notification temporaire à l'écran
 * Pourquoi : Feedback utilisateur pour les actions (succès, erreur)
 * @param {string} message - Message à afficher
 * @param {string} type - Type de notification ('success' ou 'error')
 */
export function showNotification(message, type = 'success') {
    const div = document.createElement('div');
    div.className = `fixed bottom-4 right-4 px-6 py-3 rounded-xl text-white font-medium z-50 animate-in slide-in-from-bottom-4 ${
        type === 'success' ? 'bg-green-600' : 'bg-red-600'
    }`;
    div.textContent = message;
    document.body.appendChild(div);
    
    setTimeout(() => {
        div.remove();
    }, 3000);
}

/**
 * Formate un nombre de tokens avec séparateurs de milliers
 * Pourquoi : Lisibilité des grands nombres (ex: 262144 → "262 144")
 * @param {number} tokens - Nombre de tokens
 * @returns {string} Nombre formaté
 */
export function formatTokens(tokens) {
    if (tokens === undefined || tokens === null) return '0';
    return Math.round(tokens).toLocaleString('fr-FR');
}

/**
 * Formate un pourcentage avec 1 décimale
 * @param {number} percentage - Pourcentage
 * @returns {string} Pourcentage formaté
 */
export function formatPercentage(percentage) {
    if (percentage === undefined || percentage === null) return '0.0%';
    return `${percentage.toFixed(1)}%`;
}

/**
 * Calcule la couleur selon le pourcentage d'usage
 * Pourquoi : Cohérence visuelle des indicateurs (vert → jaune → rouge)
 * @param {number} percentage - Pourcentage d'usage
 * @returns {string} Code couleur hexadécimal
 */
export function getColorForPercentage(percentage) {
    if (percentage < 50) {
        return '#22c55e';  // Vert
    } else if (percentage < 80) {
        return '#eab308';  // Jaune
    } else {
        return '#ef4444';  // Rouge
    }
}

/**
 * Débounce pour limiter les appels fréquents
 * Pourquoi : Optimisation des performances (ex: recherche, redimensionnement)
 * @param {Function} func - Fonction à debouncer
 * @param {number} wait - Délai en ms
 * @returns {Function} Fonction debouncée
 */
export function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle pour limiter les appels à une fréquence fixe
 * Pourquoi : Éviter de surcharger le navigateur avec des mises à jour trop fréquentes
 * @param {Function} func - Fonction à throttler
 * @param {number} limit - Limite en ms
 * @returns {Function} Fonction throttlée
 */
export function throttle(func, limit = 100) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Détermine la classe CSS selon le provider
 * Pourquoi : Cohérence visuelle des badges de provider dans l'UI
 * @param {string} providerKey - Clé du provider
 * @returns {string} Nom de la couleur Tailwind
 */
export function getProviderColor(providerKey) {
    const colorMap = {
        'kimi': 'purple',
        'nvidia': 'green',
        'mistral': 'blue',
        'openrouter': 'orange',
        'siliconflow': 'cyan',
        'groq': 'yellow',
        'cerebras': 'red',
        'gemini': 'indigo'
    };
    
    for (const [key, color] of Object.entries(colorMap)) {
        if (providerKey.includes(key)) {
            return color;
        }
    }
    return 'slate';
}

/**
 * Formate une taille de contexte en notation lisible
 * Pourquoi : Convertit 262144 en "256K" ou 1048576 en "1M"
 * @param {number} contextSize - Taille du contexte
 * @returns {string} Taille formatée
 */
export function formatContextSize(contextSize) {
    const contextK = Math.round(contextSize / 1024);
    if (contextK >= 1024) {
        return `${(contextK / 1024).toFixed(1)}M`;
    }
    return `${contextK}K`;
}
