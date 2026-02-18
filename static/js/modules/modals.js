/**
 * modals.js - Gestion de toutes les modales
 * 
 * Pourquoi : Centralise la logique des modales pour assurer une cohérence
 * dans les animations, la gestion des clics extérieurs, et la fermeture.
 */

import { 
    loadProviders, 
    loadModels, 
    createSession 
} from './api.js';
import { 
    showNotification, 
    formatContextSize, 
    getProviderColor,
    eventBus 
} from './utils.js';
import { clearMetrics, setCurrentMaxContext } from './sessions.js';
import { initCompactionChart } from './charts.js';

// ============================================================================
// ÉTAT DES MODALES
// ============================================================================

let selectedProvider = null;
let selectedModel = null;
let availableProviders = [];
let availableModels = [];
let currentFilter = '';

// ============================================================================
// MODALE NOUVELLE SESSION
// ============================================================================

/**
 * Affiche la modale de création de nouvelle session
 * Pourquoi : Point d'entrée pour changer de modèle LLM
 */
export function showNewSessionModal() {
    // Reset sélection
    selectedProvider = null;
    selectedModel = null;
    currentFilter = '';
    
    // Reset UI
    const filterInput = document.getElementById('modelFilter');
    const selectedInfo = document.getElementById('selectedModelInfo');
    const createBtn = document.getElementById('createSessionBtn');
    const nameInput = document.getElementById('newSessionName');
    
    if (filterInput) filterInput.value = '';
    if (selectedInfo) selectedInfo.textContent = 'Aucun modèle sélectionné';
    if (createBtn) createBtn.disabled = true;
    if (nameInput) {
        nameInput.value = `Session ${new Date().toLocaleTimeString('fr-FR')}`;
    }
    
    // Charge les providers
    loadProvidersData();
    
    // Affiche la modale avec animation
    const modal = document.getElementById('newSessionModal');
    const content = document.getElementById('modalContent');
    
    if (!modal || !content) return;
    
    modal.classList.remove('hidden');
    
    setTimeout(() => {
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
    
    // Setup event listeners
    setupNewSessionListeners();
}

/**
 * Ferme la modale de nouvelle session
 */
export function closeNewSessionModal() {
    const modal = document.getElementById('newSessionModal');
    const content = document.getElementById('modalContent');
    
    if (!modal || !content) return;
    
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 200);
}

/**
 * Charge les données des providers et modèles
 */
async function loadProvidersData() {
    const container = document.getElementById('providersList');
    if (!container) return;
    
    container.innerHTML = `
        <div class="text-slate-500 text-center py-8">
            <i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i>
            Chargement des modèles...
        </div>
    `;
    
    if (window.lucide) {
        lucide.createIcons();
    }
    
    try {
        // Charge les providers et modèles en parallèle
        const [providers, models] = await Promise.all([
            loadProviders(),
            loadModels()
        ]);
        
        availableProviders = providers;
        availableModels = models;
        
        renderProvidersList();
    } catch (error) {
        console.error('Erreur chargement providers:', error);
        if (container) {
            container.innerHTML = `
                <div class="text-red-400 text-center py-4">
                    <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-2"></i>
                    Erreur de chargement des modèles
                </div>
            `;
            if (window.lucide) {
                lucide.createIcons();
            }
        }
    }
}

/**
 * Rend la liste des providers et modèles
 */
function renderProvidersList() {
    const container = document.getElementById('providersList');
    if (!container) return;
    
    if (availableProviders.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-center py-4">Aucun provider disponible</div>';
        return;
    }
    
    let html = '';
    
    availableProviders.forEach(provider => {
        // Filtre les modèles selon la recherche
        const models = provider.models.filter(m => {
            if (!currentFilter) return true;
            const search = currentFilter.toLowerCase();
            return m.name.toLowerCase().includes(search) || 
                   provider.name.toLowerCase().includes(search);
        });
        
        if (models.length === 0 && currentFilter) return;
        
        const colorClass = provider.color;
        const hasKey = provider.has_api_key;
        
        html += `
            <div class="provider-section mb-6">
                <!-- Header Provider -->
                <div class="flex items-center gap-3 mb-3 pb-2 border-b border-slate-700/50">
                    <div class="w-8 h-8 rounded-lg bg-${colorClass}-500/20 flex items-center justify-center">
                        <i data-lucide="${provider.icon}" class="w-4 h-4 text-${colorClass}-400"></i>
                    </div>
                    <div class="flex-1">
                        <h4 class="font-semibold text-white">${provider.name}</h4>
                        <p class="text-xs text-slate-500">${provider.type} • ${models.length} modèle(s)</p>
                    </div>
                    ${!hasKey ? '<span class="text-xs text-yellow-500/80 bg-yellow-500/10 px-2 py-1 rounded">Clé manquante</span>' : ''}
                </div>
                
                <!-- Grid de modèles -->
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    ${models.map(model => renderModelCard(model, provider)).join('')}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html || '<div class="text-slate-500 text-center py-4">Aucun modèle ne correspond à votre recherche</div>';
    
    if (window.lucide) {
        lucide.createIcons();
    }
}

function renderModelCard(model, provider) {
    const isSelected = selectedProvider === provider.key && selectedModel === model.key;
    const colorClass = provider.color;
    const borderClass = isSelected 
        ? `border-${colorClass}-500 bg-${colorClass}-500/10 ring-1 ring-${colorClass}-500/50` 
        : 'border-slate-700 hover:border-slate-600 hover:bg-slate-800/50';
    
    const contextText = formatContextSize(model.max_context_size);
    
    // Capacités
    const caps = model.capabilities || [];
    const capIcons = {
        'tool_use': '<i data-lucide="wrench" class="w-3 h-3" title="Tool Use"></i>',
        'thinking': '<i data-lucide="brain" class="w-3 h-3" title="Thinking"></i>',
        'vision': '<i data-lucide="eye" class="w-3 h-3" title="Vision"></i>',
        'multimodal': '<i data-lucide="image" class="w-3 h-3" title="Multimodal"></i>',
        'autocomplete': '<i data-lucide="zap" class="w-3 h-3" title="Autocomplete"></i>',
        'reasoning': '<i data-lucide="lightbulb" class="w-3 h-3" title="Reasoning"></i>',
        'coding': '<i data-lucide="code" class="w-3 h-3" title="Coding"></i>',
        'ultra_fast': '<i data-lucide="rocket" class="w-3 h-3" title="Ultra Fast"></i>'
    };
    const capHtml = caps.map(c => capIcons[c] || '').join('');
    
    return `
        <div onclick="window.selectModel('${provider.key}', '${model.key}', '${model.name.replace(/'/g, "\\'")}')" 
             class="p-3 rounded-xl border ${borderClass} cursor-pointer transition-all ${isSelected ? '' : 'hover:border-slate-600'}">
            <div class="flex items-start justify-between">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <span class="font-medium text-white text-sm truncate">${model.name}</span>
                        ${isSelected ? `<i data-lucide="check-circle" class="w-4 h-4 text-${colorClass}-400 flex-shrink-0"></i>` : ''}
                    </div>
                    <div class="flex items-center gap-2 mt-1.5">
                        <span class="text-xs text-${colorClass}-400 bg-${colorClass}-500/10 px-1.5 py-0.5 rounded">${contextText}</span>
                        <span class="flex items-center gap-1 text-slate-500">${capHtml}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Filtre les modèles selon la recherche
 * @param {string} query - Texte de recherche
 */
export function filterModels(query) {
    currentFilter = query;
    renderProvidersList();
}

/**
 * Sélectionne un modèle
 * @param {string} providerKey - Clé du provider
 * @param {string} modelKey - Clé du modèle
 * @param {string} modelName - Nom du modèle
 */
export function selectModel(providerKey, modelKey, modelName) {
    selectedProvider = providerKey;
    selectedModel = modelKey;
    
    const provider = availableProviders.find(p => p.key === providerKey);
    const selectedInfo = document.getElementById('selectedModelInfo');
    const createBtn = document.getElementById('createSessionBtn');
    
    if (selectedInfo && provider) {
        selectedInfo.innerHTML = `<span class="text-${provider.color}-400">${provider.name}</span> • ${modelName}`;
    }
    
    if (createBtn) {
        createBtn.disabled = false;
    }
    
    renderProvidersList();
}

/**
 * Crée une nouvelle session avec le provider et modèle sélectionnés
 */
export async function createNewSessionWithProvider() {
    if (!selectedProvider) {
        showNotification('Veuillez sélectionner un modèle', 'error');
        return;
    }
    
    const nameInput = document.getElementById('newSessionName');
    const name = nameInput?.value || `Session ${new Date().toLocaleTimeString('fr-FR')}`;
    
    try {
        const data = await createSession({
            name,
            provider: selectedProvider,
            model: selectedModel
        });
        
        if (data.id) {
            // Reset et mise à jour
            clearMetrics();
            
            // Met à jour l'affichage
            const sessionNameEl = document.getElementById('session-name');
            const sessionBadgeEl = document.getElementById('session-badge');
            const sessionDateEl = document.getElementById('session-date');
            const sessionProviderEl = document.getElementById('session-provider');
            
            if (sessionNameEl) sessionNameEl.textContent = data.name;
            if (sessionBadgeEl) sessionBadgeEl.textContent = `#${data.id}`;
            if (sessionDateEl) sessionDateEl.textContent = new Date(data.created_at).toLocaleString('fr-FR');
            
            const provider = availableProviders.find(p => p.key === data.provider);
            const providerName = provider?.name || data.provider;
            const providerColor = provider?.color || 'blue';
            
            if (sessionProviderEl) {
                sessionProviderEl.innerHTML = `
                    <span class="w-2 h-2 rounded-full bg-${providerColor}-500"></span>
                    ${providerName}
                `;
            }
            
            // Met à jour max_context
            if (data.max_context) {
                setCurrentMaxContext(data.max_context);
                const maxContextEl = document.getElementById('max-context-display');
                if (maxContextEl) {
                    maxContextEl.textContent = `/ ${data.max_context.toLocaleString()}`;
                }
            } else if (selectedModel) {
                const model = availableModels.find(m => m.key === selectedModel);
                if (model) {
                    setCurrentMaxContext(model.max_context_size);
                    const maxContextEl = document.getElementById('max-context-display');
                    if (maxContextEl) {
                        maxContextEl.textContent = `/ ${model.max_context_size.toLocaleString()}`;
                    }
                }
            }
            
            closeNewSessionModal();
            showNotification(`Session créée avec ${providerName}`, 'success');
            
            // Émet l'événement de nouvelle session
            eventBus.emit('session:new_created', data);
        }
    } catch (error) {
        console.error('Erreur création session:', error);
        showNotification('Erreur lors de la création', 'error');
    }
}

/**
 * Setup les event listeners de la modale
 */
function setupNewSessionListeners() {
    const modal = document.getElementById('newSessionModal');
    const nameInput = document.getElementById('newSessionName');
    
    // Fermeture au clic extérieur
    if (modal) {
        modal.onclick = (e) => {
            if (e.target === modal) {
                closeNewSessionModal();
            }
        };
    }
    
    // Création avec Entrée
    if (nameInput) {
        nameInput.onkeypress = (e) => {
            if (e.key === 'Enter' && selectedProvider) {
                createNewSessionWithProvider();
            }
        };
    }
}

// ============================================================================
// MODALE COMPACTION PREVIEW
// ============================================================================

let compactionPreview = null;

/**
 * Affiche la modale de preview de compaction
 * Pourquoi : Permet à l'utilisateur de voir l'impact avant d'exécuter
 */
export async function showCompactPreviewModal() {
    const currentSessionId = document.getElementById('session-badge')?.textContent?.replace('#', '');
    if (!currentSessionId) return;
    
    const modal = document.getElementById('compactPreviewModal');
    const content = document.getElementById('compactPreviewModalContent');
    const messagesPreview = document.getElementById('messagesPreview');
    
    if (!modal || !content || !messagesPreview) return;
    
    // Reset
    messagesPreview.innerHTML = `
        <div class="text-slate-500 text-center py-4">
            <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
            Chargement du preview...
        </div>
    `;
    
    if (window.lucide) {
        lucide.createIcons();
    }
    
    modal.classList.remove('hidden');
    setTimeout(() => {
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
    
    // Charge le preview
    try {
        const response = await fetch(`/api/compaction/${currentSessionId}/preview`);
        compactionPreview = await response.json();
        
        renderCompactionPreview();
        
    } catch (error) {
        console.error('Erreur chargement preview:', error);
        messagesPreview.innerHTML = `
            <div class="text-red-400 text-center py-4">
                <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-2"></i>
                <p>Erreur lors du chargement du preview</p>
            </div>
        `;
        if (window.lucide) {
            lucide.createIcons();
        }
    }
}

function renderCompactionPreview() {
    const messagesPreview = document.getElementById('messagesPreview');
    const executeBtn = document.getElementById('executeCompactBtn');
    
    if (!compactionPreview || !messagesPreview) return;
    
    if (!compactionPreview.can_compact) {
        messagesPreview.innerHTML = `
            <div class="text-amber-400 text-center py-4 bg-amber-900/20 rounded-lg border border-amber-500/30">
                <i data-lucide="info" class="w-5 h-5 mx-auto mb-2"></i>
                <p>${compactionPreview.message || 'Compaction non disponible'}</p>
            </div>
        `;
        if (executeBtn) executeBtn.disabled = true;
    } else {
        // Met à jour les stats
        const previewOriginalEl = document.getElementById('previewOriginalTokens');
        const previewCompactedEl = document.getElementById('previewCompactedTokens');
        const previewSavingsEl = document.getElementById('previewSavings');
        const preserveCountEl = document.getElementById('preserveCount');
        
        if (previewOriginalEl) {
            previewOriginalEl.textContent = compactionPreview.estimate.original_tokens.toLocaleString();
        }
        if (previewCompactedEl) {
            previewCompactedEl.textContent = compactionPreview.estimate.compacted_tokens.toLocaleString();
        }
        if (previewSavingsEl) {
            previewSavingsEl.textContent = 
                `${compactionPreview.estimate.tokens_saved.toLocaleString()} (${compactionPreview.estimate.savings_percentage}%)`;
        }
        if (preserveCountEl) {
            preserveCountEl.textContent = compactionPreview.config.preserved_messages;
        }
        
        // Affiche les messages
        let html = '';
        compactionPreview.preview.messages_preview.forEach((msg) => {
            const roleColor = msg.role === 'user' ? 'text-blue-400' : 'text-purple-400';
            const roleLabel = msg.role === 'user' ? 'User' : 'Assistant';
            html += `
                <div class="p-3 bg-slate-800/50 rounded-lg text-sm">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-medium ${roleColor}">${roleLabel}</span>
                        <span class="text-xs text-slate-500">${msg.full_length} caractères</span>
                    </div>
                    <p class="text-slate-300 truncate">${msg.preview}</p>
                </div>
            `;
        });
        
        if (compactionPreview.preview.total_messages > compactionPreview.preview.messages_preview.length) {
            const remaining = compactionPreview.preview.total_messages - compactionPreview.preview.messages_preview.length;
            html += `
                <div class="text-center text-slate-500 text-sm py-2">
                    ... et ${remaining} autres messages
                </div>
            `;
        }
        
        messagesPreview.innerHTML = html;
        if (executeBtn) executeBtn.disabled = false;
    }
    
    if (window.lucide) {
        lucide.createIcons();
    }
}

/**
 * Ferme la modale de preview de compaction
 */
export function closeCompactPreviewModal() {
    const modal = document.getElementById('compactPreviewModal');
    const content = document.getElementById('compactPreviewModalContent');
    
    if (!modal || !content) return;
    
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    
    setTimeout(() => {
        modal.classList.add('hidden');
        // Reset le loading state
        const loadingState = document.getElementById('compactLoadingState');
        const executeBtn = document.getElementById('executeCompactBtn');
        
        if (loadingState) loadingState.classList.add('hidden');
        if (executeBtn) executeBtn.disabled = false;
    }, 200);
}

// ============================================================================
// MODALE RÉSULTAT COMPACTION
// ============================================================================

/**
 * Affiche la modale de résultat de compaction
 * @param {Object} result - Résultat de la compaction
 */
export function showCompactResultModal(result) {
    const resultTokensSaved = document.getElementById('resultTokensSaved');
    const resultRatio = document.getElementById('resultRatio');
    const resultMessagesBefore = document.getElementById('resultMessagesBefore');
    const resultMessagesAfter = document.getElementById('resultMessagesAfter');
    const resultSummarized = document.getElementById('resultSummarized');
    
    if (resultTokensSaved) resultTokensSaved.textContent = result.tokens_saved?.toLocaleString() || '-';
    if (resultRatio) {
        resultRatio.textContent = result.compaction_ratio ? `${result.compaction_ratio.toFixed(1)}%` : '-%';
    }
    if (resultMessagesBefore) resultMessagesBefore.textContent = result.messages_before || '-';
    if (resultMessagesAfter) resultMessagesAfter.textContent = result.messages_after || '-';
    if (resultSummarized) resultSummarized.textContent = result.summarized_count || '-';
    
    const modal = document.getElementById('compactResultModal');
    const content = document.getElementById('compactResultModalContent');
    
    if (!modal || !content) return;
    
    modal.classList.remove('hidden');
    setTimeout(() => {
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
}

/**
 * Ferme la modale de résultat
 */
export function closeCompactResultModal() {
    const modal = document.getElementById('compactResultModal');
    const content = document.getElementById('compactResultModalContent');
    
    if (!modal || !content) return;
    
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    
    setTimeout(() => {
        modal.classList.add('hidden');
    }, 200);
}

// ============================================================================
// SETUP GLOBAL
// ============================================================================

/**
 * Initialise tous les listeners de modales
 * Pourquoi : Setup une seule fois au démarrage
 */
export function initModalListeners() {
    // Fermeture modales au clic extérieur
    const compactPreviewModal = document.getElementById('compactPreviewModal');
    const compactResultModal = document.getElementById('compactResultModal');
    
    if (compactPreviewModal) {
        compactPreviewModal.onclick = (e) => {
            if (e.target === compactPreviewModal) {
                closeCompactPreviewModal();
            }
        };
    }
    
    if (compactResultModal) {
        compactResultModal.onclick = (e) => {
            if (e.target === compactResultModal) {
                closeCompactResultModal();
            }
        };
    }
    
    // Expose selectModel globalement pour les onclick inline
    window.selectModel = selectModel;
    
    // Expose filterModels globalement pour l'oninput inline du champ de recherche
    window.filterModels = filterModels;
}

/**
 * Alias pour compatibilité
 */
export function createNewSession() {
    showNewSessionModal();
}
