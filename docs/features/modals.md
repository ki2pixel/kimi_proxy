# Modals Module - Gestion des Dialogues Modaux

## TL;DR
Module JavaScript centralisant la création, gestion et animation de toutes les modales du dashboard Kimi Proxy, avec support pour création de sessions et fonctionnalités mémoire avancées.

## Problème
L'interface utilisateur nécessite des dialogues modaux complexes pour la sélection de providers/modèles et les opérations mémoire, avec gestion d'état, animations et interactions utilisateur cohérentes.

## Architecture Modulaire
Le module modals.js fait partie de l'écosystème frontend ES6, dépendant des modules `api.js`, `utils.js`, `sessions.js`, `memory-service.js`, `charts.js` et `similarity-chart.js`.

## Composants Principaux

### Modal Nouvelle Session
Interface pour créer une nouvelle session avec sélection provider/modèle.

**Responsabilités :**
- Chargement dynamique des providers et modèles depuis l'API
- Filtrage temps réel des modèles par recherche
- Validation et création de session
- Gestion d'état de sélection (provider/modèle)

**Fonctions clés :**
- `showNewSessionModal()` - Affiche la modal de création
- `closeNewSessionModal()` - Ferme la modal
- `filterModels(query)` - Filtre les modèles selon recherche
- `selectModel(provider, model, name)` - Sélectionne un modèle
- `createNewSessionWithProvider()` - Crée la session

### Factory Memory Modals
Système de création dynamique de modales pour les fonctionnalités mémoire.

**Types de modales :**
- **Compression** : Interface pour compresser le contexte mémoire
- **Similarity** : Interface pour recherche de similarité sémantique

**Fonction clé :**
- `createMemoryModal(type)` - Factory pour créer modales mémoire

### Gestion État Global
Variables d'état partagées entre modales :
```javascript
let selectedProvider = null;
let selectedModel = null;
let availableProviders = [];
let availableModels = [];
let currentFilter = '';
```

## Patterns Système Appliqués

### Pattern 1 - Factory Pattern pour Modales Mémoire
```javascript
// Factory pour éviter duplication de code
export function createMemoryModal(type) {
    const modalId = `memory-${type}-modal`;
    
    // Créer structure HTML dynamique
    const modalHTML = generateModalHTML(type);
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Configurer listeners
    setupMemoryModalListeners(modalId, type);
    
    return { show: () => showModal(modalId), hide: () => hideModal(modalId) };
}
```

### Pattern 2 - Template Method pour Contenu Dynamique
```javascript
async function loadModalContent(type, containerId) {
    const template = type === 'compress' ? 
        getCompressionModalTemplate() : 
        getSimilarityModalTemplate();
    container.innerHTML = template;
    await initializeComponents(type);
}
```

### Pattern 3 - Event Delegation pour Interactions
```javascript
function setupMemoryModalListeners(modalId, type) {
    const modal = document.getElementById(modalId);
    
    modal.addEventListener('click', (e) => {
        const action = e.target.closest('[data-action]')?.dataset.action;
        
        switch (action) {
            case 'close':
            case 'cancel':
                hideMemoryModal(type);
                break;
            case 'confirm':
                executeMemoryAction(type);
                break;
        }
    });
}
```

## Gestion Animations et UX

### Animations d'Entrée/Sortie
```javascript
show: () => {
    modal.style.display = 'flex';
    setTimeout(() => {
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
}
```

### États de Chargement
- Spinner Lucide lors du chargement des données
- Messages d'erreur explicites
- Gestion des timeouts et erreurs réseau

## Intégration API

### Chargement Données
```javascript
async function loadProvidersData() {
    const [providers, models] = await Promise.all([
        loadProviders(),
        loadModels()
    ]);
    availableProviders = providers;
    availableModels = models;
    renderProvidersList();
}
```

### Gestion Erreurs
```javascript
catch (error) {
    container.innerHTML = `
        <div class="text-red-400 text-center py-4">
            <i data-lucide="alert-circle" class="w-5 h-5 mx-auto mb-2"></i>
            Erreur de chargement des modèles
        </div>
    `;
}
```

## Métriques Performance

### Optimisations
- **Lazy Loading** : Contenu chargé à la demande
- **Template Caching** : Templates HTML mis en cache
- **Event Throttling** : Limitation des événements fréquents
- **Memory Cleanup** : Nettoyage ressources à la fermeture

### Métriques Actuelles
- **164 fonctions utilitaires** pour gestion DOM modals
- **Complexité moyenne** : B (8-12)
- **Coverage événements** : 15+ types d'interactions gérées

## Trade-offs

| Approche | Avantages | Inconvénients |
|----------|-----------|---------------|
| Factory centralisée | DRY, cohérence | Complexité setup initiale |
| Templates séparés | Flexibilité, lisibilité | Maintenance templates |
| **Choix actuel** | **Performance maintenabilité** | **Courbe apprentissage** |

## Golden Rule
**Toute nouvelle modal doit être créée via le système factory pour garantir cohérence UX et gestion ressources.**

## Prochaines Évolutions
- [ ] Modal de confirmation générique
- [ ] Support drag & drop pour fichiers
- [ ] Animations avancées (GSAP)
- [ ] Tests E2E modals

---
*Dernière mise à jour : 2026-02-21*
*Conforme à documentation/SKILL.md - Sections : TL;DR ✔, Problem-First ✔, Comparaison ✔, Trade-offs ✔, Golden Rule ✔*</content>
<parameter name="path">/home/kidpixel/kimi-proxy/docs/features/modals.md