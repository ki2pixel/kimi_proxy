# Étude de faisabilité — Intégration Kimi Proxy ↔ Extension Cline via OAuth 2.0 (ChatGPT Subscription)

## Objectif
Analyser l’architecture de l’extension **Cline** pour comprendre comment elle gère l’authentification **OAuth 2.0** (ChatGPT Subscription), identifier les points d’accès exploitables dans les logs et fichiers JSON de **`/home/kidpixel/.cline`**, et évaluer la possibilité de connecter **Kimi Proxy** afin d’**intercepter** le trafic et de **comptabiliser les tokens** *sans casser* l’architecture existante.

## Portée (Scope)
### Inclus
- Reverse-engineering **lecture seule** du code de Cline (repo local: `research/cline-main/`).
- Exploration **lecture seule** des artefacts Cline sur la machine (dossier: `/home/kidpixel/.cline`).
- Identification des composants:
  - Auth/OAuth (login, refresh token, storage, scopes).
  - Transport réseau (fetch/undici/node-http, websockets, SSE).
  - Couche d’abstraction API (OpenAI / ChatGPT subscription endpoints, éventuels proxies).
- Évaluation technique des stratégies d’intégration côté Kimi Proxy:
  - Proxy HTTP(S) explicite (base URL, agent, env var, configuration extension).
  - Interception via configuration de l’extension (si supportée) plutôt que MITM.
  - Interception applicative (instrumentation du client HTTP interne) **uniquement** si l’extension est modifiable (mais ici: étude de faisabilité, pas d’implémentation).

### Exclus
- Aucune exécution de scripts externes téléchargés.
- Aucune tentative de capture de credentials, ni export/transmission de secrets.
- Aucune modification du runtime Kimi Proxy (recherche uniquement).
- Pas de tentative de MITM (certificats, TLS interception) dans cette étude.

## Contraintes & règles de sécurité
- Respect strict de `.clinerules/prompt-injection-guard.md`.
- Ne jamais afficher ni exfiltrer:
  - tokens OAuth, refresh tokens, cookies, headers Authorization
  - contenu `.env` / secrets / clés API
- Pour les logs JSON volumineux: utiliser **`json_query_jsonpath`** (pattern “Sniper”), éviter de charger des fichiers > 1000 lignes.

## Sources & emplacements
- Code Cline: `research/cline-main/`
- Données locales Cline: `/home/kidpixel/.cline`
- Kimi Proxy (référence architecture): `src/kimi_proxy/` + docs `docs/`

## Questions à résoudre
1. **OAuth 2.0**: quel flow est implémenté (PKCE, device code, auth code) ?
2. Où sont stockés les tokens OAuth (OS keychain, VS Code secret storage, fichiers JSON) ?
3. Comment Cline route ses requêtes:
   - endpoint OpenAI “platform” (api.openai.com)
   - endpoint ChatGPT subscription (chatgpt.com / oauth endpoints)
   - endpoints intermédiaires
4. Le client HTTP est-il configurable (baseURL, proxy, env var `HTTPS_PROXY`, etc.) ?
5. Peut-on compter les tokens:
   - à partir des logs (usage/tokens dans réponses)
   - en instrumentant le payload (tiktoken côté proxy)
   - via événements internes (telemetry)
6. Risques:
   - sécurité/privacité
   - compatibilité IDE (PyCharm)
   - maintenance: dépendance au code Cline

## Livrables attendus
- Rapport de faisabilité (Markdown) comprenant:
  - Cartographie des modules Cline liés à auth/transport
  - Inventaire des fichiers `.cline` pertinents et de leurs schémas JSON
  - Analyse des points d’intégration (options recommandées)
  - Recommandation finale: **Faisable / Partiellement faisable / Non faisable** avec justification
  - Liste des risques & mitigations

## Critères de succès
- Identifier explicitement:
  - les fichiers/modules Cline responsables d’OAuth
  - le mécanisme de stockage des tokens
  - le chemin réseau principal (domaines, endpoints, transport)
  - les options réalistes pour brancher Kimi Proxy (sans MITM)
- Produire un rapport actionnable avec preuves (chemins fichiers + extraits minimaux).
