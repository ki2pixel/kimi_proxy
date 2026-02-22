/**
 * Module MCP - Gestion des serveurs MCP Phase 3 et Phase 4
 * 
 * Fonctionnalités:
 * - Phase 3: Serveurs mémoire externe (Qdrant, Context Compression)
 * - Phase 4: Outils avancés (Shrimp Task Manager:14, Sequential Thinking:1, Fast Filesystem:25, JSON Query:3)
 * - Recherche sémantique, compression, mémoires fréquentes
 * 
 * Pourquoi Phase 3+4: Visibilité complète du système MCP (6 serveurs, 43 outils)
 */

import { eventBus, throttle } from './utils.js';
import { apiRequest } from './api.js';

// ============================================================================
// État local
// ============================================================================

let mcpState = {
    servers: [],           // Tous les serveurs (Phase 3 + Phase 4)
    phase3Servers: [],     // Phase 3: Qdrant, Context Compression
    phase4Servers: [],     // Phase 4: Shrimp Task Manager, Sequential Thinking, Fast Filesystem, JSON Query
    allConnected: false,
    connectedCount: 0,
    totalCount: 0,
    lastCheck: null,
    memoryStats: null,
    frequentMemories: [],
    isLoading: false
};

// ============================================================================
// API MCP
// ============================================================================

/**
 * Récupère les statuts des serveurs MCP (Phase 3 + Phase 4)
 * 
 * Pourquoi all-servers: Visibilité complète du système MCP (6 serveurs, 43 outils)
 */
async function fetchServerStatuses() {
    try {
        const response = await apiRequest('/api/memory/all-servers');
        // Fusionne Phase 3 et Phase 4 pour compatibilité ascendante
        mcpState.servers = response.all || [];
        mcpState.phase3Servers = response.phase3 || [];
        mcpState.phase4Servers = response.phase4 || [];
        mcpState.allConnected = response.all_connected || false;
        mcpState.connectedCount = response.connected_count || 0;
        mcpState.totalCount = response.total_count || 0;
        mcpState.lastCheck = response.timestamp;
        
        eventBus.emit('mcp:statusUpdate', mcpState);
        return mcpState;
    } catch (error) {
        console.error('❌ Erreur récupération statuts MCP:', error);
        // Fallback sur l'ancien endpoint si all-servers échoue
        try {
            const response = await apiRequest('/api/memory/servers');
            mcpState.servers = response.servers || [];
            mcpState.phase3Servers = response.servers || [];
            mcpState.phase4Servers = [];
            mcpState.allConnected = response.all_connected || false;
            mcpState.connectedCount = mcpState.servers.filter(s => s.connected).length;
            mcpState.totalCount = mcpState.servers.length;
            mcpState.lastCheck = response.timestamp;
            eventBus.emit('mcp:statusUpdate', mcpState);
            return mcpState;
        } catch (fallbackError) {
            mcpState.servers = [];
            mcpState.phase3Servers = [];
            mcpState.phase4Servers = [];
            mcpState.allConnected = false;
            return null;
        }
    }
}

/**
 * Effectue une recherche sémantique
 */
async function searchSimilar(query, limit = 5, scoreThreshold = 0.7) {
    try {
        const response = await apiRequest('/api/memory/similarity', {
            method: 'POST',
            body: JSON.stringify({
                query,
                limit,
                score_threshold: scoreThreshold
            })
        });
        return response;
    } catch (error) {
        console.error('❌ Erreur recherche sémantique:', error);
        return { results: [], results_count: 0 };
    }
}

/**
 * Compresse du contenu
 */
async function compressContent(content, algorithm = 'context_aware', targetRatio = 0.5) {
    try {
        const response = await apiRequest('/api/memory/compress', {
            method: 'POST',
            body: JSON.stringify({
                content,
                algorithm,
                target_ratio: targetRatio
            })
        });
        return response;
    } catch (error) {
        console.error('❌ Erreur compression:', error);
        return null;
    }
}

/**
 * Récupère les statistiques avancées de mémoire
 */
async function fetchAdvancedMemoryStats(sessionId = null) {
    try {
        const url = sessionId 
            ? `/api/memory/stats/advanced?session_id=${sessionId}`
            : '/api/memory/stats/advanced';
        const response = await apiRequest(url);
        mcpState.memoryStats = response;
        eventBus.emit('mcp:statsUpdate', response);
        return response;
    } catch (error) {
        console.error('❌ Erreur stats mémoire:', error);
        return null;
    }
}

/**
 * Récupère les mémoires fréquentes
 */
async function fetchFrequentMemories(sessionId = null, minAccessCount = 3, limit = 10) {
    try {
        let url = `/api/memory/frequent?min_access_count=${minAccessCount}&limit=${limit}`;
        if (sessionId) {
            url += `&session_id=${sessionId}`;
        }
        
        const response = await apiRequest(url);
        mcpState.frequentMemories = response.memories || [];
        eventBus.emit('mcp:frequentMemoriesUpdate', mcpState.frequentMemories);
        return response;
    } catch (error) {
        console.error('❌ Erreur mémoires fréquentes:', error);
        return { memories: [] };
    }
}

/**
 * Stocke une nouvelle mémoire
 */
async function storeMemory(sessionId, content, memoryType = 'episodic', metadata = null) {
    try {
        const response = await apiRequest(`/api/memory/store?session_id=${sessionId}`, {
            method: 'POST',
            body: JSON.stringify({
                content,
                memory_type: memoryType,
                metadata
            })
        });
        eventBus.emit('mcp:memoryStored', response);
        return response;
    } catch (error) {
        console.error('❌ Erreur stockage mémoire:', error);
        return null;
    }
}

// ============================================================================
// Rendu UI
// ============================================================================

/**
 * Rend une carte de serveur MCP
 * 
 * Pourquoi factorisation: Évite duplication entre Phase 3 et Phase 4
 */
function renderServerCard(server) {
    const statusColor = server.connected ? 'text-emerald-400' : 'text-rose-400';
    const statusBg = server.connected ? 'bg-emerald-500/10' : 'bg-rose-500/10';
    const statusIcon = server.connected ? 'check-circle' : 'x-circle';
    const latencyText = server.connected ? `${server.latency_ms.toFixed(0)}ms` : 'N/A';
    
    // Badge de phase (Phase 3 = mémoire externe, Phase 4 = outils avancés)
    const phaseBadge = server.phase === 'phase4' 
        ? '<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">P4</span>'
        : '<span class="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-400 border border-violet-500/30">P3</span>';
    
    // Badge du nombre d'outils pour Phase 4
    const toolsBadge = server.tool_count 
        ? `<span class="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-300">${server.tool_count} outils</span>`
        : '';
    
    const capabilities = server.capabilities?.map(cap => 
        `<span class="text-xs px-2 py-0.5 rounded bg-slate-700/50 text-slate-300">${cap}</span>`
    ).join('') || '';
    
    return `
        <div class="flex items-center justify-between p-3 rounded-lg ${statusBg} border border-slate-700/50 hover:border-slate-600/50 transition-colors">
            <div class="flex items-center gap-3">
                <div class="w-2 h-2 rounded-full ${server.connected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}"></div>
                <div>
                    <div class="flex items-center gap-2">
                        <p class="font-medium text-sm text-slate-200">${server.name}</p>
                        ${phaseBadge}
                        ${toolsBadge}
                    </div>
                    <p class="text-xs text-slate-400">${server.type} • ${latencyText}</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <div class="flex gap-1">${capabilities}</div>
                <i data-lucide="${statusIcon}" class="w-4 h-4 ${statusColor}"></i>
            </div>
        </div>
    `;
}

/**
 * Rend le panneau des statuts serveurs MCP (Phase 3 + Phase 4)
 * 
 * Pourquoi groupage: Distinction visuelle entre mémoire externe (P3) et outils avancés (P4)
 */
function renderMCPStatusPanel() {
    const container = document.getElementById('mcp-status-panel');
    if (!container) return;
    
    const { servers, phase3Servers, phase4Servers, allConnected, connectedCount, totalCount } = mcpState;
    
    if (!servers.length) {
        // Affiche le message "serveurs non configurés" de manière sécurisée (sans innerHTML)
        container.textContent = ''; // Clear existing content

        const noServersDiv = document.createElement('div');
        noServersDiv.className = 'text-slate-500 text-center py-4';

        const serverIcon = document.createElement('i');
        serverIcon.setAttribute('data-lucide', 'server-off');
        serverIcon.className = 'w-8 h-8 mx-auto mb-2 opacity-50';
        noServersDiv.appendChild(serverIcon);

        const messagePara = document.createElement('p');
        messagePara.className = 'text-sm';
        messagePara.textContent = 'Serveurs MCP non configurés';
        noServersDiv.appendChild(messagePara);

        container.appendChild(noServersDiv);
        lucide.createIcons();
        return;
    }
    
    // Rendu Phase 3 (Mémoire externe)
    const phase3Html = phase3Servers.length > 0 
        ? phase3Servers.map(renderServerCard).join('')
        : '<p class="text-xs text-slate-500 italic">Aucun serveur Phase 3</p>';
    
    // Rendu Phase 4 (Outils avancés)
    const phase4Html = phase4Servers.length > 0
        ? phase4Servers.map(renderServerCard).join('')
        : '<p class="text-xs text-slate-500 italic">Aucun serveur Phase 4</p>';
    
    // Statut global avec compteur
    const overallStatus = allConnected 
        ? `<span class="text-emerald-400 flex items-center gap-1"><i data-lucide="check-circle" class="w-4 h-4"></i> ${connectedCount}/${totalCount}</span>`
        : `<span class="text-amber-400 flex items-center gap-1"><i data-lucide="alert-triangle" class="w-4 h-4"></i> ${connectedCount}/${totalCount}</span>`;
    
    // Crée la structure des serveurs MCP de manière sécurisée (sans innerHTML)
    container.textContent = ''; // Clear existing content

    const mainContainer = document.createElement('div');
    mainContainer.className = 'space-y-4';

    // Header avec titre et statut
    const headerDiv = document.createElement('div');
    headerDiv.className = 'flex items-center justify-between';

    const titleH4 = document.createElement('h4');
    titleH4.className = 'text-sm font-medium text-slate-300';
    titleH4.textContent = 'Serveurs MCP';
    headerDiv.appendChild(titleH4);

    // Statut global (HTML contrôlé)
    if (overallStatus) {
        const statusContainer = document.createElement('span');
        statusContainer.innerHTML = overallStatus; // Contexte contrôlé - statut généré
        headerDiv.appendChild(statusContainer);
    }

    mainContainer.appendChild(headerDiv);

    // Phase 3: Mémoire externe
    const phase3Div = document.createElement('div');
    phase3Div.className = 'space-y-2';

    const phase3Header = document.createElement('div');
    phase3Header.className = 'flex items-center gap-2';

    const phase3Label = document.createElement('span');
    phase3Label.className = 'text-xs font-medium text-violet-400';
    phase3Label.textContent = 'Phase 3';
    phase3Header.appendChild(phase3Label);

    const phase3Desc = document.createElement('span');
    phase3Desc.className = 'text-[10px] text-slate-500';
    phase3Desc.textContent = 'Mémoire externe';
    phase3Header.appendChild(phase3Desc);

    phase3Div.appendChild(phase3Header);

    const phase3Content = document.createElement('div');
    phase3Content.className = 'space-y-2';
    if (phase3Html) {
        phase3Content.innerHTML = phase3Html; // Contexte contrôlé - HTML généré
    }
    phase3Div.appendChild(phase3Content);

    mainContainer.appendChild(phase3Div);

    // Phase 4: Outils avancés
    const phase4Div = document.createElement('div');
    phase4Div.className = 'space-y-2';

    const phase4Header = document.createElement('div');
    phase4Header.className = 'flex items-center gap-2';

    const phase4Label = document.createElement('span');
    phase4Label.className = 'text-xs font-medium text-amber-400';
    phase4Label.textContent = 'Phase 4';
    phase4Header.appendChild(phase4Label);

    const phase4Desc = document.createElement('span');
    phase4Desc.className = 'text-[10px] text-slate-500';
    phase4Desc.textContent = 'Outils avancés';
    phase4Header.appendChild(phase4Desc);

    phase4Div.appendChild(phase4Header);

    const phase4Content = document.createElement('div');
    phase4Content.className = 'space-y-2';
    if (phase4Html) {
        phase4Content.innerHTML = phase4Html; // Contexte contrôlé - HTML généré
    }
    phase4Div.appendChild(phase4Content);

    mainContainer.appendChild(phase4Div);
    container.appendChild(mainContainer);

    lucide.createIcons();
}

/**
 * Rend le panneau des mémoires fréquentes
 */
function renderFrequentMemoriesPanel() {
    const container = document.getElementById('mcp-frequent-memories');
    if (!container) return;
    
    const memories = mcpState.frequentMemories;
    
    if (!memories.length) {
        // Affiche le message "aucune mémoire fréquente" de manière sécurisée (sans innerHTML)
        container.textContent = ''; // Clear existing content

        const noMemoriesDiv = document.createElement('div');
        noMemoriesDiv.className = 'text-slate-500 text-center py-4';

        const brainIcon = document.createElement('i');
        brainIcon.setAttribute('data-lucide', 'brain');
        brainIcon.className = 'w-8 h-8 mx-auto mb-2 opacity-50';
        noMemoriesDiv.appendChild(brainIcon);

        const messagePara = document.createElement('p');
        messagePara.className = 'text-sm';
        messagePara.textContent = 'Aucune mémoire fréquente';
        noMemoriesDiv.appendChild(messagePara);

        container.appendChild(noMemoriesDiv);
        lucide.createIcons();
        return;
    }
    
    const memoriesHtml = memories.map(mem => {
        const typeColors = {
            frequent: 'text-violet-400 bg-violet-500/10',
            episodic: 'text-blue-400 bg-blue-500/10',
            semantic: 'text-emerald-400 bg-emerald-500/10'
        };
        const typeClass = typeColors[mem.memory_type] || typeColors.episodic;
        
        return `
            <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-violet-500/30 transition-colors">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-xs px-2 py-0.5 rounded ${typeClass}">${mem.memory_type}</span>
                    <span class="text-xs text-slate-500">${mem.access_count} accès</span>
                </div>
                <p class="text-sm text-slate-300 line-clamp-2">${mem.content_preview}</p>
                <div class="flex items-center gap-3 mt-2 text-xs text-slate-500">
                    <span><i data-lucide="file-text" class="w-3 h-3 inline"></i> ${mem.token_count} tokens</span>
                    <span><i data-lucide="clock" class="w-3 h-3 inline"></i> ${new Date(mem.last_accessed_at).toLocaleDateString()}</span>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = `
        <div class="space-y-2">
            ${memoriesHtml}
        </div>
    `;
    
    lucide.createIcons();
}

/**
 * Rend les statistiques avancées
 */
function renderAdvancedStats() {
    const container = document.getElementById('mcp-advanced-stats');
    if (!container || !mcpState.memoryStats) return;
    
    const { advanced_stats, features } = mcpState.memoryStats;
    
    // Affiche les statistiques avancées de manière sécurisée (sans innerHTML)
    container.textContent = ''; // Clear existing content

    const gridContainer = document.createElement('div');
    gridContainer.className = 'grid grid-cols-2 gap-3';

    // Métriques individuelles
    const metrics = [
        {
            label: 'Mémoires Totales',
            value: advanced_stats?.total_memories || 0,
            color: 'text-violet-400'
        },
        {
            label: 'Tokens Stockés',
            value: (advanced_stats?.total_tokens || 0).toLocaleString(),
            color: 'text-blue-400'
        },
        {
            label: 'Fréquentes',
            value: advanced_stats?.frequent_memories || 0,
            color: 'text-emerald-400'
        },
        {
            label: 'Accès Moyen',
            value: (advanced_stats?.average_access_count || 0).toFixed(1),
            color: 'text-amber-400'
        }
    ];

    metrics.forEach(metric => {
        const metricDiv = document.createElement('div');
        metricDiv.className = 'p-3 rounded-lg bg-slate-800/50 border border-slate-700/50';

        const labelP = document.createElement('p');
        labelP.className = 'text-xs text-slate-500 mb-1';
        labelP.textContent = metric.label;
        metricDiv.appendChild(labelP);

        const valueP = document.createElement('p');
        valueP.className = `text-2xl font-bold ${metric.color}`;
        valueP.textContent = metric.value;
        metricDiv.appendChild(valueP);

        gridContainer.appendChild(metricDiv);
    });

    container.appendChild(gridContainer);

    // Fonctionnalités
    const featuresDiv = document.createElement('div');
    featuresDiv.className = 'mt-4 flex flex-wrap gap-2';

    const featureStatuses = [
        {
            feature: 'semantic_search',
            name: 'Qdrant',
            available: features?.semantic_search
        },
        {
            feature: 'advanced_compression',
            name: 'Compression',
            available: features?.advanced_compression
        }
    ];

    featureStatuses.forEach(feature => {
        const featureSpan = document.createElement('span');
        featureSpan.className = `text-xs px-2 py-1 rounded ${
            feature.available
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                : 'bg-slate-700 text-slate-400'
        }`;
        featureSpan.textContent = `${feature.name} ${feature.available ? '✓' : '✗'}`;
        featuresDiv.appendChild(featureSpan);
    });

    container.appendChild(featuresDiv);
}

// ============================================================================
// Initialisation
// ============================================================================

function init() {
    // Écoute les événements
    eventBus.on('mcp:statusUpdate', renderMCPStatusPanel);
    eventBus.on('mcp:frequentMemoriesUpdate', renderFrequentMemoriesPanel);
    eventBus.on('mcp:statsUpdate', renderAdvancedStats);
    
    // Rafraîchissement périodique
    setInterval(() => {
        fetchServerStatuses();
        const sessionId = window.currentSessionId;
        if (sessionId) {
            fetchAdvancedMemoryStats(sessionId);
            fetchFrequentMemories(sessionId);
        }
    }, 30000); // Toutes les 30s
    
    // Chargement initial
    fetchServerStatuses();
}

// ============================================================================
// Exports
// ============================================================================

export {
    init,
    fetchServerStatuses,
    searchSimilar,
    compressContent,
    fetchAdvancedMemoryStats,
    fetchFrequentMemories,
    storeMemory,
    renderMCPStatusPanel,
    renderFrequentMemoriesPanel,
    renderAdvancedStats,
    mcpState
};
