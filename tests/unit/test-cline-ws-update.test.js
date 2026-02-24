/**
 * Tests unitaires — WebSocketManager: handling cline_usage_updated
 */

import { WebSocketManager } from '../../static/js/modules/websocket.js';

describe('WebSocketManager cline_usage_updated', () => {
    test('should not throw when cline section is missing', () => {
        const wsManager = new WebSocketManager();

        // Ensure DOM does not contain cline elements
        document.body.innerHTML = '<div id="root"></div>';

        // should be safe and not throw
        wsManager.handleClineUsageUpdated({
            type: 'cline_usage_updated',
            latest_ts: 123,
            imported_count: 1,
            timestamp: new Date().toISOString()
        });
    });
});
