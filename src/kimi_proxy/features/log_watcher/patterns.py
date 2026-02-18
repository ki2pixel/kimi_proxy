"""
Patterns regex pour le parsing des logs Continue.
"""
import re

# Patterns standards pour extraction de tokens (avec support du tilde ~)
TOKEN_PATTERNS = [
    # Pattern: "prompt tokens: 1234, completion tokens: 567" (avec ~ optionnel)
    re.compile(r'prompt\s*tokens?[\s:]+~?(\d+)', re.IGNORECASE),
    re.compile(r'completion\s*tokens?[\s:]+~?(\d+)', re.IGNORECASE),
    # Pattern: "tokens: 1234" ou "token count: 1234" (avec ~ optionnel)
    re.compile(r'(?:total\s+)?tokens?[\s:]+~?(\d+)', re.IGNORECASE),
    # Pattern: contextLength: 262144 ou context_length: 262144
    re.compile(r'context[_\s]?[Ll]ength[\s:]+(\d+)', re.IGNORECASE),
    # Pattern JSON-like: "prompt_tokens":1234
    re.compile(r'"prompt_tokens"\s*:\s*(\d+)', re.IGNORECASE),
    re.compile(r'"completion_tokens"\s*:\s*(\d+)', re.IGNORECASE),
    re.compile(r'"total_tokens"\s*:\s*(\d+)', re.IGNORECASE),
]

# Patterns spécifiques au bloc CompileChat de Continue
COMPILE_CHAT_PATTERNS = {
    'context_length': re.compile(r'context[Ll]ength[\s:]+(\d+)', re.IGNORECASE),
    'tools': re.compile(r'tools?[\s:]+~?(\d+)', re.IGNORECASE),
    'system_message': re.compile(r'system\s+message[\s:]+~?(\d+)', re.IGNORECASE),
}

# Patterns pour les erreurs API (429/quota)
API_ERROR_PATTERNS = [
    # Pattern: input_token_count, limit: 12345
    re.compile(r'input_token_count,\s+limit:\s*(\d+)', re.IGNORECASE),
    # Pattern: "limit": 12345 dans JSON d'erreur
    re.compile(r'"limit"\s*:\s*(\d+)', re.IGNORECASE),
    # Pattern: rate limit exceeded, current: 12345
    re.compile(r'rate\s+limit.*current[:\s]+(\d+)', re.IGNORECASE),
]

# Pattern pour détecter le début du bloc CompileChat
COMPILE_CHAT_START = re.compile(r'Request\s+had\s+the\s+following\s+token\s+counts', re.IGNORECASE)

# Pattern pour détecter la fin du bloc (ligne vide)
COMPILE_CHAT_END = re.compile(r'^[\s]*$', re.IGNORECASE)

# Mots-clés pertinents pour filtrer les lignes
RELEVANT_KEYWORDS = [
    'token', 'context', 'prompt', 'completion',
    'usage', 'metrics', 'llm', 'request', 'system message',
    'tools', 'compile', 'limit', 'rate', 'quota', 'error'
]


def is_relevant_line(line: str) -> bool:
    """Vérifie si une ligne contient des métriques de tokens potentielles."""
    line_lower = line.lower()
    return any(kw in line_lower for kw in RELEVANT_KEYWORDS)
