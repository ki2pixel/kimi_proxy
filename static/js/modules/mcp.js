/**
 * Module MCP - Gestion des serveurs MCP Phase 3 et Phase 4
 * 
 * Fonctionnalités:
 * - Phase 3: Serveurs mémoire externe (Qdrant, Context Compression)
 * - Phase 4: Outils avancés (Task Master:14, Sequential Thinking:1, Fast Filesystem:25, JSON Query:3)
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
    phase4Servers: [],     // Phase 4: Task Master, Sequential Thinking, Fast Filesystem, JSON Query
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
        container.innerHTML = `
            <div class="text-slate-500 text-center py-4">
                <i data-lucide="server-off" class="w-8 h-8 mx-auto mb-2 opacity-50"></i>
                <p class="text-sm">Serveurs MCP non configurés</p>
            </div>
        `;
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
    
    container.innerHTML = `
        <div class="space-y-4">
            <div class="flex items-center justify-between">
                <h4 class="text-sm font-medium text-slate-300">Serveurs MCP</h4>
                ${overallStatus}
            </div>
            
            <!-- Phase 3: Mémoire externe -->
            <div class="space-y-2">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-medium text-violet-400">Phase 3</span>
                    <span class="text-[10px] text-slate-500">Mémoire externe</span>
                </div>
                <div class="space-y-2">
                    ${phase3Html}
                </div>
            </div>
            
            <!-- Phase 4: Outils avancés -->
            <div class="space-y-2">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-medium text-amber-400">Phase 4</span>
                    <span class="text-[10px] text-slate-500">Outils avancés</span>
                </div>
                <div class="space-y-2">
                    ${phase4Html}
                </div>
            </div>
        </div>
    `;
    
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
        container.innerHTML = `
            <div class="text-slate-500 text-center py-4">
                <i data-lucide="brain" class="w-8 h-8 mx-auto mb-2 opacity-50"></i>
                <p class="text-sm">Aucune mémoire fréquente</p>
            </div>
        `;
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
    
    container.innerHTML = `
        <div class="grid grid-cols-2 gap-3">
            <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <p class="text-xs text-slate-500 mb-1">Mémoires Totales</p>
                <p class="text-2xl font-bold text-violet-400">${advanced_stats?.total_memories || 0}</p>
            </div>
            <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <p class="text-xs text-slate-500 mb-1">Tokens Stockés</p>
                <p class="text-2xl font-bold text-blue-400">${(advanced_stats?.total_tokens || 0).toLocaleString()}</p>
            </div>
            <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <p class="text-xs text-slate-500 mb-1">Fréquentes</p>
                <p class="text-2xl font-bold text-emerald-400">${advanced_stats?.frequent_memories || 0}</p>
            </div>
            <div class="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <p class="text-xs text-slate-500 mb-1">Accès Moyen</p>
                <p class="text-2xl font-bold text-amber-400">${(advanced_stats?.average_access_count || 0).toFixed(1)}</p>
            </div>
        </div>
        
        <div class="mt-4 flex flex-wrap gap-2">
            ${features?.semantic_search ? '<span class="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Qdrant ✓</span>' : '<span class="text-xs px-2 py-1 rounded bg-slate-700 text-slate-400">Qdrant ✗</span>'}
            ${features?.advanced_compression ? '<span class="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Compression ✓</span>' : '<span class="text-xs px-2 py-1 rounded bg-slate-700 text-slate-400">Compression ✗</span>'}
        </div>
    `;
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
