#!/bin/bash
# start-mcp.sh - Lanceur Universel Memory Bank

# 1. Sécurité du chemin : on se place là où est le script
cd "$(dirname "$0")"

# 2. On définit la racine du Memory Bank
export MEMORY_BANK_ROOT="$(pwd)"

# 3. On ajoute les chemins standards (utile pour Windsurf/PyCharm)
export PATH="$PATH:/usr/local/bin:/usr/bin:/bin"

# 4. On lance le serveur proprement
# --no-install : évite les messages "Need to install..." qui cassent la connexion
# -q : mode silencieux
# exec : remplace le processus bash par node pour une gestion propre des signaux
exec npx -y -q --no-install @allpepper/memory-bank-mcp