/**
 * websocket.js - Gestion de la connexion WebSocket temps réel
 * 
 * Pourquoi : Fournit une couche d'abstraction sur WebSocket pour gérer
 * la reconnexion automatique, le parsing des messages, et la diffusion
 * des événements aux autres modules.
 */

import { WS_URL, showNotification, eventBus } from './utils.js';
import { 
    getCurrentSessionId, 
    addMetric, 
    setLastProxyData, 
    setLastLogData,
    setMemoryMetrics,
    updateMetricWithRealTokens,
    reloadSessionData,
    getSessionManager
} from './sessions.js';

// ============================================================================
// WEBSOCKETMANAGER CLASS - Gestion centralisée WebSocket avec filtrage session
// ============================================================================

/**
 * WebSocketManager - Classe principale pour gérer la connexion WebSocket
 * Pourquoi : Centralise la logique WebSocket avec filtrage par session
 */
export class WebSocketManager {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectTimeout = null;
        this.activeSessionId = null;
        this.messageQueue = [];
    }

    /**
     * Établit la connexion WebSocket avec reconnexion automatique
     */
    connect() {
        // Ferme la connexion existante si nécessaire
        if (this.ws) {
            this.ws.close();
        }
        
        this.ws = new WebSocket(WS_URL);
        
        this.ws.onopen = () => {
            this.isConnected = true;
            this.updateConnectionStatus(true);
            console.log('✅ WebSocket connecté');
            eventBus.emit('websocket:connected');
            
            // Écoute les événements d'envoi de messages
            eventBus.on('websocket:send', (message) => this.sendMessage(message));
            
            // Traite les messages en attente
            this.processMessageQueue();
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('📡 WebSocket:', data.type, data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Erreur parsing WebSocket:', error);
            }
        };
        
        this.ws.onclose = () => {
            this.isConnected = false;
            this.updateConnectionStatus(false);
            console.log('❌ WebSocket déconnecté - Reconnexion dans 3s...');
            eventBus.emit('websocket:disconnected');
            
            // Reconnexion automatique après 3 secondes
            if (this.reconnectTimeout) {
                clearTimeout(this.reconnectTimeout);
            }
            this.reconnectTimeout = setTimeout(() => this.connect(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            eventBus.emit('websocket:error', error);
        };
    }

    /**
     * Ferme proprement la connexion WebSocket
     */
    disconnect() {
        if (this.reconnectTimeout) {
            clearTimeout(this.reconnectTimeout);
            this.reconnectTimeout = null;
        }
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        
        this.isConnected = false;
        this.activeSessionId = null;
        this.messageQueue = [];
    }

    /**
     * Met à jour l'ID de session active pour le filtrage
     * @param {string} sessionId - Nouvel ID de session active
     */
    setActiveSessionId(sessionId) {
        console.log(`🔄 [WebSocketManager] Session active changée: ${this.activeSessionId} → ${sessionId}`);
        this.activeSessionId = sessionId;
    }

    /**
     * Envoie un message via WebSocket
     * @param {Object} message - Message à envoyer
     */
    sendMessage(message) {
        if (this.ws && this.isConnected) {
            try {
                this.ws.send(JSON.stringify(message));
                console.log('📤 WebSocket envoyé:', message.type);
            } catch (error) {
                console.error('Erreur envoi WebSocket:', error);
                // Met en queue pour retry
                this.messageQueue.push(message);
            }
        } else {
            console.warn('WebSocket non connecté, message mis en queue:', message.type);
            this.messageQueue.push(message);
        }
    }

    /**
     * Traite la queue des messages en attente
     */
    processMessageQueue() {
        while (this.messageQueue.length > 0 && this.isConnected) {
            const message = this.messageQueue.shift();
            this.sendMessage(message);
        }
    }

    /**
     * Route les messages WebSocket vers les handlers appropriés
     * @param {Object} data - Message WebSocket parsé
     */
    handleMessage(data) {
        const now = Date.now();
        
        // Filtrage par session - ignore les messages d'autres sessions
        if (data.session_id && data.session_id !== this.activeSessionId) {
            console.log(`🚫 [WebSocket] Message ignoré (session ${data.session_id} ≠ ${this.activeSessionId}):`, data.type);
            return;
        }
        
        switch (data.type) {
            case 'init':
                this.handleInitMessage(data);
                break;
            
            case 'metric':
                this.handleMetricMessage(data, now);
                break;
            
            case 'log_metric':
                this.handleLogMetricMessage(data, now);
                break;
            
            case 'new_session':
                this.handleNewSessionMessage();
                break;
            
            case 'session_updated':
                this.handleSessionUpdatedMessage(data);
                break;
            
            case 'metric_updated':
                this.handleMetricUpdatedMessage(data, now);
                break;
            
            case 'memory_metrics_update':
                this.handleMemoryMetricsUpdate(data);
                break;
            
            case 'compression_event':
                this.handleCompressionEvent(data);
                break;
            
            case 'compaction_event':
                this.handleCompactionEvent(data);
                break;
            
            case 'compaction_alert':
                this.handleCompactionAlert(data);
                break;
            
            case 'auto_compaction_toggled':
                this.handleAutoCompactionToggled(data);
                break;
            
            case 'auto_session_created':
                this.handleAutoSessionCreated(data);
                break;
            
            case 'auto_session_toggled':
                this.handleAutoSessionToggled(data);
                break;
            
            case 'session_deleted':
                this.handleSessionDeletedMessage(data);
                break;
            
            case 'sessions_bulk_deleted':
                this.handleSessionsBulkDeletedMessage(data);
                break;
            
            case 'memory_similarity_result_response':
                this.handleMemorySimilarityResult(data);
                break;
            
            default:
                console.log('Message WebSocket non géré:', data.type);
        }
    }

    // ============================================================================
    // HANDLERS SPÉCIFIQUES (méthodes privées)
    // ============================================================================

    handleInitMessage(data) {
        if (data.session) {
            this.setActiveSessionId(data.session.id);
            eventBus.emit('session:id', data.session.id);
        }
        eventBus.emit('websocket:init', data);
    }

    handleMetricMessage(data, now) {
        // Données du proxy
        if (data.metric) {
            setLastProxyData({
                tokens: data.metric.cumulative_tokens || data.metric.estimated_tokens,
                percentage: data.metric.percentage,
                timestamp: now
            });
            
            eventBus.emit('metric:received', data.metric);
            addMetric(data.metric, data.session_id);
            
            // Met à jour les métriques mémoire si présentes
            if (data.mcp_memory) {
                setMemoryMetrics({
                    memory_tokens: data.mcp_memory.memory_tokens,
                    chat_tokens: data.mcp_memory.chat_tokens,
                    memory_ratio: data.mcp_memory.memory_ratio,
                    has_memory: true
                });
            }
            
            if (data.metric.memory_tokens > 0) {
                setMemoryMetrics({
                    memory_tokens: data.metric.memory_tokens,
                    chat_tokens: data.metric.chat_tokens,
                    memory_ratio: data.metric.memory_ratio,
                    has_memory: true
                });
            }
        }
        
        // Mise à jour du nom de session si nécessaire
        if (data.session_updated && data.metric) {
            eventBus.emit('session:name_update', {
                preview: data.metric.content_preview
            });
        }
        
        // Alerte si présente
        if (data.alert) {
            eventBus.emit('alert:received', data.alert);
        }
    }

    handleLogMetricMessage(data, now) {
        // Données des logs PyCharm
        if (data.metrics) {
            setLastLogData({
                tokens: data.metrics.total_tokens,
                percentage: data.metrics.percentage,
                source: data.source || 'logs',
                timestamp: now,
                max_context: data.metrics.max_context
            });
            
            // Construction du message de preview selon le type
            let previewText = 'Détecté dans les logs Continue';
            if (data.source === 'compile_chat') {
                const parts = [];
                if (data.metrics.tools_tokens > 0) parts.push(`${data.metrics.tools_tokens.toLocaleString()} tools`);
                if (data.metrics.system_message_tokens > 0) parts.push(`${data.metrics.system_message_tokens.toLocaleString()} system`);
                if (data.metrics.context_length > 0) parts.push(`context: ${data.metrics.context_length.toLocaleString()}`);
                previewText = `CompileChat - ${parts.join(', ')}`;
            } else if (data.source === 'api_error') {
                previewText = `⚠️ Erreur API - Limite atteinte: ${data.metrics.total_tokens.toLocaleString()} tokens`;
            } else {
                previewText = `Logs - ${data.metrics.prompt_tokens || 0} prompt / ${data.metrics.completion_tokens || 0} completion`;
            }
            
            // Crée une métrique log
            const logMetric = {
                id: 'log_' + now,
                timestamp: data.timestamp || new Date().toISOString(),
                estimated_tokens: data.metrics.total_tokens,
                percentage: data.metrics.percentage,
                content_preview: previewText,
                is_estimated: false,
                source: data.source || 'logs',
                tools_tokens: data.metrics.tools_tokens || 0,
                system_message_tokens: data.metrics.system_message_tokens || 0
            };
            
            eventBus.emit('log:received', { metric: logMetric, max_context: data.metrics.max_context });
        }
    }

    handleNewSessionMessage() {
        // Recharge les données pour récupérer la nouvelle session
        reloadSessionData();
        eventBus.emit('session:new');
    }

    handleSessionUpdatedMessage(data) {
        if (data.session_name) {
            eventBus.emit('session:name_changed', { name: data.session_name });
        }
    }

    handleMetricUpdatedMessage(data, now) {
        if (data.real_tokens) {
            updateMetricWithRealTokens(data.metric_id, data.real_tokens);
        }
        
        // Met à jour aussi lastProxyData
        if (data.cumulative_tokens !== undefined) {
            setLastProxyData({
                tokens: data.cumulative_tokens,
                percentage: data.cumulative_percentage || data.real_tokens?.percentage || 0,
                timestamp: now
            });
        }
        
        if (data.cumulative_tokens !== undefined && data.cumulative_percentage !== undefined) {
            eventBus.emit('display:update', {
                tokens: data.real_tokens?.prompt || 0,
                percentage: data.cumulative_percentage,
                cumulativeTokens: data.cumulative_tokens
            });
        }
        
        if (data.alert) {
            eventBus.emit('alert:received', data.alert);
        }
    }

    handleMemoryMetricsUpdate(data) {
        if (data.memory) {
            setMemoryMetrics({
                memory_tokens: data.memory.memory_tokens,
                chat_tokens: data.memory.chat_tokens,
                memory_ratio: data.memory.memory_ratio,
                has_memory: true
            });
            
            // Crée un log pour la mémoire
            const memoryLog = {
                id: 'memory_' + Date.now(),
                timestamp: data.timestamp || new Date().toISOString(),
                estimated_tokens: data.memory.total_tokens,
                percentage: data.memory.memory_ratio,
                content_preview: `🧠 Mémoire MCP - ${data.memory.memory_tokens.toLocaleString()} tokens (${data.memory.memory_ratio.toFixed(1)}%)`,
                is_estimated: false,
                source: 'mcp_memory'
            };
            
            eventBus.emit('log:received', { metric: memoryLog });
        }
    }

    handleCompressionEvent(data) {
        eventBus.emit('compression:event', data);
    }

    handleCompactionEvent(data) {
        if (data.compaction) {
            // Ajoute un log
            const logEntry = {
                id: 'compact_' + Date.now(),
                timestamp: data.timestamp || new Date().toISOString(),
                estimated_tokens: data.compaction.tokens_saved || 0,
                percentage: data.compaction.compaction_ratio || 0,
                content_preview: `🗜️ Compaction: ${data.compaction.original_tokens.toLocaleString()} → ${data.compaction.compacted_tokens.toLocaleString()} tokens (${data.compaction.compaction_ratio.toFixed(1)}% économisés)`,
                is_estimated: false,
                source: 'compaction'
            };
            
            eventBus.emit('log:received', { metric: logEntry });
            eventBus.emit('compaction:event', data);
            
            // Notification
            const triggerReason = data.trigger_reason || 'manuelle';
            showNotification(
                `Compaction ${triggerReason}: ${data.compaction.compaction_ratio.toFixed(1)}% économisés`,
                'success'
            );
        }
    }

    handleCompactionAlert(data) {
        if (data.alert) {
            const alert = data.alert;
            
            // Ajoute un log d'alerte
            const logEntry = {
                id: 'alert_' + Date.now(),
                timestamp: new Date().toISOString(),
                estimated_tokens: alert.tokens || 0,
                percentage: alert.percentage || 0,
                content_preview: `⚠️ ${alert.message}`,
                is_estimated: false,
                source: 'alert'
            };
            
            eventBus.emit('log:received', { metric: logEntry });
            eventBus.emit('compaction:alert', alert);
        }
    }

    handleAutoCompactionToggled(data) {
        eventBus.emit('compaction:auto_toggled', { enabled: data.enabled });
    }

    async handleAutoSessionCreated(data) {
        console.log('🔄 [WebSocket] Auto-session créée, chargement des données...', data);
        
        try {
            // Charger les données complètes de la nouvelle session (avec métriques)
            const response = await fetch('/api/sessions/active', {
                method: 'GET'
            });
            if (response.ok) {
                const fullData = await response.json();
                
                // Utiliser SessionManager pour changer de session avec les métriques
                const sessionManager = getSessionManager();
                const existingMetrics = fullData.recent_metrics || [];
                
                await sessionManager.switchSession(fullData.session.id, existingMetrics);
                
                // Émettre l'événement de session chargée (pour compatibilité)
                eventBus.emit('session:loaded', fullData);
                
                console.log(`✅ [WebSocket] Auto-session ${fullData.session.id} chargée avec ${existingMetrics.length} métriques`);
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
        } catch (error) {
            console.error('❌ [WebSocket] Erreur chargement auto-session:', error);
            
            // Fallback: juste notifier sans changer de session
            eventBus.emit('session:auto_created', data);
        }
        
        // Notification
        showNotification(
            `Nouvelle session auto: #${data.session?.id || '?'}-${data.model || data.provider || 'inconnu'}`,
            'info'
        );
    }

    handleAutoSessionToggled(data) {
        eventBus.emit('auto_session:toggled', { enabled: data.enabled });
    }

    handleSessionsBulkDeletedMessage(data) {
        console.log(`🗑️ [WebSocket] Sessions supprimées en bulk détectées: ${data.session_ids.join(', ')}`);
        
        // Recharge la liste des sessions pour mettre à jour le dropdown
        // Note: On ne peut pas importer loadSessions directement ici car c'est défini dans main.js
        // On émet un événement que main.js peut écouter
        eventBus.emit('sessions:bulk_deleted', data);
        
        // Notification
        showNotification(`${data.deleted_count} session(s) supprimée(s) en bulk`, 'success');
    }

    handleSessionDeletedMessage(data) {
        console.log(`🗑️ [WebSocket] Session supprimée détectée: ${data.session_id}`);
        
        // Recharge la liste des sessions pour mettre à jour le dropdown
        // Note: On ne peut pas importer loadSessions directement ici car c'est défini dans main.js
        // On émet un événement que main.js peut écouter
        eventBus.emit('session:deleted', { session_id: data.session_id });
        
        // Notification
        showNotification(`Session #${data.session_id} supprimée`, 'info');
    }

    handleMemorySimilarityResult(data) {
        // Route vers le similarity service
        eventBus.emit('memory:similarity_result', data);
    }

    /**
     * Met à jour l'indicateur visuel de connexion
     * @param {boolean} connected - État de la connexion
     */
    updateConnectionStatus(connected) {
        eventBus.emit('websocket:status', { connected });
    }
}

// ============================================================================
// INSTANCE GLOBALE (pour compatibilité)
// ============================================================================

let webSocketManagerInstance = null;

/**
 * Récupère l'instance globale du WebSocketManager
 * @returns {WebSocketManager}
 */
export function getWebSocketManager() {
    if (!webSocketManagerInstance) {
        webSocketManagerInstance = new WebSocketManager();
    }
    return webSocketManagerInstance;
}

// ============================================================================
// FONCTIONS DE COMPATIBILITÉ (legacy)
// ============================================================================

export function getWebSocket() {
    return getWebSocketManager().ws;
}

export function isWebSocketConnected() {
    return getWebSocketManager().isConnected;
}

export function sendWebSocketMessage(message) {
    return getWebSocketManager().sendMessage(message);
}

export function connectWebSocket() {
    return getWebSocketManager().connect();
}

export function disconnectWebSocket() {
    return getWebSocketManager().disconnect();
}
