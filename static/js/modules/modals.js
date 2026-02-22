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
import {
    memoryCompressionService,
    similarityService,
    handleMemoryError,
    throttle
} from './memory-service.js';
import {
    renderSimilarityChart,
    destroySimilarityChart
} from './similarity-chart.js';
import { getModalManager } from './accessibility/modal-manager.js';

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

    // Intègre ModalManager pour gestion du focus
    const modalManager = getModalManager();
    modalManager.open(modal);

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

    // Intègre ModalManager pour restauration du focus
    const modalManager = getModalManager();
    modalManager.close(modal);

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

    // Affiche le message de chargement de manière sécurisée (sans innerHTML)
    container.textContent = ''; // Clear existing content

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'text-slate-500 text-center py-8';

    const loadingIcon = document.createElement('i');
    loadingIcon.setAttribute('data-lucide', 'loader-2');
    loadingIcon.className = 'w-6 h-6 animate-spin mx-auto mb-2';

    const loadingText = document.createElement('div');
    loadingText.textContent = 'Chargement des modèles...';

    loadingDiv.appendChild(loadingIcon);
    loadingDiv.appendChild(loadingText);
    container.appendChild(loadingDiv);

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
            // Affiche le message d'erreur de manière sécurisée (sans innerHTML)
            container.textContent = ''; // Clear existing content

            const errorDiv = document.createElement('div');
            errorDiv.className = 'text-red-400 text-center py-4';

            const errorIcon = document.createElement('i');
            errorIcon.setAttribute('data-lucide', 'alert-circle');
            errorIcon.className = 'w-5 h-5 mx-auto mb-2';

            const errorText = document.createElement('div');
            errorText.textContent = 'Erreur de chargement des modèles';

            errorDiv.appendChild(errorIcon);
            errorDiv.appendChild(errorText);
            container.appendChild(errorDiv);

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
        // Affiche le message "aucun provider" de manière sécurisée (sans innerHTML)
        container.textContent = ''; // Clear existing content

        const noProvidersDiv = document.createElement('div');
        noProvidersDiv.className = 'text-slate-500 text-center py-4';
        noProvidersDiv.textContent = 'Aucun provider disponible';

        container.appendChild(noProvidersDiv);
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

    // Affiche le contenu de manière sécurisée (sans innerHTML)
    container.textContent = ''; // Clear existing content

    if (html) {
        // Si du contenu HTML dynamique existe, utiliser une approche sécurisée
        container.innerHTML = html; // Temporaire - à remplacer par DOM sécurisé si nécessaire
    } else {
        // Message statique sécurisé
        const noResultsDiv = document.createElement('div');
        noResultsDiv.className = 'text-slate-500 text-center py-4';
        noResultsDiv.textContent = 'Aucun modèle ne correspond à votre recherche';
        container.appendChild(noResultsDiv);
    }

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
        // Crée le contenu de manière sécurisée (sans innerHTML)
        selectedInfo.textContent = ''; // Clear existing content

        const providerSpan = document.createElement('span');
        providerSpan.className = `text-${provider.color}-400`;
        providerSpan.textContent = provider.name;

        const separator = document.createTextNode(' • ');
        const modelText = document.createTextNode(modelName);

        selectedInfo.appendChild(providerSpan);
        selectedInfo.appendChild(separator);
        selectedInfo.appendChild(modelText);
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
            closeNewSessionModal();
            eventBus.emit('session:new', data);
            showNotification(`Session "${name}" créée avec succès`, 'success');
        } else {
            throw new Error('Erreur lors de la création de la session');
        }
    } catch (error) {
        console.error('Erreur création session:', error);
        showNotification('Erreur lors de la création de la session', 'error');
    }
}

/**
 * Configure les listeners de la modale nouvelle session
 */
function setupNewSessionListeners() {
    // Fermeture
    const modal = document.getElementById('newSessionModal');
    const closeBtn = document.getElementById('closeNewSessionModal');
    const cancelBtn = document.getElementById('cancelNewSession');

    if (closeBtn) closeBtn.onclick = closeNewSessionModal;
    if (cancelBtn) cancelBtn.onclick = closeNewSessionModal;
    if (modal) {
        modal.onclick = (e) => {
            if (e.target === modal) closeNewSessionModal();
        };
    }

    // Création avec Entrée
    const nameInput = document.getElementById('newSessionName');
    if (nameInput) {
        nameInput.onkeypress = (e) => {
            if (e.key === 'Enter' && selectedProvider) {
                createNewSessionWithProvider();
            }
        };
    }
}

// ============================================================================
// MODALES MÉMOIRE (Compression & Similarité)
// ============================================================================

/**
 * Factory pattern pour créer les modales mémoire
 * Pourquoi : Évite la duplication et assure la cohérence des modales
 * @param {string} type - Type de modal ('compress' | 'similarity')
 * @returns {Object} Interface de contrôle (show, hide)
 */
export function createMemoryModal(type) {
    const modalId = `memory-${type}-modal`;

    // Vérifier si la modale existe déjà
    if (document.getElementById(modalId)) {
        return {
            show: () => {
                const modal = document.getElementById(modalId);
                modal.style.display = 'flex';
                document.body.style.overflow = 'hidden';
                loadModalContent(type, `${modalId}-body`);
            },
            hide: () => {
                const modal = document.getElementById(modalId);
                modal.style.display = 'none';
                document.body.style.overflow = '';
                cleanupModalResources(modalId);
            }
        };
    }

    // Créer la structure de la modale
    const modalHTML = `
        <div id="${modalId}" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
            <div class="glass-panel rounded-2xl w-full max-w-4xl mx-auto transform transition-all scale-100 opacity-100 max-h-[90vh] flex flex-col">
                <!-- Header -->
                <div class="flex items-center justify-between p-6 border-b border-slate-700/50">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-br ${type === 'compress' ? 'from-amber-500 to-orange-600' : 'from-violet-500 to-purple-600'} flex items-center justify-center">
                            <i data-lucide="${type === 'compress' ? 'minimize-2' : 'search'}" class="w-5 h-5 text-white"></i>
                        </div>
                        <div>
                            <h3 class="text-xl font-bold text-white">${type === 'compress' ? 'Compression Mémoire' : 'Recherche Similarité'}</h3>
                            <p class="text-slate-400 text-sm">${type === 'compress' ? 'Réduction intelligente du contexte' : 'Recherche sémantique avancée'}</p>
                        </div>
                    </div>
                    <button class="modal-close text-slate-400 hover:text-white transition-colors p-2 hover:bg-slate-800 rounded-lg" data-action="close">
                        <i data-lucide="x" class="w-5 h-5"></i>
                    </button>
                </div>

                <!-- Body -->
                <div class="p-6 overflow-y-auto custom-scroll flex-1" id="${modalId}-body">
                    <!-- Contenu dynamique injecté ici -->
                    <div class="text-slate-500 text-center py-8">
                        <i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto mb-2"></i>
                        Chargement...
                    </div>
                </div>

                <!-- Footer -->
                <div class="flex items-center justify-between p-6 border-t border-slate-700/50">
                    <div class="text-sm text-slate-500">
                        ${type === 'compress' ? 'Compression avec rollback possible' : 'Recherche via embeddings vectoriels'}
                    </div>
                    <div class="flex items-center gap-3">
                        <button class="modal-cancel px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors font-medium" data-action="cancel">
                            Annuler
                        </button>
                        <button class="modal-confirm px-5 py-2 ${type === 'compress' ? 'bg-amber-600 hover:bg-amber-500' : 'bg-violet-600 hover:bg-violet-500'} text-white rounded-lg transition-colors font-medium flex items-center gap-2" data-action="confirm">
                            <i data-lucide="${type === 'compress' ? 'minimize-2' : 'search'}" class="w-4 h-4"></i>
                            ${type === 'compress' ? 'Lancer Compression' : 'Rechercher'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Setup des event listeners
    setupMemoryModalListeners(modalId, type);

    return {
        show: () => {
            const modal = document.getElementById(modalId);
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';

            // Animation d'entrée
            setTimeout(() => {
                const content = modal.querySelector('.glass-panel');
                content.classList.remove('scale-95', 'opacity-0');
                content.classList.add('scale-100', 'opacity-100');
            }, 10);

            // Lazy loading du contenu
            loadModalContent(type, `${modalId}-body`);
        },
        hide: () => {
            const modal = document.getElementById(modalId);
            const content = modal.querySelector('.glass-panel');

            // Animation de sortie
            content.classList.remove('scale-100', 'opacity-100');
            content.classList.add('scale-95', 'opacity-0');

            setTimeout(() => {
                modal.style.display = 'none';
                document.body.style.overflow = '';
            }, 200);

            cleanupModalResources(modalId);
        }
    };
}

/**
 * Charge le contenu dynamique d'une modale mémoire
 * @param {string} type - Type de modal
 * @param {string} containerId - ID du conteneur
 */
async function loadModalContent(type, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        const template = type === 'compress' ? getCompressionModalTemplate() : getSimilarityModalTemplate();
        container.innerHTML = template;

        // Initialiser les composants après le rendu
        await nextTick();

        if (type === 'similarity') {
            preloadMemoryOptions();
        }

        // Recréer les icônes Lucide
        if (window.lucide) {
            lucide.createIcons();
        }

    } catch (error) {
        console.error(`Erreur chargement modal ${type}:`, error);
        // Affiche le message d'erreur de manière sécurisée (sans innerHTML)
        container.textContent = ''; // Clear existing content

        const errorDiv = document.createElement('div');
        errorDiv.className = 'text-red-400 text-center py-4';

        const errorIcon = document.createElement('i');
        errorIcon.setAttribute('data-lucide', 'alert-circle');
        errorIcon.className = 'w-5 h-5 mx-auto mb-2';

        const errorText = document.createElement('p');
        errorText.textContent = 'Erreur lors du chargement';

        errorDiv.appendChild(errorIcon);
        errorDiv.appendChild(errorText);
        container.appendChild(errorDiv);

        if (window.lucide) {
            window.lucide.createIcons();
        }
    }
}

/**
 * Template HTML pour la modal de compression
 */
function getCompressionModalTemplate() {
    return `
        <div class="compress-options space-y-6">
            <!-- Stratégie de compression -->
            <section class="option-group">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="settings" class="w-5 h-5 text-amber-400"></i>
                    Stratégie de Compression
                </h4>
                <div class="space-y-3">
                    <label class="flex items-center gap-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-amber-500/30 transition-colors cursor-pointer">
                        <input type="radio" name="compress-strategy" value="token" checked class="text-amber-500 focus:ring-amber-500">
                        <div class="flex-1">
                            <span class="text-white font-medium">Par token count</span>
                            <p class="text-slate-400 text-sm">Consolider les petites mémoires</p>
                        </div>
                    </label>
                    <label class="flex items-center gap-3 p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 hover:border-amber-500/30 transition-colors cursor-pointer">
                        <input type="radio" name="compress-strategy" value="semantic" class="text-amber-500 focus:ring-amber-500">
                        <div class="flex-1">
                            <span class="text-white font-medium">Par similarité sémantique</span>
                            <p class="text-slate-400 text-sm">Regrouper conceptuellement</p>
                        </div>
                    </label>
                </div>
            </section>

            <!-- Seuil de compression -->
            <section class="option-group">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="sliders" class="w-5 h-5 text-amber-400"></i>
                    Seuil de Compression
                </h4>
                <div class="space-y-3">
                    <div class="flex items-center gap-4">
                        <input type="range" id="compress-threshold" min="0.1" max="0.9" step="0.1" value="0.3"
                               class="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer">
                        <span id="threshold-value" class="text-amber-400 font-bold min-w-[3rem] text-right">30%</span>
                    </div>
                    <p class="text-slate-500 text-sm">Plus le seuil est bas, plus la compression est agressive</p>
                </div>
            </section>

            <!-- Aperçu impact -->
            <section class="option-group">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="bar-chart-3" class="w-5 h-5 text-amber-400"></i>
                    Aperçu Impact
                </h4>
                <div class="grid grid-cols-3 gap-4">
                    <div class="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <p class="text-slate-500 text-sm mb-1">Mémoires actuelles</p>
                        <p id="current-count" class="text-2xl font-bold text-white">--</p>
                    </div>
                    <div class="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <p class="text-slate-500 text-sm mb-1">Après compression</p>
                        <p id="projected-count" class="text-2xl font-bold text-amber-400">--</p>
                    </div>
                    <div class="text-center p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <p class="text-slate-500 text-sm mb-1">Espace gagné</p>
                        <p id="space-saved" class="text-2xl font-bold text-green-400">--</p>
                    </div>
                </div>
            </section>

            <!-- Prévisualisation -->
            <section class="option-group">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="eye" class="w-5 h-5 text-amber-400"></i>
                    Prévisualisation
                </h4>
                <div id="compression-preview" class="preview-content space-y-2 max-h-60 overflow-y-auto custom-scroll">
                    <div class="text-slate-500 text-center py-4">
                        <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                        Analyse des mémoires...
                    </div>
                </div>
            </section>
        </div>
    `;
}

/**
 * Template HTML pour la modal de similarité
 */
function getSimilarityModalTemplate() {
    return `
        <div class="similarity-search space-y-6">
            <!-- Mémoire de référence -->
            <section class="search-input">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="target" class="w-5 h-5 text-violet-400"></i>
                    Mémoire de Référence
                </h4>
                <div class="space-y-3">
                    <select id="reference-memory-select" class="w-full px-4 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-violet-500 transition-colors">
                        <option value="">Sélectionner une mémoire...</option>
                        <!-- Populé dynamiquement -->
                    </select>
                    <div class="relative">
                        <textarea id="reference-text" placeholder="Ou coller texte à comparer..."
                                  class="glass-panel max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto bg-slate-900/95 backdrop-blur-xl border border-slate-700/50 rounded-2xl shadow-2xl scale-95 transition-all duration-300 ease-out" 
                                  rows="4"></textarea>
                    </div>
                </div>
            </section>

            <!-- Paramètres de recherche -->
            <section class="search-options">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="settings-2" class="w-5 h-5 text-violet-400"></i>
                    Paramètres de Recherche
                </h4>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Méthode</label>
                        <select id="similarity-method" class="w-full px-3 py-2 bg-slate-800/80 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500 transition-colors">
                            <option value="cosine">Similarité Cosinus</option>
                            <option value="jaccard">Coefficient Jaccard</option>
                            <option value="levenshtein">Distance Levenshtein</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Seuil minimum</label>
                        <div class="flex items-center gap-2">
                            <input type="range" id="similarity-threshold" min="0.5" max="1.0" step="0.05" value="0.75"
                                   class="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer">
                            <span id="similarity-value" class="text-violet-400 font-bold min-w-[3rem] text-right">75%</span>
                        </div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-300 mb-2">Max résultats</label>
                        <input type="number" id="max-results" min="5" max="100" value="20"
                               class="w-full px-3 py-2 bg-slate-800/80 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-violet-500 transition-colors">
                    </div>
                </div>
            </section>

            <!-- Résultats -->
            <section class="results-container">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="list" class="w-5 h-5 text-violet-400"></i>
                    Résultats de Similarité
                </h4>
                <div id="similarity-results" class="results-list space-y-2 max-h-60 overflow-y-auto custom-scroll">
                    <div class="text-slate-500 text-center py-8">
                        <i data-lucide="search" class="w-8 h-8 mx-auto mb-2 opacity-30"></i>
                        <p>Sélectionnez une référence ou collez du texte</p>
                    </div>
                </div>
            </section>

            <!-- Visualisation -->
            <section class="visualization-panel">
                <h4 class="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <i data-lucide="scatter-chart" class="w-5 h-5 text-violet-400"></i>
                    Carte de Similarité
                </h4>
                <div class="bg-slate-800/50 rounded-lg p-4 border border-slate-700/50">
                    <canvas id="similarity-chart" width="400" height="300" class="w-full"></canvas>
                </div>
            </section>
        </div>
    `;
}

/**
 * Configure les listeners pour une modale mémoire
 * @param {string} modalId - ID de la modale
 * @param {string} type - Type de modal
 */
function setupMemoryModalListeners(modalId, type) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    // Fermeture au clic extérieur
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            hideMemoryModal(type);
        }
    });

    // Actions des boutons
    modal.addEventListener('click', (e) => {
        const action = e.target.closest('[data-action]')?.dataset.action;

        switch (action) {
            case 'close':
            case 'cancel':
                hideMemoryModal(type);
                break;
            case 'confirm':
                executeMemoryAction(type);
                break;
        }
    });

    // Listeners spécifiques au type
    if (type === 'compress') {
        setupCompressionListeners(modalId);
    } else if (type === 'similarity') {
        setupSimilarityListeners(modalId);
    }
}

/**
 * Configure les listeners pour la compression
 */
function setupCompressionListeners(modalId) {
    const modal = document.getElementById(modalId);

    // Mise à jour du seuil
    const thresholdSlider = modal.querySelector('#compress-threshold');
    const thresholdValue = modal.querySelector('#threshold-value');

    if (thresholdSlider && thresholdValue) {
        thresholdSlider.addEventListener('input', (e) => {
            const value = Math.round(e.target.value * 100);
            thresholdValue.textContent = `${value}%`;
            updateCompressionPreview();
        });
    }

    // Changement de stratégie
    const strategyRadios = modal.querySelectorAll('input[name="compress-strategy"]');
    strategyRadios.forEach(radio => {
        radio.addEventListener('change', updateCompressionPreview);
    });
}

/**
 * Configure les listeners pour la similarité
 */
function setupSimilarityListeners(modalId) {
    const modal = document.getElementById(modalId);

    // Mise à jour du seuil
    const thresholdSlider = modal.querySelector('#similarity-threshold');
    const similarityValue = modal.querySelector('#similarity-value');

    if (thresholdSlider && similarityValue) {
        thresholdSlider.addEventListener('input', (e) => {
            const value = Math.round(e.target.value * 100);
            similarityValue.textContent = `${value}%`;
        });
    }

    // Recherche automatique
    const referenceSelect = modal.querySelector('#reference-memory-select');
    const referenceText = modal.querySelector('#reference-text');

    const triggerSearch = () => {
        const hasContent = referenceSelect.value || referenceText.value.trim();
        if (hasContent) {
            executeSimilaritySearch();
        }
    };

    if (referenceSelect) referenceSelect.addEventListener('change', triggerSearch);
    if (referenceText) referenceText.addEventListener('input', throttle(triggerSearch, 1000));
}

/**
 * Affiche une modale mémoire
 * @param {string} type - Type de modal
 */
export function showMemoryModal(type) {
    console.log(`🧠 showMemoryModal appelé avec type: ${type}`);
    
    if (!window.memoryModals) {
        window.memoryModals = {};
    }
    
    if (!window.memoryModals[type]) {
        window.memoryModals[type] = createMemoryModal(type);
    }
    
    window.memoryModals[type].show();
}

/**
 * Cache une modale mémoire
 * @param {string} type - Type de modal
 */
export function hideMemoryModal(type) {
    if (window.memoryModals?.[type]) {
        window.memoryModals[type].hide();
    }
}

/**
 * Exécute l'action mémoire
 * @param {string} type - Type d'action
 */
async function executeMemoryAction(type) {
    if (type === 'compress') {
        await executeCompression();
    } else if (type === 'similarity') {
        await executeSimilaritySearch();
    }
}

/**
 * Nettoie les ressources d'une modale
 * @param {string} modalId - ID de la modale
 */
function cleanupModalResources(modalId) {
    // Détruire les graphiques Chart.js
    const chartCanvas = document.querySelector(`#${modalId} canvas`);
    if (chartCanvas && window.similarityChartInstance) {
        window.similarityChartInstance.destroy();
        window.similarityChartInstance = null;
    }

    // Nettoyer les timeouts
    if (window.compressionTimeout) {
        clearTimeout(window.compressionTimeout);
        window.compressionTimeout = null;
    }
}

/**
 * Helper pour nextTick
 */
function nextTick() {
    return new Promise(resolve => requestAnimationFrame(resolve));
}

/**
 * Précharge les options de mémoire
 */
async function preloadMemoryOptions() {
    // TODO: Implémenter le chargement des mémoires depuis l'API
    const select = document.getElementById('reference-memory-select');
    if (!select) return;

    try {
        const response = await fetch('/api/memory/frequent');
        const data = await response.json();
        
        let memories;
        if (Array.isArray(data)) {
            memories = data;
        } else if (data && Array.isArray(data.memories)) {
            memories = data.memories;
        } else {
            console.warn('API /api/memory/frequent returned unexpected format:', data);
            memories = [];
        }

        if (Array.isArray(memories)) {
            memories.forEach(memory => {
                const option = document.createElement('option');
                option.value = memory.id;
                option.textContent = memory.title;
                select.appendChild(option);
            });
        } else {
            console.warn('Memories data is not an array:', memories);
        }
    } catch (error) {
        console.error('Erreur chargement mémoires:', error);
    }
}

/**
 * Mise à jour de l'aperçu de compression
 */
async function updateCompressionPreview() {
    const modal = document.querySelector('[id^="memory-compress-modal"]');
    if (!modal) return;

    const strategy = modal.querySelector('input[name="compress-strategy"]:checked')?.value || 'token';
    const threshold = parseFloat(modal.querySelector('#compress-threshold')?.value || 0.3);

    const previewContainer = modal.querySelector('#compression-preview');
    const currentCountEl = modal.querySelector('#current-count');
    const projectedCountEl = modal.querySelector('#projected-count');
    const spaceSavedEl = modal.querySelector('#space-saved');

    try {
        previewContainer.innerHTML = `
            <div class="text-slate-500 text-center py-4">
                <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                Analyse des mémoires...
            </div>
        `;

        if (window.lucide) lucide.createIcons();

        const result = await memoryCompressionService.previewCompression(strategy, threshold);

        // Mettre à jour les stats
        if (currentCountEl) currentCountEl.textContent = result.current_count || '--';
        if (projectedCountEl) projectedCountEl.textContent = result.projected_count || '--';
        if (spaceSavedEl) spaceSavedEl.textContent = result.space_saved || '--';

        // Afficher la prévisualisation
        if (result.preview && result.preview.length > 0) {
            previewContainer.innerHTML = result.preview.map(item => `
                <div class="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 mb-2">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                            ${item.action || 'fusionner'}
                        </span>
                        <span class="text-xs text-slate-500">${item.tokens || '--'} tokens</span>
                    </div>
                    <p class="text-sm text-slate-300 truncate">${item.preview || 'Aperçu non disponible'}</p>
                </div>
            `).join('');
        } else {
            previewContainer.innerHTML = `
                <div class="text-slate-500 text-center py-4">
                    <i data-lucide="info" class="w-5 h-5 mx-auto mb-2"></i>
                    Aucune compression nécessaire avec ces paramètres
                </div>
            `;
        }

        if (window.lucide) lucide.createIcons();

    } catch (error) {
        handleMemoryError(error, 'preview compression');
        previewContainer.innerHTML = `
            <div class="text-red-400 text-center py-4">
                <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-2"></i>
                Erreur lors de l'analyse
            </div>
        `;
    }
}

/**
 * Exécute la compression
 */
async function executeCompression() {
    const modal = document.querySelector('[id^="memory-compress-modal"]');
    if (!modal) return;

    const strategy = modal.querySelector('input[name="compress-strategy"]:checked')?.value || 'token';
    const threshold = parseFloat(modal.querySelector('#compress-threshold')?.value || 0.3);
    const confirmBtn = modal.querySelector('.modal-confirm');

    try {
        confirmBtn.disabled = true;
        // Met à jour le texte du bouton de manière sécurisée (sans innerHTML)
        confirmBtn.textContent = 'Compression...';
        // Ajouter l'icône de chargement séparément
        const existingIcon = confirmBtn.querySelector('i');
        if (existingIcon) existingIcon.remove();
        const loadingIcon = document.createElement('i');
        loadingIcon.setAttribute('data-lucide', 'loader-2');
        loadingIcon.className = 'w-4 h-4 animate-spin';
        confirmBtn.prepend(loadingIcon);

        if (window.lucide) lucide.createIcons();

        const result = await memoryCompressionService.executeCompression(strategy, threshold, false);

        if (result.success) {
            showNotification(`Compression réussie: ${result.space_saved} économisés`, 'success');

            // Mettre à jour l'UI
            const stats = {
                total_memories: result.projected_count,
                compression_ratio: result.compression_ratio ? (result.compression_ratio * 100).toFixed(1) + '%' : '--'
            };

            updateMemoryStats(stats);
            hideMemoryModal('compress');
        } else {
            throw new Error(result.error || 'Échec de la compression');
        }

    } catch (error) {
        handleMemoryError(error, 'exécution compression');
    } finally {
        confirmBtn.disabled = false;
        // Met à jour le texte du bouton de manière sécurisée (sans innerHTML)
        confirmBtn.textContent = 'Lancer Compression';
        // Ajouter l'icône séparément
        const existingIcon = confirmBtn.querySelector('i');
        if (existingIcon) existingIcon.remove();
        const compressIcon = document.createElement('i');
        compressIcon.setAttribute('data-lucide', 'minimize-2');
        compressIcon.className = 'w-4 h-4';
        confirmBtn.prepend(compressIcon);

        if (window.lucide) lucide.createIcons();
    }
}

/**
 * Exécute la recherche de similarité
 */
async function executeSimilaritySearch() {
    const modal = document.querySelector('[id^="memory-similarity-modal"]');
    if (!modal) return;

    const referenceSelect = modal.querySelector('#reference-memory-select');
    const referenceText = modal.querySelector('#reference-text');
    const method = modal.querySelector('#similarity-method')?.value || 'cosine';
    const threshold = parseFloat(modal.querySelector('#similarity-threshold')?.value || 0.75);
    const limit = parseInt(modal.querySelector('#max-results')?.value || 20);

    const referenceId = referenceSelect?.value;
    const refText = referenceText?.value.trim();

    if (!referenceId && !refText) {
        showNotification('Veuillez sélectionner une mémoire ou coller du texte', 'error');
        return;
    }

    const resultsContainer = modal.querySelector('#similarity-results');
    const confirmBtn = modal.querySelector('.modal-confirm');

    try {
        confirmBtn.disabled = true;
        // Met à jour le texte du bouton de manière sécurisée (sans innerHTML)
        confirmBtn.textContent = 'Recherche...';
        // Ajouter l'icône de chargement séparément
        const existingIcon = confirmBtn.querySelector('i');
        if (existingIcon) existingIcon.remove();
        const loadingIcon = document.createElement('i');
        loadingIcon.setAttribute('data-lucide', 'loader-2');
        loadingIcon.className = 'w-4 h-4 animate-spin';
        confirmBtn.prepend(loadingIcon);

        if (window.lucide) lucide.createIcons();

        resultsContainer.innerHTML = `
            <div class="text-slate-500 text-center py-4">
                <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2"></i>
                Recherche en cours...
            </div>
        `;

        const result = await similarityService.findSimilarMemories(
            referenceId,
            refText,
            method,
            threshold,
            limit
        );

        if (result.success && result.results.length > 0) {
            // Afficher les résultats
            resultsContainer.innerHTML = result.results.map(mem => `
                <div class="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50 mb-2 hover:border-violet-500/30 transition-colors">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-xs px-2 py-0.5 rounded ${getScoreColorClass(mem.similarity_score)}">
                            Score: ${(mem.similarity_score * 100).toFixed(1)}%
                        </span>
                        <span class="text-xs text-slate-500">${mem.type}</span>
                    </div>
                    <h5 class="text-white font-medium mb-1">${mem.title}</h5>
                    <p class="text-sm text-slate-300">${mem.content_preview}</p>
                    <div class="flex items-center gap-2 mt-2 text-xs text-slate-500">
                        <span>${mem.tokens} tokens</span>
                        <span>•</span>
                        <span>${new Date(mem.created_at).toLocaleDateString('fr-FR')}</span>
                    </div>
                </div>
            `).join('');

            // Créer le graphique de similarité
            const chartCanvas = modal.querySelector('#similarity-chart');
            if (chartCanvas) {
                renderSimilarityChart('similarity-chart', result.results);
            }

        } else {
            resultsContainer.innerHTML = `
                <div class="text-slate-500 text-center py-8">
                    <i data-lucide="search" class="w-8 h-8 mx-auto mb-2 opacity-30"></i>
                    <p>Aucun résultat trouvé pour ces critères</p>
                </div>
            `;
        }

        if (window.lucide) lucide.createIcons();

    } catch (error) {
        handleMemoryError(error, 'recherche similarité');
        resultsContainer.innerHTML = `
            <div class="text-red-400 text-center py-4">
                <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-2"></i>
                Erreur lors de la recherche
            </div>
        `;
    } finally {
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '<i data-lucide="search" class="w-4 h-4"></i> Rechercher';

        if (window.lucide) lucide.createIcons();
    }
}

/**
 * Détermine la classe CSS selon le score
 */
function getScoreColorClass(score) {
    if (score >= 0.9) return 'bg-green-500/20 text-green-400';
    if (score >= 0.8) return 'bg-blue-500/20 text-blue-400';
    if (score >= 0.7) return 'bg-yellow-500/20 text-yellow-400';
    return 'bg-red-500/20 text-red-400';
}

/**
 * Met à jour les statistiques mémoire
 */
function updateMemoryStats(stats) {
    const totalMemoriesEl = document.getElementById('total-memories');
    const compressionRatioEl = document.getElementById('compression-ratio');

    if (totalMemoriesEl && stats.total_memories !== undefined) {
        totalMemoriesEl.textContent = stats.total_memories;
    }

    if (compressionRatioEl && stats.compression_ratio !== undefined) {
        compressionRatioEl.textContent = stats.compression_ratio;
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

    // Intègre ModalManager pour gestion du focus
    const modalManager = getModalManager();
    modalManager.open(modal);

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

    // Intègre ModalManager pour restauration du focus
    const modalManager = getModalManager();
    modalManager.close(modal);

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

    // Intègre ModalManager pour gestion du focus
    const modalManager = getModalManager();
    modalManager.open(modal);
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

    // Expose showMemoryModal globalement pour les boutons HTML
    window.showMemoryModal = showMemoryModal;
}

/**
 * Alias pour compatibilité
 */
export function createNewSession() {
    showNewSessionModal();
}