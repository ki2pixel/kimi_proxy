/**
 * Module Auto Session
 * 
 * Pourquoi: Gère le toggle d'auto-création de sessions et les notifications
 * liées à la création automatique de sessions selon le provider détecté.
 */

import { getAutoSessionStatus, toggleAutoSession } from './api.js';
import { eventBus, showNotification } from './utils.js';

// ============================================================================
// ÉTAT
// ============================================================================

let isAutoSessionEnabled = true;
let isInitialized = false;

// ============================================================================
// INITIALISATION
// ============================================================================

/**
 * Initialise le module auto-session
 * Pourquoi: Charge le statut initial et configure les écouteurs d'événements
 */
export async function initAutoSession() {
    if (isInitialized) return;
    
    try {
        // Charge le statut depuis le localStorage (persiste entre les sessions)
        const storedEnabled = localStorage.getItem('autoSessionEnabled');
        if (storedEnabled !== null) {
            isAutoSessionEnabled = storedEnabled === 'true';
        } else {
            // Sinon, charge depuis le serveur
            const status = await getAutoSessionStatus();
            isAutoSessionEnabled = status.enabled;
        }
        
        // Met à jour l'UI
        updateToggleUI();
        
        // Écoute les événements WebSocket
        eventBus.on('session:auto_created', handleAutoSessionCreated);
        eventBus.on('auto_session:toggled', handleAutoSessionToggled);
        
        isInitialized = true;
        
    } catch (error) {
        console.error('❌ Erreur initialisation auto-session:', error);
        // Par défaut activé
        isAutoSessionEnabled = true;
        updateToggleUI();
    }
}

// ============================================================================
// TOGGLE
// ============================================================================

/**
 * Bascule l'état de l'auto-session
 * Pourquoi: Permet à l'utilisateur d'activer/désactiver la création auto
 */
export async function toggleAutoSessionState() {
    try {
        const newEnabled = !isAutoSessionEnabled;
        
        // Appelle l'API
        await toggleAutoSession(newEnabled);
        
        // Met à jour l'état local
        isAutoSessionEnabled = newEnabled;
        
        // Persiste dans localStorage
        localStorage.setItem('autoSessionEnabled', String(newEnabled));
        
        // Met à jour l'UI
        updateToggleUI();
        
        // Notification
        showNotification(
            `Auto-session ${newEnabled ? 'activée' : 'désactivée'}`,
            newEnabled ? 'success' : 'info'
        );
        
        console.log(`🔄 Auto-session ${newEnabled ? 'activée' : 'désactivée'}`);
        
    } catch (error) {
        console.error('❌ Erreur toggle auto-session:', error);
        showNotification('Erreur lors du changement de mode', 'error');
    }
}

/**
 * Met à jour l'apparence du toggle selon l'état
 * Pourquoi: Feedback visuel immédiat pour l'utilisateur
 */
function updateToggleUI() {
    const toggle = document.getElementById('autoSessionToggle');
    const knob = document.getElementById('autoSessionKnob');
    
    if (!toggle || !knob) return;
    
    if (isAutoSessionEnabled) {
        toggle.classList.remove('bg-slate-600');
        toggle.classList.add('bg-blue-600');
        knob.classList.add('translate-x-5');
        knob.classList.remove('translate-x-0');
    } else {
        toggle.classList.remove('bg-blue-600');
        toggle.classList.add('bg-slate-600');
        knob.classList.remove('translate-x-5');
        knob.classList.add('translate-x-0');
    }
}

// ============================================================================
// HANDLERS
// ============================================================================

/**
 * Gère la création automatique d'une session
 * Pourquoi: Affiche une notification et met à jour l'UI
 */
function handleAutoSessionCreated(data) {
    console.log('🔄 Session auto créée:', data);
    
    // Notification visuelle
    showNotification(
        data.message || 'Nouvelle session créée automatiquement',
        'info',
        5000  // 5 secondes
    );
    
    // Émet un événement pour les autres modules
    eventBus.emit('auto_session:created', data);
}

/**
 * Gère le changement de statut depuis le serveur
 * Pourquoi: Synchronise l'état si changé depuis un autre client
 */
function handleAutoSessionToggled(data) {
    isAutoSessionEnabled = data.enabled;
    updateToggleUI();
    
    // Persiste
    localStorage.setItem('autoSessionEnabled', String(data.enabled));
    
    console.log('🔄 Auto-session mise à jour depuis le serveur:', data.enabled);
}

// ============================================================================
// GETTERS
// ============================================================================

/**
 * Retourne l'état actuel de l'auto-session
 */
export function isAutoSessionActive() {
    return isAutoSessionEnabled;
}

// ============================================================================
// EXPOSITION GLOBALE
// ============================================================================

/**
 * Expose la fonction toggle globalement pour l'HTML inline
 * Pourquoi: Permet l'utilisation dans onclick="toggleAutoSession()"
 */
export function exposeAutoSessionGlobals() {
    window.toggleAutoSession = toggleAutoSessionState;
}
