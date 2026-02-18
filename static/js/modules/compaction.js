/**
 * compaction.js - Fonctionnalités de compaction de contexte
 * 
 * Pourquoi : Centralise toute la logique liée à la compaction (preview,
 * exécution, historique, auto-compaction) pour une maintenance facilitée.
 */

import { 
    getCompactionStats, 
    getAutoCompactionStatus,
    toggleAutoCompaction as apiToggleAutoCompaction,
    getCompactionHistoryChart,
    getCompactionPreview as apiGetCompactionPreview,
    executeCompaction as apiExecuteCompaction
} from './api.js';
import { showNotification, formatTokens, formatPercentage, eventBus } from './utils.js';
import { updateCompactionChart } from './charts.js';
import { getCurrentSessionId } from './sessions.js';

// ============================================================================
// CONSTANTES
// ============================================================================

const COMPACTION_BUTTON_THRESHOLD = 70;  // Seuil d'activation du bouton (%)

// ============================================================================
// ÉTAT
// ============================================================================

let autoCompactionEnabled = true;
let compactionPreview = null;

// ============================================================================
// MISE À JOUR UI
// ============================================================================

/**
 * Met à jour le bouton de compaction et les indicateurs associés
 * Pourquoi : Appelé régulièrement pour refléter l'état courant
 */
export async function updateCompactionButton() {
    const sessionId = getCurrentSessionId();
    const btn = document.getElementById('compactBtn');
    const btnText = document.getElementById('compactBtnText');
    
    if (!sessionId) {
        if (btn) {
            btn.disabled = true;
            btn.className = "flex items-center gap-2 px-5 py-2.5 bg-slate-700 text-slate-500 rounded-xl font-medium transition-all";
        }
        if (btnText) btnText.textContent = 'Compacter Contexte';
        return;
    }
    
    try {
        // Récupère le statut auto-compaction
        const autoData = await getAutoCompactionStatus(sessionId);
        if (autoData.status) {
            autoCompactionEnabled = autoData.status.session_auto_enabled;
            updateAutoCompactionToggle();
        }
        
        // Récupère les stats de compaction
        const data = await getCompactionStats(sessionId);
        
        if (data.context) {
            const percentage = data.context.percentage;
            const threshold = data.context.threshold;
            
            // Active le bouton si au-dessus du seuil d'UI
            const shouldEnable = percentage >= COMPACTION_BUTTON_THRESHOLD;
            
            if (btn) {
                btn.disabled = !shouldEnable;
                
                // Style selon le niveau
                if (percentage >= 95) {
                    btn.className = "flex items-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-xl font-medium transition-all hover:shadow-lg hover:shadow-red-500/25 active:scale-95 animate-pulse";
                } else if (percentage >= 80) {
                    btn.className = "flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl font-medium transition-all hover:shadow-lg hover:shadow-amber-500/25 active:scale-95";
                } else {
                    btn.className = "flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-xl font-medium transition-all hover:shadow-lg hover:shadow-amber-500/25 active:scale-95";
                }
            }
            
            if (btnText) {
                btnText.textContent = shouldEnable 
                    ? `🗜️ Compacter (${percentage.toFixed(0)}%)`
                    : `Compacter (${percentage.toFixed(0)}%)`;
            }
            
            // Met à jour les barres multi-couches
            updateMultiLayerGauge(data.context, threshold);
        }
        
        // Met à jour l'historique de compaction
        await updateCompactionHistory(sessionId);
        
    } catch (error) {
        console.error('❌ Erreur chargement stats compaction:', error);
    }
}

/**
 * Met à jour les jauges multi-couches (usage, réservé, seuil)
 * Pourquoi : Visualisation détaillée de l'usage du contexte
 * @param {Object} context - Données de contexte
 * @param {number} threshold - Seuil de compaction
 */
export function updateMultiLayerGauge(context, threshold) {
    const usageBar = document.getElementById('usage-bar');
    const reservedZone = document.getElementById('reserved-zone');
    const thresholdMarker = document.getElementById('compaction-threshold-marker');
    const usageText = document.getElementById('usage-percentage-text');
    
    if (!usageBar) return;
    
    const percentage = context.percentage;
    const reservedTokens = context.reserved_tokens || 0;
    const maxContext = context.max_context;
    
    // Barre d'usage
    usageBar.style.width = `${Math.min(percentage, 100)}%`;
    if (usageText) usageText.textContent = `${percentage.toFixed(1)}%`;
    
    // Zone réservée
    if (reservedZone && maxContext > 0) {
        const reservedPercent = (reservedTokens / maxContext) * 100;
        reservedZone.style.width = `${Math.min(reservedPercent, 100 - percentage)}%`;
    }
    
    // Marqueur de seuil
    if (thresholdMarker && threshold) {
        thresholdMarker.style.left = `${threshold}%`;
    }
    
    // Couleur selon le niveau
    if (percentage < 50) {
        usageBar.className = "h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full transition-all duration-500";
    } else if (percentage < 80) {
        usageBar.className = "h-full bg-gradient-to-r from-green-500 via-yellow-500 to-yellow-400 rounded-full transition-all duration-500";
    } else {
        usageBar.className = "h-full bg-gradient-to-r from-yellow-500 via-orange-500 to-red-500 rounded-full transition-all duration-500";
    }
}

/**
 * Met à jour le toggle d'auto-compaction
 * Pourquoi : Affiche l'état actuel du mode auto/manuel
 */
export function updateAutoCompactionToggle() {
    const toggle = document.getElementById('autoCompactToggle');
    const text = document.getElementById('autoCompactText');
    
    if (!toggle || !text) return;
    
    if (autoCompactionEnabled) {
        toggle.className = "text-xs flex items-center gap-1.5 px-2 py-1 rounded-lg bg-green-500/20 text-green-400 border border-green-500/30 transition-colors cursor-pointer";
        text.textContent = "Auto";
        toggle.title = "Auto-compaction activée - Cliquez pour désactiver";
    } else {
        toggle.className = "text-xs flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-700 text-slate-400 border border-slate-600 transition-colors cursor-pointer";
        text.textContent = "Manuel";
        toggle.title = "Auto-compaction désactivée - Cliquez pour activer";
    }
}

/**
 * Bascule l'état de l'auto-compaction
 * Pourquoi : Permet à l'utilisateur de contrôler le comportement auto
 */
export async function toggleAutoCompaction() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    
    const newState = !autoCompactionEnabled;
    
    try {
        const data = await apiToggleAutoCompaction(sessionId, newState);
        
        if (data.success) {
            autoCompactionEnabled = newState;
            updateAutoCompactionToggle();
            showNotification(
                `Auto-compaction ${newState ? 'activée' : 'désactivée'}`,
                'success'
            );
        }
    } catch (error) {
        console.error('Erreur toggle auto-compaction:', error);
        showNotification('Erreur lors du changement', 'error');
    }
}

// ============================================================================
// HISTORIQUE
// ============================================================================

/**
 * Met à jour l'historique de compaction
 * Pourquoi : Affiche les statistiques et le graphique d'historique
 * @param {number} sessionId - ID de la session
 */
async function updateCompactionHistory(sessionId) {
    try {
        // Récupère les données du graphique
        const chartData = await getCompactionHistoryChart(sessionId);
        
        // Met à jour le graphique
        updateCompactionChart(chartData);
        
        // Récupère les stats
        const statsData = await getCompactionStats(sessionId);
        
        // Affiche ou masque la carte d'historique
        const historyCard = document.getElementById('compaction-history-card');
        const compaction = statsData.compaction;
        
        if (historyCard && compaction && compaction.compaction_count > 0) {
            historyCard.classList.remove('hidden');
            
            // Met à jour les badges
            const totalSavedBadge = document.getElementById('total-saved-badge');
            const compactionCount = document.getElementById('compaction-count');
            const compactionAvgRatio = document.getElementById('compaction-avg-ratio');
            const lastCompactionTime = document.getElementById('last-compaction-time');
            
            if (totalSavedBadge) {
                totalSavedBadge.textContent = `${formatTokens(compaction.total_tokens_saved)} tokens économisés`;
            }
            if (compactionCount) {
                compactionCount.textContent = compaction.compaction_count;
            }
            
            // Calcule la moyenne
            if (compaction.history && compaction.history.length > 0) {
                const avgRatio = compaction.history.reduce((sum, h) => sum + (h.compaction_ratio || 0), 0) 
                    / compaction.history.length;
                if (compactionAvgRatio) {
                    compactionAvgRatio.textContent = formatPercentage(avgRatio);
                }
            }
            
            // Dernière compaction
            if (compaction.last_compaction_at && lastCompactionTime) {
                const date = new Date(compaction.last_compaction_at);
                lastCompactionTime.textContent = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
            }
        } else if (historyCard) {
            historyCard.classList.add('hidden');
        }
        
    } catch (error) {
        console.error('❌ Erreur chargement historique compaction:', error);
    }
}

// ============================================================================
// EXÉCUTION
// ============================================================================

/**
 * Charge et affiche le preview de compaction
 * Pourquoi : Permet à l'utilisateur de voir l'impact avant d'exécuter
 */
export async function loadCompactionPreview() {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    
    try {
        compactionPreview = await apiGetCompactionPreview(sessionId);
        return compactionPreview;
    } catch (error) {
        console.error('Erreur chargement preview:', error);
        throw error;
    }
}

/**
 * Exécute la compaction
 * Pourquoi : Action principale de réduction du contexte
 * @param {Object} options - Options de compaction
 */
export async function executeCompaction(options = {}) {
    const sessionId = getCurrentSessionId();
    if (!sessionId) return;
    
    const opts = {
        preserve_messages: options.preserve_messages ?? 2,
        force: options.force ?? false
    };
    
    // Affiche le loading
    const loadingState = document.getElementById('compactLoadingState');
    const executeBtn = document.getElementById('executeCompactBtn');
    
    if (loadingState) loadingState.classList.remove('hidden');
    if (executeBtn) executeBtn.disabled = true;
    
    try {
        const result = await apiExecuteCompaction(sessionId, opts);
        
        if (result.error) {
            showNotification(`Erreur: ${result.error}`, 'error');
            return { error: result.error };
        }
        
        if (result.current_stats) {
            // Met à jour l'auto-compaction si checkbox modifiée
            const checkbox = document.getElementById('autoCompactCheckbox');
            if (checkbox && checkbox.checked !== autoCompactionEnabled) {
                await toggleAutoCompaction();
            }
            
            showNotification('Compaction initialisée avec succès', 'success');
            
            // Rafraîchit les stats
            await updateCompactionButton();
            
            return result;
        } else {
            showNotification('Aucune compaction nécessaire', 'info');
            return { noop: true };
        }
    } catch (error) {
        console.error('Erreur compaction:', error);
        showNotification('Erreur lors de la compaction', 'error');
        throw error;
    } finally {
        if (loadingState) loadingState.classList.add('hidden');
        if (executeBtn) executeBtn.disabled = false;
    }
}

// ============================================================================
// GESTION DES ÉVÉNEMENTS
// ============================================================================

/**
 * Gère les événements WebSocket de compaction
 * Pourquoi : Réagit aux compactions automatiques et résultats
 * @param {Object} data - Données de l'événement
 */
export function handleCompactionEvent(data) {
    if (data.compaction) {
        // Met à jour le bouton et l'historique
        updateCompactionButton();
        
        // Émet l'événement pour les logs
        eventBus.emit('compaction:completed', data);
    }
}

/**
 * Gère les alertes de seuil de compaction
 * Pourquoi : Notifie l'utilisateur des seuils critiques
 * @param {Object} data - Données de l'alerte
 */
export function handleCompactionAlert(data) {
    if (data.alert) {
        const alert = data.alert;
        
        // Met à jour l'alerte visuelle
        eventBus.emit('alert:received', {
            level: alert.level,
            color: alert.level === 'critical' ? '#ef4444' : alert.level === 'warning' ? '#f97316' : '#eab308',
            bg: alert.level === 'critical' ? 'bg-red-500/20' : alert.level === 'warning' ? 'bg-orange-500/20' : 'bg-yellow-500/20',
            text: alert.level === 'critical' ? 'text-red-400' : alert.level === 'warning' ? 'text-orange-400' : 'text-yellow-400',
            message: alert.message
        });
        
        // Active le bouton si nécessaire
        if (alert.level === 'critical' || alert.level === 'warning') {
            const btn = document.getElementById('compactBtn');
            if (btn) {
                btn.disabled = false;
                btn.classList.add('animate-pulse');
            }
        }
    }
}

// ============================================================================
// POLLING
// ============================================================================

let compactionInterval = null;

/**
 * Démarre le polling périodique des stats de compaction
 * Pourquoi : Garde l'UI synchronisée avec l'état du serveur
 * @param {number} interval - Intervalle en ms (défaut: 5000)
 */
export function startCompactionPolling(interval = 5000) {
    stopCompactionPolling();
    compactionInterval = setInterval(() => {
        const sessionId = getCurrentSessionId();
        if (sessionId) {
            updateCompactionButton();
        }
    }, interval);
}

/**
 * Arrête le polling
 */
export function stopCompactionPolling() {
    if (compactionInterval) {
        clearInterval(compactionInterval);
        compactionInterval = null;
    }
}

// ============================================================================
// INITIALISATION
// ============================================================================

/**
 * Initialise les listeners liés à la compaction
 */
export function initCompactionListeners() {
    // Toggle auto-compaction
    const autoToggle = document.getElementById('autoCompactToggle');
    if (autoToggle) {
        autoToggle.addEventListener('click', toggleAutoCompaction);
    }
    
    // Événements WebSocket
    eventBus.on('compaction:event', handleCompactionEvent);
    eventBus.on('compaction:alert', handleCompactionAlert);
    eventBus.on('compaction:auto_toggled', ({ enabled }) => {
        autoCompactionEnabled = enabled;
        updateAutoCompactionToggle();
    });
    
    // Nouvelle session
    eventBus.on('session:new_created', () => {
        updateCompactionButton();
    });
}

/**
 * Récupère l'état actuel de l'auto-compaction
 * @returns {boolean}
 */
export function isAutoCompactionEnabled() {
    return autoCompactionEnabled;
}
