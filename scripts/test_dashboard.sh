#!/bin/bash
# Script de test automatique du Dashboard NVIDIA Proxy
# Simule des requêtes de différentes tailles pour tester le monitoring

API_URL="http://localhost:8000"
COLORS=$(tput colors 2>/dev/null)
if [ -n "$COLORS" ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    GREEN=''
    YELLOW=''
    RED=''
    BLUE=''
    NC=''
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       🧪 TEST AUTOMATIQUE DU DASHBOARD NVIDIA             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Vérifier que le serveur est accessible
echo -e "${YELLOW}🔍 Vérification du serveur...${NC}"
if ! curl -s "$API_URL/health" > /dev/null; then
    echo -e "${RED}❌ Serveur inaccessible sur $API_URL${NC}"
    echo "   Lancez d'abord: ./start.sh"
    exit 1
fi
echo -e "${GREEN}✅ Serveur accessible${NC}"
echo ""

# Créer une nouvelle session de test
echo -e "${YELLOW}📁 Création d'une session de test...${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$API_URL/api/sessions" \
    -H "Content-Type: application/json" \
    -d '{"name": "Session Test Auto"}')
SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"id":[0-9]*' | cut -d: -f2)
echo -e "${GREEN}✅ Session créée (ID: $SESSION_ID)${NC}"
echo ""

# Fonction pour envoyer une requête de test
send_request() {
    local content="$1"
    local description="$2"
    local color="$3"
    
    echo -e "${color}➡️  $description${NC}"
    
    curl -s -X POST "$API_URL/chat/completions" \
        -H "Content-Type: application/json" \
        -H "Accept: text/event-stream" \
        -d "{\"messages\":[{\"role\":\"user\",\"content\":\"$content\"}]}" \
        > /dev/null 2>&1 &
    
    echo -e "${GREEN}   ✅ Requête envoyée${NC}"
}

# Test 1: Message court
echo -e "${YELLOW}📝 Test 1: Messages de différentes tailles${NC}"
send_request "Hello, test court" "Message court (~50 tokens)" "$BLUE"
sleep 2

# Test 2: Message moyen
send_request "Je travaille sur un projet de monitoring temps réel avec FastAPI et WebSockets pour surveiller la consommation de tokens de l'API NVIDIA." "Message moyen (~150 tokens)" "$BLUE"
sleep 2

# Test 3: Message long (simulé)
LONG_TEXT="$(cat << 'EOF'
Je suis en train de développer une application web complète pour le monitoring de l'utilisation des tokens avec l'API NVIDIA. 
Cette application utilise FastAPI comme backend, SQLite pour la persistance des données, et WebSockets pour la communication temps réel.
Le frontend est construit avec HTML/JS vanilla et utilise TailwindCSS pour le design moderne en mode sombre.
Je veux pouvoir suivre en temps réel la consommation de tokens, avec des alertes quand je m'approche de la limite de contexte.
L'application agit comme un proxy entre mon client local et l'API NVIDIA, interceptant toutes les requêtes pour les analyser.
EOF
)"
send_request "$LONG_TEXT" "Message long (~800+ tokens)" "$BLUE"
echo ""

# Attendre que les requêtes soient traitées
echo -e "${YELLOW}⏳ Attente du traitement...${NC}"
sleep 3

# Vérifier les stats
echo ""
echo -e "${YELLOW}📊 Vérification des statistiques...${NC}"
STATS=$(curl -s "$API_URL/api/sessions/active")
REQUESTS=$(echo $STATS | grep -o '"total_requests":[0-9]*' | cut -d: -f2)
echo -e "${GREEN}📈 Total requêtes enregistrées: $REQUESTS${NC}"
echo ""

# Test d'export CSV
echo -e "${YELLOW}📤 Test export CSV...${NC}"
curl -s "$API_URL/api/export/csv" -o /tmp/test_export.csv
if [ -f "/tmp/test_export.csv" ]; then
    LINES=$(wc -l < /tmp/test_export.csv)
    echo -e "${GREEN}✅ Export CSV réussi ($LINES lignes)${NC}"
    echo "   Fichier: /tmp/test_export.csv"
else
    echo -e "${RED}❌ Échec de l'export CSV${NC}"
fi
echo ""

# Test d'export JSON
echo -e "${YELLOW}📤 Test export JSON...${NC}"
curl -s "$API_URL/api/export/json" -o /tmp/test_export.json
if [ -f "/tmp/test_export.json" ]; then
    METRICS=$(grep -o '"id"' /tmp/test_export.json | wc -l)
    echo -e "${GREEN}✅ Export JSON réussi ($METRICS métriques)${NC}"
    echo "   Fichier: /tmp/test_export.json"
else
    echo -e "${RED}❌ Échec de l'export JSON${NC}"
fi
echo ""

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   ✅ TESTS TERMINÉS                       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "📱 Vérifiez le dashboard: http://localhost:8000"
echo ""
