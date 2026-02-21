/**
 * Tests unitaires pour ChartManager
 * Teste la gestion des sessions et le filtrage des métriques
 */

import { ChartManager } from '../static/js/modules/charts.js';

// Mock Chart.js
global.Chart = class Chart {
    constructor() {
        this.data = { datasets: [], labels: [] };
    }
    update(mode) {
        // Mock update
    }
    destroy() {
        // Mock destroy
    }
}

describe('ChartManager', () => {
    let chartManager;
    let mockEvent;

    beforeEach(() => {
        chartManager = new ChartManager();
        mockEvent = {
            detail: {
                newSession: { id: 'session-123' }
            }
        };
    });

    test('should initialize with correct structure', () => {
        expect(chartManager.charts).toBeInstanceOf(Map);
        expect(chartManager.dataBuffers).toBeInstanceOf(Map);
        expect(chartManager.sessionContext).toBeNull();
    });

    test('should init and store gauge chart', () => {
        // Mock DOM element
        document.getElementById = jest.fn().mockReturnValue({
            getContext: () => ({})
        });

        const chart = chartManager.initGauge();
        expect(chart).toBeDefined();
        expect(chartManager.charts.get('gauge')).toBe(chart);
    });

    test('should filter gauge updates by session', () => {
        chartManager.sessionContext = 'session-123';

        const mockChart = { data: { datasets: [{ data: [] }] }, update: jest.fn() };
        chartManager.charts.set('gauge', mockChart);

        // Update avec session matching - devrait passer
        chartManager.updateGauge(75, 'session-123');
        expect(mockChart.update).toHaveBeenCalledWith('none');

        // Reset mock
        mockChart.update.mockClear();

        // Update avec session différente - devrait être filtré
        chartManager.updateGauge(50, 'session-456');
        expect(mockChart.update).not.toHaveBeenCalled();
    });

    test('should reset all charts on session change', () => {
        // Mock charts
        const mockGauge = {
            data: { datasets: [{ data: [50] }] },
            update: jest.fn()
        };
        const mockHistory = {
            data: { datasets: [{ data: [10, 20] }], labels: ['A', 'B'] },
            update: jest.fn()
        };

        chartManager.charts.set('gauge', mockGauge);
        chartManager.charts.set('history', mockHistory);
        chartManager.dataBuffers.set('buffer1', [1, 2, 3]);

        // Change session
        chartManager.handleSessionChange(mockEvent);

        // Vérifications
        expect(chartManager.sessionContext).toBe('session-123');
        expect(mockGauge.data.datasets[0].data).toEqual([]);
        expect(mockHistory.data.datasets[0].data).toEqual([]);
        expect(mockHistory.data.labels).toEqual([]);
        expect(chartManager.dataBuffers.size).toBe(0);

        expect(mockGauge.update).toHaveBeenCalledWith('none');
        expect(mockHistory.update).toHaveBeenCalledWith('none');
    });

    test('should handle destroy properly', () => {
        const mockChart1 = { destroy: jest.fn() };
        const mockChart2 = { destroy: jest.fn() };

        chartManager.charts.set('chart1', mockChart1);
        chartManager.charts.set('chart2', mockChart2);
        chartManager.dataBuffers.set('buffer1', [1, 2, 3]);

        chartManager.destroy();

        expect(mockChart1.destroy).toHaveBeenCalled();
        expect(mockChart2.destroy).toHaveBeenCalled();
        expect(chartManager.charts.size).toBe(0);
        expect(chartManager.dataBuffers.size).toBe(0);
        expect(chartManager.sessionContext).toBeNull();
    });
});
