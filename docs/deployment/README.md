# 🚀 Déploiement : Installation et Utilisation

**TL;DR**: Tu as 5 minutes pour installer Kimi Proxy Dashboard et commencer à économiser 20-40% de tokens LLM. C'est simple, rapide, et ça marche avec PyCharm, VS Code ou n'importe quel client compatible OpenAI.

## Pourquoi cette documentation est différente

### Pas de jargon inutile
Je ne vais pas te parler de "stack technique" ou "architecture cloud". Je vais te dire exactement quoi faire pour que ça marche, maintenant.

### Les vrais problèmes que j'ai résolus
- **"Je ne sais pas comment installer"** → Instructions étape par étape
- **"Ça ne marche pas avec PyCharm"** → Configuration Continue.dev incluse  
- **"J'ai peur de casser mon setup existant"** → Compatibilité totale préservée

## Installation en 5 minutes

### Prérequis (vérifie maintenant)
```bash
python --version  # Doit être 3.10+
pip --version       # Doit être installé
```

Si tu n'as pas Python 3.10+, installe-le avant de continuer.

### Étape 1 : Cloner et installer
```bash
# Clone le projet
git clone <repository-url>
cd kimi-proxy

# Crée l'environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows

# Installe les dépendances
pip install -r requirements.txt
```

### Étape 2 : Configure tes clés API
Ouvre `config.toml` et ajoute tes vraies clés :

```toml
[providers."managed:kimi-code"]
type = "kimi"
base_url = "https://api.kimi.com/coding/v1"
api_key = "sk-kimi-VOTRE_CLE_ICI"

[providers.nvidia]
type = "openai" 
base_url = "https://integrate.api.nvidia.com/v1"
api_key = "nvapi-VOTRE_CLE_ICI"
```

**Important** : Utilise tes vraies clés API. Sans ça, rien ne fonctionnera.

### Étape 3 : Démarre le serveur
```bash
./bin/kimi-proxy start
```

C'est tout. Vraiment.

### Étape 4 : Vérifie que ça marche
Ouvre `http://localhost:8000` dans ton navigateur. Tu devrais voir le dashboard avec la jauge verte.

## Configuration Continue.dev (PyCharm/VS Code)

### Pour PyCharm
1. Dans PyCharm, va à `File → Settings → Plugins`
2. Cherche "Continue" et installe-le
3. Copie `config.yaml` dans `~/.continue/config.yaml`

### Pour VS Code
1. Installe l'extension Continue
2. Copie `config.yaml` dans `~/.continue/config.yaml`

### Le truc magique
Continue.dev enverra automatiquement toutes tes requêtes à travers le proxy. Tu verras les tokens apparaître sur le dashboard en temps réel.

## Utilisation au quotidien

### La nouvelle CLI que j'adore
```bash
./bin/kimi-proxy start      # Démarre le serveur
./bin/kimi-proxy status     # "Running on port 8000, 3 active sessions"  
./bin/kimi-proxy logs       # Voir les dernières requêtes
./bin/kimi-proxy stop       # Arrêt propre
./bin/kimi-proxy restart    # Redémarrage
./bin/kimi-proxy test       # Lance les tests
```

### Le dashboard en pratique
Quand tu ouvres `http://localhost:8000`, tu vois :

- **Jauge de contexte** : Vert (sûr) → Jaune (attention) → Rouge (urgent)
- **Logs temps réel** : Chaque requête avec sa source (🔵 PROXY | 🟢 LOGS | 🟣 COMPILE | 🔴 ERROR)
- **Nouvelle session** : Choisis ton provider et modèle
- **Export** : CSV ou JSON pour analyser tes coûts
- **Compression** : Bouton d'urgence si > 85% contexte

### Mon workflow typique
1. **Matin** : Session "Debugging" avec 🌙 Kimi Code
2. **Après-midi** : Session "Prototypage" avec 🟢 NVIDIA K2.5  
3. **Soir** : Session "Coding" avec 🔷 Mistral Codestral
4. **Export** : CSV pour analyser mes coûts mensuels

## Les problèmes que j'ai rencontrés (et comment les résoudre)

### ❌ Erreur 401 Unauthorized
**Le problème** : Clé API incorrecte ou manquante
**La solution** : Vérifie `config.toml`. Assure-toi que la clé est correcte et sans espaces.

### ❌ Port déjà utilisé  
**Le problème** : Un autre processus utilise le port 8000
**La solution** : 
```bash
./bin/kimi-proxy stop && ./bin/kimi-proxy start
```

### ❌ Log Watcher ne détecte rien
**Le problème** : Continue n'écrit pas dans `~/.continue/logs/core.log`
**La solution** : Vérifie que Continue est bien configuré. Teste `/health` pour voir si le fichier existe.

### ❌ Base de données corrompue
**Le problème** : Fichier `sessions.db` endommagé
**La solution** :
```bash
./scripts/backup.sh  # Backup d'abord!
rm sessions.db && ./bin/kimi-proxy start
```

## Pour qui ce guide?

### Le développeur pressé
Tu veux que ça marche maintenant, pas dans 2 heures.

### L'équipe collaborative  
Plusieurs développeurs, un seul proxy. Tu veux que tout le monde utilise la même configuration.

### Le budget-conscious
Chaque token compte. Tu veux voir exactement ce que tu dépenses.

### L'architecte système
Tu veux comprendre comment ça fonctionne sous le capot.

## La Règle d'Or : Simplicité avant tout

**Le principe** : Si l'installation prend plus de 5 minutes, c'est trop compliqué.

J'ai optimisé chaque étape pour qu'elle soit la plus simple possible. Pas de configuration complexe, pas de dépendances mystérieuses, pas de scripts magiques.

## Les fichiers importants à connaître

### `config.toml` - Tes clés API
C'est ici que tu configures tes providers. Garde ce fichier privé!

### `config.yaml` - Configuration Continue  
Copie-le dans `~/.continue/config.yaml` pour l'intégration PyCharm/VS Code.

### `sessions.db` - Ta base de données
SQLite stocke tout : sessions, métriques, historique. Backup-le régulièrement!

### `bin/kimi-proxy` - Ta nouvelle CLI
Remplace tous les anciens scripts. Plus puissant, plus simple.

---

**Le verdict** : En 5 minutes, tu passes d'un coût opaque à un contrôle total sur ta consommation LLM. C'est le meilleur investissement de temps que tu feras ce mois-ci.

*Navigation : [← Retour à l'index](../README.md)*
