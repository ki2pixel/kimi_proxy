"""
Constantes globales pour Kimi Proxy Dashboard.
"""

# ============================================================================
# CONFIGURATION PAR DÉFAUT
# ============================================================================
DEFAULT_MAX_CONTEXT = 262144  # 256K tokens
DATABASE_FILE = "sessions.db"
DEFAULT_PROVIDER = "managed:kimi-code"

# ============================================================================
# MCP TOOL RESPONSE CHUNKING
# ============================================================================
MCP_MAX_RESPONSE_TOKENS = 50000  # Limite par chunk de réponse MCP (50K tokens)
MCP_CHUNK_OVERLAP_TOKENS = 1000  # Overlap entre chunks pour continuité

# ============================================================================
# RATE LIMITING
# ============================================================================
RATE_LIMITS = {
    "nvidia": 40,
    "mistral": 60,
    "openrouter": 30,
    "siliconflow": 100,
    "groq": 100,
    "cerebras": 100,
    "gemini": 60,
    "managed:kimi-code": 40
}

MAX_RPM = 40  # Défaut
RATE_LIMIT_WARNING_THRESHOLD = 0.875
RATE_LIMIT_CRITICAL_THRESHOLD = 0.95

# ============================================================================
# SANITIZER & ROUTING
# ============================================================================
CONTEXT_FALLBACK_THRESHOLD = 0.90  # Seuil pour fallback modèle (90%)

# Configuration par défaut du sanitizer
DEFAULT_SANITIZER_CONFIG = {
    "enabled": True,
    "threshold_tokens": 1000,
    "preview_length": 200,
    "tmp_dir": "/tmp/kimi_proxy_masked",
    "tags": ["@file", "@codebase", "@tool", "@console", "@output"]
}

# ============================================================================
# MCP MEMORY
# ============================================================================
MCP_MIN_MEMORY_TOKENS = 20  # Seuil minimum pour considérer du contenu comme mémoire

# Patterns de détection MCP (utilisés dans detector.py)
MCP_PATTERNS = {
    # Balises explicites de mémoire MCP
    "memory_tag": r"<mcp-memory>.*?</mcp-memory>",
    "memory_ref": r"@memory\[[^\]]+\]",
    "memory_block": r"\[MEMORY\].*?\[/MEMORY\]",
    # Contenu MCP injecté par Continue
    "mcp_result": r"<mcp-result[^>]*>.*?</mcp-result>",
    "mcp_tool": r"<mcp-tool[^>]*>.*?</mcp-tool>",
    # Détection contexte mémoire
    "context_memory": r"Contexte\s+précédent|Mémoire\s+de\s+la\s+session|Memory\s+from\s+previous",
    # =========================================================================
    # NOUVEAUX SERVEURS MCP - Intégration Phase 4
    # =========================================================================
    # 1. task-master-ai (14 outils)
    "mcp_task_master": r"(get_tasks|next_task|get_task|set_task_status|update_subtask|parse_prd|expand_task|initialize_project|analyze_project_complexity|expand_all|add_subtask|remove_task|add_task|complexity_report)",
    # 2. sequential-thinking (1 outil)
    "mcp_sequential_thinking": r"(sequentialthinking_tools|sequential_thinking)",
    # 3. fast-filesystem (25 outils)
    "mcp_fast_filesystem": r"(fast_list_allowed_directories|fast_read_file|fast_read_multiple_files|fast_write_file|fast_large_write_file|fast_list_directory|fast_get_file_info|fast_create_directory|fast_search_files|fast_search_code|fast_get_directory_tree|fast_get_disk_usage|fast_find_large_files|fast_edit_block|fast_safe_edit|fast_edit_multiple_blocks|fast_edit_blocks|fast_extract_lines|fast_copy_file|fast_move_file|fast_delete_file|fast_batch_file_operations|fast_compress_files|fast_extract_archive|fast_sync_directories)",
    # 4. json-query (3 outils)
    "mcp_json_query": r"(json_query_jsonpath|json_query_search_keys|json_query_search_values)",
}

# ============================================================================
# COMPRESSION (Phase 3 - Compression de dernier recours)
# ============================================================================
DEFAULT_COMPRESSION_CONFIG = {
    "enabled": True,
    "threshold_percentage": 85,  # Seuil pour activer le bouton de compression
    "preserve_recent_exchanges": 5,  # Nombre d'échanges à préserver
    "summary_max_tokens": 500,  # Taille max du résumé LLM
}

# ============================================================================
# COMPACTION (Phase 1 - Infrastructure de Base)
# ============================================================================
DEFAULT_COMPACTION_CONFIG = {
    "enabled": True,
    "threshold_percentage": 80,  # Seuil pour recommander la compaction
    "max_preserved_messages": 2,  # Nombre d'échanges récents à préserver
    "min_tokens_to_compact": 500,  # Minimum de tokens pour déclencher
    "min_messages_to_compact": 6,  # Minimum de messages pour déclencher
    "target_reduction_ratio": 0.60,  # Objectif de réduction (60%)
}

# ============================================================================
# MCP PHASE 3 - Configuration des Serveurs Externes
# ============================================================================
MCP_PHASE3_CONFIG = {
    "qdrant": {
        "enabled": True,
        "url": "http://localhost:6333",
        "collection": "kimi_proxy_memory",
        "search_timeout_ms": 50,
        "similarity_threshold": 0.7,
        "redundancy_threshold": 0.85
    },
    "compression": {
        "enabled": True,
        "url": "http://localhost:8001",
        "timeout_ms": 5000,
        "target_ratio": 0.5,
        "min_tokens_to_compress": 500
    },
    "routing": {
        "enabled": True,
        "context_buffer_percent": 10,
        "max_cost_factor": 1.5,
        "evaluate_fallback": 0.70,
        "force_fallback": 0.90
    }
}

# ============================================================================
# MCP PHASE 4 - Nouveaux Serveurs MCP (task-master, sequential-thinking, filesystem, json-query)
# ============================================================================
MCP_PHASE4_CONFIG = {
    "task_master": {
        "enabled": True,
        "url": "http://localhost:8002",  # Port par défaut
        "timeout_ms": 30000,
        "tools": [
            "get_tasks", "next_task", "get_task", "set_task_status", "update_subtask",
            "parse_prd", "expand_task", "initialize_project", "analyze_project_complexity",
            "expand_all", "add_subtask", "remove_task", "add_task", "complexity_report"
        ]
    },
    "sequential_thinking": {
        "enabled": True,
        "url": "http://localhost:8003",  # Port par défaut
        "timeout_ms": 60000,  # Plus long pour le raisonnement
        "tools": ["sequentialthinking_tools"]
    },
    "fast_filesystem": {
        "enabled": True,
        "url": "http://localhost:8004",  # Port par défaut
        "timeout_ms": 10000,
        "tools": [
            "fast_list_allowed_directories", "fast_read_file", "fast_read_multiple_files",
            "fast_write_file", "fast_large_write_file", "fast_list_directory", "fast_get_file_info",
            "fast_create_directory", "fast_search_files", "fast_search_code", "fast_get_directory_tree",
            "fast_get_disk_usage", "fast_find_large_files", "fast_edit_block", "fast_safe_edit",
    "fast_edit_multiple_blocks", "fast_edit_blocks", "fast_extract_lines", "fast_copy_file",
            "fast_move_file", "fast_delete_file", "fast_batch_file_operations", "fast_compress_files",
            "fast_extract_archive", "fast_sync_directories"
        ]
    },
    "json_query": {
        "enabled": True,
        "url": "http://localhost:8005",  # Port par défaut
        "timeout_ms": 5000,
        "tools": ["json_query_jsonpath", "json_query_search_keys", "json_query_search_values"]
    }
}

# ============================================================================
# SEUILS D'ALERTES
# ============================================================================
ALERT_THRESHOLDS = {
    "caution": 80,
    "warning": 90,
    "critical": 95
}

# ============================================================================
# CHEMINS
# ============================================================================
DEFAULT_LOG_PATH = "~/.continue/logs/core.log"
