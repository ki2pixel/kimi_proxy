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
    reloadSessionData
} from './sessions.js';

// ============================================================================
// ÉTAT DE LA CONNEXION
// ============================================================================

let ws = null;
let isConnected = false;
let reconnectTimeout = null;

// ============================================================================
// GETTERS
// ============================================================================

export function getWebSocket() {
    return ws;
}

export function isWebSocketConnected() {
    return isConnected;
}

// ============================================================================
// CONNEXION
// ============================================================================

/**
 * Établit la connexion WebSocket avec reconnexion automatique
 * Pourquoi : Maintient une connexion temps réel persistante avec le serveur
 */
export function connectWebSocket() {
    // Ferme la connexion existante si nécessaire
    if (ws) {
        ws.close();
    }
    
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
        isConnected = true;
        updateConnectionStatus(true);
        console.log('✅ WebSocket connecté');
        eventBus.emit('websocket:connected');
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('📡 WebSocket:', data.type, data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('Erreur parsing WebSocket:', error);
        }
    };
    
    ws.onclose = () => {
        isConnected = false;
        updateConnectionStatus(false);
        console.log('❌ WebSocket déconnecté - Reconnexion dans 3s...');
        eventBus.emit('websocket:disconnected');
        
        // Reconnexion automatique après 3 secondes
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
        }
        reconnectTimeout = setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        eventBus.emit('websocket:error', error);
    };
}

/**
 * Ferme proprement la connexion WebSocket
 * Pourquoi : Nettoyage lors du déchargement de la page
 */
export function disconnectWebSocket() {
    if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
        reconnectTimeout = null;
    }
    
    if (ws) {
        ws.close();
        ws = null;
    }
    
    isConnected = false;
}

/**
 * Met à jour l'indicateur visuel de connexion
 * Pourquoi : Feedback utilisateur sur l'état de la connexion
 * @param {boolean} connected - État de la connexion
 */
function updateConnectionStatus(connected) {
    eventBus.emit('websocket:status', { connected });
}

// ============================================================================
// GESTION DES MESSAGES
// ============================================================================

/**
 * Route les messages WebSocket vers les handlers appropriés
 * Pourquoi : Centralise le traitement des différents types de messages
 * @param {Object} data - Message WebSocket parsé
 */
function handleWebSocketMessage(data) {
    const now = Date.now();
    
    switch (data.type) {
        case 'init':
            handleInitMessage(data);
            break;
        
        case 'metric':
            handleMetricMessage(data, now);
            break;
        
        case 'log_metric':
            handleLogMetricMessage(data, now);
            break;
        
        case 'new_session':
            handleNewSessionMessage();
            break;
        
        case 'session_updated':
            handleSessionUpdatedMessage(data);
            break;
        
        case 'metric_updated':
            handleMetricUpdatedMessage(data, now);
            break;
        
        case 'memory_metrics_update':
            handleMemoryMetricsUpdate(data);
            break;
        
        case 'compression_event':
            handleCompressionEvent(data);
            break;
        
        case 'compaction_event':
            handleCompactionEvent(data);
            break;
        
        case 'compaction_alert':
            handleCompactionAlert(data);
            break;
        
        case 'auto_compaction_toggled':
            handleAutoCompactionToggled(data);
            break;
        
        case 'reserved_tokens_updated':
            handleReservedTokensUpdated(data);
            break;
        
        default:
            console.log('Message WebSocket non géré:', data.type);
    }
}

// ============================================================================
// HANDLERS SPÉCIFIQUES
// ============================================================================

function handleInitMessage(data) {
    if (data.session) {
        eventBus.emit('session:id', data.session.id);
    }
    eventBus.emit('websocket:init', data);
}

function handleMetricMessage(data, now) {
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

function handleLogMetricMessage(data, now) {
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

function handleNewSessionMessage() {
    // Recharge les données pour récupérer la nouvelle session
    reloadSessionData();
    eventBus.emit('session:new');
}

function handleSessionUpdatedMessage(data) {
    if (data.session_name) {
        eventBus.emit('session:name_changed', { name: data.session_name });
    }
}

function handleMetricUpdatedMessage(data, now) {
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

function handleMemoryMetricsUpdate(data) {
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

function handleCompressionEvent(data) {
    eventBus.emit('compression:event', data);
}

function handleCompactionEvent(data) {
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

function handleCompactionAlert(data) {
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

function handleAutoCompactionToggled(data) {
    eventBus.emit('compaction:auto_toggled', { enabled: data.enabled });
}

function handleReservedTokensUpdated(data) {
    console.log('Tokens réservés mis à jour:', data.reserved_tokens);
    eventBus.emit('compaction:reserved_updated', { reserved_tokens: data.reserved_tokens });
}
