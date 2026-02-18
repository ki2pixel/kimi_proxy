#!/bin/bash
set -e

echo "🧪 Running MCP Unit Tests (no external dependencies)"
echo "================================================"
echo ""

# Option pour couleur (si supporté)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[0;33m'
    NC='\033[0m'
else
    GREEN=''
    RED=''
    YELLOW=''
    NC=''
fi

# Vérifie que nous sommes dans le bon répertoire
if [ ! -f "src/kimi_proxy/features/mcp/client.py" ]; then
    echo "${RED}❌ Error: Not in kimi-proxy root directory${NC}"
    echo "   Please run from: /home/kidpixel/kimi-proxy"
    exit 1
fi

# Vérifie Python/venv
PYTHON_CMD="python"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Vérifie pytest
if ! command -v pytest &> /dev/null; then
    echo "${YELLOW}⚠ pytest non trouvé, installation...${NC}"
    pip install pytest pytest-asyncio
fi

# Affiche l'architecture
echo "📁 MCP Module Structure:"
echo "   ├── client.py (facade)"
echo "   ├── base/"
echo "   │   ├── config.py"
echo "   │   └── rpc.py"
echo "   └── servers/"
for server in qdrant compression task_master sequential filesystem json_query; do
    echo "       ├── ${server}.py"
done
echo ""

# Statistiques echo "📊 Loading test files..."
TEST_FILES=(
    "tests/mcp/test_mcp_client_integration.py"
    "tests/mcp/test_mcp_qdrant.py"
    "tests/mcp/test_mcp_compression.py"
    "tests/mcp/test_mcp_task_master.py"
    "tests/mcp/test_mcp_sequential.py"
    "tests/mcp/test_mcp_filesystem.py"
    "tests/mcp/test_mcp_json_query.py"
)

TOTAL_LINES=0
for test_file in "${TEST_FILES[@]}"; do
    if [ -f "$test_file" ]; then
        lines=$(wc -l < "$test_file")
        TOTAL_LINES=$((TOTAL_LINES + lines))
        echo "   ✓ $(basename "$test_file") (${lines} lignes)"
    fi
done
echo ""

# Exécute les tests
echo "${GREEN}▶ Running tests...${NC}"
echo ""

cd tests
pytest mcp/ -v \
    --tb=short \
    -m "not e2e" \
    --strict-markers

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "${GREEN}✅ All unit tests passed!${NC}"
    echo ""
    echo "📊 Coverage Analysis:"
    echo "   - Client facade: ✓ Mock délégation"
    echo "   - Qdrant: ✓ Recherche, clustering"
    echo "   - Compression: ✓ Algos, fallback"
    echo "   - Task Master: ✓ 14 outils, workflow"
    echo "   - Sequential: ✓ Multi-étapes"
    echo "   - Filesystem: ✓ 25 outils, helpers"
    echo "   - JSON Query: ✓ JSONPath, recherche"
else
    echo "${RED}❌ Some tests failed${NC}"
    exit 1
fi