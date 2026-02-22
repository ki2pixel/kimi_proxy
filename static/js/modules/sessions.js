/**
 * sessions.js - Gestion des sessions et des métriques
 * 
 * Pourquoi : Centralise la logique métier des sessions et maintient l'état
 * des métriques pour l'affichage et l'historique.
 */

import { loadInitialData } from './api.js';
import { formatTokens, eventBus } from './utils.js';

// ============================================================================
// SESSIONMANAGER CLASS - Gestion centralisée des sessions
// ============================================================================

/**
 * SessionManager - Classe principale pour gérer les sessions et leur configuration
 * Pourquoi : Centralise la logique de changement de session et mise à jour proxy
 */
export class SessionManager {
    constructor() {
        this.activeSession = null;
        this.sessionHistory = [];
        this.sessionProxyMap = new Map();
    }

    /**
     * Change de session de manière atomique
     * @param {string} sessionId - ID de la nouvelle session
     * @param {Array} existingMetrics - Métriques existantes (optionnel)
     * @returns {Promise<Object>} Nouvelle session chargée
     */
    async switchSession(sessionId, existingMetrics = null) {
        try {
            console.log(`🔄 [SessionManager] Changement vers session: ${sessionId}`);

            // Récupère la session précédente
            const previousSession = this.activeSession;

            // Charge la nouvelle session
            const newSession = await this.loadSession(sessionId);
            if (!newSession) {
                throw new Error(`Session ${sessionId} introuvable`);
            }

            // Ajouter les métriques existantes si fournies
            if (existingMetrics) {
                newSession.metrics = existingMetrics;
                console.log(`📊 [SessionManager] Métriques existantes chargées: ${existingMetrics.length} éléments`);
            }

            // Mise à jour atomique de l'état
            this.activeSession = newSession;
            this.sessionHistory.push(newSession);

            // La configuration proxy est gérée automatiquement par le routing
            // Plus besoin d'appel explicite à updateProxyConfig()

            // Émet l'événement de changement de session avec toutes les données nécessaires
            eventBus.emit('sessionChanged', {
                oldSession: previousSession,
                newSession: newSession,
                proxyConfig: this.getProxyConfig(newSession)
            });

            console.log(`✅ [SessionManager] Session changée: ${newSession.id}`);
            return newSession;

        } catch (error) {
            console.error('❌ [SessionManager] Erreur changement session:', error);
            throw error;
        }
    }

    /**
     * Charge une session depuis l'API
     * @param {string} sessionId - ID de la session
     * @returns {Promise<Object|null>} Données de session
     */
    async loadSession(sessionId) {
        try {
            const response = await fetch(`/api/sessions/${sessionId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const sessionData = await response.json();
            return sessionData.session || sessionData;
        } catch (error) {
            console.error(`Erreur chargement session ${sessionId}:`, error);
            return null;
        }
    }

    /**
     * Met à jour la configuration proxy pour la session active
     * @param {Object} session - Données de session
     * @returns {Promise<void>}
     * @deprecated La configuration est gérée automatiquement par le routing
     */
    async updateProxyConfig(session) {
        console.warn('⚠️ [SessionManager] updateProxyConfig() est déprécié - le routing gère la configuration automatiquement');
        try {
            // Extraction du provider depuis le modèle
            const provider = this.extractProvider(session.model);

            // Configuration de routage (pour compatibilité)
            const routingConfig = {
                model: session.model,
                provider: provider,
                api_key: session.api_key || await this.getApiKeyForProvider(provider),
                timeout: this.getTimeoutForProvider(provider),
                session_id: session.id
            };

            // Met à jour le cache local
            this.sessionProxyMap.set(session.id, routingConfig);

            console.log(`✅ [SessionManager] Config proxy mise à jour localement pour ${provider}`);
        } catch (error) {
            console.error('❌ [SessionManager] Erreur config proxy:', error);
            throw error;
        }
    }

    /**
     * Extrait le provider depuis le nom du modèle
     * @param {string} model - Nom du modèle (ex: "kimi-code", "gpt-4", "claude-3")
     * @returns {string} Nom du provider
     */
    extractProvider(model) {
        if (!model) return 'unknown';

        // Mapping direct pour les modèles connus
        const modelMappings = {
            'kimi': 'nvidia',
            'kimi-code': 'nvidia',
            'kimi-code-2.5': 'nvidia',
            'gpt': 'openai',
            'claude': 'anthropic',
            'mistral': 'mistral',
            'llama': 'meta',
            'gemini': 'google'
        };

        // Recherche par préfixe
        for (const [prefix, provider] of Object.entries(modelMappings)) {
            if (model.toLowerCase().startsWith(prefix)) {
                return provider;
            }
        }

        // Fallback: extraction du préfixe avant le premier tiret
        const parts = model.split('-');
        return parts.length > 1 ? parts[0].toLowerCase() : 'unknown';
    }

    /**
     * Récupère la clé API pour un provider
     * @param {string} provider - Nom du provider
     * @returns {Promise<string|null>} Clé API
     */
    async getApiKeyForProvider(provider) {
        try {
            // Dans un environnement réel, ceci devrait venir des variables d'environnement
            // ou d'un service de gestion des secrets
            const apiKeys = {
                'nvidia': process.env.KIMI_API_KEY || null,
                'openai': process.env.OPENAI_API_KEY || null,
                'anthropic': process.env.ANTHROPIC_API_KEY || null,
                'mistral': process.env.MISTRAL_API_KEY || null
            };

            return apiKeys[provider] || null;
        } catch (error) {
            console.warn(`Clé API non trouvée pour ${provider}`);
            return null;
        }
    }

    /**
     * Définit le timeout selon le provider
     * @param {string} provider - Nom du provider
     * @returns {number} Timeout en secondes
     */
    getTimeoutForProvider(provider) {
        const timeouts = {
            'nvidia': 30,
            'openai': 60,
            'anthropic': 120,
            'mistral': 45,
            'google': 60,
            'meta': 90
        };

        return timeouts[provider] || 30;
    }

    /**
     * Récupère la configuration proxy pour une session
     * @param {Object} session - Données de session
     * @returns {Object|null} Configuration proxy
     */
    getProxyConfig(session) {
        return this.sessionProxyMap.get(session.id) || null;
    }

    /**
     * Récupère la session active
     * @returns {Object|null} Session active
     */
    getActiveSession() {
        return this.activeSession;
    }

    /**
     * Vérifie si une session est active
     * @param {string} sessionId - ID de session
     * @returns {boolean} True si active
     */
    isSessionActive(sessionId) {
        return this.activeSession && this.activeSession.id === sessionId;
    }

    /**
     * Nettoie les anciennes configurations proxy
     * @param {number} maxHistory - Nombre maximum de sessions en historique
     */
    cleanupOldConfigs(maxHistory = 10) {
        if (this.sessionHistory.length > maxHistory) {
            const oldSessions = this.sessionHistory.splice(0, this.sessionHistory.length - maxHistory);
            oldSessions.forEach(session => {
                this.sessionProxyMap.delete(session.id);
            });
        }
    }
}

// ============================================================================
// INSTANCE GLOBALE (pour compatibilité)
// ============================================================================

let sessionManagerInstance = null;

/**
 * Récupère l'instance globale du SessionManager
 * @returns {SessionManager}
 */
export function getSessionManager() {
    if (!sessionManagerInstance) {
        sessionManagerInstance = new SessionManager();
    }
    return sessionManagerInstance;
}

// ============================================================================
// ÉTAT GLOBAL DES SESSIONS (legacy - à migrer)
// ============================================================================

let currentSessionId = null;
let sessionMetrics = [];
let currentMaxContext = 262144;

// Gestion des sources de données (proxy vs logs)
let lastProxyData = null;
let lastLogData = null;

// Mémoire MCP
let currentMemoryMetrics = {
    memory_tokens: 0,
    chat_tokens: 0,
    memory_ratio: 0,
    has_memory: false
};

// ============================================================================
// GETTERS
// ============================================================================

export function getCurrentSessionId() {
    return currentSessionId;
}

export function getSessionMetrics() {
    return sessionMetrics;
}

export function getCurrentMaxContext() {
    return currentMaxContext;
}

export function getCurrentMemoryMetrics() {
    return currentMemoryMetrics;
}

export function getLastProxyData() {
    return lastProxyData;
}

export function getLastLogData() {
    return lastLogData;
}

// ============================================================================
// SETTERS
// ============================================================================

export function setCurrentSessionId(id) {
    currentSessionId = id;
}

export function setCurrentMaxContext(context) {
    currentMaxContext = context;
}

export function setLastProxyData(data) {
    lastProxyData = data;
}

export function setLastLogData(data) {
    lastLogData = data;
}

// ============================================================================
// CHARGEMENT DES DONNÉES
// ============================================================================

/**
 * Charge et traite les données de session
 * Pourquoi : Initialise l'état complet de l'application au démarrage
 * @param {Object} data - Données brutes de l'API
 * @returns {Object} Données traitées
 */
export function loadSessionData(data) {
    if (!data.session) return null;
    
    currentSessionId = data.session.id;
    
    // Émet l'événement de changement de session
    eventBus.emit('session:loaded', data);
    
    // Met à jour le max_context
    currentMaxContext = data.session.max_context || 262144;
    
    // Met à jour les métriques mémoire si présentes
    if (data.memory) {
        currentMemoryMetrics = {
            memory_tokens: data.memory.memory_tokens || 0,
            chat_tokens: data.memory.chat_tokens || 0,
            memory_ratio: data.memory.memory_ratio || 0,
            has_memory: data.memory.memory_tokens > 0
        };
        eventBus.emit('memory:updated', currentMemoryMetrics);
    }
    
    // Charge les métriques existantes
    if (data.recent_metrics) {
        sessionMetrics = data.recent_metrics.reverse();
        eventBus.emit('metrics:loaded', sessionMetrics);
    }
    
    return data;
}

/**
 * Recharge les données depuis le serveur
 * Pourquoi : Synchronisation après changement de session
 */
export async function reloadSessionData() {
    try {
        const data = await loadInitialData();
        
        // Reload complete session data including provider and model info
        if (data && data.session) {
            eventBus.emit('session:loaded', data);
        }
        
        return loadSessionData(data);
    } catch (error) {
        console.error('❌ Erreur rechargement données:', error);
        throw error;
    }
}

// ============================================================================
// GESTION DES MÉTRIQUES
// ============================================================================

/**
 * Calcule le delta de tokens entre deux requêtes consécutives
 * Pourquoi : Montre l'incrément réel de nouveau contenu
 * @param {Object} currentMetric - Métrique courante
 * @returns {number} Delta de tokens (nouveau contenu)
 */
function calculateTokenDelta(currentMetric) {
    if (sessionMetrics.length === 0) {
        return currentMetric.estimated_tokens || 0;
    }
    
    // Prend la dernière métrique existante
    const lastMetric = sessionMetrics[sessionMetrics.length - 1];
    const currentTokens = currentMetric.estimated_tokens || 0;
    const lastTokens = lastMetric.estimated_tokens || 0;
    
    // Si la métrique courante contient un delta du serveur, l'utilise
    if (currentMetric.delta_tokens > 0) {
        return currentMetric.delta_tokens;
    }
    
    // Sinon calcule la différence
    return Math.max(0, currentTokens - lastTokens);
}

/**
 * Ajoute une nouvelle métrique à la session courante
 * Pourquoi : Maintient l'historique des tokens pour les graphiques
 * @param {Object} metric - Métrique à ajouter
 * @param {number} sessionId - ID de la session associée
 */
export function addMetric(metric, sessionId) {
    if (!currentSessionId && sessionId) {
        currentSessionId = sessionId;
    }
    
    // Si changement de session, recharge tout
    if (currentSessionId && sessionId && sessionId !== currentSessionId) {
        reloadSessionData();
        return;
    }
    
    // Calcule le delta de tokens (nouveau contenu)
    const deltaTokens = calculateTokenDelta(metric);
    metric.delta_tokens = deltaTokens;
    
    // Log pour débogage du bruit
    const totalTokens = metric.estimated_tokens || 0;
    const noiseRatio = totalTokens > 0 ? (totalTokens - deltaTokens) / totalTokens : 0;
    
    if (totalTokens > 10000 && noiseRatio > 0.7) {
        console.log(`🔍 [TOKEN NOISE] Total: ${totalTokens.toLocaleString()}, Delta: ${deltaTokens.toLocaleString()}, Ratio historique: ${(noiseRatio * 100).toFixed(1)}%`);
        if (metric.system_tokens > 0) {
            console.log(`   └─ Système: ${metric.system_tokens.toLocaleString()} tokens`);
        }
        if (metric.history_tokens > 0) {
            console.log(`   └─ Historique: ${metric.history_tokens.toLocaleString()} tokens`);
        }
    }
    
    sessionMetrics.push(metric);
    
    // Limite la taille du buffer
    if (sessionMetrics.length > 100) {
        sessionMetrics.shift();
    }
    
    // Met à jour les métriques mémoire si présentes
    if (metric.memory_tokens > 0) {
        currentMemoryMetrics = {
            memory_tokens: metric.memory_tokens,
            chat_tokens: metric.chat_tokens,
            memory_ratio: metric.memory_ratio,
            has_memory: true
        };
        eventBus.emit('memory:updated', currentMemoryMetrics);
    }
    
    eventBus.emit('metric:added', metric);
}

/**
 * Met à jour une métrique existante avec les tokens réels
 * Pourquoi : Correction post-traitement quand l'API retourne les vrais tokens
 * @param {string} metricId - ID de la métrique
 * @param {Object} realTokens - Tokens réels {total, prompt, completion, percentage}
 * @param {number} cumulativeTokens - Tokens cumulés
 * @param {number} cumulativePercentage - Pourcentage cumulé
 * @returns {Object|null} Métrique mise à jour
 */
export function updateMetricWithRealTokens(metricId, realTokens, cumulativeTokens = null, cumulativePercentage = null) {
    const metric = sessionMetrics.find(m => m.id === metricId);
    if (metric) {
        metric.estimated_tokens = realTokens.total;
        metric.percentage = realTokens.percentage;
        metric.prompt_tokens = realTokens.prompt;
        metric.completion_tokens = realTokens.completion;
        metric.is_estimated = false;
        
        eventBus.emit('metric:updated', { metric, realTokens, cumulativeTokens, cumulativePercentage });
        return metric;
    }
    return null;
}

// ============================================================================
// CALCULS STATISTIQUES
// ============================================================================

/**
 * Calcule les statistiques globales de la session
 * Pourquoi : Alimente les KPIs du dashboard
 * @returns {Object} Statistiques calculées
 */
export function calculateStats() {
    if (sessionMetrics.length === 0) {
        return {
            totalRequests: 0,
            maxTokens: 0,
            avgTokens: 0,
            totalPrompt: 0,
            totalCompletion: 0
        };
    }
    
    const tokens = sessionMetrics.map(m => m.estimated_tokens);
    const max = Math.max(...tokens);
    const avg = tokens.reduce((a, b) => a + b, 0) / tokens.length;
    
    const realMetrics = sessionMetrics.filter(m => !m.is_estimated && m.prompt_tokens);
    const totalPrompt = realMetrics.reduce((sum, m) => sum + (m.prompt_tokens || 0), 0);
    const totalCompletion = realMetrics.reduce((sum, m) => sum + (m.completion_tokens || 0), 0);
    
    return {
        totalRequests: sessionMetrics.length,
        maxTokens: Math.round(max),
        avgTokens: Math.round(avg),
        totalPrompt,
        totalCompletion
    };
}

/**
 * Calcule la précision des estimations vs réel
 * Pourquoi : Affiche la qualité de l'estimation Tiktoken
 * @returns {Object|null} Précision calculée
 */
export function calculateAccuracy() {
    const realMetrics = sessionMetrics.filter(m => !m.is_estimated && m.prompt_tokens > 0);
    if (realMetrics.length === 0) return null;
    
    const lastReal = realMetrics[realMetrics.length - 1];
    const estimated = lastReal.estimated_tokens;
    const real = lastReal.prompt_tokens + lastReal.completion_tokens;
    
    const accuracy = ((1 - Math.abs(estimated - real) / real) * 100);
    const diff = estimated - real;
    
    let accuracyColor = 'text-green-400';
    if (accuracy < 70) accuracyColor = 'text-red-400';
    else if (accuracy < 85) accuracyColor = 'text-yellow-400';
    
    return {
        estimated,
        real,
        accuracy,
        diff,
        diffText: diff > 0 ? `+${diff}` : `${diff}`,
        accuracyColor,
        formattedAccuracy: accuracy.toFixed(1)
    };
}

// ============================================================================
// GESTION DES SOURCES DE DONNÉES
// ============================================================================

/**
 * Stratégie de fusion des sources proxy/logs
 * Pourquoi : Le proxy et les logs peuvent avoir des données différentes,
 * on privilégie la fraîcheur et la priorité pour une expérience cohérente
 * @returns {Object|null} Meilleure source de données
 */
export function mergeDataSources() {
    const now = Date.now();
    const TIME_THRESHOLD = 5000;  // 5 secondes
    
    // Poids de priorité des sources (plus haut = plus prioritaire)
    const SOURCE_PRIORITY = {
        'compile_chat': 4,  // Données officielles de Continue
        'api_error': 3,     // Information critique
        'proxy': 2,         // Données en temps réel
        'logs': 1           // Données secondaires
    };
    
    let bestData = null;
    let source = 'proxy';
    let bestPriority = -1;
    
    // Collecte toutes les sources disponibles
    const sources = [];
    
    if (lastProxyData && (now - lastProxyData.timestamp) < TIME_THRESHOLD) {
        sources.push({ data: lastProxyData, name: 'proxy', priority: SOURCE_PRIORITY['proxy'] });
    }
    
    if (lastLogData && (now - lastLogData.timestamp) < TIME_THRESHOLD) {
        const logSourceName = lastLogData.source || 'logs';
        const priority = SOURCE_PRIORITY[logSourceName] || SOURCE_PRIORITY['logs'];
        sources.push({ data: lastLogData, name: logSourceName, priority: priority });
    }
    
    // Trouve la meilleure source selon la priorité
    for (const src of sources) {
        if (src.priority > bestPriority) {
            bestPriority = src.priority;
            bestData = src.data;
            source = src.name;
        }
    }
    
    // Si les deux sources ont des données, vérifie si elles sont proches
    if (lastProxyData && lastLogData) {
        const proxyTokens = lastProxyData.tokens;
        const logTokens = lastLogData.tokens;
        const diff = Math.abs(proxyTokens - logTokens);
        const avg = (proxyTokens + logTokens) / 2;
        
        // Si les valeurs sont proches (< 20% de différence), c'est hybride
        if (diff / avg < 0.2 && diff > 100) {
            source = 'hybrid';
            bestData = {
                tokens: Math.max(proxyTokens, logTokens),
                percentage: Math.max(lastProxyData.percentage, lastLogData.percentage)
            };
        }
    }
    
    // Fallback sur la dernière valeur connue
    if (!bestData) {
        if (lastProxyData) {
            bestData = lastProxyData;
            source = 'proxy';
        } else if (lastLogData) {
            bestData = lastLogData;
            source = lastLogData.source || 'logs';
        }
    }
    
    if (bestData) {
        return { ...bestData, source };
    }
    
    return null;
}

// ============================================================================
// UTILITAIRES
// ============================================================================

/**
 * Efface toutes les métriques
 * Pourquoi : Reset lors de la création d'une nouvelle session
 */
export function clearMetrics() {
    sessionMetrics = [];
    lastProxyData = null;
    lastLogData = null;
    eventBus.emit('metrics:cleared');
}

/**
 * Définit les métriques mémoire MCP
 * Pourquoi : Met à jour l'affichage de la mémoire long terme
 * @param {Object} memoryData - Données mémoire
 */
export function setMemoryMetrics(memoryData) {
    if (!memoryData) return;
    
    currentMemoryMetrics = {
        memory_tokens: memoryData.memory_tokens || 0,
        chat_tokens: memoryData.chat_tokens || 0,
        memory_ratio: memoryData.memory_ratio || 0,
        has_memory: memoryData.memory_tokens > 0
    };
    
    eventBus.emit('memory:updated', currentMemoryMetrics);
}
