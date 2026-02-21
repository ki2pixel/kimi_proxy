/**
 * main.js - Point d'entrée de l'application
 * 
 * Pourquoi : Orchestre l'initialisation de tous les modules et gère le
 * cycle de vie de l'application (démarrage, rechargement, nettoyage).
 */

// ============================================================================
// IMPORTS
// ============================================================================

import { eventBus, showNotification } from './modules/utils.js';
import { loadInitialData } from './modules/api.js';
import { getChartManager } from './modules/charts.js';
import { 
    loadSessionData, 
    setCurrentMaxContext,
    clearMetrics,
    reloadSessionData
} from './modules/sessions.js';
import { getWebSocketManager } from './modules/websocket.js';
import { getUIManager } from './modules/ui.js';
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
        
        // 3. Initialise les managers principaux
        const chartManager = getChartManager();
        const webSocketManager = getWebSocketManager();
        const uiManager = getUIManager();
        
        // 4. Initialise les graphiques Chart.js
        chartManager.initGauge();
        chartManager.initHistoryChart();
        chartManager.initCompactionChart();
        
        // 5. Configure les listeners de modules
        initUIListeners();
        initModalListeners();
        initCompactionListeners();
        
        // 6. Charge les données initiales
        await loadInitialAppData();
        
        // 7. Démarre la connexion WebSocket
        webSocketManager.connect();
        
        // 8. Démarre le polling de compaction
        startCompactionPolling();
        
        // 9. Initialise le module MCP Phase 3
        initMCP();
        
        // 10. Configure les handlers EventBus pour les modales mémoire
        setupMemoryModalHandlers();
        
        // 11. Configure les handlers pour le changement de session
        setupSessionChangeHandlers(chartManager, webSocketManager, uiManager);
        
        // 12. Initialise le module Auto Session
        await initAutoSession();
        
        // 13. Expose les fonctions globales nécessaires
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
    
    // Session Management
    window.toggleSelectAll = toggleSelectAll;
    window.updateBulkDeleteButton = updateBulkDeleteButton;
    window.deleteSelectedSessions = deleteSelectedSessions;
    window.deleteSession = deleteSession;
    
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
 * Configure les handlers pour le changement de session
 * Pourquoi : Coordination entre tous les managers lors du changement de session
 * @param {ChartManager} chartManager - Instance du ChartManager
 * @param {WebSocketManager} webSocketManager - Instance du WebSocketManager  
 * @param {UIManager} uiManager - Instance du UIManager
 */
function setupSessionChangeHandlers(chartManager, webSocketManager, uiManager) {
    eventBus.on('sessionChanged', (event) => {
        const { newSession } = event.detail;
        
        console.log(`🔄 [Main] Changement de session détecté: ${newSession.id}`);
        
        // 1. Met à jour le contexte de session pour ChartManager
        chartManager.handleSessionChange(event);
        
        // 2. Met à jour l'ID de session active pour WebSocketManager
        webSocketManager.setActiveSessionId(newSession.id);
        
        // 3. Met à jour l'état des boutons UI selon la session
        uiManager.updateButtonStates(newSession);
        
        console.log(`✅ [Main] Gestionnaires de session synchronisés pour ${newSession.id}`);
    });
    
    // Gestionnaire pour les suppressions de sessions (WebSocket)
    eventBus.on('session:deleted', (data) => {
        console.log(`🗑️ [Main] Session supprimée détectée: ${data.session_id}, rechargement du dropdown...`);
        
        // Recharge la liste des sessions pour mettre à jour le dropdown
        // Note: On attend un court instant pour éviter les conflits de requêtes
        setTimeout(() => {
            loadSessions();
        }, 100);
    });
}

/**
 * Nettoyage avant fermeture de la page
 * Pourquoi : Ferme proprement les connexions et intervals
 */
function cleanup() {
    console.log('🧹 Nettoyage...');
    
    // Utilise les nouvelles instances de managers
    const webSocketManager = getWebSocketManager();
    const chartManager = getChartManager();
    
    // Ferme la connexion WebSocket
    webSocketManager.disconnect();
    
    // Nettoie les graphiques
    chartManager.destroy();
    
    // Arrête le polling de compaction
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
// ============================================================================
// SESSION SWITCHING FUNCTIONS
// ============================================================================

/**
 * Toggle la visibilité du sélecteur de session
 */
window.toggleSessionSelector = function() {
    const selector = document.getElementById('sessionSelector');
    if (selector.classList.contains('hidden')) {
        loadSessions();
        selector.classList.remove('hidden');
    } else {
        selector.classList.add('hidden');
    }
};

/**
 * Charge et affiche la liste des sessions disponibles
 */
async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const sessions = await response.json();
        const sessionList = document.getElementById('sessionList');
        const currentSessionName = document.getElementById('currentSessionName');
        
        // Met à jour le nom de la session courante
        const activeSession = sessions.find(s => s.is_active);
        if (activeSession) {
            currentSessionName.textContent = activeSession.name;
        }
        
        // Génère la liste des sessions
        sessionList.innerHTML = '';
        
        // Header avec sélection multiple
        const headerDiv = document.createElement('div');
        headerDiv.className = 'flex items-center justify-between p-3 border-b border-slate-700/50 mb-2';
        headerDiv.innerHTML = `
            <div class="flex items-center gap-3">
                <input type="checkbox" id="selectAllSessions" class="w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-blue-500">
                <label for="selectAllSessions" class="text-xs text-slate-400 cursor-pointer">Tout sélectionner</label>
            </div>
            <button id="bulkDeleteBtn" 
                    class="hidden px-3 py-1 text-xs bg-red-600 hover:bg-red-500 text-white rounded transition-colors flex items-center gap-1">
                <i data-lucide="trash-2" class="w-3 h-3"></i>
                Supprimer sélection
            </button>
        `;
        sessionList.appendChild(headerDiv);
        
        // Add event listener programmatically
        const selectAllCheckbox = headerDiv.querySelector('#selectAllSessions');
        selectAllCheckbox.addEventListener('change', toggleSelectAll);
        
        const bulkDeleteBtn = headerDiv.querySelector('#bulkDeleteBtn');
        bulkDeleteBtn.addEventListener('click', deleteSelectedSessions);
        
        sessions.forEach(session => {
            const sessionItem = document.createElement('div');
            sessionItem.className = `flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-200 ${
                session.is_active 
                    ? 'bg-blue-500/20 border border-blue-500/30' 
                    : 'hover:bg-slate-600/80 hover:shadow-lg hover:shadow-slate-900/50 hover:scale-[1.02] hover:border-slate-600/50'
            }`;
            
            sessionItem.onclick = () => switchSession(session.id);
            
            sessionItem.innerHTML = `
                <div class="flex items-center gap-3">
                    ${!session.is_active ? 
                        `<input type="checkbox" class="session-checkbox w-4 h-4 text-blue-600 bg-slate-700 border-slate-600 rounded focus:ring-blue-500" value="${session.id}">` : 
                        '<div class="w-4"></div>'
                    }
                    <div class="w-8 h-8 rounded-lg flex items-center justify-center ${
                        session.is_active ? 'bg-blue-500/20' : 'bg-slate-700/50'
                    }">
                        <i data-lucide="${session.is_active ? 'folder-open' : 'folder'}" class="w-4 h-4 ${
                            session.is_active ? 'text-blue-400' : 'text-slate-400'
                        }"></i>
                    </div>
                    <div>
                        <p class="text-white font-medium text-sm">#${session.id} ${session.name}</p>
                        <p class="text-slate-400 text-xs">${session.provider} • ${session.model || 'N/A'}</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    ${session.is_active ? 
                        '<span class="text-xs text-blue-400 font-medium">ACTIVE</span>' : 
                        `<button class="delete-session-btn text-slate-500 hover:text-red-400 transition-colors p-1 rounded hover:bg-red-500/10" 
                                title="Supprimer la session">
                            <i data-lucide="trash-2" class="w-3 h-3"></i>
                        </button>`
                    }
                    <div class="text-xs text-slate-500">
                        ${new Date(session.created_at).toLocaleDateString('fr-FR')}
                    </div>
                </div>
            `;
            
            sessionList.appendChild(sessionItem);
            
            // Add event listeners programmatically
            if (!session.is_active) {
                const checkbox = sessionItem.querySelector('.session-checkbox');
                if (checkbox) {
                    checkbox.addEventListener('click', (e) => e.stopPropagation());
                    checkbox.addEventListener('change', updateBulkDeleteButton);
                }
                
                const deleteBtn = sessionItem.querySelector('.delete-session-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteSession(session.id);
                    });
                }
            }
        });
        
        // Re-initialise les icônes Lucide pour les nouveaux éléments
        if (window.lucide) {
            window.lucide.createIcons();
        }
        
    } catch (error) {
        console.error('Erreur chargement sessions:', error);
        const sessionList = document.getElementById('sessionList');
        sessionList.innerHTML = '<div class="text-red-400 text-center py-4 text-sm">Erreur chargement sessions</div>';
    }
}

/**
 * Change vers une session spécifique
 */
async function switchSession(sessionId) {
    try {
        console.log(`🔄 Changement vers session ${sessionId}...`);
        
        // Ferme le sélecteur
        document.getElementById('sessionSelector').classList.add('hidden');
        
        // Active la nouvelle session
        const response = await fetch(`/api/sessions/${sessionId}/activate`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log(`✅ Session ${sessionId} activée:`, result);
        
        // Recharge les données de l'application
        await reloadSessionData();
        
        // Met à jour l'affichage du sélecteur
        const currentSessionName = document.getElementById('currentSessionName');
        if (result.session) {
            currentSessionName.textContent = result.session.name;
        }
        
        // Notification
        showNotification(`Session changée: ${result.session?.name || sessionId}`, 'success');
        
    } catch (error) {
        console.error('❌ Erreur changement session:', error);
        showNotification(`Erreur changement session: ${error.message}`, 'error');
    }
}

/**
 * Ferme le sélecteur de session quand on clique ailleurs
 */
document.addEventListener('click', (event) => {
    const selector = document.getElementById('sessionSelector');
    const button = document.getElementById('sessionSelectorBtn');
    
    if (selector && button && 
        !selector.contains(event.target) && 
        !button.contains(event.target)) {
        selector.classList.add('hidden');
    }
});

/**
 * Ferme le sélecteur avec la touche Échap
 */
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
        const selector = document.getElementById('sessionSelector');
        if (selector) {
            selector.classList.add('hidden');
        }
    }
});

/**
 * Supprime une session avec confirmation
 */
async function deleteSession(sessionId) {
    // Confirmation
    const confirmed = confirm(`Êtes-vous sûr de vouloir supprimer la session #${sessionId} ?\\n\\nCette action est irréversible et supprimera toutes les données associées à cette session.`);
    
    if (!confirmed) return;
    
    try {
        console.log(`🗑️ Suppression de la session ${sessionId}...`);
        
        // Appelle l'API de suppression
        const response = await fetch(`/api/sessions/${sessionId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log(`✅ Session ${sessionId} supprimée:`, result);
        
        // Recharge la liste des sessions
        await loadSessions();
        
        // Notification
        showNotification(`Session #${sessionId} supprimée avec succès`, 'success');
        
    } catch (error) {
        console.error('❌ Erreur suppression session:', error);
        showNotification(`Erreur suppression session: ${error.message}`, 'error');
    }
}

/**
 * Bascule la sélection de toutes les sessions
 */
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('selectAllSessions');
    const checkboxes = document.querySelectorAll('.session-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    
    updateBulkDeleteButton();
}

/**
 * Met à jour la visibilité du bouton de suppression en bulk
 */
function updateBulkDeleteButton() {
    const checkboxes = document.querySelectorAll('.session-checkbox:checked');
    const bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
    
    if (checkboxes.length > 0) {
        bulkDeleteBtn.classList.remove('hidden');
        bulkDeleteBtn.innerHTML = `<i data-lucide="trash-2" class="w-3 h-3"></i> Supprimer (${checkboxes.length})`;
    } else {
        bulkDeleteBtn.classList.add('hidden');
    }
    
    // Re-initialise les icônes Lucide
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

/**
 * Supprime les sessions sélectionnées en bulk
 */
async function deleteSelectedSessions() {
    const checkboxes = document.querySelectorAll('.session-checkbox:checked');
    const selectedIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (selectedIds.length === 0) return;
    
    // Confirmation
    const confirmed = confirm(`Êtes-vous sûr de vouloir supprimer ${selectedIds.length} session(s) ?\\n\\nIDs: ${selectedIds.join(', ')}\\n\\nCette action est irréversible et supprimera toutes les données associées.`);
    
    if (!confirmed) return;
    
    try {
        console.log(`🗑️ Suppression en bulk des sessions: ${selectedIds.join(', ')}`);
        
        // Appelle l'API de suppression en bulk
        const response = await fetch('/api/sessions', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ session_ids: selectedIds })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        const result = await response.json();
        console.log(`✅ Sessions supprimées en bulk:`, result);
        
        // Recharge la liste des sessions
        await loadSessions();
        
        // Notification
        const deletedCount = result.results ? result.results.deleted_count : selectedIds.length;
        showNotification(`${deletedCount} session(s) supprimée(s) avec succès`, 'success');
        
    } catch (error) {
        console.error('❌ Erreur suppression en bulk:', error);
        showNotification(`Erreur suppression en bulk: ${error.message}`, 'error');
    }
}

window.addEventListener('beforeunload', cleanup);
