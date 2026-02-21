/**
 * ui.js - Manipulations DOM et mise à jour de l'interface
 * 
 * Pourquoi : Sépare toute la logique d'affichage du reste de l'application
 * pour faciliter les changements de design et améliorer les performances.
 */

import { 
    escapeHtml, 
    formatTokens, 
    formatPercentage,
    getProviderColor,
    getColorForPercentage,
    eventBus 
} from './utils.js';
import { updateGauge, updateHistoryChart } from './charts.js';
import { 
    getSessionMetrics, 
    getCurrentMaxContext,
    getCurrentMemoryMetrics,
    calculateStats,
    calculateAccuracy,
    mergeDataSources,
    getCurrentSessionId
} from './sessions.js';
import { showMemoryModal } from './modals.js';

// ============================================================================
// UIMANAGER CLASS - Gestion centralisée des boutons UI
// ============================================================================

/**
 * UIManager - Classe principale pour gérer l'état des boutons UI
 * Pourquoi : Centralise la logique de gestion d'état des boutons selon les capacités des sessions
 */
export class UIManager {
    constructor() {
        this.buttonStates = new Map();
        this.sessionCapabilities = new Map();
    }

    /**
     * Met à jour l'état de tous les boutons selon la session active
     * @param {Object} session - Données de session
     */
    updateButtonStates(session) {
        console.log(`🔄 [UIManager] Mise à jour boutons pour session: ${session.id}`);

        const buttons = {
            'compaction-btn': this.isCompactionSupported(session),
            'warning-btn': this.isWarningSupported(session),
            'export-btn': true, // Toujours supporté
            'delete-btn': this.isDeleteSupported(session)
        };

        // Met à jour chaque bouton
        for (const [buttonId, isEnabled] of Object.entries(buttons)) {
            const button = document.getElementById(buttonId);
            if (button) {
                this.setButtonState(button, isEnabled, buttonId);
            }
        }

        // Met à jour le cache des états
        this.buttonStates.set(session.id, buttons);
    }

    /**
     * Définit l'état d'un bouton (activé/désactivé)
     * @param {HTMLElement} button - Élément bouton
     * @param {boolean} isEnabled - État activé
     * @param {string} buttonId - ID du bouton pour tooltips
     */
    setButtonState(button, isEnabled, buttonId) {
        const wasEnabled = !button.disabled;

        button.disabled = !isEnabled;
        button.classList.toggle('disabled', !isEnabled);
        button.setAttribute('aria-disabled', !isEnabled);

        // Met à jour le tooltip si nécessaire
        if (!isEnabled) {
            const tooltip = button.querySelector('.tooltip') || button;
            if (tooltip) {
                tooltip.title = this.getDisabledTooltip(buttonId);
            }
        }

        // Log si l'état a changé
        if (wasEnabled !== isEnabled) {
            console.log(`🔄 [UIManager] Bouton ${buttonId}: ${wasEnabled ? 'activé' : 'désactivé'} → ${isEnabled ? 'activé' : 'désactivé'}`);
        }
    }

    /**
     * Vérifie si la compaction est supportée pour cette session
     * @param {Object} session - Données de session
     * @returns {boolean} True si supporté
     */
    isCompactionSupported(session) {
        if (!session?.model) return false;

        // Extraction du provider
        const provider = this.extractProvider(session.model);

        // Providers qui ne supportent pas la compaction
        const unsupportedProviders = ['nvidia', 'mistral'];
        if (unsupportedProviders.includes(provider)) {
            return false;
        }

        // Vérifications supplémentaires selon le modèle
        const model = session.model.toLowerCase();

        // Certains modèles spécifiques
        if (model.includes('kimi-code-2.5')) {
            return false; // Version expérimentale
        }

        return true;
    }

    /**
     * Vérifie si les avertissements de contexte sont supportés
     * @param {Object} session - Données de session
     * @returns {boolean} True si supporté
     */
    isWarningSupported(session) {
        if (!session?.total_tokens) return false;

        // Seulement si le contexte est volumineux (>10k tokens)
        const hasLargeContext = session.total_tokens > 10000;

        // Certains providers ont des limites spécifiques
        const provider = this.extractProvider(session.model);
        const warningSupportedProviders = ['openai', 'anthropic', 'google'];

        return hasLargeContext && warningSupportedProviders.includes(provider);
    }

    /**
     * Vérifie si la suppression est supportée
     * @param {Object} session - Données de session
     * @returns {boolean} True si supporté
     */
    isDeleteSupported(session) {
        // La suppression est généralement toujours supportée
        // Mais pourrait être désactivée pour certaines sessions système
        return session?.id && !session?.is_system;
    }

    /**
     * Extrait le provider depuis le nom du modèle
     * @param {string} model - Nom du modèle
     * @returns {string} Provider extrait
     */
    extractProvider(model) {
        if (!model) return 'unknown';

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

        for (const [prefix, provider] of Object.entries(modelMappings)) {
            if (model.toLowerCase().startsWith(prefix)) {
                return provider;
            }
        }

        const parts = model.split('-');
        return parts.length > 1 ? parts[0].toLowerCase() : 'unknown';
    }

    /**
     * Récupère le tooltip pour un bouton désactivé
     * @param {string} buttonId - ID du bouton
     * @returns {string} Texte du tooltip
     */
    getDisabledTooltip(buttonId) {
        const tooltips = {
            'compaction-btn': 'Compaction non supportée pour ce modèle/provider',
            'warning-btn': 'Avertissements nécessitent un contexte volumineux (>10k tokens) et un provider compatible',
            'delete-btn': 'Suppression non autorisée pour cette session',
            'export-btn': 'Export toujours disponible'
        };

        return tooltips[buttonId] || 'Fonctionnalité non disponible';
    }

    /**
     * Récupère l'état des boutons pour une session
     * @param {string} sessionId - ID de session
     * @returns {Object} États des boutons
     */
    getButtonStates(sessionId) {
        return this.buttonStates.get(sessionId) || {};
    }

    /**
     * Réinitialise les états pour une nouvelle session
     * @param {string} sessionId - ID de session
     */
    resetButtonStates(sessionId) {
        this.buttonStates.delete(sessionId);
    }

    /**
     * Met à jour les capacités connues pour un provider
     * @param {string} provider - Nom du provider
     * @param {Object} capabilities - Capacités du provider
     */
    updateProviderCapabilities(provider, capabilities) {
        this.sessionCapabilities.set(provider, capabilities);
    }
}

// ============================================================================
// INSTANCE GLOBALE (pour compatibilité)
// ============================================================================

let uiManagerInstance = null;

/**
 * Récupère l'instance globale du UIManager
 * @returns {UIManager}
 */
export function getUIManager() {
    if (!uiManagerInstance) {
        uiManagerInstance = new UIManager();
    }
    return uiManagerInstance;
}

// ============================================================================
// CACHE DES ÉLÉMENTS DOM
// ============================================================================

const elements = {};

/**
 * Initialise le cache des éléments fréquemment utilisés
 * Pourquoi : Évite les requêtes DOM répétées qui impactent les performances
 */
export function initElements() {
    const ids = [
        'gaugeChart', 'historyChart', 'compactionChart',
        'session-name', 'session-badge', 'session-date', 'session-provider',
        'max-context-display', 'current-tokens', 'percentage-text',
        'progress-bar', 'progress-percent',
        'total-requests', 'max-tokens', 'avg-tokens',
        'prompt-tokens', 'completion-tokens',
        'last-estimated', 'last-real', 'accuracy-text',
        'logs-container', 'alert-container', 'alert-badge',
        'source-indicator-container', 'source-badge', 'gauge-source-indicator',
        'ws-status-dot', 'ws-status-text',
        'memory-indicator', 'memory-ratio', 'memory-bar',
        'memory-tokens', 'chat-tokens',
        'usage-bar', 'reserved-zone', 'compaction-threshold-marker',
        'usage-percentage-text',
        'autoCompactToggle', 'autoCompactText',
        'compactBtn', 'compactBtnText',
        'compaction-history-card', 'total-saved-badge',
        'compaction-count', 'compaction-avg-ratio', 'last-compaction-time'
    ];
    
    ids.forEach(id => {
        elements[id] = document.getElementById(id);
    });
}

/**
 * Récupère un élément du cache
 * @param {string} id - ID de l'élément
 * @returns {HTMLElement|null}
 */
export function getElement(id) {
    return elements[id] || document.getElementById(id);
}

// ============================================================================
// MISE À JOUR PRINCIPALE
// ============================================================================

/**
 * Met à jour l'affichage principal des tokens
 * Pourquoi : Point central de mise à jour de l'UI après réception de données
 * @param {number} tokens - Nombre de tokens courants
 * @param {number} percentage - Pourcentage d'usage
 * @param {number} cumulativeTokens - Tokens cumulés (optionnel)
 */
export function updateDisplay(tokens, percentage, cumulativeTokens = null) {
    const displayTokens = cumulativeTokens !== null ? cumulativeTokens : tokens;
    
    const currentTokensEl = getElement('current-tokens');
    const percentageTextEl = getElement('percentage-text');
    
    if (currentTokensEl) {
        currentTokensEl.textContent = formatTokens(displayTokens);
    }
    
    if (percentageTextEl) {
        percentageTextEl.textContent = `${percentage.toFixed(2)}% utilisé`;
    }
    
    updateGauge(percentage);
    updateProgressBar(percentage);
}

function updateProgressBar(percentage) {
    const progressBar = getElement('progress-bar');
    const progressPercent = getElement('progress-percent');
    
    if (progressBar) {
        progressBar.style.width = `${Math.min(percentage, 100)}%`;
    }
    
    if (progressPercent) {
        progressPercent.textContent = `${percentage.toFixed(1)}%`;
    }
}

// ============================================================================
// MISE À JOUR SESSION
// ============================================================================

/**
 * Met à jour l'affichage des informations de session
 * Pourquoi : Synchronise l'UI avec l'état courant de la session
 * @param {Object} data - Données de la session
 */
export function updateSessionDisplay(data) {
    if (!data.session) return;
    
    const session = data.session;
    const providerKey = session.provider || 'managed:kimi-code';
    const providerInfo = data.provider || {};
    const providerName = providerInfo.name || providerKey.replace('managed:', '').replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    
    // Nom et badge
    const nameEl = getElement('session-name');
    const badgeEl = getElement('session-badge');
    const dateEl = getElement('session-date');
    
    if (nameEl) nameEl.textContent = session.name;
    if (badgeEl) badgeEl.textContent = `#${session.id}`;
    if (dateEl) dateEl.textContent = new Date(session.created_at).toLocaleString('fr-FR');
    
    // Provider avec couleur
    const providerEl = getElement('session-provider');
    if (providerEl) {
        const color = getProviderColor(providerKey);
        providerEl.innerHTML = `
            <span class="w-2 h-2 rounded-full bg-${color}-500"></span>
            ${providerName}
        `;
    }
    
    // Modèle
    const modelEl = getElement('session-model');
    if (modelEl) {
        const modelName = session.model || '-';
        modelEl.textContent = modelName;
    }
    
    // Max context
    const maxContextEl = getElement('max-context-display');
    if (maxContextEl) {
        const maxContext = session.max_context || 262144;
        maxContextEl.textContent = `/ ${formatTokens(maxContext)}`;
    }
}

// ============================================================================
// MISE À JOUR STATISTIQUES
// ============================================================================

/**
 * Met à jour toutes les statistiques affichées
 * Pourquoi : Recalcule et affiche les KPIs après ajout de métriques
 */
export function updateStats() {
    const metrics = getSessionMetrics();
    const stats = calculateStats();
    
    // Stats principales
    const totalRequestsEl = getElement('total-requests');
    const maxTokensEl = getElement('max-tokens');
    const avgTokensEl = getElement('avg-tokens');
    const promptTokensEl = getElement('prompt-tokens');
    const completionTokensEl = getElement('completion-tokens');
    
    if (totalRequestsEl) totalRequestsEl.textContent = stats.totalRequests;
    if (maxTokensEl) maxTokensEl.textContent = formatTokens(stats.maxTokens);
    if (avgTokensEl) avgTokensEl.textContent = formatTokens(stats.avgTokens);
    if (promptTokensEl) promptTokensEl.textContent = formatTokens(stats.totalPrompt);
    if (completionTokensEl) completionTokensEl.textContent = formatTokens(stats.totalCompletion);
    
    // Graphique d'historique
    updateHistoryChart(metrics);
    
    // Précision
    updateAccuracyComparison();
}

/**
 * Met à jour la comparaison précision estimée vs réelle
 * Pourquoi : Affiche la qualité de l'estimation Tiktoken
 */
export function updateAccuracyComparison() {
    const accuracy = calculateAccuracy();
    
    const lastEstimatedEl = getElement('last-estimated');
    const lastRealEl = getElement('last-real');
    const accuracyTextEl = getElement('accuracy-text');
    
    if (!accuracy) {
        if (lastEstimatedEl) lastEstimatedEl.textContent = '-';
        if (lastRealEl) lastRealEl.textContent = '-';
        if (accuracyTextEl) accuracyTextEl.textContent = 'En attente de données réelles...';
        return;
    }
    
    if (lastEstimatedEl) lastEstimatedEl.textContent = formatTokens(accuracy.estimated);
    if (lastRealEl) lastRealEl.textContent = formatTokens(accuracy.real);
    
    if (accuracyTextEl) {
        accuracyTextEl.innerHTML = 
            `Précision: <span class="${accuracy.accuracyColor} font-bold">${accuracy.formattedAccuracy}%</span> (diff: ${accuracy.diffText})`;
    }
}

// ============================================================================
// GESTION DES LOGS
// ============================================================================

/**
 * Rend tous les logs dans le conteneur
 * Pourquoi : Initialisation ou rechargement complet de l'historique
 * @param {boolean} scroll - Scroll vers le bas après rendu
 */
export function renderLogs(scroll = false) {
    const container = getElement('logs-container');
    if (!container) return;
    
    const metrics = getSessionMetrics();
    
    container.innerHTML = '';
    
    if (metrics.length === 0) {
        container.innerHTML = '<div class="text-slate-500 text-center py-8">En attente de données...</div>';
        return;
    }
    
    metrics.forEach(metric => addLogEntry(metric, false));
    
    if (scroll) {
        scrollToBottom();
    }
}

/**
 * Ajoute une entrée de log au conteneur
 * Pourquoi : Affichage temps réel des nouvelles métriques
 * @param {Object} metric - Métrique à afficher
 * @param {boolean} scroll - Scroll vers le bas après ajout
 */
export function addLogEntry(metric, scroll = true) {
    const container = getElement('logs-container');
    if (!container) return;
    
    // Supprime le message "En attente de données..." si présent
    if (container.children.length === 1 && 
        container.children[0].classList.contains('text-center')) {
        container.innerHTML = '';
    }
    
    const entry = createLogEntryElement(metric);
    container.appendChild(entry);
    
    // Initialise les icônes Lucide sur le nouvel élément
    if (window.lucide) {
        lucide.createIcons({ nodes: [entry] });
    }
    
    // Limite le nombre d'entrées
    while (container.children.length > 50) {
        container.removeChild(container.firstChild);
    }
    
    if (scroll) {
        scrollToBottom();
    }
}

function createLogEntryElement(metric) {
    const entry = document.createElement('div');
    entry.className = 'log-entry flex items-start gap-3 p-3 rounded-lg bg-slate-800/30 border border-slate-700/30';
    
    // Détermine la source et les styles
    const source = metric.source || 'proxy';
    const isLogSource = source === 'logs';
    const isCompileChat = source === 'compile_chat';
    const isApiError = source === 'api_error';
    const isMcpMemory = source === 'mcp_memory';
    const isCompression = source === 'compression';
    const isAlert = source === 'alert';
    
    let iconColor = 'text-green-400';
    if (metric.percentage > 50) iconColor = 'text-yellow-400';
    if (metric.percentage > 80) iconColor = 'text-red-400';
    if (isApiError || isAlert) iconColor = 'text-red-500';
    if (isMcpMemory) iconColor = 'text-pink-400';
    if (isCompression) iconColor = 'text-red-400';
    
    const time = new Date(metric.timestamp).toLocaleTimeString('fr-FR');
    const preview = metric.content_preview || '...';
    
    // Badge selon la source
    let badgeInfo = getBadgeInfo(source, metric);
    
    // Icône selon la source
    let iconName = 'arrow-right-circle';
    if (isCompileChat) iconName = 'layers';
    else if (isApiError) iconName = 'alert-triangle';
    else if (isLogSource) iconName = 'file-text';
    else if (isMcpMemory) iconName = 'brain';
    else if (isCompression) iconName = 'minimize-2';
    else if (isAlert) iconName = 'alert-circle';
    
    // Calcule l'affichage des tokens avec delta si pertinent
    const totalTokens = metric.estimated_tokens || 0;
    const deltaTokens = metric.delta_tokens || 0;
    
    // Détermine si on montre le delta (quand il y a beaucoup d'historique)
    const showDelta = deltaTokens > 0 && deltaTokens < totalTokens * 0.8 && totalTokens > 1000;
    
    let tokensDisplay = `<span class="${iconColor}">${formatTokens(totalTokens)} tokens (${formatPercentage(metric.percentage)})</span>`;
    
    if (showDelta) {
        const historyTokens = totalTokens - deltaTokens;
        tokensDisplay = `
            <span class="${iconColor}">${formatTokens(totalTokens)} tokens</span>
            <span class="text-slate-500">(</span>
            <span class="text-green-400" title="Nouveau contenu">+${formatTokens(deltaTokens)}</span>
            <span class="text-slate-500">+</span>
            <span class="text-slate-400" title="Historique/contexte">${formatTokens(historyTokens)} hist.</span>
            <span class="text-slate-500">)</span>
        `;
    }
    
    // Détail des composants si disponible
    let componentsDetail = '';
    if (metric.tools_tokens > 0 || metric.system_message_tokens > 0) {
        const parts = [];
        if (metric.tools_tokens > 0) parts.push(`${formatTokens(metric.tools_tokens)} tools`);
        if (metric.system_message_tokens > 0) parts.push(`${formatTokens(metric.system_message_tokens)} system`);
        componentsDetail = `<span class="text-slate-500">(${parts.join(' + ')})</span>`;
    }
    
    // Ajoute les infos de breakdown si disponibles
    let breakdownDetail = '';
    if (metric.system_tokens > 0 || metric.history_tokens > 0) {
        const parts = [];
        if (metric.system_tokens > 0) parts.push(`${formatTokens(metric.system_tokens)} sys`);
        if (metric.history_tokens > 0) parts.push(`${formatTokens(metric.history_tokens)} hist`);
        breakdownDetail = `<span class="text-slate-600 text-[10px]">[${parts.join(' | ')}]</span>`;
    }
    
    entry.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 ${iconColor} mt-0.5 flex-shrink-0"></i>
        <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 text-xs text-slate-500 mb-1 flex-wrap">
                <span class="font-mono">${time}</span>
                ${tokensDisplay}
                ${componentsDetail}
                ${breakdownDetail}
                <span class="${badgeInfo.class}" title="${badgeInfo.title}">${badgeInfo.text}</span>
            </div>
            <p class="text-slate-300 truncate">${escapeHtml(preview)}</p>
        </div>
    `;
    
    return entry;
}

function getBadgeInfo(source, metric) {
    const isEstimated = metric.is_estimated !== false;
    
    // Détection automatique des patterns MCP/Memory
    // Si le type commence par 'mcp_' ou contient 'memory_', affiche 'MCP MEMORY' en violet
    if (source && (source.startsWith('mcp_') || source.includes('memory_'))) {
        return {
            class: 'source-indicator source-mcp text-[9px]',
            text: 'MCP MEMORY',
            title: 'Mémoire Long Terme MCP'
        };
    }
    
    switch (source) {
        case 'compile_chat':
            return {
                class: 'source-indicator source-logs text-[9px]',
                text: 'COMPILE',
                title: 'Bloc CompileChat (Continue)'
            };
        case 'api_error':
            return {
                class: 'bg-red-900/50 text-red-400 border border-red-700/50 px-1.5 py-0.5 rounded text-[10px]',
                text: 'ERROR',
                title: 'Erreur API (quota/limit)'
            };
        case 'logs':
            return {
                class: 'source-indicator source-logs text-[9px]',
                text: 'LOGS',
                title: 'Depuis les logs PyCharm'
            };
        case 'mcp_memory':
            return {
                class: 'source-indicator source-mcp text-[9px]',
                text: 'MCP',
                title: 'Mémoire Long Terme MCP'
            };
        case 'compression':
            return {
                class: 'source-indicator source-compression text-[9px]',
                text: 'COMPRESS',
                title: 'Compression de contexte'
            };
        case 'alert':
            return {
                class: 'bg-red-900/50 text-red-400 border border-red-700/50 px-1.5 py-0.5 rounded text-[10px]',
                text: 'ALERT',
                title: 'Alerte de seuil'
            };
        default:
            return {
                class: isEstimated 
                    ? 'bg-slate-700 text-slate-400 px-1.5 py-0.5 rounded text-[10px]' 
                    : 'bg-green-900/50 text-green-400 border border-green-700/50 px-1.5 py-0.5 rounded text-[10px]',
                text: isEstimated ? 'EST' : 'RÉEL',
                title: isEstimated ? 'Estimé' : 'Tokens réels'
            };
    }
}

function scrollToBottom() {
    const container = getElement('logs-container');
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

/**
 * Efface tous les logs
 * Pourquoi : Reset de l'affichage lors d'une nouvelle session
 */
export function clearLogs() {
    const container = getElement('logs-container');
    if (container) {
        container.innerHTML = '<div class="text-slate-500 text-center py-8">En attente de données...</div>';
    }
}

// ============================================================================
// INDICATEURS DE SOURCE
// ============================================================================

/**
 * Met à jour l'indicateur de source de données
 * Pourquoi : Informe l'utilisateur de la provenance des données affichées
 * @param {string} source - Type de source (proxy, logs, compile_chat, etc.)
 * @param {number} tokens - Nombre de tokens
 * @param {number} percentage - Pourcentage d'usage
 */
export function updateSourceIndicator(source, tokens, percentage) {
    const container = getElement('source-indicator-container');
    const badge = getElement('source-badge');
    const gaugeIndicator = getElement('gauge-source-indicator');
    
    if (container) container.classList.remove('hidden');
    if (gaugeIndicator) gaugeIndicator.classList.remove('hidden');
    
    // Détermine la classe CSS selon la source
    let cssSource = source;
    if (source === 'compile_chat' || source === 'api_error') {
        cssSource = 'logs';
    }
    
    // Met à jour les classes
    if (badge) {
        badge.className = `source-indicator source-${cssSource}`;
    }
    
    // Texte selon la source
    const sourceLabels = {
        'proxy': 'Proxy Live',
        'logs': 'Logs PyCharm',
        'compile_chat': 'CompileChat',
        'api_error': 'API Error',
        'hybrid': 'Hybride'
    };
    
    const label = sourceLabels[source] || source;
    
    if (badge) {
        badge.innerHTML = `
            <span class="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>
            ${label}
        `;
    }
    
    // Abréviation pour la jauge
    if (gaugeIndicator) {
        const gaugeLabels = {
            'proxy': 'PROXY',
            'logs': 'LOGS',
            'compile_chat': 'COMPILE',
            'api_error': 'ERROR',
            'hybrid': 'HYBRID'
        };
        gaugeIndicator.textContent = gaugeLabels[source] || 'LOGS';
    }
}

// ============================================================================
// ALERTES
// ============================================================================

/**
 * Met à jour l'affichage d'alerte
 * Pourquoi : Notification visuelle des seuils critiques atteints
 * @param {Object|null} alert - Données de l'alerte ou null pour masquer
 */
export function updateAlert(alert) {
    const container = getElement('alert-container');
    const badge = getElement('alert-badge');
    
    if (!container || !badge) return;
    
    if (!alert) {
        container.classList.add('hidden');
        return;
    }
    
    container.classList.remove('hidden');
    badge.textContent = alert.message;
    badge.className = `px-3 py-1.5 rounded-lg text-sm font-bold animate-pulse ${alert.bg || 'bg-red-500/20'} ${alert.text || 'text-red-400'}`;
    badge.style.border = `1px solid ${alert.color}`;
}

// ============================================================================
// MÉMOIRE MCP
// ============================================================================

/**
 * Met à jour l'affichage de la mémoire MCP
 * Pourquoi : Visualise l'utilisation de la mémoire long terme
 * @param {Object} memoryData - Données mémoire
 */
export function updateMemoryDisplay(memoryData) {
    const indicator = getElement('memory-indicator');
    const ratioEl = getElement('memory-ratio');
    const barEl = getElement('memory-bar');
    const memoryTokensEl = getElement('memory-tokens');
    const chatTokensEl = getElement('chat-tokens');
    
    if (!indicator) return;
    
    if (!memoryData || !memoryData.has_memory) {
        indicator.classList.add('hidden');
        return;
    }
    
    indicator.classList.remove('hidden');
    
    const ratio = memoryData.memory_ratio || 0;
    const memoryTokens = memoryData.memory_tokens || 0;
    const chatTokens = memoryData.chat_tokens || 0;
    
    if (ratioEl) ratioEl.textContent = `${ratio.toFixed(1)}%`;
    if (barEl) barEl.style.width = `${Math.min(ratio, 100)}%`;
    if (memoryTokensEl) memoryTokensEl.textContent = `${formatTokens(memoryTokens)} tokens mémoire`;
    if (chatTokensEl) chatTokensEl.textContent = `${formatTokens(chatTokens)} chat`;
    
    // Animation sur mise à jour
    indicator.classList.add('data-update');
    setTimeout(() => indicator.classList.remove('data-update'), 500);
}

// ============================================================================
// STATUT WEBSOCKET
// ============================================================================

/**
 * Met à jour l'indicateur de statut WebSocket
 * Pourquoi : Feedback visuel sur l'état de la connexion temps réel
 * @param {boolean} connected - État de la connexion
 */
export function updateConnectionStatus(connected) {
    const dot = getElement('ws-status-dot');
    const text = getElement('ws-status-text');
    
    if (!dot || !text) return;
    
    if (connected) {
        dot.classList.remove('bg-red-500');
        dot.classList.add('bg-green-500');
        text.classList.remove('status-disconnected');
        text.classList.add('status-connected');
        text.textContent = 'Connecté';
    } else {
        dot.classList.remove('bg-green-500');
        dot.classList.add('bg-red-500');
        text.classList.remove('status-connected');
        text.classList.add('status-disconnected');
        text.textContent = 'Déconnecté';
    }
}

// ============================================================================
// INITIALISATION DES LISTENERS
// ============================================================================

/**
 * Initialise les écouteurs d'événements pour l'UI
 * Pourquoi : Connecte le bus d'événements aux mises à jour d'interface
 */
export function initUIListeners() {
    // WebSocket
    eventBus.on('websocket:status', ({ connected }) => {
        updateConnectionStatus(connected);
    });
    
    // Sessions
    eventBus.on('session:loaded', (data) => {
        updateSessionDisplay(data);
        renderLogs();
        updateStats();
    });
    
    // Reset UI when auto-session creates a new session (model switch)
    eventBus.on('auto_session:created', (data) => {
        console.log('🔄 UI: Auto-session créée, reset de la jauge');
        clearLogs();
        updateDisplay(0, 0);
        updateStats();
    });
    
    eventBus.on('session:name_changed', ({ name }) => {
        const nameEl = getElement('session-name');
        if (nameEl) nameEl.textContent = name;
    });
    
    eventBus.on('session:name_update', ({ preview }) => {
        const nameEl = getElement('session-name');
        if (!nameEl) return;
        
        const currentName = nameEl.textContent;
        if (currentName.startsWith('Session') || currentName === 'Session par défaut') {
            const truncated = preview.length > 50 ? preview.substring(0, 50) + '...' : preview;
            nameEl.textContent = truncated;
        }
    });
    
    // Métriques
    eventBus.on('metric:added', (metric) => {
        addLogEntry(metric);
        updateStats();
    });
    
    // IMPORTANT: Met à jour le statut EST → RÉEL quand les vrais tokens arrivent
    eventBus.on('metric:updated', ({ metric, realTokens }) => {
        console.log(`✅ [METRIC UPDATE] ID ${metric.id}: EST → RÉEL (${realTokens.total} tokens)`);
        // Re-render les logs pour mettre à jour le badge EST/RÉEL
        renderLogs();
        updateStats();
        updateAccuracyComparison();
    });
    
    eventBus.on('metrics:loaded', () => {
        renderLogs();
    });
    
    eventBus.on('metrics:cleared', () => {
        clearLogs();
        updateDisplay(0, 0);
        updateStats();
    });
    
    // Sources de données
    eventBus.on('metric:received', () => {
        const merged = mergeDataSources();
        if (merged) {
            updateDisplay(merged.tokens, merged.percentage, merged.tokens);
            updateSourceIndicator(merged.source, merged.tokens, merged.percentage);
        }
    });
    
    eventBus.on('log:received', ({ metric, max_context }) => {
        const merged = mergeDataSources();
        if (merged) {
            updateDisplay(merged.tokens, merged.percentage, merged.tokens);
            updateSourceIndicator(merged.source, merged.tokens, merged.percentage);
        }
        
        // Met à jour max_context si fourni
        if (max_context && max_context > 0) {
            const maxContextEl = getElement('max-context-display');
            if (maxContextEl) {
                maxContextEl.textContent = `/ ${formatTokens(max_context)}`;
            }
        }
        
        addLogEntry(metric);
    });
    
    // Mémoire
    eventBus.on('memory:updated', (memoryData) => {
        updateMemoryDisplay(memoryData);
    });
    
    // Alertes
    eventBus.on('alert:received', (alert) => {
        updateAlert(alert);
    });
    
    // Affichage général
    eventBus.on('display:update', ({ tokens, percentage, cumulativeTokens }) => {
        updateDisplay(tokens, percentage, cumulativeTokens);
    });
    
    // Actions mémoire (boutons Similarité/Compresser)
    eventBus.on('memory:compress:show', () => {
        console.log('🧠 UI: Affichage modal compression mémoire');
        showMemoryModal('compress');
    });
    
    eventBus.on('memory:similarity:show', () => {
        console.log('🧠 UI: Affichage modal similarité mémoire');
        showMemoryModal('similarity');
    });
}
