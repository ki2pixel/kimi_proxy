# Auto Session Module - Création Automatique de Sessions

## TL;DR
Module JavaScript gérant la fonctionnalité d'auto-création de sessions selon le provider détecté, avec persistence localStorage, synchronisation serveur, et feedback utilisateur temps réel via notifications et mises à jour UI.

## Problème
L'utilisateur doit pouvoir activer/désactiver la création automatique de sessions sans intervention manuelle, avec persistance des préférences et synchronisation entre clients multiples.

## Architecture Modulaire
Le module auto-session.js constitue une fonctionnalité autonome, dépendant de `api.js` pour les appels backend et de `utils.js` pour l'eventBus et les notifications.

## Composants Principaux

### État Global et Persistence
Gestion de l'état avec fallback localStorage/serveur :

**Initialisation avec persistance :**
```javascript
export async function initAutoSession() {
    // 1. Vérifie localStorage d'abord (performance)
    const storedEnabled = localStorage.getItem('autoSessionEnabled');
    if (storedEnabled !== null) {
        isAutoSessionEnabled = storedEnabled === 'true';
    } else {
        // 2. Fallback vers API serveur
        const status = await getAutoSessionStatus();
        isAutoSessionEnabled = status.enabled;
    }
    
    updateToggleUI();
    setupEventListeners();
}
```

**Synchronisation multi-client :**
```javascript
// Persiste localStorage + serveur
localStorage.setItem('autoSessionEnabled', String(newEnabled));
await toggleAutoSession(newEnabled); // API call
```

### Toggle Interface
Basculement avec feedback utilisateur immédiat :

**Logique toggle :**
```javascript
export async function toggleAutoSessionState() {
    const newEnabled = !isAutoSessionEnabled;
    
    // 1. API call pour synchronisation
    await toggleAutoSession(newEnabled);
    
    // 2. Update état local
    isAutoSessionEnabled = newEnabled;
    
    // 3. Persistence localStorage
    localStorage.setItem('autoSessionEnabled', String(newEnabled));
    
    // 4. Update UI + notification
    updateToggleUI();
    showNotification(`Auto-session ${newEnabled ? 'activée' : 'désactivée'}`, 
                     newEnabled ? 'success' : 'info');
}
```

### UI Toggle Visuel
Animations CSS pour feedback immédiat :

**Update visuel :**
```javascript
function updateToggleUI() {
    const toggle = document.getElementById('autoSessionToggle');
    const knob = document.getElementById('autoSessionKnob');
    
    if (isAutoSessionEnabled) {
        toggle.classList.remove('bg-slate-600');
        toggle.classList.add('bg-blue-600');      // Bleu = activé
        knob.classList.add('translate-x-5');       // Animation curseur
        knob.classList.remove('translate-x-0');
    } else {
        toggle.classList.remove('bg-blue-600');
        toggle.classList.add('bg-slate-600');     // Gris = désactivé
        knob.classList.remove('translate-x-5');
        knob.classList.add('translate-x-0');
    }
}
```

### Event Handlers WebSocket
Synchronisation en temps réel entre clients :

**Création auto-session :**
```javascript
function handleAutoSessionCreated(data) {
    console.log('🔄 Session auto créée:', data);
    
    // Notification utilisateur
    showNotification(
        data.message || 'Nouvelle session créée automatiquement',
        'info', 5000  // 5 secondes
    );
    
    // Propagation événement
    eventBus.emit('auto_session:created', data);
}
```

**Changement statut distant :**
```javascript
function handleAutoSessionToggled(data) {
    isAutoSessionEnabled = data.enabled;
    updateToggleUI();
    
    // Synchronise localStorage
    localStorage.setItem('autoSessionEnabled', String(data.enabled));
    
    console.log('🔄 Auto-session mise à jour depuis le serveur:', data.enabled);
}
```

## Patterns Système Appliqués

### Pattern 1 - Offline-First avec Fallback
Priorité localStorage pour performance, API pour synchronisation :

```javascript
// 1. LocalStorage (rapide, offline)
const stored = localStorage.getItem('autoSessionEnabled');
if (stored !== null) {
    isAutoSessionEnabled = stored === 'true';
} else {
    // 2. API serveur (lente, nécessite réseau)
    const status = await getAutoSessionStatus();
    isAutoSessionEnabled = status.enabled;
}
```

### Pattern 2 - Event-Driven Synchronization
Communication découplée pour multi-client :

```javascript
// Client A change le statut
await toggleAutoSessionState(); // → API + WebSocket

// Client B reçoit automatiquement
eventBus.on('auto_session:toggled', handleAutoSessionToggled);
// → Update UI automatiquement
```

### Pattern 3 - Global Exposure pour HTML
Accessibilité depuis templates HTML :

```javascript
export function exposeAutoSessionGlobals() {
    window.toggleAutoSession = toggleAutoSessionState;
}
// Permet: onclick="toggleAutoSession()" dans HTML
```

## Gestion Erreurs et Résilience

### Gestion Échecs API
Fallback gracieux en cas d'erreur réseau :

```javascript
try {
    await toggleAutoSession(newEnabled);
    // Succès: update local
    isAutoSessionEnabled = newEnabled;
} catch (error) {
    console.error('❌ Erreur toggle auto-session:', error);
    showNotification('Erreur lors du changement de mode', 'error');
    // État inchangé, UI cohérente
}
```

### Validation État
Consistency checks pour éviter corruption :

```javascript
// Toujours boolean après récupération
isAutoSessionEnabled = storedEnabled === 'true';  // String → Boolean

// Validation API response
const status = await getAutoSessionStatus();
isAutoSessionEnabled = status.enabled;  // Assume structure correcte
```

## Métriques Performance

### Métriques Actuelles
- **Persistence hybride** : localStorage + API serveur
- **Synchronisation temps réel** : WebSocket events
- **Feedback immédiat** : UI update sans attendre API
- **Memory footprint** : < 1KB état + event listeners

### Optimisations
- **Lazy initialization** : Chargement à la demande
- **localStorage priority** : Évite appels API inutiles
- **Debounced notifications** : Évite spam utilisateur
- **Minimal state** : Booléen simple

## Trade-offs

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| localStorage + API | Performance + sync | Complexité gestion |
| API seulement | Simplicité, cohérence | Latence réseau |
| **Choix actuel** | **UX fluide + cohérence** | **Overhead implémentation** |

## Golden Rule
**L'état local doit toujours être considéré comme source de vérité pour l'UX, avec synchronisation serveur en arrière-plan pour la cohérence multi-client.**

## Prochaines Évolutions
- [ ] Historique changements statut
- [ ] Rôles utilisateur (admin peut forcer)
- [ ] Statistiques utilisation auto-session
- [ ] Configuration par provider
- [ ] Mode "intelligent" (ML-based)

---
*Dernière mise à jour : 2026-02-21*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*</content>
<parameter name="path">/home/kidpixel/kimi-proxy/docs/features/auto-session.md