/**
 * api.js - Couche d'accès aux API backend
 * 
 * Pourquoi : Centralise tous les appels HTTP vers le backend pour faciliter
 * la gestion des erreurs, le retry, et l'évolution de l'API.
 */

import { showNotification } from './utils.js';

// ============================================================================
// API GENERIC
// ============================================================================

/**
 * Effectue une requête HTTP vers l'API backend
 * Pourquoi : Fonction générique réutilisable pour tous les appels MCP et autres
 * @param {string} url - URL de l'endpoint
 * @param {Object} options - Options de la requête (method, headers, body)
 * @returns {Promise<Object>} Réponse JSON parsée
 * @throws {Error} Si la requête échoue
 */
export async function apiRequest(url, options = {}) {
    const defaultOptions = {
        method: 'GET',
        headers: {}
    };

    const config = { ...defaultOptions, ...options };

    // Ajoute Content-Type JSON si body est présent et n'est pas une chaîne
    if (config.body && typeof config.body === 'string' && !config.headers['Content-Type']) {
        config.headers['Content-Type'] = 'application/json';
    }

    try {
        const response = await fetch(url, config);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        // Gère les réponses vides (204 No Content)
        if (response.status === 204) {
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error(`❌ Erreur API ${url}:`, error);
        throw error;
    }
}

// ============================================================================
// API SESSIONS
// ============================================================================

/**
 * Charge les données de la session active
 * Pourquoi : Récupère l'état initial au chargement de la page
 * @returns {Promise<Object>} Données de la session active
 */
export async function loadInitialData() {
    try {
        const response = await fetch('/api/sessions/active');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('❌ Erreur chargement données:', error);
        throw error;
    }
}

/**
 * Charge la liste des providers disponibles
 * Pourquoi : Nécessaire pour le modal de création de session
 * @returns {Promise<Array>} Liste des providers
 */
export async function loadProviders() {
    try {
        const response = await fetch('/api/providers');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur chargement providers:', error);
        throw error;
    }
}

/**
 * Charge la liste de tous les modèles disponibles
 * Pourquoi : Nécessaire pour afficher les détails des modèles
 * @returns {Promise<Array>} Liste des modèles
 */
export async function loadModels() {
    try {
        const response = await fetch('/api/models');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur chargement modèles:', error);
        throw error;
    }
}

/**
 * Crée une nouvelle session avec provider et modèle
 * Pourquoi : Permet à l'utilisateur de changer de modèle LLM
 * @param {Object} params - Paramètres de la session
 * @param {string} params.name - Nom de la session
 * @param {string} params.provider - Clé du provider
 * @param {string} params.model - Clé du modèle
 * @returns {Promise<Object>} Session créée
 */
export async function createSession({ name, provider, model }) {
    try {
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, provider, model })
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur création session:', error);
        throw error;
    }
}

// ============================================================================
// API EXPORT
// ============================================================================

/**
 * Exporte les données de la session active
 * Pourquoi : Permet à l'utilisateur de sauvegarder ses données
 * @param {string} format - Format d'export ('csv' ou 'json')
 */
export async function exportData(format) {
    try {
        const response = await fetch(`/api/export/${format}`);
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `session_export_${new Date().toISOString().slice(0, 10)}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification(`Export ${format.toUpperCase()} téléchargé !`, 'success');
    } catch (error) {
        console.error('Erreur export:', error);
        showNotification('Erreur lors de l\'export', 'error');
    }
}

// ============================================================================
// API COMPACTION
// ============================================================================

/**
 * Charge les statistiques de compaction d'une session
 * Pourquoi : Met à jour l'UI du bouton de compaction
 * @param {number} sessionId - ID de la session
 * @returns {Promise<Object>} Statistiques de compaction
 */
export async function getCompactionStats(sessionId) {
    try {
        const response = await fetch(`/api/compaction/${sessionId}/stats`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('❌ Erreur chargement stats compaction:', error);
        throw error;
    }
}

/**
 * Charge le statut de l'auto-compaction
 * Pourquoi : Initialise le toggle d'auto-compaction
 * @param {number} sessionId - ID de la session
 * @returns {Promise<Object>} Statut de l'auto-compaction
 */
export async function getAutoCompactionStatus(sessionId) {
    try {
        const response = await fetch(`/api/compaction/${sessionId}/auto-status`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur chargement statut auto-compaction:', error);
        throw error;
    }
}

/**
 * Bascule l'auto-compaction
 * Pourquoi : Permet à l'utilisateur de contrôler le comportement automatique
 * @param {number} sessionId - ID de la session
 * @param {boolean} enabled - État souhaité
 * @returns {Promise<Object>} Résultat de l'opération
 */
export async function toggleAutoCompaction(sessionId, enabled) {
    try {
        const response = await fetch(`/api/compaction/${sessionId}/toggle-auto`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur toggle auto-compaction:', error);
        throw error;
    }
}

/**
 * Charge l'historique de compaction pour le graphique
 * Pourquoi : Alimente le graphique d'historique
 * @param {number} sessionId - ID de la session
 * @returns {Promise<Object>} Données du graphique
 */
export async function getCompactionHistoryChart(sessionId) {
    try {
        const response = await fetch(`/api/compaction/${sessionId}/history-chart`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('❌ Erreur chargement historique compaction:', error);
        throw error;
    }
}

/**
 * Charge le preview de compaction
 * Pourquoi : Affiche à l'utilisateur l'impact avant d'exécuter
 * @param {number} sessionId - ID de la session
 * @returns {Promise<Object>} Preview de compaction
 */
export async function getCompactionPreview(sessionId) {
    try {
        const response = await fetch(`/api/compaction/${sessionId}/preview`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur chargement preview:', error);
        throw error;
    }
}

/**
 * Exécute la compaction d'une session
 * Pourquoi : Réduit l'usage du contexte en résumant l'historique
 * @param {number} sessionId - ID de la session
 * @param {Object} options - Options de compaction
 * @returns {Promise<Object>} Résultat de la compaction
 */
export async function executeCompaction(sessionId, options = {}) {
    const body = {
        preserve_messages: options.preserve_messages ?? 2,
        force: options.force ?? false
    };
    
    try {
        const response = await fetch(`/api/compaction/${sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur compaction:', error);
        throw error;
    }
}

// ============================================================================
// API RATE LIMIT
// ============================================================================

/**
 * Charge le statut du rate limiting
 * Pourquoi : Affiche les limites d'API restantes
 * @returns {Promise<Object>} Statut du rate limiting
 */
export async function getRateLimitStatus() {
    try {
        const response = await fetch('/api/rate-limit');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur chargement rate limit:', error);
        throw error;
    }
}

// ============================================================================
// API HEALTH
// ============================================================================

/**
 * Vérifie la santé du serveur
 * Pourquoi : Monitoring et diagnostics
 * @returns {Promise<Object>} Statut de santé
 */
export async function checkHealth() {
    try {
        const response = await fetch('/health');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error('Erreur health check:', error);
        throw error;
    }
}
