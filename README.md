# Kimi Proxy

**TL;DR**: Kimi Proxy est un middleware MCP transparent qui s'insère entre votre IDE (Cline, Continue.dev) et n'importe quel provider LLM. Il applique automatiquement du tool-fixing, du pruning de contexte et de la compression intelligente pour réduire votre facture API de 20-40%, sans jamais stocker vos conversations.

J'étais fatigué de voir mes tokens disparaître dans des réponses tool verbeuses, des boucles de retry infinies et des contextes qui gonflaient sans raison. Avec Cline et Continue.dev, je passais d'un provider à l'autre (OpenRouter, Kimi, Gemini, OpenAI) sans visibilité sur ce qui était réellement envoyé. Chaque session de debugging devenait un gouffre à tokens : 500 tokens de logs système pour une réponse tool, des arguments malformés qui déclenchaient des erreurs 400, des anciens résultats d'outil qui encombraient le contexte sans plus servir.

Alors j'ai construit Kimi Proxy. Ce n'est pas un dashboard. Ce n'est pas une base de données de chat. C'est un filtre intelligent : votre IDE parle au proxy, le proxy nettoie et optimise, le proxy parle au provider. Le résultat : moins de tokens gaspillés, moins d'erreurs tool, et la liberté de changer de provider sans toucher à une ligne de configuration.

## Ce que ça résout vraiment

### ❌ Avant : le tunnel brut
- Envoyer directement au provider = contexte brut, tokens perdus, tool errors
- Changer de provider = reconfiguration manuelle dans l'IDE
- Arguments tool malformés = erreurs 400 et retry inutiles
- Anciens résultats d'outil qui dominent le contexte actuel
- Pas de visibilité sur ce qui est réellement transmis

### ✅ Après : le middleware intelligent
- **Passthrough Session-Less** : Cline envoie `X-Target-Base-URL` + `Authorization`, le proxy applique les features MCP sans créer de session
- **MCP Tool Fixing** : IDs manquants générés automatiquement, arguments malformés normalisés avant d'atteindre le provider
- **Context Sanitizer** : Messages tool/console verbeux masqués à la volée, 20-40% d'économie sans perte d'information
- **Intelligent Compression** : Pruning de contexte et résumé automatique quand la fenêtre approche ses limites
- **Agnosticisme total** : OpenRouter, OpenAI, Gemini, Kimi, Mistral, n'importe quel provider compatible OpenAI

### L'analogie du filtre à eau

Pensez à votre conversation LLM comme à l'eau du robinet. Sans filtre, vous buvez tout : le chlore, les sédiments, les impuretés. Avec un filtre, l'eau est potable instantanément sans que vous ayez à penser au processus.

Kimi Proxy, c'est le filtre entre votre IDE et le provider. Vous ne voyez pas le filtre, mais vous buvez de l'eau propre.

## Les trois features de nettoyage

### 1. Tool Fixing (MCP) — La correction automatique

Cline et les autres IDEs envoient parfois des appels tool incomplets : IDs manquants, arguments mal formés, structures JSON cassées. Le proxy intercepte et répare avant l'envoi au provider.

```python
# ❌ Ce que Cline envoie parfois
{"tool_calls": [{"id": null, "function": {"name": "read_file", "arguments": "{path: '/tmp/test'}"}}]}

# ✅ Ce que le proxy transmet au provider
{"tool_calls": [{"id": "call_abc123", "function": {"name": "read_file", "arguments": "{\"path\": \"/tmp/test\"}"}}]}
```

### 2. Context Sanitizer — Le tri automatique

Le sanitizer détecte automatiquement les messages > 1000 tokens de type tool/console, les remplace par des placeholders récupérables, et stocke le contenu original indexé par hash.

```python
# ❌ Sans sanitizer : 1500 tokens de JSON tool
{"role": "tool", "content": "{\"status\":200,\"data\":[{\"id\":1,\"name\":...1500 tokens...}]}", "tool_call_id": "call_123"}

# ✅ Avec sanitizer : 50 tokens de placeholder
{"role": "tool", "content": "[MASKED: hash=abc123, preview=API response with 47 items]", "tool_call_id": "call_123"}
```

Résultat : 20-40% d'économie de tokens. Le contenu original est récupérable via `/api/mask/{hash}` si vous en avez besoin.

### 3. Intelligent Compression — Le pruning de contexte

Quand la fenêtre de contexte approche ses limites, le proxy active le pruning : les anciens résultats d'outil sont tronqués, les messages système sont préservés, et le reste est résumé intelligemment. Pas de perte de session, pas de redémarrage à zéro.

## Architecture : 5 couches modulaires

J'ai commencé avec un fichier monolithique de 3,073 lignes. C'était comme avoir toute une maison dans une seule pièce. Maintenant, c'est organisé par étages :

```
┌─────────────────────────────────────────┐
│           API Layer (FastAPI)          │  ← Interface REST /v1/chat/completions
├─────────────────────────────────────────┤
│         Services Layer                 │  ← Rate Limiting, Validation
├─────────────────────────────────────────┤
│         Features Layer                 │  ← Sanitizer, MCP Tool Fixing, Compression
├─────────────────────────────────────────┤
│         Proxy Layer (HTTPX)            │  ← Passthrough session-less vers provider
├─────────────────────────────────────────┤
│         Core Layer                     │  ← Tiktoken, Models, Configuration
└─────────────────────────────────────────┘
```

**Pourquoi cette structure ?** Chaque couche ne dépend que de celles en dessous. Je peux tester le sanitizer sans démarrer l'API. Je peux remplacer le proxy HTTPX sans casser les features MCP. C'est maintenabilité et évolutivité.

### Le flux d'une requête

```
Cline/Continue.dev
        ↓
    POST /v1/chat/completions
        ↓
    Headers: X-Target-Base-URL + Authorization
        ↓
    ┌────────────────────────────────────┐
    │  1. Fix tool calls                 │
    │  2. Observation masking (pruning)  │
    │  3. Context sanitization           │
    └────────────────────────────────────┘
        ↓
    Provider cible (OpenRouter, OpenAI, etc.)
        ↓
    Réponse streamée ou complète
```

**Pas de sessions SQLite. Pas de stockage de chat. Pas de frontend.** Le proxy est stateless : il transforme la requête, la forward, et oublie.

## MCP Gateway : appeler les serveurs MCP locaux via HTTP

Des serveurs MCP tournent en local (compression, filesystem, thinking), mais vous n'avez pas envie que chaque client connaisse leurs ports et base URL. Le MCP Gateway est le point d'entrée unique.

`POST /api/mcp-gateway/{server_name}/rpc` forwarde une requête JSON-RPC 2.0 vers le serveur MCP local ; la réponse est renvoyée telle quelle, avec un **Observation Masking** automatique pour éviter les retours gigantesques.

| Serveur | base_url |
|---|---|
| `context-compression` | `http://127.0.0.1:8001` |
| `sequential-thinking` | `http://127.0.0.1:8003` |
| `fast-filesystem` | `http://127.0.0.1:8004` |
| `json-query` | `http://127.0.0.1:8005` |
| `mcp-pruner` | `http://127.0.0.1:8006` |

```bash
curl -sS \
  -X POST http://localhost:8000/api/mcp-gateway/fast-filesystem/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Démarrage rapide

Vous avez 2 minutes. C'est tout ce qu'il vous faut.

```bash
# 1. Démarrer le proxy
./bin/kimi-proxy start

# 2. Configurer Cline
# Dans les settings de Cline, définir :
#   Base URL : http://localhost:8000/v1/chat/completions
#   Modèle   : openai/gpt-4 (ou n'importe quel modèle)
#
# Le proxy lit automatiquement X-Target-Base-URL et Authorization
# depuis les headers envoyés par Cline.
```

### Configuration Continue (optionnel)

```bash
cp config.yaml ~/.continue/config.yaml
```

Continue.dev utilisera automatiquement les modèles configurés.

## Les modèles que j'utilise

J'ai testé 20+ modèles pour trouver le meilleur équilibre coût/performance. Voici mes préférés :

| Modèle | Provider | Pourquoi je l'aime | Contexte |
|--------|----------|-------------------|----------|
| `kimi-code/kimi-for-coding` | Kimi Code | Le meilleur pour le code — thinking intégré | 256K |
| `nvidia/kimi-k2.5` | NVIDIA | Rapide et pas cher — $0.001/1K tokens | 256K |
| `mistral/codestral-2501` | Mistral | Spécialisé coding — autocomplete incroyable | 256K |
| `openrouter/aurora-alpha` | OpenRouter | Équilibre parfait — bon marché et capable | 128K |
| `gemini/gemini-2.5-pro` | Gemini | Le plus puissant — multimodal et 1M context | 1M |

**Mon choix quotidien** : Kimi Code pour le développement sérieux, NVIDIA K2.5 pour les tests rapides.

### Le truc des providers

Chaque provider a ses particularités. Kimi Code est cher mais incroyablement intelligent. NVIDIA est ultra-rapide mais limité à 3 modèles. OpenRouter me donne accès à tout mais avec une latence supplémentaire.

Le système gère tout ça automatiquement : vous choisissez le modèle dans Cline, le proxy s'occupe du reste.

## Au quotidien : comment je l'utilise

### La CLI

```bash
./bin/kimi-proxy start      # Démarrer
./bin/kimi-proxy status     # Vérifier le port et l'état
./bin/kimi-proxy logs       # Voir les dernières requêtes
./bin/kimi-proxy stop       # Arrêt propre
```

### Avec Cline

Une fois configuré, Cline envoie tout à travers le proxy sans que j'y pense. Le proxy applique le sanitizer, fixe les tools, et forwards vers le provider cible. Je change de provider en un clic dans Cline, sans toucher à `config.toml`.

### Quand je vois la compression agir

Quand le contexte approche ses limites, le pruning s'active automatiquement :
1. Les messages système sont préservés
2. Les 5 derniers échanges sont conservés
3. Les anciens résultats d'outil sont tronqués
4. La conversation continue sans interruption

## Trade-offs

| Approche | Avantage | Limite |
|---|---|---|
| Direct au provider | Latence minimale, pas d'intermédiaire | Contexte brut, tool errors, tokens gaspillés |
| Session-based avec persistance | Historique, métriques détaillées | Configuration requise, stockage SQLite |
| **Kimi Proxy Middleware** | **Zéro config, features MCP automatiques** | **Pas de persistance des conversations** |

## La Règle d'Or : Transparence totale

**Le principe** : Chaque transformation appliquée doit être explicable et réversible.

Je voulais savoir exactement ce que le proxy modifiait. Pas de boîte noire. Tiktoken compte précisément chaque entrée/sortie. Le sanitizer stocke le contenu original pour récupération. Le tool fixing logge les corrections appliquées. Si le proxy change quelque chose, vous pouvez le voir et le récupérer.

## Dépannage rapide

### Erreur 401 ?
Vérifiez que le header `Authorization` est bien envoyé par Cline. Le proxy le transmet tel quel au provider cible.

### X-Target-Base-URL manquant ?
Assurez-vous que Cline envoie bien le header `X-Target-Base-URL` (ex: `https://api.openai.com/v1`). Sans ce header, le proxy tente le fallback legacy via `config.toml`.

### Port déjà utilisé ?
```bash
./bin/kimi-proxy stop && ./bin/kimi-proxy start
```

## Métriques Projet

### Architecture 5 Couches
- **87 fichiers Python** de production (dans `src/` et `scripts/`)
- **14 177 lignes de code** Python (hors commentaires et lignes vides)
- **18 répertoires** structurés par responsabilité dans le cœur du code
- **137 fichiers Python totaux** (incluant 50 fichiers de tests unitaires et d'intégration)

### API Layer
- **44 routes HTTP** effectives pour **44 couples méthode+chemin uniques**
- **Complexité moyenne** : A (3.95)

### Base de Données
- **110 opérations SQL** limitées aux features MCP et sanitizer (pas de stockage de chat)
- **14 migrations de base de données** (ALTER TABLE) appliquées automatiquement au démarrage

## Pourquoi je partage ça

J'ai passé des mois à optimiser ma consommation LLM. Au début, c'était juste un script perso. Puis j'ai ajouté le sanitizer, la compression, l'architecture modulaire...

Aujourd'hui, c'est un middleware qui me fait économiser des centaines d'euros chaque mois. Si ça peut aider d'autres développeurs à réduire leur facture API et à comprendre ce qui est réellement envoyé aux providers, tant mieux.

---

**Note technique** : Le projet est optimisé pour Cline + Continue.dev, mais fonctionne avec n'importe quel client compatible OpenAI. Configurez simplement `http://localhost:8000/v1/chat/completions` comme endpoint et envoyez `X-Target-Base-URL` + `Authorization` dans les headers.
