#!/bin/bash
# =============================================================================
# Script de diagnostic MCP - Diagnostic rapide des connexions serveurs MCP
# =============================================================================
# Usage: ./scripts/diagnose-mcp.sh
# =============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

echo -e "${PURPLE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║       DIAGNOSTIC SERVEURS MCP - Kimi Proxy Dashboard          ║${NC}"
echo -e "${PURPLE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# =============================================================================
# 1. Vérification de la configuration
# =============================================================================
echo -e "${BLUE}📋 1. Vérification de la configuration...${NC}"

if [[ -f "config.toml" ]]; then
    echo "   ✅ config.toml trouvé"
    
    # Extraire les URLs MCP
    QDRANT_URL=$(grep -A 5 '\[mcp.qdrant\]' config.toml 2>/dev/null | grep 'url' | cut -d'"' -f2 || echo "")
    COMPRESSION_URL=$(grep -A 5 '\[mcp.compression\]' config.toml 2>/dev/null | grep 'url' | cut -d'"' -f2 || echo "")
    
    echo "   📍 Qdrant URL: $QDRANT_URL"
    echo "   📍 Compression URL: $COMPRESSION_URL"
else
    echo "   ❌ config.toml non trouvé"
    exit 1
fi

echo ""

# =============================================================================
# 2. Test de connectivité réseau
# =============================================================================
echo -e "${BLUE}🌐 2. Test de connectivité réseau...${NC}"

# Qdrant
if [[ "$QDRANT_URL" == *"localhost"* ]] || [[ "$QDRANT_URL" == *"127.0.0.1"* ]]; then
    echo -n "   Qdrant (local:6333): "
    if nc -z localhost 6333 2>/dev/null || curl -s http://localhost:6333/healthz > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Connecté${NC}"
    else
        echo -e "${RED}❌ Déconnecté${NC}"
    fi
else
    echo -n "   Qdrant (cloud): "
    # Essayer avec l'API key si disponible
    QDRANT_API_KEY=$(grep -A 10 '\[mcp.qdrant\]' config.toml 2>/dev/null | grep 'api_key' | cut -d'"' -f2 || echo "")
    if [[ ! -z "$QDRANT_API_KEY" ]]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "api-key: $QDRANT_API_KEY" "$QDRANT_URL/healthz" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            echo -e "${GREEN}✅ Connecté (HTTP $HTTP_CODE)${NC}"
        else
            echo -e "${YELLOW}⚠️  Vérifiez l'API key (HTTP $HTTP_CODE)${NC}"
        fi
    else
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$QDRANT_URL/healthz" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            echo -e "${GREEN}✅ Connecté${NC}"
        else
            echo -e "${YELLOW}⚠️  Accès restreint (HTTP $HTTP_CODE - API key requise)${NC}"
        fi
    fi
fi

# Compression
echo -n "   Compression (localhost:8001): "
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Connecté${NC}"
else
    echo -e "${RED}❌ Déconnecté${NC}"
fi

echo ""

# =============================================================================
# 3. Test des endpoints JSON-RPC
# =============================================================================
echo -e "${BLUE}🔌 3. Test des endpoints JSON-RPC...${NC}"

# Test Compression RPC
echo -n "   Compression /rpc: "
RPC_RESPONSE=$(curl -s -X POST http://localhost:8001/rpc \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"health","params":{},"id":1}' 2>/dev/null || echo "")

if [[ "$RPC_RESPONSE" == *"healthy"* ]]; then
    echo -e "${GREEN}✅ Répond correctement${NC}"
else
    echo -e "${RED}❌ Pas de réponse JSON-RPC${NC}"
fi

echo ""

# =============================================================================
# 4. Test depuis l'API Kimi Proxy
# =============================================================================
echo -e "${BLUE}🔗 4. Test depuis l'API Kimi Proxy...${NC}"

PROXY_STATUS=$(curl -s http://localhost:8000/api/memory/servers 2>/dev/null || echo "")

if [[ ! -z "$PROXY_STATUS" ]]; then
    echo "   ✅ Endpoint /api/memory/servers accessible"
    
    # Analyser la réponse
    if echo "$PROXY_STATUS" | grep -q '"connected":true'; then
        echo -e "   ${GREEN}✅ Au moins un serveur est connecté${NC}"
    else
        echo -e "   ${RED}❌ Tous les serveurs sont déconnectés${NC}"
    fi
    
    # Afficher les détails
    echo ""
    echo "   Détail des serveurs:"
    echo "$PROXY_STATUS" | python3 -m json.tool 2>/dev/null | grep -E '"name"|"connected"|"latency_ms"|"error"' | sed 's/^/     /' || echo "     (format non JSON)"
else
    echo -e "   ${RED}❌ API Kimi Proxy non accessible sur le port 8000${NC}"
fi

echo ""

# =============================================================================
# 5. Diagnostic du problème de transport
# =============================================================================
echo -e "${BLUE}🔍 5. Diagnostic du problème de transport...${NC}"

echo ""
echo "   ${PURPLE}╔════════════════════════════════════════════════════════════╗${NC}"
echo "   ${PURPLE}║  ANALYSE: Différence STDIO vs HTTP                         ║${NC}"
echo "   ${PURPLE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier si des processus fastmcp tournent
FASTMCP_PIDS=$(pgrep -f "fastmcp" 2>/dev/null || echo "")
if [[ ! -z "$FASTMCP_PIDS" ]]; then
    echo -e "   ${YELLOW}⚠️  ATTENTION: Processus fastmcp détectés (PIDs: $FASTMCP_PIDS)${NC}"
    echo "      → fastmcp run server.py démarre en mode STDIO (pas HTTP)"
    echo "      → Le client MCP Kimi Proxy attend des serveurs HTTP"
    echo ""
    echo "   ${RED}❌ PROBLÈME IDENTIFIÉ: Transport mismatch${NC}"
    echo ""
    echo "   Solution:"
    echo "   1. Arrêtez les serveurs fastmcp actuels:"
    echo "      kill $FASTMCP_PIDS"
    echo ""
    echo "   2. Démarrez les serveurs en mode HTTP:"
    echo "      ./scripts/start-mcp-servers.sh start"
    echo ""
else
    echo "   ✅ Aucun processus fastmcp en mode stdio détecté"
    
    # Vérifier les ports
    if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo ""
        echo -e "   ${YELLOW}⚠️  Les serveurs MCP ne sont pas démarrés${NC}"
        echo ""
        echo "   Solution:"
        echo "   ./scripts/start-mcp-servers.sh start"
    fi
fi

echo ""

# =============================================================================
# 6. Résumé et recommandations
# =============================================================================
echo -e "${BLUE}📊 6. Résumé et recommandations...${NC}"
echo ""

# Compter les problèmes
ISSUES=0

if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    ISSUES=$((ISSUES + 1))
fi

if [[ "$QDRANT_URL" == *"localhost"* ]] && ! nc -z localhost 6333 2>/dev/null; then
    ISSUES=$((ISSUES + 1))
fi

if [[ ! -z "$FASTMCP_PIDS" ]]; then
    ISSUES=$((ISSUES + 1))
fi

if [[ $ISSUES -eq 0 ]]; then
    echo -e "   ${GREEN}✅ Tous les systèmes sont opérationnels !${NC}"
    echo ""
    echo "   Le dashboard devrait afficher:"
    echo "   - Qdrant MCP: Connecté"
    echo "   - Context Compression MCP: Connecté"
else
    echo -e "   ${YELLOW}⚠️  $ISSUES problème(s) détecté(s)${NC}"
    echo ""
    echo "   Actions recommandées:"
    echo "   1. Arrêter tous les serveurs MCP existants:"
    echo "      pkill -f fastmcp; pkill -f mcp_"
    echo ""
    echo "   2. Démarrer les serveurs MCP en mode HTTP:"
    echo "      ./scripts/start-mcp-servers.sh start"
    echo ""
    echo "   3. Vérifier le statut:"
    echo "      ./scripts/diagnose-mcp.sh"
    echo ""
    echo "   4. Rafraîchir le dashboard:"
    echo "      http://localhost:8000"
fi

echo ""
echo -e "${PURPLE}════════════════════════════════════════════════════════════════${NC}"
