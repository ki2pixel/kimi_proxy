#!/bin/bash
# =============================================================================
# Script de démarrage des serveurs MCP Externes (Phase 3 + Phase 4)
# =============================================================================
# Ce script démarre les serveurs MCP en mode HTTP (pas stdio)
# pour permettre la communication avec le client MCP du Kimi Proxy Dashboard
#
# Architecture:
#   - Qdrant MCP: Cloud (déjà HTTP) ou Local (port 6333)
#   - Context Compression MCP: Local (port 8001)
#   - Task Master MCP: Local (port 8002)
#   - Sequential Thinking MCP: Local (port 8003)
#   - Fast Filesystem MCP: Local (port 8004)
#   - JSON Query MCP: Local (port 8005)
#
# Usage: ./scripts/start-mcp-servers.sh [start|stop|status]
# =============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ports et URLs
QDRANT_PORT=6333
COMPRESSION_PORT=8001
TASK_MASTER_PORT=8002
SEQUENTIAL_THINKING_PORT=8003
FAST_FILESYSTEM_PORT=8004
JSON_QUERY_PORT=8005
PID_FILE_MCP=".mcp-servers.pid"

# =============================================================================
# Fonctions utilitaires
# =============================================================================

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# =============================================================================
# Démarrage des serveurs
# =============================================================================

start_servers() {
    echo "🚀 Démarrage des serveurs MCP Externes..."
    echo ""
    
    # Vérifier l'environnement virtuel
    if [ -d "venv" ]; then
        source venv/bin/activate
        log_info "Environnement virtuel activé"
    fi
    
    # -------------------------------------------------------------------------
    # 1. Serveur Qdrant
    # -------------------------------------------------------------------------
    echo ""
    log_info "Configuration Qdrant MCP..."
    
    # Vérifier si Qdrant Cloud est configuré
    QDRANT_URL=$(grep -A 10 '\[mcp.qdrant\]' config.toml 2>/dev/null | grep '^url' | cut -d'"' -f2)
    
    if [[ "$QDRANT_URL" == *"cloud.qdrant.io"* ]]; then
        log_success "Qdrant Cloud configuré (mode cloud)"
        echo "   URL: $QDRANT_URL"
        echo "   ℹ️  Le serveur Cloud est géré par Qdrant, pas besoin de démarrage local"
    elif check_port $QDRANT_PORT; then
        log_success "Qdrant local déjà en écoute sur le port $QDRANT_PORT"
    else
        log_warning "Qdrant n'est pas démarré"
        echo "   Option 1: Utilisez Qdrant Cloud (recommandé) - configurez dans config.toml"
        echo "   Option 2: Démarrez Qdrant localement: docker run -p 6333:6333 qdrant/qdrant"
    fi
    
    # -------------------------------------------------------------------------
    # 2. Serveur Context Compression MCP
    # -------------------------------------------------------------------------
    echo ""
    log_info "Démarrage Context Compression MCP..."
    
    # Vérifier si déjà en écoute
    if check_port $COMPRESSION_PORT; then
        log_success "Context Compression MCP déjà en écoute sur le port $COMPRESSION_PORT"
    else
        # Créer le serveur HTTP de compression s'il n'existe pas
        create_compression_server
        
        # Démarrer le serveur de compression
        log_info "Lancement du serveur de compression sur le port $COMPRESSION_PORT..."
        
        # Démarrer en arrière-plan avec nohup
        WORKSPACE_PATH="$(pwd)" nohup python3 /tmp/mcp_compression_server.py > /tmp/mcp_compression.log 2>&1 &
        COMPRESSION_PID=$!
        
        # Attendre que le serveur démarre
        sleep 2
        
        if check_port $COMPRESSION_PORT; then
            log_success "Context Compression MCP démarré (PID: $COMPRESSION_PID)"
            echo $COMPRESSION_PID > /tmp/mcp_compression.pid
        else
            log_error "Échec du démarrage du serveur de compression"
            echo "   Logs: /tmp/mcp_compression.log"
            exit 1
        fi
    fi
    
    # -------------------------------------------------------------------------
    # 4. Serveur Sequential Thinking MCP
    # -------------------------------------------------------------------------
    echo ""
    log_info "Démarrage Sequential Thinking MCP..."
    
    # Vérifier si déjà en écoute
    if check_port $SEQUENTIAL_THINKING_PORT; then
        log_success "Sequential Thinking MCP déjà en écoute sur le port $SEQUENTIAL_THINKING_PORT"
    else
        # Créer le serveur HTTP de sequential thinking s'il n'existe pas
        create_sequential_thinking_server
        
        # Démarrer le serveur de sequential thinking
        log_info "Lancement du serveur de sequential thinking sur le port $SEQUENTIAL_THINKING_PORT..."
        
        # Démarrer en arrière-plan avec nohup
        WORKSPACE_PATH="$(pwd)" nohup python3 /tmp/mcp_sequential_thinking_server.py > /tmp/mcp_sequential_thinking.log 2>&1 &
        SEQUENTIAL_THINKING_PID=$!
        
        # Attendre que le serveur démarre
        sleep 2
        
        if check_port $SEQUENTIAL_THINKING_PORT; then
            log_success "Sequential Thinking MCP démarré (PID: $SEQUENTIAL_THINKING_PID)"
            echo $SEQUENTIAL_THINKING_PID > /tmp/mcp_sequential_thinking.pid
        else
            log_error "Échec du démarrage du serveur de sequential thinking"
            echo "   Logs: /tmp/mcp_sequential_thinking.log"
            exit 1
        fi
    fi
    
    # -------------------------------------------------------------------------
    # 5. Serveur Fast Filesystem MCP
    # -------------------------------------------------------------------------
    echo ""
    log_info "Démarrage Fast Filesystem MCP..."
    
    # Vérifier si déjà en écoute
    if check_port $FAST_FILESYSTEM_PORT; then
        log_success "Fast Filesystem MCP déjà en écoute sur le port $FAST_FILESYSTEM_PORT"
    else
        # Créer le serveur HTTP de fast filesystem s'il n'existe pas
        create_fast_filesystem_server
        
        # Démarrer le serveur
        log_info "Lancement du serveur de fast filesystem sur le port $FAST_FILESYSTEM_PORT..."
        
        # Démarrer en arrière-plan avec nohup
        WORKSPACE_PATH="$(pwd)" nohup python3 /tmp/mcp_fast_filesystem_server.py > /tmp/mcp_fast_filesystem.log 2>&1 &
        FAST_FILESYSTEM_PID=$!
        
        # Attendre que le serveur démarre
        sleep 2
        
        if check_port $FAST_FILESYSTEM_PORT; then
            log_success "Fast Filesystem MCP démarré (PID: $FAST_FILESYSTEM_PID)"
            echo $FAST_FILESYSTEM_PID > /tmp/mcp_fast_filesystem.pid
        else
            log_error "Échec du démarrage du serveur de fast filesystem"
            echo "   Logs: /tmp/mcp_fast_filesystem.log"
            exit 1
        fi
    fi
    
    # -------------------------------------------------------------------------
    # 6. Serveur JSON Query MCP
    # -------------------------------------------------------------------------
    echo ""
    log_info "Démarrage JSON Query MCP..."
    
    # Vérifier si déjà en écoute
    if check_port $JSON_QUERY_PORT; then
        log_success "JSON Query MCP déjà en écoute sur le port $JSON_QUERY_PORT"
    else
        # Créer le serveur HTTP de json query s'il n'existe pas
        create_json_query_server
        
        # Démarrer le serveur de json query
        log_info "Lancement du serveur de json query sur le port $JSON_QUERY_PORT..."
        
        # Démarrer en arrière-plan avec nohup
        WORKSPACE_PATH="$(pwd)" nohup python3 /tmp/mcp_json_query_server.py > /tmp/mcp_json_query.log 2>&1 &
        JSON_QUERY_PID=$!
        
        # Attendre que le serveur démarre
        sleep 2
        
        if check_port $JSON_QUERY_PORT; then
            log_success "JSON Query MCP démarré (PID: $JSON_QUERY_PID)"
            echo $JSON_QUERY_PID > /tmp/mcp_json_query.pid
        else
            log_error "Échec du démarrage du serveur de json query"
            echo "   Logs: /tmp/mcp_json_query.log"
            exit 1
        fi
    fi
    
    # -------------------------------------------------------------------------
    # Résumé
    # -------------------------------------------------------------------------
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    log_success "Serveurs MCP prêts !"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "Qdrant MCP:"
    QDRANT_URL_FINAL=$(grep -A 10 '\[mcp.qdrant\]' config.toml 2>/dev/null | grep '^url' | cut -d'"' -f2)
    if [[ "$QDRANT_URL_FINAL" == *"cloud.qdrant.io"* ]]; then
        echo "  🌐 Mode: Cloud (Qdrant Cloud)"
        echo "  🔗 URL: $QDRANT_URL_FINAL"
    else
        echo "  🖥️  Mode: Local"
        echo "  🔗 URL: http://localhost:$QDRANT_PORT"
    fi
    echo ""
    echo "Context Compression MCP:"
    echo "  🖥️  Mode: Local"
    echo "  🔗 URL: http://localhost:$COMPRESSION_PORT"
    echo "  📋 Endpoint: /rpc (JSON-RPC 2.0)"
    echo ""
    echo "Dashboard: http://localhost:8000"
    echo ""
    log_info "Pour arrêter: ./scripts/start-mcp-servers.sh stop"
}

# =============================================================================
# Création du serveur de compression MCP (HTTP)
# =============================================================================

create_compression_server() {
    cat > /tmp/mcp_compression_server.py << 'EOF'
#!/usr/bin/env python3
"""
Serveur MCP Context Compression HTTP
Traduit les requêtes HTTP JSON-RPC 2.0 en appels de compression
"""

import json
import zlib
import base64
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

# Configuration
HOST = "0.0.0.0"
PORT = 8001

# Configuration workspace (reçu depuis l'environnement)
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", "/home/kidpixel/kimi-proxy")

class CompressionHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes JSON-RPC 2.0"""
    
    def log_message(self, format, *args):
        """Supprime les logs par défaut"""
        pass
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Envoie une réponse JSON"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Gère les requêtes CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self):
        """Gère les requêtes GET (health check)"""
        if self.path == "/health":
            self._send_json_response({
                "status": "healthy",
                "server": "context-compression-mcp",
                "version": "1.0.0",
                "capabilities": ["zlib", "context_aware", "gzip"]
            })
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Gère les requêtes POST (JSON-RPC)"""
        if self.path != "/rpc":
            self._send_json_response({"error": "Not found"}, 404)
            return
        
        try:
            # Lire le body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
            
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")
            
            # Router vers la méthode appropriée
            if method == "health":
                result = self._handle_health()
            elif method == "compress":
                result = self._handle_compress(params)
            elif method == "decompress":
                result = self._handle_decompress(params)
            else:
                result = {"error": f"Méthode inconnue: {method}"}
            
            # Réponse JSON-RPC 2.0
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
            self._send_json_response(response)
            
        except Exception as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": None
            }, 500)
    
    def _handle_health(self) -> Dict[str, Any]:
        """Retourne le statut de santé"""
        return {
            "status": "healthy",
            "capabilities": ["zlib", "context_aware"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _handle_compress(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Compresse du contenu"""
        content = params.get("content", "")
        algorithm = params.get("algorithm", "context_aware")
        target_ratio = params.get("target_ratio", 0.5)
        
        original_length = len(content)
        
        if algorithm == "zlib":
            # Compression zlib
            compressed = zlib.compress(content.encode('utf-8'), level=6)
            compressed_b64 = base64.b64encode(compressed).decode('utf-8')
            compressed_length = len(compressed_b64)
        else:
            # Simulation de compression context-aware
            # En production, ceci utiliserait un modèle LLM
            words = content.split()
            if len(words) > 50:
                # Résumé simple: garde le début et la fin
                summary = " ".join(words[:20]) + " ... [compressé] ... " + " ".join(words[-20:])
            else:
                summary = content
            compressed_b64 = base64.b64encode(summary.encode()).decode()
            compressed_length = len(compressed_b64)
        
        ratio = (original_length - compressed_length) / original_length if original_length > 0 else 0
        
        return {
            "compressed": compressed_b64,
            "original_length": original_length,
            "compressed_length": compressed_length,
            "compression_ratio": max(0, ratio),
            "algorithm": algorithm,
            "quality_score": 0.85 if algorithm == "context_aware" else 0.95
        }
    
    def _handle_decompress(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Décompresse du contenu"""
        compressed_data = params.get("compressed", "")
        algorithm = params.get("algorithm", "zlib")
        
        if algorithm in ["zlib", "gzip"]:
            try:
                compressed = base64.b64decode(compressed_data)
                content = zlib.decompress(compressed).decode('utf-8')
            except:
                content = compressed_data
        else:
            content = compressed_data
        
        return {"content": content}


def run_server():
    """Démarre le serveur HTTP"""
    server = HTTPServer((HOST, PORT), CompressionHandler)
    print(f"🚀 Serveur MCP Context Compression démarré sur http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
EOF
    chmod +x /tmp/mcp_compression_server.py
}

# =============================================================================
# Création du serveur de sequential thinking MCP (HTTP)
# =============================================================================

create_sequential_thinking_server() {
    cat > /tmp/mcp_sequential_thinking_server.py << 'EOF'
#!/usr/bin/env python3
"""
Serveur MCP Sequential Thinking HTTP
Gère le raisonnement séquentiel structuré
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Configuration
HOST = "0.0.0.0"
PORT = 8003

class SequentialThinkingHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes JSON-RPC 2.0"""
    
    def log_message(self, format, *args):
        """Supprime les logs par défaut"""
        pass
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Envoie une réponse JSON"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_OPTIONS(self):
        """Gère les requêtes CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self):
        """Gère les requêtes GET (health check)"""
        if self.path == "/health":
            self._send_json_response({
                "status": "healthy",
                "server": "sequential-thinking-mcp",
                "version": "1.0.0",
                "capabilities": ["structured_reasoning", "step_by_step_analysis"],
                "tools_count": 1
            })
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Gère les requêtes POST (JSON-RPC)"""
        if self.path != "/rpc":
            self._send_json_response({"error": "Not found"}, 404)
            return
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
            
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")
            
            if method == "health":
                result = self._handle_health()
            elif method == "sequential_thinking":
                result = self._handle_sequential_thinking(params)
            else:
                result = {"error": f"Méthode inconnue: {method}"}
            
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
            self._send_json_response(response)
            
        except Exception as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": None
            }, 500)
    
    def _handle_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "capabilities": ["structured_reasoning"],
            "tools": ["sequential_thinking"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _handle_sequential_thinking(self, params: Dict[str, Any]) -> Dict[str, Any]:
        problem = params.get("problem", "")
        # Simulation de raisonnement séquentiel
        return {
            "steps": [
                {"step": 1, "title": "Analyser le problème", "description": f"Comprendre: {problem[:100]}..."},
                {"step": 2, "title": "Identifier les contraintes", "description": "Évaluer les limites et exigences"},
                {"step": 3, "title": "Proposer une solution", "description": "Formuler une approche structurée"},
                {"step": 4, "title": "Valider la solution", "description": "Vérifier la cohérence et la faisabilité"}
            ],
            "conclusion": "Solution proposée avec approche méthodique",
            "confidence_score": 0.85
        }

def run_server():
    """Démarre le serveur HTTP"""
    server = HTTPServer((HOST, PORT), SequentialThinkingHandler)
    print(f"🚀 Serveur MCP Sequential Thinking démarré sur http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
EOF
    chmod +x /tmp/mcp_sequential_thinking_server.py
}

# =============================================================================
# Création du serveur de fast filesystem MCP (HTTP)
# =============================================================================

create_fast_filesystem_server() {
    cat > /tmp/mcp_fast_filesystem_server.py << 'EOF'
#!/usr/bin/env python3
"""
Serveur MCP Fast Filesystem HTTP
Gère les opérations fichiers haute performance
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Configuration
HOST = "0.0.0.0"
PORT = 8004

# Configuration workspace (reçu depuis l'environnement)
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", "/home/kidpixel/kimi-proxy")

class FastFilesystemHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes JSON-RPC 2.0"""
    
    def log_message(self, format, *args):
        """Supprime les logs par défaut"""
        pass
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Envoie une réponse JSON"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _is_path_allowed(self, path: str) -> bool:
        """Vérifie si le chemin est dans le workspace autorisé"""
        if not path:
            return False
        
        # Résoudre le chemin absolu
        abs_path = os.path.abspath(path)
        workspace_abs = os.path.abspath(WORKSPACE_PATH)
        
        # Vérifier que le chemin commence par le workspace
        return abs_path.startswith(workspace_abs)
    
    def _restrict_to_workspace(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restreint les paramètres aux chemins workspace autorisés"""
        # Pour les paramètres de fichier, vérifier les permissions
        file_params = ["path", "file_path", "directory", "source", "destination"]
        for param in file_params:
            if param in params:
                path = params[param]
                if not self._is_path_allowed(path):
                    raise PermissionError(f"Accès refusé: chemin '{path}' hors du workspace autorisé '{WORKSPACE_PATH}'")
        
        return params
    
    def do_OPTIONS(self):
        """Gère les requêtes CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self):
        """Gère les requêtes GET (health check)"""
        if self.path == "/health":
            self._send_json_response({
                "status": "healthy",
                "server": "fast-filesystem-mcp",
                "version": "1.0.0",
                "capabilities": ["file_operations", "directory_management", "search"],
                "tools_count": 25
            })
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Gère les requêtes POST (JSON-RPC)"""
        if self.path != "/rpc":
            self._send_json_response({"error": "Not found"}, 404)
            return
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
            
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")
            
            # Vérifier les permissions pour toutes les méthodes filesystem
            params = self._restrict_to_workspace(params)
            
            if method == "health":
                result = self._handle_health()
            elif method == "list_directory":
                result = self._handle_list_directory(params)
            elif method == "read_file":
                result = self._handle_read_file(params)
            elif method == "write_file":
                result = self._handle_write_file(params)
            elif method == "search_files":
                result = self._handle_search_files(params)
            else:
                result = {"error": f"Méthode inconnue: {method}"}
            
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
            self._send_json_response(response)
            
        except PermissionError as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": None
            }, 403)
        except Exception as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": None
            }, 500)
    
    def _handle_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "capabilities": ["file_operations", "search"],
            "tools": ["list_directory", "read_file", "write_file", "search_files"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _handle_list_directory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", ".")
        try:
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                items.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else 0
                })
            return {"items": items, "count": len(items)}
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_read_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "size": len(content)}
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_write_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        path = params.get("path", "")
        content = params.get("content", "")
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "bytes_written": len(content)}
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_search_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        directory = params.get("directory", ".")
        pattern = params.get("pattern", "*")
        try:
            matches = []
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if pattern in file:
                        matches.append(os.path.join(root, file))
            return {"matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}

def run_server():
    """Démarre le serveur HTTP"""
    server = HTTPServer((HOST, PORT), FastFilesystemHandler)
    print(f"🚀 Serveur MCP Fast Filesystem démarré sur http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
EOF
    chmod +x /tmp/mcp_fast_filesystem_server.py
}

# =============================================================================
# Création du serveur de json query MCP (HTTP)
# =============================================================================

create_json_query_server() {
    cat > /tmp/mcp_json_query_server.py << 'EOF'
#!/usr/bin/env python3
"""
Serveur MCP JSON Query HTTP
Gère les requêtes JSON avancées
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Configuration
HOST = "0.0.0.0"
PORT = 8005

# Configuration workspace (reçu depuis l'environnement)
WORKSPACE_PATH = os.getenv("WORKSPACE_PATH", "/home/kidpixel/kimi-proxy")

class JsonQueryHandler(BaseHTTPRequestHandler):
    """Handler pour les requêtes JSON-RPC 2.0"""
    
    def log_message(self, format, *args):
        """Supprime les logs par défaut"""
        pass
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Envoie une réponse JSON"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def _is_path_allowed(self, path: str) -> bool:
        """Vérifie si le chemin est dans le workspace autorisé"""
        if not path:
            return False
        
        # Résoudre le chemin absolu
        abs_path = os.path.abspath(path)
        workspace_abs = os.path.abspath(WORKSPACE_PATH)
        
        # Vérifier que le chemin commence par le workspace
        return abs_path.startswith(workspace_abs)
    
    def _restrict_to_workspace(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restreint les paramètres aux chemins workspace autorisés"""
        # Pour les paramètres de fichier, vérifier les permissions
        file_params = ["file_path", "path"]
        for param in file_params:
            if param in params:
                path = params[param]
                if not self._is_path_allowed(path):
                    raise PermissionError(f"Accès refusé: chemin '{path}' hors du workspace autorisé '{WORKSPACE_PATH}'")
        
        return params
    
    def do_OPTIONS(self):
        """Gère les requêtes CORS preflight"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
    
    def do_GET(self):
        """Gère les requêtes GET (health check)"""
        if self.path == "/health":
            self._send_json_response({
                "status": "healthy",
                "server": "json-query-mcp",
                "version": "1.0.0",
                "capabilities": ["json_query", "jsonpath", "data_extraction"],
                "tools_count": 3
            })
        else:
            self._send_json_response({"error": "Not found"}, 404)
    
    def do_POST(self):
        """Gère les requêtes POST (JSON-RPC)"""
        if self.path != "/rpc":
            self._send_json_response({"error": "Not found"}, 404)
            return
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            request = json.loads(body)
            
            method = request.get("method")
            params = request.get("params", {})
            req_id = request.get("id")
            
            # Vérifier les permissions pour les méthodes qui accèdent aux fichiers
            if method in ["query_json", "extract_keys", "find_values"]:
                params = self._restrict_to_workspace(params)
            
            if method == "health":
                result = self._handle_health()
            elif method == "query_json":
                result = self._handle_query_json(params)
            elif method == "extract_keys":
                result = self._handle_extract_keys(params)
            elif method == "find_values":
                result = self._handle_find_values(params)
            else:
                result = {"error": f"Méthode inconnue: {method}"}
            
            response = {
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id
            }
            self._send_json_response(response)
            
        except PermissionError as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": None
            }, 403)
        except Exception as e:
            self._send_json_response({
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": str(e)},
                "id": None
            }, 500)
    
    def _handle_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "capabilities": ["json_query", "data_extraction"],
            "tools": ["query_json", "extract_keys", "find_values"],
            "timestamp": datetime.now().isoformat()
        }
    
    def _handle_query_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        json_data = params.get("json_data", {})
        query = params.get("query", "")
        # Simulation de requête JSON simplifiée
        try:
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            
            # Recherche simple par clé
            result = self._find_by_key(json_data, query)
            return {"result": result, "count": len(result) if isinstance(result, list) else 1}
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_extract_keys(self, params: Dict[str, Any]) -> Dict[str, Any]:
        json_data = params.get("json_data", {})
        try:
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            
            keys = self._extract_all_keys(json_data)
            return {"keys": list(set(keys)), "count": len(set(keys))}
        except Exception as e:
            return {"error": str(e)}
    
    def _handle_find_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        json_data = params.get("json_data", {})
        key = params.get("key", "")
        try:
            if isinstance(json_data, str):
                json_data = json.loads(json_data)
            
            values = self._find_values_by_key(json_data, key)
            return {"values": values, "count": len(values)}
        except Exception as e:
            return {"error": str(e)}
    
    def _find_by_key(self, data, key):
        """Recherche récursive par clé"""
        if isinstance(data, dict):
            if key in data:
                return data[key]
            for v in data.values():
                result = self._find_by_key(v, key)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_by_key(item, key)
                if result is not None:
                    return result
        return None
    
    def _extract_all_keys(self, data):
        """Extrait toutes les clés récursivement"""
        keys = []
        if isinstance(data, dict):
            keys.extend(data.keys())
            for v in data.values():
                keys.extend(self._extract_all_keys(v))
        elif isinstance(data, list):
            for item in data:
                keys.extend(self._extract_all_keys(item))
        return keys
    
    def _find_values_by_key(self, data, key):
        """Trouve toutes les valeurs pour une clé donnée"""
        values = []
        if isinstance(data, dict):
            if key in data:
                values.append(data[key])
            for v in data.values():
                values.extend(self._find_values_by_key(v, key))
        elif isinstance(data, list):
            for item in data:
                values.extend(self._find_values_by_key(item, key))
        return values

def run_server():
    """Démarre le serveur HTTP"""
    server = HTTPServer((HOST, PORT), JsonQueryHandler)
    print(f"🚀 Serveur MCP JSON Query démarré sur http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
EOF
    chmod +x /tmp/mcp_json_query_server.py
}

# =============================================================================
# Arrêt des serveurs
# =============================================================================

stop_servers() {
    echo "🛑 Arrêt des serveurs MCP..."
    
    # Arrêter le serveur de compression
    if [ -f /tmp/mcp_compression.pid ]; then
        pid=$(cat /tmp/mcp_compression.pid)
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null || true
            log_success "Compression MCP arrêté (PID: $pid)"
        fi
        rm -f /tmp/mcp_compression.pid
    fi
    
    # Arrêter le serveur de sequential thinking
    if [ -f /tmp/mcp_sequential_thinking.pid ]; then
        pid=$(cat /tmp/mcp_sequential_thinking.pid)
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null || true
            log_success "Sequential Thinking MCP arrêté (PID: $pid)"
        fi
        rm -f /tmp/mcp_sequential_thinking.pid
    fi
    
    # Arrêter le serveur de fast filesystem
    if [ -f /tmp/mcp_fast_filesystem.pid ]; then
        pid=$(cat /tmp/mcp_fast_filesystem.pid)
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null || true
            log_success "Fast Filesystem MCP arrêté (PID: $pid)"
        fi
        rm -f /tmp/mcp_fast_filesystem.pid
    fi
    
    # Arrêter le serveur de json query
    if [ -f /tmp/mcp_json_query.pid ]; then
        pid=$(cat /tmp/mcp_json_query.pid)
        if kill -0 $pid 2>/dev/null; then
            kill -9 $pid 2>/dev/null || true
            log_success "JSON Query MCP arrêté (PID: $pid)"
        fi
        rm -f /tmp/mcp_json_query.pid
    fi
    
    # Tuer par port si nécessaire
    kill_port $COMPRESSION_PORT 2>/dev/null || true
    kill_port $SEQUENTIAL_THINKING_PORT 2>/dev/null || true
    kill_port $FAST_FILESYSTEM_PORT 2>/dev/null || true
    kill_port $JSON_QUERY_PORT 2>/dev/null || true
    
    log_success "Tous les serveurs MCP arrêtés"
}

# =============================================================================
# Statut des serveurs
# =============================================================================

status_servers() {
    echo "📊 Statut des serveurs MCP"
    echo ""
    
    # Qdrant
    echo -n "Qdrant MCP: "
    QDRANT_URL=$(grep -A 10 '\[mcp.qdrant\]' config.toml 2>/dev/null | grep '^url' | cut -d'"' -f2)
    
    if [[ "$QDRANT_URL" == *"cloud.qdrant.io"* ]]; then
        # Vérifier la connectivité Cloud
        QDRANT_API_KEY=$(grep -A 15 '\[mcp.qdrant\]' config.toml 2>/dev/null | grep '^api_key' | cut -d'"' -f2)
        if [ ! -z "$QDRANT_API_KEY" ]; then
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "api-key: $QDRANT_API_KEY" "$QDRANT_URL/healthz" 2>/dev/null || echo "000")
            if [ "$HTTP_CODE" == "200" ]; then
                log_success "✅ Cloud Connecté ($QDRANT_URL)"
            else
                log_warning "⚠️  Cloud vérifier API key (HTTP $HTTP_CODE)"
            fi
        else
            log_info "☁️  Cloud configuré ($QDRANT_URL)"
        fi
    elif check_port $QDRANT_PORT; then
        log_success "✅ Local Connecté (port $QDRANT_PORT)"
    else
        log_warning "❌ Déconnecté (port $QDRANT_PORT non écouté)"
    fi
    
    # Compression
    echo -n "Compression MCP: "
    if check_port $COMPRESSION_PORT; then
        log_success "✅ Connecté (port $COMPRESSION_PORT)"
    else
        log_warning "❌ Déconnecté (port $COMPRESSION_PORT non écouté)"
    fi
    
    # Sequential Thinking
    echo -n "Sequential Thinking MCP: "
    if check_port $SEQUENTIAL_THINKING_PORT; then
        log_success "✅ Connecté (port $SEQUENTIAL_THINKING_PORT)"
    else
        log_warning "❌ Déconnecté (port $SEQUENTIAL_THINKING_PORT non écouté)"
    fi
    
    # Fast Filesystem
    echo -n "Fast Filesystem MCP: "
    if check_port $FAST_FILESYSTEM_PORT; then
        log_success "✅ Connecté (port $FAST_FILESYSTEM_PORT)"
    else
        log_warning "❌ Déconnecté (port $FAST_FILESYSTEM_PORT non écouté)"
    fi
    
    # JSON Query
    echo -n "JSON Query MCP: "
    if check_port $JSON_QUERY_PORT; then
        log_success "✅ Connecté (port $JSON_QUERY_PORT)"
    else
        log_warning "❌ Déconnecté (port $JSON_QUERY_PORT non écouté)"
    fi
}

# =============================================================================
# Main
# =============================================================================

case "${1:-start}" in
    start)
        start_servers
        ;;
    stop)
        stop_servers
        ;;
    status)
        status_servers
        ;;
    restart)
        stop_servers
        sleep 2
        start_servers
        ;;
    *)
        echo "Usage: $0 [start|stop|status|restart]"
        exit 1
        ;;
esac
