# 🚀 Kimi Proxy Dashboard

**TL;DR**: Je construis un proxy transparent qui me fait économiser 20-40% de tokens LLM tout en me montrant exactement ce que je consomme en temps réel.

J'étais fatigué de payer $30/mois pour des services de transcription alors que les APIs me coûtaient $0.36/heure. Avec Continue.dev dans PyCharm, je voyais bien mes tokens s'envoler, mais je ne savais pas combien ni pourquoi. Pire encore, je devais choisir entre perdre mon contexte ou payer encore plus.

Alors j'ai construit Kimi Proxy Dashboard. C'est comme avoir un compteur intelligent entre mon IDE et les APIs LLM; il intercepte tout, compte précisément les tokens avec Tiktoken, et me montre exactement où je dépense. Le meilleur? Il compresse automatiquement les conversations verbeuses pour me faire économiser jusqu'à 40% de tokens sans que je perde l'essentiel.

![Dashboard](https://img.shields.io/badge/Dashboard-Live-success?style=for-the-badge)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-Realtime-blue?style=for-the-badge)
![Log Watcher](https://img.shields.io/badge/Log%20Watcher-PyCharm-purple?style=for-the-badge)
![Architecture](https://img.shields.io/badge/Architecture-Modulaire-orange?style=for-the-badge)

## Ce que ça résout vraiment

### ❌ Avant : La boîte noire des tokens
- Pas de visibilité sur ma consommation réelle
- Contexte qui disparaît au milieu d'une conversation importante  
- Factures API qui montent sans comprendre pourquoi
- Perte de productivité à devoir recréer le contexte

### ✅ Après : Le contrôle total
- **Jauge visuelle instantanée** : Je vois exactement où j'en suis (Vert → Jaune → Rouge)
- **Économie automatique** : Le sanitizer masque les messages tools/console verbeux
- **Compression intelligente** : Un bouton d'urgence quand je dépasse 85% du contexte
- **Historique complet** : Chaque token compté avec sa source (Proxy, Logs, CompileChat, Erreur)

### 🔌 Proxy Multi-Provider
- Redirection transparente vers **8 providers** : Kimi Code, NVIDIA, Mistral, OpenRouter, SiliconFlow, Groq, Cerebras, Gemini
- Streaming SSE et requêtes non-streaming supportées
- Sélection granulaire du modèle dans l'UI (20+ modèles disponibles)
- Interception automatique des requêtes `chat/completions`
- Injection robuste des clés API depuis `config.toml`
- Mise à jour automatique du header `Host` pour éviter les erreurs 401
- Conservation de la latence temps réel

## L'astuce qui change tout : Le Sanitizer

J'ai remarqué que 30-40% de mes tokens étaient gaspillés dans des messages tools/console que je ne lisais jamais. C'est comme avoir un restaurant où le serveur vous lit à voix haute les tickets de cuisine - inutile et verbeux.

### ❌ L'approche naïve
```python
# Envoyer tout à l'API, y compris le bruit
messages = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Help me debug"},
    {"role": "assistant", "content": "I'll help"},
    {"role": "tool", "content": "[500+ tokens de logs système]"}  # Gaspillé!
]
```

### ✅ L'approche intelligente
```python
# Masquer ce qui n'apporte pas de valeur
messages = [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Help me debug"},
    {"role": "assistant", "content": "I'll help"},
    # Message tool masqué automatiquement, récupérable si besoin
]
```

Le sanitizer détecte automatiquement les messages > 1000 tokens de type tool/console, les masque pendant l'envoi, et les stocke pour récupération ultérieure. Résultat : 20-40% d'économie de tokens sans perte d'information.

## Les trois phases de gestion du contexte

Pensez à votre conversation comme à un restaurant. Le sanitizer, c'est le serveur qui ne vous lit pas les tickets de cuisine. MCP, c'est votre sommelier qui se souvient de vos préférences. La compression, c'est quand vous demandez l'addition et le serveur vous résume ce que vous avez commandé.

### Phase 1 : Sanitizer - Le tri automatique
Le système masque les messages tools/console verbeux (>1000 tokens) et les remplace par une note "contenu masqué". C'est récupérable via `/api/mask/{hash}` si vous en avez besoin.

### Phase 2 : MCP - La mémoire à long terme  
Détecte les balises `<mcp-memory>`, `@memory[]`, `@recall()` pour distinguer ce qui est stocké à long terme vs ce qui fait partie de la conversation actuelle. Indicateur violet/rose sur le dashboard.

### Phase 3 : MCP & Compression - L'intelligence augmentée
Quand vous dépassez 85% du contexte, un bouton apparaît. Mais ce n'est pas tout :

**Compression Intelligente** : Préserve les messages système, garde les 5 derniers échanges, résume le reste avec le LLM actuel.

**MCP Avancé** : Intégration de serveurs MCP externes pour des optimisations de niveau supérieur :
- **Qdrant MCP** : Recherche sémantique en <50ms pour trouver des patterns similaires dans votre historique
- **Context Compression MCP** : Compression avancée 20-80% avec stockage persistant
- **Routage Intelligent** : Le système choisit automatiquement le provider avec le meilleur ratio capacité/coût/latence
- **Mémoire Standardisée** : Distinction entre mémoires fréquentes (patterns), épisodiques (conversations), et sémantiques (vecteurs)

### Phase 4 : Nouveaux Serveurs MCP - L'écosystème étendu
Quatre serveurs MCP supplémentaires pour étendre les capacités du proxy :

**Shrimp Task Manager MCP** (14 outils) : Gestion de tâches complète avec priorisation, dépendances et analyse de complexité. Intègre `get_tasks`, `parse_prd`, `expand_task`, `analyze_project_complexity` et plus.

**Sequential Thinking MCP** (1 outil) : Raisonnement séquentiel structuré pour résoudre des problèmes complexes étape par étape, avec support de branches et révisions.

**Fast Filesystem MCP** (25 outils) : Opérations fichiers haute performance - lecture, écriture, recherche de code, édition block-safe, compression, synchronisation de répertoires.

**JSON Query MCP** (3 outils) : Requêtes JSON avancées avec JSONPath, recherche de clés et valeurs dans de gros fichiers JSON.

## Le Dashboard en temps réel

C'est comme avoir un tableau de bord de voiture pour votre conversation LLM. La jauge change de couleur au fur et à mesure que vous consommez votre contexte, et vous voyez exactement d'où viennent les tokens.

### La magie du Log Watcher
Continue.dev écrit tout dans `~/.continue/logs/core.log`. Mon système surveille ce fichier en temps réel, extrait les métriques, et les fusionne intelligemment avec les données du proxy.

**Priorité de fusion** : CompileChat (violet) > Erreur (rouge) > Proxy (bleu) > Logs (vert)

Le résultat? Une vue unifiée et précise de votre consommation, même si vous utilisez plusieurs sources de données.

### Ce que vous voyez
- **Jauge de contexte** : Vert (sûr) → Jaune (attention) → Rouge (urgent)
- **Graphique historique** : Évolution des tokens dans le temps
- **Source des tokens** : Couleur selon l'origine
- **Export instantané** : CSV ou JSON pour analyse

## Comment ça marche : L'architecture modulaire

J'ai commencé avec un fichier monolithique de 3,073 lignes. C'était comme avoir toute une maison dans une seule pièce - impossible à entretenir. Maintenant, c'est organisé par étages :

```
┌─────────────────────────────────────────┐
│           API Layer (FastAPI)          │  ← Interface utilisateur
├─────────────────────────────────────────┤
│         Services Layer                 │  ← WebSocket, Rate Limiting  
├─────────────────────────────────────────┤
│         Features Layer                 │  ← Sanitizer, MCP, Compression
├─────────────────────────────────────────┤
│         Proxy Layer                    │  ← Routage vers les APIs
├─────────────────────────────────────────┤
│         Core Layer                     │  ← Database, Tokens, Models
└─────────────────────────────────────────┘
```

**Pourquoi cette structure?** Chaque couche ne dépend que de celles en dessous. Je peux tester le système de tokens sans démarrer l'API. Je peux remplacer le sanitizer sans casser le proxy. C'est maintenabilité et évolutivité.

## Installation rapide

Vous avez 5 minutes? C'est tout ce qu'il vous faut.

```bash
# 2. Configurer vos clés API (méthode recommandée)
# Copier le template et éditer avec vos vraies clés
cp .env.example .env
# Éditer .env avec vos clés API (voir section ci-dessous)

# 3. Démarrer (chargement automatique des variables d'environnement)
./scripts/start.sh
# Dashboard sur http://localhost:8000
```

### Configuration des variables d'environnement

Au lieu d'éditer manuellement `config.toml`, vous pouvez utiliser le fichier `.env` pour une configuration plus simple et sécurisée :

```bash
# Copier le template
cp .env.example .env

# Éditer avec vos vraies clés API
nano .env  # ou votre éditeur préféré
```

**Variables requises :**
- `KIMI_API_KEY` : Clé principale Kimi Code
- `NVIDIA_API_KEY` : Pour les modèles Kimi sur NVIDIA
- `MISTRAL_API_KEY` : Pour les modèles Mistral AI

**Variables optionnelles (tiers gratuits disponibles) :**
- `OPENROUTER_API_KEY` : Accès multi-provider
- `SILICONFLOW_API_KEY` : Crédits gratuits disponibles
- `GROQ_API_KEY` : Inférence ultra-rapide, tier gratuit
- `CEREBRAS_API_KEY` : Tier gratuit disponible
- `GEMINI_API_KEY` : Tier gratuit disponible

**Utilisation automatique :**
Le script `./scripts/start.sh` charge automatiquement le fichier `.env` s'il existe. Si le fichier n'existe pas, il affiche des instructions pour le créer.

Le fichier `.env` est automatiquement ignoré par Git pour éviter de committer vos clés API.

### Configuration Continue (optionnel)
```bash
cp config.yaml ~/.continue/config.yaml
```
Continue.dev utilisera automatiquement les modèles configurés.

## Les modèles que j'utilise

J'ai testé 20+ modèles pour trouver le meilleur équilibre coût/performance. Voici mes préférés :

| Modèle | Provider | Pourquoi je l'aime | Contexte |
|--------|----------|-------------------|----------|
| `kimi-code/kimi-for-coding` | 🌙 Kimi Code | **Le meilleur pour le code** - thinking intégré | 256K |
| `nvidia/kimi-k2.5` | 🟢 NVIDIA | **Rapide et pas cher** - $0.001/1K tokens | 256K |
| `mistral/codestral-2501` | 🔷 Mistral | **Spécialisé coding** - autocomplete incroyable | 256K |
| `openrouter/aurora-alpha` | 🔀 OpenRouter | **Équilibre parfait** - bon marché et capable | 128K |
| `gemini/gemini-2.5-pro` | 💎 Gemini | **Le plus puissant** - multimodal et 1M context | 1M |

**Mon choix quotidien** : Kimi Code pour le développement sérieux, NVIDIA K2.5 pour les tests rapides.

### Le truc des providers
Chaque provider a ses particularités. Kimi Code est cher mais incroyablement intelligent. NVIDIA est ultra-rapide mais limité à 3 modèles. OpenRouter me donne accès à tout mais avec une latence supplémentaire.

Le système gère tout ça automatiquement - vous choisissez juste dans l'interface.

## Au quotidien : Comment je l'utilise

### Le Dashboard
Ouvrez `http://localhost:8000`. C'est là que je passe ma journée :

- **Jauge de contexte** : Je vois quand j'approche des limites (vert → jaune → rouge)
- **Logs en temps réel** : Chaque requête apparaît instantanément avec sa source
- **Nouvelle session** : Je change de provider/modèle en un clic
- **Export** : Je télécharge CSV pour analyser mes coûts mensuels

### La CLI que j'adore
```bash
./bin/kimi-proxy start      # Démarrer
./bin/kimi-proxy status     # "Running on port 8000, 3 active sessions"
./bin/kimi-proxy logs       # Voir les dernières requêtes
./bin/kimi-proxy stop       # Arrêt propre
```

### L'intégration Continue.dev
Une fois configuré, Continue.dev envoie tout à travers le proxy sans que j'y pense. Les tokens apparaissent magiquement sur le dashboard.

### Quand j'utilise la compression
Le bouton rouge apparaît à 85% du contexte. Un clic, et le système :
1. Préserve mes instructions système
2. Garde les 5 derniers échanges  
3. Résume tout le reste intelligemment
4. Me fait économiser 60% de tokens

C'est le bouton "oh non je vais perdre mon contexte" qui me sauve la vie.

## La Règle d'Or : Transparence totale

**Le principe** : Chaque token compté doit être visible, expliqué et optimisable.

Je voulais savoir exactement ce que je paie. Pas de "coûts estimés", pas de "tokens approximatifs". Tiktoken compte précisément chaque entrée/sortie. Le dashboard me montre la source exacte. Le sanitizer me fait économiser ce qui est gaspillé.

## Dépannage rapide

### Erreur 401?
Vérifiez votre `api_key` dans `config.toml`. Le proxy met automatiquement à jour le header `Host` - c'est une erreur classique que j'ai déjà résolue.

### Log Watcher ne détecte rien?
Continue doit écrire dans `~/.continue/logs/core.log`. Vérifiez `/health` pour voir si le fichier existe.

### Port déjà utilisé?
```bash
./bin/kimi-proxy stop && ./bin/kimi-proxy start
```

### Base de données corrompue?
```bash
./scripts/backup.sh  # Backup d'abord!
rm sessions.db && ./bin/kimi-proxy start
```

## Pourquoi je partage ça

J'ai passé des mois à optimiser ma consommation LLM. Au début, c'était juste un script perso. Puis mes collègues l'ont utilisé. Puis j'ai ajouté le sanitizer, la compression, l'architecture modulaire...

Aujourd'hui, c'est un système complet qui me fait économiser des centaines d'euros chaque mois. Si ça peut aider d'autres développeurs à comprendre et contrôler leur consommation, tant mieux.

---

**Note technique** : Le projet est optimisé pour PyCharm + Continue.dev, mais fonctionne parfaitement avec VS Code ou n'importe quel client compatible OpenAI.
