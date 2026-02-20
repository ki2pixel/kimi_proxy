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
    closeCompactResultModal,
    showMemoryModal,
    hideMemoryModal
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
import {
    initAutoSession,
    exposeAutoSessionGlobals
} from './modules/auto-session.js';

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
        
        // 9. Configure les handlers EventBus pour les modales mémoire
        setupMemoryModalHandlers();
        
        // 10. Initialise le module Auto Session
        await initAutoSession();
        
        // 11. Expose les fonctions globales nécessaires
        exposeGlobals();
        exposeAutoSessionGlobals();
        
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
            if (data.stats?.current_total_tokens !== undefined) {
                const current = data.stats.current_total_tokens;
                const maxContext = data.session?.max_context || 262144;
                const percentage = (current / maxContext) * 100;
                updateDisplay(current, percentage);
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
// FONCTIONS MODALE MÉMORISER
// ============================================================================

/**
 * Affiche la modal de stockage mémoire
 */
function showMemoryStoreModal() {
    const modal = document.getElementById('memory-store-modal');
    const content = document.getElementById('memory-store-modal-content');
    
    if (!modal || !content) return;
    
    // Reset le formulaire
    const contentInput = document.getElementById('memory-content-input');
    const typeSelect = document.getElementById('memory-type-select');
    if (contentInput) contentInput.value = '';
    if (typeSelect) typeSelect.value = 'episodic';
    
    // Affiche la modal
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    
    setTimeout(() => {
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
    
    // Focus sur le textarea
    setTimeout(() => {
        if (contentInput) contentInput.focus();
    }, 100);
}

/**
 * Ferme la modal de stockage mémoire
 */
function closeMemoryStoreModal() {
    const modal = document.getElementById('memory-store-modal');
    const content = document.getElementById('memory-store-modal-content');
    
    if (!modal || !content) return;
    
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    
    setTimeout(() => {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }, 200);
}

/**
 * Exécute le stockage d'une mémoire
 */
async function executeStoreMemory() {
    const contentInput = document.getElementById('memory-content-input');
    const typeSelect = document.getElementById('memory-type-select');
    
    const content = contentInput?.value?.trim();
    const memoryType = typeSelect?.value || 'episodic';
    
    if (!content) {
        eventBus.emit('notification:show', {
            message: 'Veuillez entrer du contenu à mémoriser',
            type: 'error'
        });
        return;
    }
    
    try {
        // Récupère la session courante
        const sessionBadge = document.getElementById('session-badge');
        const sessionId = sessionBadge?.textContent?.replace('#', '') || '1';
        
        // Appelle l'API de stockage
        const response = await fetch(`/api/memory/store?session_id=${sessionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: content,
                memory_type: memoryType,
                metadata: {
                    source: 'manual',
                    timestamp: new Date().toISOString()
                }
            })
        });
        
        if (!response.ok) {
            throw new Error('Erreur lors du stockage');
        }
        
        const result = await response.json();
        
        if (result.success) {
            eventBus.emit('notification:show', {
                message: `Mémoire stockée avec succès (ID: ${result.memory_id})`,
                type: 'success'
            });
            
            closeMemoryStoreModal();
            
            // Rafraîchit la liste des mémoires fréquentes si disponible
            const { fetchFrequentMemories } = await import('./modules/mcp.js');
            await fetchFrequentMemories();
        } else {
            throw new Error(result.detail || 'Échec du stockage');
        }
        
    } catch (error) {
        console.error('Erreur stockage mémoire:', error);
        eventBus.emit('notification:show', {
            message: 'Erreur lors du stockage de la mémoire',
            type: 'error'
        });
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
    
    // Memory Modals
    window.showMemoryModal = showMemoryModal;
    window.hideMemoryModal = hideMemoryModal;
    
    // Store Memory Modal
    window.showMemoryStoreModal = showMemoryStoreModal;
    window.closeMemoryStoreModal = closeMemoryStoreModal;
    window.executeStoreMemory = executeStoreMemory;
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
 * Configure les handlers EventBus pour les modales mémoire
 * Pourquoi : Communication découplée entre les boutons UI et les modales
 */
function setupMemoryModalHandlers() {
    // Handler pour afficher la modal de compression
    eventBus.on('memory:compress:show', () => {
        showMemoryModal('compress');
    });
    
    // Handler pour afficher la modal de similarité
    eventBus.on('memory:similarity:show', () => {
        showMemoryModal('similarity');
    });
    
    // Handler pour afficher la modal de stockage mémoire
    eventBus.on('memory:store:show', () => {
        showMemoryStoreModal();
    });
    
    // Handler pour cacher les modales
    eventBus.on('memory:modal:hide', (data) => {
        if (data?.type) {
            hideMemoryModal(data.type);
        }
    });
}

/**
 * Nettoyage avant fermeture de la page
 * Pourquoi : Ferme proprement les connexions et intervals
 */
function cleanup() {
    console.log('🧹 Nettoyage...');
    disconnectWebSocket();
    stopCompactionPolling();
    
    // Nettoyer les modales mémoire
    if (window.memoryModals) {
        Object.values(window.memoryModals).forEach(modal => {
            if (modal.hide) modal.hide();
        });
        window.memoryModals = {};
    }
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
