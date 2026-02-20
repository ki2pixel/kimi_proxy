/**
 * similarity-chart.js - Visualisation Chart.js pour la similarité mémoire
 * 
 * Pourquoi : Fournit des visualisations interactives pour les résultats
 * de similarité avec nettoyage mémoire et performance optimisée
 */

import { eventBus } from './utils.js';

// ============================================================================
// SIMILARITY CHART SERVICE
// ============================================================================

export class SimilarityChartService {
    constructor() {
        this.chartInstance = null;
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // Nettoyer le chart lors du changement de page
        eventBus.on('memory:similarity:hide', () => {
            this.destroyChart();
        });
        
        // Nettoyer lors du déchargement
        window.addEventListener('beforeunload', () => {
            this.destroyChart();
        });
    }
    
    /**
     * Crée un graphique de dispersion pour les résultats de similarité
     * @param {string} canvasId - ID du canvas
     * @param {Array} results - Résultats de similarité
     */
    renderSimilarityChart(canvasId, results) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`Canvas ${canvasId} non trouvé`);
            return;
        }
        
        // Détruire le graphique existant
        this.destroyChart();
        
        // Préparer les données pour le scatter plot
        const scatterData = results.map((mem, idx) => ({
            x: idx,
            y: mem.similarity_score,
            memory: mem,
            label: mem.title || `Mémoire ${idx + 1}`
        }));
        
        const ctx = canvas.getContext('2d');
        
        this.chartInstance = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Score de Similarité',
                    data: scatterData,
                    backgroundColor: scatterData.map(point => 
                        this.getColorForScore(point.y)
                    ),
                    borderColor: scatterData.map(point => 
                        this.getBorderColorForScore(point.y)
                    ),
                    borderWidth: 2,
                    pointRadius: 8,
                    pointHoverRadius: 10,
                    pointStyle: 'circle'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 750,
                    easing: 'easeInOutQuart'
                },
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(15, 23, 42, 0.95)',
                        titleColor: '#f1f5f9',
                        bodyColor: '#cbd5e1',
                        borderColor: '#475569',
                        borderWidth: 1,
                        padding: 12,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            title: (context) => {
                                const point = context[0]?.raw;
                                return point?.label || 'Mémoire inconnue';
                            },
                            label: (context) => {
                                const point = context.raw;
                                const score = (point.y * 100).toFixed(1);
                                return [
                                    `Score: ${score}%`,
                                    `ID: ${point.memory.id || 'N/A'}`,
                                    `Type: ${point.memory.type || 'inconnu'}`
                                ];
                            },
                            afterLabel: (context) => {
                                const point = context.raw;
                                const preview = point.memory.content_preview || point.memory.content;
                                if (preview && preview.length > 0) {
                                    const truncated = preview.length > 100 
                                        ? preview.substring(0, 100) + '...' 
                                        : preview;
                                    return `Aperçu: ${truncated}`;
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        title: {
                            display: true,
                            text: 'Index Mémoire',
                            color: '#94a3b8',
                            font: {
                                size: 14,
                                weight: '500'
                            }
                        },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: {
                                size: 11
                            }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Score de Similarité',
                            color: '#94a3b8',
                            font: {
                                size: 14,
                                weight: '500'
                            }
                        },
                        min: 0,
                        max: 1,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)',
                            drawBorder: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: {
                                size: 11
                            },
                            callback: function(value) {
                                return (value * 100).toFixed(0) + '%';
                            }
                        }
                    }
                }
            }
        });
        
        return this.chartInstance;
    }
    
    /**
     * Détermine la couleur selon le score de similarité
     * @param {number} score - Score de similarité (0-1)
     * @returns {string} Couleur RGBA
     */
    getColorForScore(score) {
        if (score >= 0.9) {
            return 'rgba(34, 197, 94, 0.8)';    // Vert - excellente
        } else if (score >= 0.8) {
            return 'rgba(59, 130, 246, 0.8)';   // Bleu - bonne
        } else if (score >= 0.7) {
            return 'rgba(251, 191, 36, 0.8)';   // Jaune - moyenne
        } else {
            return 'rgba(239, 68, 68, 0.8)';     // Rouge - faible
        }
    }
    
    /**
     * Détermine la couleur de bordure selon le score
     * @param {number} score - Score de similarité (0-1)
     * @returns {string} Couleur RGBA
     */
    getBorderColorForScore(score) {
        if (score >= 0.9) {
            return 'rgba(34, 197, 94, 1)';
        } else if (score >= 0.8) {
            return 'rgba(59, 130, 246, 1)';
        } else if (score >= 0.7) {
            return 'rgba(251, 191, 36, 1)';
        } else {
            return 'rgba(239, 68, 68, 1)';
        }
    }
    
    /**
     * Met à jour le graphique avec de nouvelles données
     * @param {Array} results - Nouveaux résultats
     */
    updateChart(results) {
        if (!this.chartInstance) return;
        
        const scatterData = results.map((mem, idx) => ({
            x: idx,
            y: mem.similarity_score,
            memory: mem,
            label: mem.title || `Mémoire ${idx + 1}`
        }));
        
        this.chartInstance.data.datasets[0].data = scatterData;
        this.chartInstance.data.datasets[0].backgroundColor = scatterData.map(point => 
            this.getColorForScore(point.y)
        );
        this.chartInstance.data.datasets[0].borderColor = scatterData.map(point => 
            this.getBorderColorForScore(point.y)
        );
        
        this.chartInstance.update('active');
    }
    
    /**
     * Détruit proprement l'instance du graphique
     */
    destroyChart() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
            this.chartInstance = null;
        }
    }
    
    /**
     * Crée un graphique de distribution des scores
     * @param {string} canvasId - ID du canvas
     * @param {Array} results - Résultats de similarité
     */
    renderScoreDistribution(canvasId, results) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        
        // Calculer la distribution
        const distribution = this.calculateScoreDistribution(results);
        
        const ctx = canvas.getContext('2d');
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: distribution.map(d => d.label),
                datasets: [{
                    label: 'Nombre de mémoires',
                    data: distribution.map(d => d.count),
                    backgroundColor: distribution.map(d => this.getColorForRange(d.range)),
                    borderColor: distribution.map(d => this.getBorderColorForRange(d.range)),
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${context.parsed.y} mémoires (${context.label})`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Nombre de mémoires',
                            color: '#94a3b8'
                        },
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#64748b',
                            stepSize: 1
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Plage de scores',
                            color: '#94a3b8'
                        },
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#64748b'
                        }
                    }
                }
            }
        });
    }
    
    /**
     * Calcule la distribution des scores
     * @param {Array} results - Résultats de similarité
     * @returns {Array} Distribution des scores
     */
    calculateScoreDistribution(results) {
        const ranges = [
            { range: '0.9-1.0', min: 0.9, max: 1.0, label: '90-100%' },
            { range: '0.8-0.9', min: 0.8, max: 0.9, label: '80-90%' },
            { range: '0.7-0.8', min: 0.7, max: 0.8, label: '70-80%' },
            { range: '0.6-0.7', min: 0.6, max: 0.7, label: '60-70%' },
            { range: '0.5-0.6', min: 0.5, max: 0.6, label: '50-60%' },
            { range: '0.0-0.5', min: 0.0, max: 0.5, label: '0-50%' }
        ];
        
        return ranges.map(range => ({
            ...range,
            count: results.filter(r => r.similarity_score >= range.min && r.similarity_score < range.max).length
        }));
    }
    
    /**
     * Couleur pour une plage de scores
     * @param {string} range - Plage de scores
     * @returns {string} Couleur RGBA
     */
    getColorForRange(range) {
        const colors = {
            '0.9-1.0': 'rgba(34, 197, 94, 0.8)',
            '0.8-0.9': 'rgba(59, 130, 246, 0.8)',
            '0.7-0.8': 'rgba(251, 191, 36, 0.8)',
            '0.6-0.7': 'rgba(251, 146, 60, 0.8)',
            '0.5-0.6': 'rgba(239, 68, 68, 0.8)',
            '0.0-0.5': 'rgba(127, 29, 29, 0.8)'
        };
        return colors[range] || 'rgba(148, 163, 184, 0.8)';
    }
    
    /**
     * Couleur de bordure pour une plage
     * @param {string} range - Plage de scores
     * @returns {string} Couleur RGBA
     */
    getBorderColorForRange(range) {
        const colors = {
            '0.9-1.0': 'rgba(34, 197, 94, 1)',
            '0.8-0.9': 'rgba(59, 130, 246, 1)',
            '0.7-0.8': 'rgba(251, 191, 36, 1)',
            '0.6-0.7': 'rgba(251, 146, 60, 1)',
            '0.5-0.6': 'rgba(239, 68, 68, 1)',
            '0.0-0.5': 'rgba(127, 29, 29, 1)'
        };
        return colors[range] || 'rgba(148, 163, 184, 1)';
    }
}

// ============================================================================
// INSTANCE GLOBALE
// ============================================================================

export const similarityChartService = new SimilarityChartService();

// ============================================================================
// EXPORTS CONVENIENCE
// ============================================================================

export function renderSimilarityChart(canvasId, results) {
    return similarityChartService.renderSimilarityChart(canvasId, results);
}

export function updateSimilarityChart(results) {
    similarityChartService.updateChart(results);
}

export function destroySimilarityChart() {
    similarityChartService.destroyChart();
}

export function renderScoreDistribution(canvasId, results) {
    similarityChartService.renderScoreDistribution(canvasId, results);
}