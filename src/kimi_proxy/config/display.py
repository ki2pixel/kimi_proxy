"""
Fonctions d'affichage pour providers et modèles.
"""

# Mapping des noms d'affichage des providers
PROVIDER_DISPLAY_NAMES = {
    "managed:kimi-code": "🌙 Kimi Code",
    "nvidia": "🟢 NVIDIA",
    "mistral": "🔷 Mistral",
    "openrouter": "🔀 OpenRouter",
    "siliconflow": "💧 SiliconFlow",
    "groq": "⚡ Groq",
    "cerebras": "🧠 Cerebras",
    "gemini": "💎 Gemini"
}

# Mapping des icônes Lucide
PROVIDER_ICONS = {
    "managed:kimi-code": "bot",
    "nvidia": "gpu",
    "mistral": "wind",
    "openrouter": "git-branch",
    "siliconflow": "droplets",
    "groq": "zap",
    "cerebras": "brain",
    "gemini": "sparkles"
}

# Mapping des couleurs Tailwind
PROVIDER_COLORS = {
    "managed:kimi-code": "purple",
    "nvidia": "green",
    "mistral": "blue",
    "openrouter": "orange",
    "siliconflow": "cyan",
    "groq": "yellow",
    "cerebras": "red",
    "gemini": "indigo"
}

# Mapping des noms d'affichage des modèles
MODEL_DISPLAY_NAMES = {
    "kimi-code/kimi-for-coding": "Kimi for Coding",
    "nvidia/kimi-k2.5": "Kimi K2.5",
    "nvidia/kimi-k2-thinking": "Kimi K2 Thinking",
    "mistral/codestral-2501": "Codestral 2501",
    "mistral/mistral-large-2411": "Mistral Large",
    "mistral/pixtral-large-2411": "Pixtral Large",
    "mistral/ministral-8b-2410": "Ministral 8B",
    "openrouter/aurora-alpha": "Aurora Alpha",
    "siliconflow/qwen3-32b": "Qwen 3 32B",
    "siliconflow/deepseek-v3.2": "DeepSeek V3.2",
    "groq/compound": "Compound",
    "groq/qwen3-32b": "Qwen 3 32B",
    "groq/gpt-oss-120b": "GPT-OSS 120B",
    "cerebras/qwen3-235b": "Qwen 3 235B",
    "cerebras/gpt-oss-120b": "GPT-OSS 120B",
    "cerebras/glm-4.7": "GLM-4.7",
    "gemini/gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite",
    "gemini/gemini-3-flash-preview": "Gemini 3 Flash Preview",
    "gemini/gemini-2.5-flash": "Gemini 2.5 Flash",
    "gemini/gemini-2.5-pro": "Gemini 2.5 Pro"
}


def get_provider_display_name(provider_key: str) -> str:
    """Retourne le nom d'affichage d'un provider."""
    return PROVIDER_DISPLAY_NAMES.get(
        provider_key,
        provider_key.replace("managed:", "").replace("-", " ").title()
    )


def get_provider_icon(provider_key: str) -> str:
    """Retourne l'icône Lucide pour un provider."""
    return PROVIDER_ICONS.get(provider_key, "cpu")


def get_provider_color(provider_key: str) -> str:
    """Retourne la couleur Tailwind pour un provider."""
    return PROVIDER_COLORS.get(provider_key, "slate")


def get_model_display_name(model_key: str) -> str:
    """Retourne le nom d'affichage d'un modèle."""
    if model_key in MODEL_DISPLAY_NAMES:
        return MODEL_DISPLAY_NAMES[model_key]
    
    # Fallback: nettoie le nom
    parts = model_key.split("/")
    if len(parts) > 1:
        return parts[-1].replace("-", " ").title()
    return model_key.replace("-", " ").title()


def get_max_context_for_model(model_key: str, models: dict, default: int = 262144) -> int:
    """Retourne la taille de contexte maximale pour un modèle."""
    model = models.get(model_key, {})
    return model.get("max_context_size", default)


def get_max_context_for_session(session: dict, models: dict, default: int = 262144) -> int:
    """
    Récupère le contexte max pour une session basé sur son provider.
    
    Si un modèle spécifique est stocké dans la session, utilise son contexte.
    Sinon, utilise le contexte le plus petit parmi les modèles du provider (conservateur).
    """
    if not session:
        return default
    
    from ..core.constants import DEFAULT_PROVIDER
    
    provider_key = session.get("provider", DEFAULT_PROVIDER)
    model_key = session.get("model")
    
    # Si un modèle spécifique est stocké, utilise son contexte
    if model_key and model_key in models:
        return models[model_key].get("max_context_size", default)
    
    # Sinon, trouve le contexte le plus petit parmi les modèles du provider
    min_context = None
    for mk, model in models.items():
        if model.get("provider") == provider_key:
            ctx = model.get("max_context_size", default)
            if min_context is None or ctx < min_context:
                min_context = ctx
    
    return min_context if min_context else default
