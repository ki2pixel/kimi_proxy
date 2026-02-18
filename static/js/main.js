/**
 * main.js - Point d'entrée de l'application
 * 
 * Pourquoi : Orchestre l'initialisation de tous les modules et gère le
 * cycle de vie de l'application (démarrage, rechargement, nettoyage).
 */

// ============================================================================
// IMPORTS
// ============================================================================

import { eventBus } from './modules/utils.js';
import { loadInitialData } from './modules/api.js';
import { initGauge, initHistoryChart, initCompactionChart } from './modules/charts.js';
import { 
    loadSessionData, 
    setCurrentMaxContext,
    clearMetrics 
} from './modules/sessions.js';
import { connectWebSocket, disconnectWebSocket } from './modules/websocket.js';
import { 
    initElements, 
    initUIListeners,
    updateDisplay,
    updateStats,
    renderLogs,
    clearLogs,
    updateConnectionStatus
} from './modules/ui.js';
import { 
    initModalListeners,
    showNewSessionModal,
    closeNewSessionModal,
    createNewSessionWithProvider,
    showCompactPreviewModal,
    closeCompactPreviewModal,
    closeCompactResultModal
} from './modules/modals.js';
import { 
    updateCompactionButton,
    initCompactionListeners,
    startCompactionPolling,
    stopCompactionPolling,
    executeCompaction,
    toggleAutoCompaction
} from './modules/compaction.js';
import {
    init as initMCP,
    fetchServerStatuses,
    fetchAdvancedMemoryStats,
    fetchFrequentMemories
} from './modules/mcp.js';

// ============================================================================
// INITIALISATION PRINCIPALE
// ============================================================================

/**
 * Initialise l'application au chargement de la page
 * Pourquoi : Point d'entrée unique pour tout le cycle de démarrage
 */
async function initApp() {
    console.log('🚀 Initialisation du Kimi Proxy Dashboard...');
    
    try {
        // 1. Initialise les icônes Lucide
        if (window.lucide) {
            lucide.createIcons();
        }
        
        // 2. Cache les éléments DOM fréquemment utilisés
        initElements();
        
        // 3. Initialise les graphiques Chart.js
        initGauge();
        initHistoryChart();
        initCompactionChart();
        
        // 4. Configure les listeners de modules
        initUIListeners();
        initModalListeners();
        initCompactionListeners();
        
        // 5. Charge les données initiales
        await loadInitialAppData();
        
        // 6. Démarre la connexion WebSocket
        connectWebSocket();
        
        // 7. Démarre le polling de compaction
        startCompactionPolling();
        
        // 8. Initialise le module MCP Phase 3
        initMCP();
        
        // 9. Expose les fonctions globales nécessaires
        exposeGlobals();
        
        console.log('✅ Application initialisée avec succès');
        
    } catch (error) {
        console.error('❌ Erreur lors de l\'initialisation:', error);
    }
}

/**
 * Charge les données initiales de l'application
 * Pourquoi : Récupère l'état courant avant de démarrer les mises à jour temps réel
 */
async function loadInitialAppData() {
    try {
        const data = await loadInitialData();
        
        if (data) {
            loadSessionData(data);
            
            // Met à jour le max_context global
            if (data.session?.max_context) {
                setCurrentMaxContext(data.session.max_context);
            }
            
            // Met à jour l'UI initiale
            if (data.stats?.cumulative_total_tokens !== undefined) {
                const cumulative = data.stats.cumulative_total_tokens;
                const maxContext = data.session?.max_context || 262144;
                const percentage = (cumulative / maxContext) * 100;
                updateDisplay(
                    data.stats.cumulative_input_tokens || cumulative, 
                    percentage, 
                    cumulative
                );
            }
            
            // Met à jour les stats et logs
            updateStats();
            renderLogs();
            
            // Met à jour le bouton de compaction
            await updateCompactionButton();
        }
        
    } catch (error) {
        console.error('❌ Erreur chargement données initiales:', error);
    }
}

// ============================================================================
// EXPOSITION GLOBALE
// ============================================================================

/**
 * Expose les fonctions nécessaires globalement
 * Pourquoi : Certaines fonctions sont appelées depuis HTML (onclick, etc.)
 */
function exposeGlobals() {
    // Modales
    window.showNewSessionModal = showNewSessionModal;
    window.closeNewSessionModal = closeNewSessionModal;
    window.createNewSession = showNewSessionModal; // Alias pour compatibilité
    window.createNewSessionWithProvider = createNewSessionWithProvider;
    
    // Compaction
    window.showCompactPreviewModal = showCompactPreviewModal;
    window.closeCompactPreviewModal = closeCompactPreviewModal;
    window.closeCompactResultModal = closeCompactResultModal;
    window.executeCompaction = executeCompaction;
    window.toggleAutoCompaction = toggleAutoCompaction;
    
    // Export
    window.exportData = exportData;
    
    // Logs
    window.clearLogs = () => {
        clearMetrics();
        clearLogs();
        updateDisplay(0, 0);
        updateStats();
    };
    
    // MCP Phase 3
    window.refreshMCPStatus = fetchServerStatuses;
    window.searchSimilar = async (query) => {
        const { searchSimilar } = await import('./modules/mcp.js');
        return searchSimilar(query);
    };
    window.compressContent = async (content) => {
        const { compressContent } = await import('./modules/mcp.js');
        return compressContent(content);
    };
}

/**
 * Fonction d'export globale
 * Pourquoi : Appelée depuis le HTML
 * @param {string} format - Format d'export
 */
async function exportData(format) {
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
        
        // Notification via eventBus
        eventBus.emit('notification:show', { 
            message: `Export ${format.toUpperCase()} téléchargé !`, 
            type: 'success' 
        });
        
    } catch (error) {
        console.error('Erreur export:', error);
        eventBus.emit('notification:show', { 
            message: 'Erreur lors de l\'export', 
            type: 'error' 
        });
    }
}

// ============================================================================
// GESTION DU CYCLE DE VIE
// ============================================================================

/**
 * Nettoyage avant fermeture de la page
 * Pourquoi : Ferme proprement les connexions et intervals
 */
function cleanup() {
    console.log('🧹 Nettoyage...');
    disconnectWebSocket();
    stopCompactionPolling();
}

// ============================================================================
// DÉMARRAGE
// ============================================================================

// Attend que le DOM soit prêt
document.addEventListener('DOMContentLoaded', initApp);

// Nettoyage au déchargement
window.addEventListener('beforeunload', cleanup);

// Gestion du rechargement de page (évite les erreurs de reconnexion)
window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
        // Page restaurée depuis le cache bfcache
        console.log('🔄 Page restaurée depuis le cache');
        connectWebSocket();
    }
});
