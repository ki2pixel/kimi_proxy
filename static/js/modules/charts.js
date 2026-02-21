/**
 * charts.js - Gestion de tous les graphiques Chart.js
 *
 * Pourquoi : Centralise la logique des graphiques pour garantir la cohérence
 * visuelle et faciliter les mises à jour globales du style.
 */

import { getColorForPercentage } from './utils.js';

// ============================================================================
// CHARTMANAGER CLASS - Gestion centralisée des graphiques
// ============================================================================

/**
 * ChartManager - Classe principale pour gérer tous les graphiques
 * Pourquoi : Centralise la logique de gestion d'état et de session des graphiques
 */
export class ChartManager {
    constructor() {
        this.charts = new Map();
        this.dataBuffers = new Map();
        this.sessionContext = null;
    }

    /**
     * Initialise la jauge principale
     * @returns {Chart|null} Instance Chart.js
     */
    initGauge() {
        const ctx = document.getElementById('gaugeChart')?.getContext('2d');
        if (!ctx) return null;

        const gaugeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Utilisé', 'Disponible'],
                datasets: [{
                    data: [0, 100],
                    backgroundColor: [
                        '#22c55e',
                        'rgba(30, 41, 59, 0.5)'
                    ],
                    borderWidth: 0,
                    cutout: '75%',
                    circumference: 180,
                    rotation: 270,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false }
                },
                animation: {
                    animateRotate: true,
                    duration: 500
                }
            }
        });

        this.charts.set('gauge', gaugeChart);
        return gaugeChart;
    }

    /**
     * Met à jour la jauge avec un nouveau pourcentage
     * @param {number} percentage - Pourcentage d'usage (0-100)
     * @param {string} sessionId - ID de session pour filtrage
     */
    updateGauge(percentage, sessionId = null) {
        // Filtre par session si spécifié
        if (sessionId && sessionId !== this.sessionContext) {
            return;
        }

        const gaugeChart = this.charts.get('gauge');
        if (!gaugeChart) return;

        const color = getColorForPercentage(percentage);

        gaugeChart.data.datasets[0].data = [percentage, 100 - percentage];
        gaugeChart.data.datasets[0].backgroundColor[0] = color;
        gaugeChart.update('none'); // Animation optimisée
    }

    /**
     * Initialise le graphique d'historique
     * @returns {Chart|null} Instance Chart.js
     */
    initHistoryChart() {
        const ctx = document.getElementById('historyChart')?.getContext('2d');
        if (!ctx) return null;

        const historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Tokens Total',
                    data: [],
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointBackgroundColor: '#3b82f6'
                }, {
                    label: 'Prompt',
                    data: [],
                    borderColor: '#22c55e',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.4,
                    pointRadius: 0,
                    hidden: false
                }, {
                    label: 'Completion',
                    data: [],
                    borderColor: '#a855f7',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.4,
                    pointRadius: 0,
                    hidden: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { size: 11 } }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#64748b', font: { size: 10 }, maxTicksLimit: 6 },
                        grid: { color: 'rgba(71, 85, 105, 0.2)' }
                    },
                    y: {
                        ticks: { color: '#64748b', font: { size: 10 } },
                        grid: { color: 'rgba(71, 85, 105, 0.2)' },
                        beginAtZero: true
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        });

        this.charts.set('history', historyChart);
        return historyChart;
    }

    /**
     * Met à jour le graphique d'historique avec métriques filtrées par session
     * @param {Array} sessionMetrics - Liste des métriques de session
     * @param {string} sessionId - ID de session pour filtrage (optionnel)
     */
    updateHistoryChart(sessionMetrics, sessionId = null) {
        // Utilise la session active si aucun session_id fourni
        const targetSessionId = sessionId || this.sessionContext;

        // Filtre par session si spécifié ou si on a un contexte de session
        if (targetSessionId && targetSessionId !== this.sessionContext) {
            return;
        }

        const historyChart = this.charts.get('history');
        if (!historyChart || !sessionMetrics || sessionMetrics.length === 0) return;

        const recentMetrics = sessionMetrics.slice(-20);

        const labels = recentMetrics.map((m, i) => `#${i + 1}`);
        const totalTokens = recentMetrics.map(m => m.estimated_tokens);
        const promptTokens = recentMetrics.map(m => m.prompt_tokens || 0);
        const completionTokens = recentMetrics.map(m => m.completion_tokens || 0);

        historyChart.data.labels = labels;
        historyChart.data.datasets[0].data = totalTokens;
        historyChart.data.datasets[1].data = promptTokens;
        historyChart.data.datasets[2].data = completionTokens;
        historyChart.update('none');
    }

    /**
     * Initialise le graphique de compaction
     * @returns {Chart|null} Instance Chart.js
     */
    initCompactionChart() {
        const ctx = document.getElementById('compactionChart')?.getContext('2d');
        if (!ctx) return null;

        const compactionChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Tokens économisés',
                    data: [],
                    backgroundColor: 'rgba(34, 197, 94, 0.6)',
                    borderColor: '#22c55e',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        ticks: { color: '#64748b', font: { size: 10 } },
                        grid: { display: false }
                    },
                    y: {
                        ticks: { color: '#64748b', font: { size: 10 } },
                        grid: { color: 'rgba(71, 85, 105, 0.2)' },
                        beginAtZero: true
                    }
                }
            }
        });

        this.charts.set('compaction', compactionChart);
        return compactionChart;
    }

    /**
     * Met à jour le graphique de compaction avec filtrage par session
     * @param {Object} chartData - Données du graphique
     * @param {string} sessionId - ID de session pour filtrage
     */
    updateCompactionChart(chartData, sessionId = null) {
        // Filtre par session si spécifié
        if (sessionId && sessionId !== this.sessionContext) {
            return;
        }

        const compactionChart = this.charts.get('compaction');
        if (!compactionChart || !chartData?.datasets) return;

        compactionChart.data.labels = chartData.labels || [];
        compactionChart.data.datasets[0].data = chartData.datasets[0]?.data || [];
        compactionChart.update('none');
    }

    /**
     * Gère le changement de session - nettoie les anciennes données et charge les nouvelles
     * @param {CustomEvent} event - Événement de changement de session
     */
    handleSessionChange(event) {
        const { newSession, oldSession } = event.detail;
        const previousContext = this.sessionContext;
        
        // Met à jour le contexte de session
        this.sessionContext = newSession.id;

        console.log(`🔄 [ChartManager] Changement de session: ${previousContext} → ${newSession.id}`);

        // Si c'est la même session, ne rien faire
        if (previousContext === newSession.id) {
            console.log(`ℹ️ [ChartManager] Même session, pas de changement nécessaire`);
            return;
        }

        // Nettoyer les anciennes données seulement si c'est vraiment une nouvelle session
        if (previousContext && previousContext !== newSession.id) {
            console.log(`🧹 [ChartManager] Nettoyage données anciennes session: ${previousContext}`);
            
            // Réinitialiser tous les datasets
            for (const [chartId, chart] of this.charts) {
                if (chart.data.datasets) {
                    chart.data.datasets.forEach(dataset => {
                        dataset.data = [];
                    });
                    // Réinitialiser les labels pour les graphiques qui en ont
                    if (chart.data.labels) {
                        chart.data.labels = [];
                    }
                    chart.update('none');
                }
            }

            // Vider les buffers de données
            this.dataBuffers.clear();
        }

        // Charger les métriques existantes de la nouvelle session si disponibles
        if (newSession.metrics && newSession.metrics.length > 0) {
            console.log(`📊 [ChartManager] Chargement ${newSession.metrics.length} métriques existantes pour session ${newSession.id}`);
            
            // Charger les données dans les graphiques
            this.loadExistingMetrics(newSession.metrics);
        } else {
            console.log(`📭 [ChartManager] Aucune métrique existante pour session ${newSession.id}`);
        }

        console.log(`✅ [ChartManager] Session ${newSession.id} prête`);
    }

    /**
     * Charge les métriques existantes dans les graphiques
     * @param {Array} metrics - Métriques de la session
     */
    loadExistingMetrics(metrics) {
        if (!metrics || metrics.length === 0) return;

        try {
            // Calculer les statistiques globales
            const totalTokens = metrics.reduce((sum, m) => sum + (m.estimated_tokens || 0), 0);
            const maxTokens = Math.max(...metrics.map(m => m.estimated_tokens || 0));
            
            // Mettre à jour la jauge avec le total
            const gaugeChart = this.charts.get('gauge');
            if (gaugeChart && maxTokens > 0) {
                const percentage = Math.min((totalTokens / maxTokens) * 100, 100);
                this.updateGauge(percentage, this.sessionContext);
            }

            // Mettre à jour le graphique d'historique avec les métriques récentes
            const historyChart = this.charts.get('history');
            if (historyChart && metrics.length > 0) {
                this.updateHistoryChart(metrics, this.sessionContext);
            }

            console.log(`✅ [ChartManager] Métriques chargées: ${totalTokens} tokens, ${metrics.length} requêtes`);
        } catch (error) {
            console.error('❌ [ChartManager] Erreur chargement métriques:', error);
        }
    }

    /**
     * Met à jour n'importe quel graphique avec filtrage par session
     * @param {string} chartId - ID du graphique
     * @param {*} newData - Nouvelles données
     * @param {string} sessionId - ID de session pour filtrage
     */
    updateChart(chartId, newData, sessionId = null) {
        // Filtre par session
        if (sessionId && sessionId !== this.sessionContext) {
            return;
        }

        const chart = this.charts.get(chartId);
        if (!chart) return;

        // Logique spécifique selon le type de graphique
        switch (chartId) {
            case 'gauge':
                this.updateGauge(newData, sessionId);
                break;
            case 'history':
                this.updateHistoryChart(newData, sessionId);
                break;
            case 'compaction':
                this.updateCompactionChart(newData, sessionId);
                break;
        }
    }

    /**
     * Récupère une instance de graphique
     * @param {string} chartId - ID du graphique
     * @returns {Chart|null}
     */
    getChart(chartId) {
        return this.charts.get(chartId) || null;
    }

    /**
     * Détruit tous les graphiques
     */
    destroy() {
        for (const [chartId, chart] of this.charts) {
            if (chart) {
                chart.destroy();
            }
        }
        this.charts.clear();
        this.dataBuffers.clear();
        this.sessionContext = null;
    }
}

// ============================================================================
// INSTANCE GLOBALE (pour compatibilité)
// ============================================================================

let chartManagerInstance = null;

/**
 * Récupère l'instance globale du ChartManager
 * @returns {ChartManager}
 */
export function getChartManager() {
    if (!chartManagerInstance) {
        chartManagerInstance = new ChartManager();
    }
    return chartManagerInstance;
}

// ============================================================================
// FONCTIONS DE COMPATIBILITÉ (legacy)
// ============================================================================

/**
 * Fonctions legacy pour compatibilité
 * @deprecated Utiliser ChartManager à la place
 */
export function initGauge() {
    return getChartManager().initGauge();
}

export function updateGauge(percentage) {
    return getChartManager().updateGauge(percentage);
}

export function initHistoryChart() {
    return getChartManager().initHistoryChart();
}

export function updateHistoryChart(sessionMetrics) {
    return getChartManager().updateHistoryChart(sessionMetrics);
}

export function initCompactionChart() {
    return getChartManager().initCompactionChart();
}

export function updateCompactionChart(chartData) {
    return getChartManager().updateCompactionChart(chartData);
}

export function getGaugeChart() {
    return getChartManager().getChart('gauge');
}

export function getHistoryChart() {
    return getChartManager().getChart('history');
}

export function getCompactionChart() {
    return getChartManager().getChart('compaction');
}

export function destroyCharts() {
    return getChartManager().destroy();
}
