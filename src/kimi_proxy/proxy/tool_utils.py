"""
Utilitaires pour les tool calls dans le proxy.

Génère et valide les IDs de tool calls, et répare les arguments JSON malformés
via un pipeline de stratégies pures. Aucune évaluation dynamique de code n'est
effectuée sur les chaînes issues du modèle.
"""
import json
import re
import secrets
import string
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Optional, Sequence, TypedDict


# Budget de réparation par appel (millisecondes).
CIRCUIT_BREAKER_CONFIG = {
    "max_time_ms": 100,
    "enabled": True,
}


class StrategyMetrics(TypedDict):
    direct_fix: int
    reconstruct_basic: int
    reconstruct_complex: int
    all_failed: int


class JsonFixMetrics(TypedDict):
    total_attempts: int
    success_by_strategy: StrategyMetrics
    failure_reasons: Deque[str]


JSON_FIX_METRICS: JsonFixMetrics = {
    "total_attempts": 0,
    "success_by_strategy": {
        "direct_fix": 0,
        "reconstruct_basic": 0,
        "reconstruct_complex": 0,
        "all_failed": 0,
    },
    "failure_reasons": deque(maxlen=100),
}


@dataclass(frozen=True)
class RepairStrategy:
    """Stratégie pure de réparation JSON."""

    name: str
    metric_key: str
    apply: Callable[[str], str]


def _try_validate_json_candidate(candidate: str) -> bool:
    """Retourne True si `candidate` est un JSON valide."""
    try:
        json.loads(candidate)
        return True
    except json.JSONDecodeError:
        return False


def detect_and_merge_concatenated_json(json_str: str) -> str:
    """Détecte et fusionne les structures JSON concaténées ou dupliquées."""
    if not json_str or len(json_str) < 4:
        return json_str

    if not re.search(r'}\s*{', json_str):
        return json_str

    try:
        objects = []
        depth = 0
        start_idx = None

        for index, char in enumerate(json_str):
            if char == '{':
                if depth == 0:
                    start_idx = index
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start_idx is not None:
                    obj_str = json_str[start_idx:index + 1]
                    try:
                        objects.append(json.loads(obj_str))
                    except json.JSONDecodeError:
                        pass
                    start_idx = None

        if len(objects) > 1:
            merged: Dict[str, Any] = {}
            for obj in objects:
                if isinstance(obj, dict):
                    merged.update(obj)
            if merged:
                return json.dumps(merged, ensure_ascii=False)

    except Exception as exc:
        print(f"   Erreur de détection de concaténation JSON : {exc}")

    return json_str


def generate_tool_call_id(length: int = 9) -> str:
    """Génère un ID de tool call alphanumérique valide."""
    if length < 1:
        raise ValueError("La longueur doit être au moins 1")

    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def fix_tool_calls_in_request(body: Dict[str, Any]) -> Dict[str, Any]:
    """Corrige les tool calls dans une requête en générant les IDs manquants."""
    if not isinstance(body, dict):
        return body

    messages = body.get('messages', [])
    for message in messages:
        if not isinstance(message, dict):
            continue

        tool_calls = message.get('tool_calls', [])
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue

                tool_call_id = tool_call.get('id')
                if not tool_call_id:
                    new_id = generate_tool_call_id()
                    tool_call['id'] = new_id
                    print(f"   [TOOL CALL] ID généré : {new_id}")

    return body


def normalize_tool_call_arguments(body: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
    """Normalise les `function.arguments` des `assistant.tool_calls` avant envoi."""
    if not isinstance(body, dict):
        return body, 0

    fixed_arguments_count = 0
    messages = body.get("messages", [])
    if not isinstance(messages, list):
        return body, 0

    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "assistant":
            continue

        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue

        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue

            function_obj = tool_call.get("function")
            if not isinstance(function_obj, dict):
                continue

            arguments = function_obj.get("arguments")

            if isinstance(arguments, dict):
                function_obj["arguments"] = json.dumps(arguments, ensure_ascii=False)
                fixed_arguments_count += 1
                continue

            if not isinstance(arguments, str) or not arguments.strip():
                continue

            try:
                json.loads(arguments)
                continue
            except json.JSONDecodeError:
                fixed_arguments = fix_malformed_json_arguments(arguments)
                if fixed_arguments == arguments:
                    continue

                try:
                    json.loads(fixed_arguments)
                except json.JSONDecodeError:
                    continue

                function_obj["arguments"] = fixed_arguments
                fixed_arguments_count += 1

    return body, fixed_arguments_count


def reconstruct_from_corrupted_arguments(corrupted_str: str) -> Optional[str]:
    """Reconstruction conservatrice d'un objet JSON d'arguments corrompu."""
    if not corrupted_str or not corrupted_str.strip():
        return None

    property_pattern = re.compile(
        r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*"|true|false|null|-?\d+(?:\.\d+)?)'
    )
    reconstructed: Dict[str, Any] = {}

    for match in property_pattern.finditer(corrupted_str):
        key = match.group(1)
        raw_value = match.group(2)

        if raw_value.startswith('"') and raw_value.endswith('"'):
            reconstructed[key] = raw_value[1:-1]
        elif raw_value == 'true':
            reconstructed[key] = True
        elif raw_value == 'false':
            reconstructed[key] = False
        elif raw_value == 'null':
            reconstructed[key] = None
        else:
            reconstructed[key] = float(raw_value) if '.' in raw_value else int(raw_value)

    if not reconstructed:
        return None

    return json.dumps(reconstructed, ensure_ascii=False)


def _parse_simple_value(value_str: str) -> object:
    if value_str.startswith('"') and value_str.endswith('"'):
        return value_str[1:-1]
    if value_str == 'true':
        return True
    if value_str == 'false':
        return False
    if value_str == 'null':
        return None
    if value_str.replace('.', '').replace('-', '').isdigit():
        return float(value_str) if '.' in value_str else int(value_str)
    return value_str


def _parse_simple_array(value_str: str) -> list[object]:
    if not (value_str.startswith('[') and value_str.endswith(']')):
        return []
    items: list[object] = []
    for item in value_str[1:-1].split(','):
        stripped = item.strip()
        if stripped:
            items.append(_parse_simple_value(stripped))
    return items


def _extract_properties_regex(corrupted_str: str) -> Dict[str, Any]:
    property_pattern = r'"([^"]+)"\s*:\s*([^,}\]]*?)(?=,|"[^"]*"\s*:|})'
    properties: Dict[str, Any] = {}

    for match in re.finditer(property_pattern, corrupted_str):
        key = match.group(1)
        value_str = match.group(2).strip()
        if value_str.startswith('[') and value_str.endswith(']'):
            properties[key] = _parse_simple_array(value_str)
        else:
            properties[key] = _parse_simple_value(value_str)

    return properties


def _reconstruct_from_tokens(corrupted_str: str) -> Optional[str]:
    tokens = re.findall(r'"[^"]*"|true|false|null|\d+\.?\d*|\{|\}|\[|\]|,', corrupted_str)
    clean_tokens = [token.strip() for token in tokens if token.strip()]

    if len(clean_tokens) < 3 or clean_tokens[0] != '{' or clean_tokens[-1] != '}':
        return None

    content_tokens = clean_tokens[1:-1]
    reconstructed: Dict[str, Any] = {}
    index = 0

    while index < len(content_tokens) - 1:
        token = content_tokens[index]
        if not (token.startswith('"') and content_tokens[index + 1] == ':'):
            index += 1
            continue

        key = token[1:-1] if token.startswith('"') else token
        value_token = content_tokens[index + 2] if index + 2 < len(content_tokens) else 'null'
        reconstructed[key] = _parse_simple_value(value_token)
        index += 3
        if index < len(content_tokens) and content_tokens[index] == ',':
            index += 1

    if not reconstructed:
        return None

    return json.dumps(reconstructed, ensure_ascii=False)


def reconstruct_complex_json(corrupted_str: str) -> Optional[str]:
    """Reconstruction agressive pour les JSON très corrompus."""
    try:
        properties = _extract_properties_regex(corrupted_str)
        if properties:
            return json.dumps(properties, ensure_ascii=False)
        return _reconstruct_from_tokens(corrupted_str)
    except Exception as exc:
        print(f"   Reconstruction complexe impossible : {exc}")
        return None


def _fix_direct_pattern_looped(value: str) -> str:
    for _ in range(5):
        previous = value
        value = value.replace('"rules": [""]cursor{"', '"rules": ["cursor"], "')
        if value == previous:
            break
    return value


def _fix_general_array(value: str) -> str:
    return re.sub(r'\[""\](\w+)\{', r'["\1"], {', value)


def _fix_trailing_commas(value: str) -> str:
    return value.replace(',}', '}').replace(',]', ']')


def _fix_property_comma(value: str) -> str:
    return re.sub(r'(\w+)"\s*"(\w+)":', r'\1","\2":', value)


def _fix_numeric_comma(value: str) -> str:
    return re.sub(r'(\d+)\s*"(\w+)":', r'\1, "\2":', value)


def _fix_boolean_comma(value: str) -> str:
    return re.sub(r'(true|false|null)\s*"(\w+)":', r'\1, "\2":', value)


def _fix_specific_reconstruction(value: str) -> str:
    return re.sub(r'\[""\]([a-zA-Z_]\w*)\{([a-zA-Z_]\w*)', r'["\1"], "\2": {', value)


def _fix_empty_array(value: str) -> str:
    return re.sub(r'\[\](\w+)\{', r'[], "\1": {', value)


def _fix_empty_element(value: str) -> str:
    return re.sub(r'\[""\]([^,])', r'["\1"]', value)


def _fix_advanced_quotes(value: str) -> str:
    value = re.sub(r'("(?:[^"\\]|\\.)*")', lambda match: match.group(1).replace("'", "\\'"), value)
    value = re.sub(r'("\w+")\s*(")', r'\1,\2', value)
    value = re.sub(r'(\w+|\]|\})\s*\{', r'\1, {', value)
    value = re.sub(r'(\w+|\]|\})\s*\[', r'\1, [', value)
    value = re.sub(r'(true|false|null|\d+|\w+)\s*(")', r'\1,\2', value)
    return value


def _fix_duplicate_object(value: str) -> str:
    if len(value) <= 50:
        return value

    duplicate_pattern = r'(\{"[^"]+"\s*:\s*"[^"]*"[^}]*\})\s*\{'
    match = re.search(duplicate_pattern, value)
    if not match:
        return value

    potential_duplicate = match.group(1)
    rest = value[match.end() - 1:]
    if potential_duplicate[:30] in rest[:60]:
        return potential_duplicate
    return value


def _fix_comma_before_property(value: str) -> str:
    return re.sub(r'("[^"]*")\s*"(\w+)":', r'\1, "\2":', value)


def _fix_comma_before_brace(value: str) -> str:
    return re.sub(r'("[^"]*"|\d+|true|false|null)\s*\{', r'\1, {', value)


def _fix_position_based(value: str) -> str:
    if len(value) <= 1000:
        return value

    potential_error_positions = [1146, len(value) // 2, len(value) - 100]
    for error_position in potential_error_positions:
        if len(value) <= error_position:
            continue

        start_position = max(0, error_position - 50)
        end_position = min(len(value), error_position + 50)
        context = value[start_position:end_position]
        context_fixed = re.sub(r'"\s+"(\w+)":', r'", "\1":', context)

        if context_fixed != context:
            return value[:start_position] + context_fixed + value[end_position:]

    return value


def _strategy_merge_concatenated(value: str) -> str:
    return detect_and_merge_concatenated_json(value)


def _strategy_direct_fixes(value: str) -> str:
    value = _fix_direct_pattern_looped(value)
    value = _fix_general_array(value)
    value = _fix_trailing_commas(value)
    value = _fix_property_comma(value)
    return value


def _strategy_advanced_fixes(value: str) -> str:
    value = _fix_specific_reconstruction(value)
    value = _fix_empty_array(value)
    value = _fix_empty_element(value)
    value = _fix_advanced_quotes(value)
    value = _fix_duplicate_object(value)
    value = _fix_comma_before_property(value)
    value = _fix_comma_before_brace(value)
    value = _fix_position_based(value)
    return value


def _strategy_reconstruct_basic(value: str) -> str:
    return reconstruct_from_corrupted_arguments(value) or value


def _strategy_reconstruct_complex(value: str) -> str:
    return reconstruct_complex_json(value) or value


REPAIR_STRATEGIES: tuple[RepairStrategy, ...] = (
    RepairStrategy("fusion_json_concatene", "direct_fix", _strategy_merge_concatenated),
    RepairStrategy("corrections_directes", "direct_fix", _strategy_direct_fixes),
    RepairStrategy("virgule_numerique", "direct_fix", _fix_numeric_comma),
    RepairStrategy("virgule_booleenne", "direct_fix", _fix_boolean_comma),
    RepairStrategy("corrections_avancees", "direct_fix", _strategy_advanced_fixes),
    RepairStrategy("reconstruction_basique", "reconstruct_basic", _strategy_reconstruct_basic),
    RepairStrategy("reconstruction_complexe", "reconstruct_complex", _strategy_reconstruct_complex),
)


def run_repair_pipeline(
    arguments_str: str,
    strategies: Sequence[RepairStrategy] = REPAIR_STRATEGIES,
    *,
    max_time_ms: int | None = None,
) -> str:
    """Exécute les stratégies de réparation JSON sans évaluation dynamique."""
    cleaned = arguments_str.strip()
    if _try_validate_json_candidate(cleaned):
        return cleaned

    JSON_FIX_METRICS["total_attempts"] += 1
    started_at = time.monotonic()

    for strategy in strategies:
        if max_time_ms is not None:
            elapsed_ms = (time.monotonic() - started_at) * 1000
            if elapsed_ms > max_time_ms:
                print("   ⚠️ Réparation JSON interrompue : délai maximal dépassé")
                JSON_FIX_METRICS["failure_reasons"].append(
                    "Disjoncteur activé : délai maximal de réparation JSON dépassé"
                )
                break

        candidate = strategy.apply(cleaned)
        if _try_validate_json_candidate(candidate):
            metric_key = strategy.metric_key
            if metric_key in JSON_FIX_METRICS["success_by_strategy"]:
                JSON_FIX_METRICS["success_by_strategy"][metric_key] += 1  # type: ignore[literal-required]
            print(f"   ✅ Réparation JSON réussie via {strategy.name}")
            return candidate

        cleaned = candidate

    JSON_FIX_METRICS["success_by_strategy"]["all_failed"] += 1
    JSON_FIX_METRICS["failure_reasons"].append(
        "Échec de toutes les stratégies de réparation JSON"
    )
    print("   ❌ Réparation JSON impossible après toutes les stratégies")
    return arguments_str


def fix_malformed_json_arguments(
    arguments_str: str,
    enable_circuit_breaker: bool = True,
) -> str:
    """Répare des arguments JSON malformés avec un budget de temps borné."""
    if not arguments_str or not arguments_str.strip():
        return arguments_str

    max_time_ms: int | None = None
    if enable_circuit_breaker and CIRCUIT_BREAKER_CONFIG["enabled"]:
        max_time_ms = CIRCUIT_BREAKER_CONFIG["max_time_ms"]

    return run_repair_pipeline(
        arguments_str,
        REPAIR_STRATEGIES,
        max_time_ms=max_time_ms,
    )
