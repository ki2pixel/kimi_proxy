/**
 * memory-service.js - Service de gestion mémoire pour compression et similarité
 * 
 * Pourquoi : Fournit une interface unifiée pour les opérations mémoire
 * via WebSocket avec cache LRU et gestion d'erreurs
 */

import { eventBus } from './utils.js';

// ============================================================================
// CACHE LRU POUR LA SIMILARITÉ
// ============================================================================

class LRUCache {
    constructor(maxSize = 50, ttl = 5 * 60 * 1000) { // 5 minutes TTL
        this.cache = new Map();
        this.maxSize = maxSize;
        this.ttl = ttl;
    }
    
    get(key) {
        const item = this.cache.get(key);
        if (!item) return null;
        
        if (Date.now() - item.timestamp > this.ttl) {
            this.cache.delete(key);
            return null;
        }
        
        // Move to end (most recently used)
        this.cache.delete(key);
        this.cache.set(key, item);
        return item.data;
    }
    
    set(key, data) {
        // Remove oldest if at capacity
        if (this.cache.size >= this.maxSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
    }
    
    clear() {
        this.cache.clear();
    }
}

// ============================================================================
// MEMORY COMPRESSION SERVICE
// ============================================================================

export class MemoryCompressionService {
    constructor() {
        this.pendingRequests = new Map();
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Écouter les réponses WebSocket
        eventBus.on('memory_compress_preview_response', (data) => {
            this.handlePreviewResponse(data);
        });
        
        eventBus.on('memory_compress_result_response', (data) => {
            this.handleCompressResponse(data);
        });
    }
    
    /**
     * Prévisualise la compression mémoire
     * @param {string} strategy - Stratégie de compression ('token' | 'semantic')
     * @param {number} threshold - Seuil de compression (0.1-0.9)
     * @returns {Promise<Object>} Résultat de la prévisualisation
     */
    async previewCompression(strategy, threshold) {
        const requestId = `compress-preview-${Date.now()}`;
        
        return new Promise((resolve, reject) => {
            // Timeout de 30 secondes
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(requestId);
                reject(new Error('Timeout: prévisualisation compression'));
            }, 30000);
            
            this.pendingRequests.set(requestId, {
                resolve: (data) => {
                    clearTimeout(timeout);
                    resolve(data);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            // Émettre la requête via WebSocket
            eventBus.emit('websocket:send', {
                type: 'memory_compress_preview',
                requestId,
                payload: { strategy, threshold }
            });
        });
    }
    
    /**
     * Exécute la compression mémoire
     * @param {string} strategy - Stratégie de compression
     * @param {number} threshold - Seuil de compression
     * @param {boolean} dryRun - Mode simulation uniquement
     * @returns {Promise<Object>} Résultat de la compression
     */
    async executeCompression(strategy, threshold, dryRun = false) {
        const requestId = `compress-exec-${Date.now()}`;
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(requestId);
                reject(new Error('Timeout: exécution compression'));
            }, 60000); // 1 minute pour l'exécution
            
            this.pendingRequests.set(requestId, {
                resolve: (data) => {
                    clearTimeout(timeout);
                    resolve(data);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            eventBus.emit('websocket:send', {
                type: 'memory_compress_execute',
                requestId,
                payload: { strategy, threshold, dryRun }
            });
        });
    }
    
    handlePreviewResponse(data) {
        const request = this.pendingRequests.get(data.requestId);
        if (request) {
            this.pendingRequests.delete(data.requestId);
            
            if (data.error) {
                request.reject(new Error(data.error));
            } else {
                request.resolve(data.result);
            }
        }
    }
    
    handleCompressResponse(data) {
        const request = this.pendingRequests.get(data.requestId);
        if (request) {
            this.pendingRequests.delete(data.requestId);
            
            if (data.error) {
                request.reject(new Error(data.error));
            } else {
                request.resolve(data.result);
            }
        }
    }
}

// ============================================================================
// SIMILARITY SERVICE
// ============================================================================

export class SimilarityService {
    constructor() {
        this.cache = new LRUCache(50, 5 * 60 * 1000); // 50 items, 5min TTL
        this.pendingRequests = new Map();
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        eventBus.on('memory:similarity_result', (data) => {
            this.handleSimilarityResponse(data);
        });
    }
    
    /**
     * Recherche des mémoires similaires
     * @param {string} referenceId - ID de la mémoire de référence
     * @param {string} referenceText - Texte de référence (alternative)
     * @param {string} method - Méthode de similarité ('cosine' | 'jaccard' | 'levenshtein')
     * @param {number} threshold - Seuil de similarité (0.5-1.0)
     * @param {number} limit - Nombre maximum de résultats
     * @returns {Promise<Object>} Résultats de similarité
     */
    async findSimilarMemories(referenceId, referenceText, method = 'cosine', threshold = 0.75, limit = 20) {
        // Vérifier le cache d'abord
        const cacheKey = this.getCacheKey(referenceId, referenceText, method, threshold, limit);
        const cached = this.cache.get(cacheKey);
        if (cached) {
            return cached;
        }
        
        const requestId = `similarity-${Date.now()}`;
        
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                this.pendingRequests.delete(requestId);
                reject(new Error('Timeout: recherche similarité'));
            }, 30000); // 30 secondes
            
            this.pendingRequests.set(requestId, {
                resolve: (data) => {
                    clearTimeout(timeout);
                    
                    // Mettre en cache
                    this.cache.set(cacheKey, data);
                    
                    resolve(data);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                }
            });
            
            eventBus.emit('websocket:send', {
                type: 'memory_similarity_search',
                requestId,
                payload: {
                    reference_id: referenceId,
                    reference_text: referenceText,
                    method,
                    threshold,
                    limit
                }
            });
        });
    }
    
    /**
     * Génère une clé de cache unique
     */
    getCacheKey(referenceId, referenceText, method, threshold, limit) {
        const ref = referenceId || referenceText.substring(0, 100);
        return `${ref}:${method}:${threshold}:${limit}`;
    }
    
    handleSimilarityResponse(data) {
        const request = this.pendingRequests.get(data.requestId);
        if (request) {
            this.pendingRequests.delete(data.requestId);
            
            if (data.error) {
                request.reject(new Error(data.error));
            } else {
                request.resolve(data.result);
            }
        }
    }
    
    /**
     * Vide le cache
     */
    clearCache() {
        this.cache.clear();
    }
}

// ============================================================================
// INSTANCES GLOBALES
// ============================================================================

export const memoryCompressionService = new MemoryCompressionService();
export const similarityService = new SimilarityService();

// ============================================================================
// UTILITAIRES
// ============================================================================

/**
 * Throttle pour limiter les appels fréquents
 */
export function throttle(func, limit = 1000) {
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
 * Gestionnaire d'erreurs centralisé pour les opérations mémoire
 */
export class MemoryOperationError extends Error {
    constructor(message, type, recoverable = true) {
        super(message);
        this.name = 'MemoryOperationError';
        this.type = type; // 'compression' | 'similarity' | 'websocket'
        this.recoverable = recoverable;
    }
}

/**
 * Gestionnaire d'erreurs mémoire
 */
export function handleMemoryError(error, context) {
    console.error(`Erreur ${context}:`, error);
    
    // Log via WebSocket pour monitoring
    eventBus.emit('websocket:send', {
        type: 'memory_error_log',
        payload: {
            context,
            error: error.message,
            timestamp: new Date().toISOString(),
            recoverable: error.recoverable || true
        }
    });
    
    // Notification utilisateur
    const errorMessage = error.recoverable 
        ? `Erreur ${context}: ${error.message}` 
        : `Erreur critique ${context}: ${error.message}`;
    
    eventBus.emit('notification:show', {
        message: errorMessage,
        type: error.recoverable ? 'error' : 'critical'
    });
}