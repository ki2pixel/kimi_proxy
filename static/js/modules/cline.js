/**
 * cline.js - UI + API client pour la section “Cline (local)”
 *
 * Objectif:
 * - Afficher des métriques importées depuis `/api/cline/*`
 * - Permettre un import manuel (POST /api/cline/import)
 *
 * Contraintes:
 * - ES6 modules (named exports)
 * - DOM sécurisé: aucun rendu HTML direct (prévenir XSS)
 */

import { showNotification, eventBus } from './utils.js';

/** @typedef {{ task_id: string, ts: number, model_id: (string|null), tokens_in: number, tokens_out: number, total_cost: number, imported_at: string }} ClineUsageRow */

/**
 * @typedef {Object} ClineUsageResponse
 * @property {ClineUsageRow[]} items
 * @property {number} limit
 * @property {number} offset
 */

/**
 * @typedef {Object} ClineStatusResponse
 * @property {number|null} latest_ts
 */

/**
 * @typedef {Object} ClineImportResponse
 * @property {number} imported_count
 * @property {number} skipped_count
 * @property {number} error_count
 * @property {number|null} latest_ts
 */

const DEFAULT_LIMIT = 8;

function formatTimestamp(ts) {
    if (!ts) return '-';
    // taskHistory.json peut être en ms ou seconds, best-effort
    const isMs = ts > 10_000_000_000;
    const date = new Date(isMs ? ts : ts * 1000);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleString('fr-FR');
}

function formatCost(cost) {
    if (cost === null || cost === undefined) return '-';
    const num = Number(cost);
    if (Number.isNaN(num)) return '-';
    // 4 décimales max, sans forcer (évite 0.0000)
    return num.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 4 });
}

function clearTbody(tbody) {
    while (tbody.firstChild) {
        tbody.removeChild(tbody.firstChild);
    }
}

function setLoadingRow(tbody, message) {
    clearTbody(tbody);
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.className = 'py-3 text-slate-500';
    td.textContent = message;
    tr.appendChild(td);
    tbody.appendChild(tr);
}

/**
 * @param {HTMLTableSectionElement} tbody
 * @param {ClineUsageRow[]} items
 */
function renderUsageRows(tbody, items) {
    clearTbody(tbody);

    if (!items || items.length === 0) {
        setLoadingRow(tbody, "Aucune donnée. Cliquez sur « Importer maintenant ».");
        return;
    }

    items.forEach((row) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/30 transition-colors';

        const taskTd = document.createElement('td');
        taskTd.className = 'py-2 pr-2 text-slate-200 font-mono text-xs';
        taskTd.textContent = row.task_id;

        const dateTd = document.createElement('td');
        dateTd.className = 'py-2 px-2 text-slate-300 text-xs';
        dateTd.textContent = formatTimestamp(row.ts);

        const modelTd = document.createElement('td');
        modelTd.className = 'py-2 px-2 text-slate-300 text-xs';
        modelTd.textContent = row.model_id || '-';

        const inTd = document.createElement('td');
        inTd.className = 'py-2 px-2 text-slate-200 text-right font-mono text-xs';
        inTd.textContent = (row.tokens_in ?? 0).toLocaleString('fr-FR');

        const outTd = document.createElement('td');
        outTd.className = 'py-2 px-2 text-slate-200 text-right font-mono text-xs';
        outTd.textContent = (row.tokens_out ?? 0).toLocaleString('fr-FR');

        const costTd = document.createElement('td');
        costTd.className = 'py-2 pl-2 text-slate-200 text-right font-mono text-xs';
        costTd.textContent = formatCost(row.total_cost);

        tr.appendChild(taskTd);
        tr.appendChild(dateTd);
        tr.appendChild(modelTd);
        tr.appendChild(inTd);
        tr.appendChild(outTd);
        tr.appendChild(costTd);

        tbody.appendChild(tr);
    });
}

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
        let detail = null;
        try {
            const data = await response.json();
            detail = typeof data?.detail === 'string' ? data.detail : null;
        } catch {
            // ignore parse
        }
        const msg = detail || `HTTP ${response.status}`;
        throw new Error(msg);
    }
    return await response.json();
}

/** @returns {Promise<ClineStatusResponse>} */
export async function fetchClineStatus() {
    return await fetchJson('/api/cline/status', { method: 'GET' });
}

/** @returns {Promise<ClineUsageResponse>} */
export async function fetchClineUsage(limit = DEFAULT_LIMIT, offset = 0) {
    const safeLimit = Math.min(Math.max(Number(limit) || DEFAULT_LIMIT, 1), 100);
    const safeOffset = Math.max(Number(offset) || 0, 0);
    return await fetchJson(`/api/cline/usage?limit=${safeLimit}&offset=${safeOffset}`, { method: 'GET' });
}

/** @returns {Promise<ClineImportResponse>} */
export async function importClineLedger() {
    return await fetchJson('/api/cline/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    });
}

export async function initClineSection() {
    // Si la section n'existe pas (fork UI), on ne fait rien.
    const tbody = document.getElementById('cline-usage-tbody');
    const latestImportEl = document.getElementById('cline-latest-import');
    const importBtn = document.getElementById('cline-import-btn');
    const importBtnLabel = document.getElementById('cline-import-btn-label');

    if (!tbody || !latestImportEl || !importBtn || !importBtnLabel) {
        return;
    }

    const tbodyEl = /** @type {HTMLTableSectionElement} */ (tbody);
    const btnEl = /** @type {HTMLButtonElement} */ (importBtn);
    const btnLabelEl = /** @type {HTMLSpanElement} */ (importBtnLabel);

    const refresh = async () => {
        try {
            const [status, usage] = await Promise.all([
                fetchClineStatus(),
                fetchClineUsage(DEFAULT_LIMIT, 0)
            ]);
            latestImportEl.textContent = formatTimestamp(status.latest_ts);
            renderUsageRows(tbodyEl, usage.items);
        } catch (error) {
            console.error('❌ Erreur chargement Cline usage:', error);
            showNotification('Erreur chargement Cline (local)', 'error');
        }
    };

    // Rafraîchit via WebSocket broadcast
    eventBus.on('cline:usage_updated', async () => {
        await refresh();
    });

    // Handler bouton import
    btnEl.addEventListener('click', async () => {
        const previousLabel = btnLabelEl.textContent;
        btnEl.disabled = true;
        btnEl.setAttribute('aria-busy', 'true');

        // UI: remplace le texte uniquement via DOM (sans rendu HTML direct)
        btnLabelEl.textContent = 'Import en cours...';

        try {
            const result = await importClineLedger();
            showNotification(
                `Import Cline: ${result.imported_count} importé(s), ${result.skipped_count} ignoré(s)`,
                'success'
            );
            await refresh();
        } catch (error) {
            console.error('❌ Erreur import Cline:', error);
            showNotification(`Erreur import Cline: ${error.message}`, 'error');
        } finally {
            btnEl.disabled = false;
            btnEl.removeAttribute('aria-busy');
            btnLabelEl.textContent = previousLabel || 'Importer maintenant';
        }
    });

    // Chargement initial
    setLoadingRow(tbodyEl, 'Chargement...');
    await refresh();

    // Rendu icônes (nouvelle card)
    if (window.lucide) {
        window.lucide.createIcons();
    }
}
