/**
 * charts.js - Gestion de tous les graphiques Chart.js
 * 
 * Pourquoi : Centralise la logique des graphiques pour garantir la cohérence
 * visuelle et faciliter les mises à jour globales du style.
 */

import { getColorForPercentage } from './utils.js';

// ============================================================================
// ÉTAT DES GRAPHIQUES
// ============================================================================

let gaugeChart = null;
let historyChart = null;
let compactionChart = null;

// ============================================================================
// JAUGE PRINCIPALE (DOUGHNUT)
// ============================================================================

/**
 * Initialise la jauge principale de contexte
 * Pourquoi : Visualisation immédiate de l'usage du contexte LLM
 */
export function initGauge() {
    const ctx = document.getElementById('gaugeChart')?.getContext('2d');
    if (!ctx) return null;
    
    gaugeChart = new Chart(ctx, {
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
    
    return gaugeChart;
}

/**
 * Met à jour la jauge avec un nouveau pourcentage
 * Pourquoi : Animation fluide lors des changements de contexte
 * @param {number} percentage - Pourcentage d'usage (0-100)
 */
export function updateGauge(percentage) {
    if (!gaugeChart) return;
    
    const color = getColorForPercentage(percentage);
    
    gaugeChart.data.datasets[0].data = [percentage, 100 - percentage];
    gaugeChart.data.datasets[0].backgroundColor[0] = color;
    gaugeChart.update();
}

// ============================================================================
// GRAPHIQUE D'HISTORIQUE (LINE)
// ============================================================================

/**
 * Initialise le graphique d'historique des tokens
 * Pourquoi : Visualisation de l'évolution temporelle de l'usage
 */
export function initHistoryChart() {
    const ctx = document.getElementById('historyChart')?.getContext('2d');
    if (!ctx) return null;
    
    historyChart = new Chart(ctx, {
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
    
    return historyChart;
}

/**
 * Met à jour le graphique d'historique avec de nouvelles métriques
 * Pourquoi : Affiche les 20 dernières métriques pour éviter la saturation
 * @param {Array} sessionMetrics - Liste des métriques de session
 */
export function updateHistoryChart(sessionMetrics) {
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
    historyChart.update();
}

// ============================================================================
// GRAPHIQUE DE COMPACTION (BAR)
// ============================================================================

/**
 * Initialise le graphique d'historique de compaction
 * Pourquoi : Visualise les tokens économisés par compaction au fil du temps
 */
export function initCompactionChart() {
    const ctx = document.getElementById('compactionChart')?.getContext('2d');
    if (!ctx) return null;
    
    compactionChart = new Chart(ctx, {
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
    
    return compactionChart;
}

/**
 * Met à jour le graphique de compaction
 * Pourquoi : Affiche l'historique des tokens économisés
 * @param {Object} chartData - Données du graphique (labels et datasets)
 */
export function updateCompactionChart(chartData) {
    if (!compactionChart || !chartData?.datasets) return;
    
    compactionChart.data.labels = chartData.labels || [];
    compactionChart.data.datasets[0].data = chartData.datasets[0]?.data || [];
    compactionChart.update();
}

// ============================================================================
// ACCESSEURS
// ============================================================================

export function getGaugeChart() {
    return gaugeChart;
}

export function getHistoryChart() {
    return historyChart;
}

export function getCompactionChart() {
    return compactionChart;
}

// ============================================================================
// DESTRUCTION
// ============================================================================

/**
 * Détruit tous les graphiques
 * Pourquoi : Nettoyage lors du rechargement ou démontage
 */
export function destroyCharts() {
    if (gaugeChart) {
        gaugeChart.destroy();
        gaugeChart = null;
    }
    if (historyChart) {
        historyChart.destroy();
        historyChart = null;
    }
    if (compactionChart) {
        compactionChart.destroy();
        compactionChart = null;
    }
}
