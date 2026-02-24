# Brief - Audit complet frontend (Kimi Proxy Dashboard)

## Objectif
Réaliser un audit approfondi de l'architecture frontend du Kimi Proxy Dashboard (Vanilla JS + ES6 modules) afin d'identifier :
- vulnerabilites (XSS/CSRF, injection DOM, supply chain, exposition d'informations)
- optimisations (performance temps reel WebSocket, rendu Chart.js, consommation memoire)
- conformite aux standards internes (.clinerules/codingstandards.md) et bonnes pratiques (KISS/DRY, modularite, accessibilite)

## Contexte technique
- Frontend en Vanilla JS (pas de framework)
- ES6 modules attendus (imports/exports nommes, pas d'export default)
- Pattern EventBus recommande pour decouplage
- WebSocket utilise pour temps reel (metriques, sessions, logs, etc.)
- Chart.js : contexte recent de compatibilite (usage UMD global Chart suite a erreurs d'import) a auditer et cadrer

## Perimetre
1. Architecture modules : structure static/js/, coherence des responsabilites, couplage, imports, dependances circulaires, respect de l'isolation UI.
2. Securite frontend :
   - sinks DOM (innerHTML, insertAdjacentHTML, outerHTML, document.write)
   - manipulation d'URL / query params, stockage local (localStorage/sessionStorage)
   - gestion des erreurs et logs (fuites de donnees sensibles)
   - surface CSRF (si cookies/session)
   - politiques de securite (CSP, Trusted Types si applicable)
3. Performance temps reel :
   - gestion du flux WebSocket (throttling/debounce, backpressure, batch updates)
   - frequence des re-render et mises a jour Chart.js
   - fuites memoire (listeners, timers, charts non detruits)
   - couts DOM (layouts, reflows)
4. Accessibilite (WCAG) : ARIA, navigation clavier, focus management, annonces (aria-live), modales/notifications.
5. Optimisation chargement/assets : strategie de chargement (defer/module/nomodule), cache, duplication de code, poids des assets, splitting sans bundler.

## Livrables
- Rapport d'audit complet (Markdown) incluant :
  - cartographie des modules et flux (WebSocket -> state -> DOM/Chart)
  - liste des constats avec preuves (fichiers + extraits)
  - recommandations priorisees (P0/P1/P2) avec effort estimatif
  - evaluation de conformite vs codingstandards.md

## Contraintes
- Ne pas casser l'architecture existante
- Rester compatible avec les choix actuels (ex: Chart.js UMD global) tant qu'aucun plan de migration n'est valide
- Pas de frameworks. ES6 modules + EventBus, eviter etat global

## Criteres de reussite
- Rapport actionnable avec recommandations claires, ordonnees par risque/impact
- Couverture : architecture, securite, performance WebSocket, accessibilite, optimisation chargement
