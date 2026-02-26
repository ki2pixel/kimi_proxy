"""kimi_proxy.features.observation_masking.schema1

Schéma 1 — Observation Masking (conversation-level).

Responsabilité (couche Features):
- Masquer les anciens tool results (messages `role="tool"`) plus vieux qu'une
  fenêtre N de "tours tool".
- Préserver strictement l'intégrité du tool-calling:
  - ne jamais supprimer/ajouter/réordonner des messages,
  - ne jamais modifier `assistant.tool_calls` ni `tool.tool_call_id`,
  - remplacer uniquement `content` des messages `role="tool"` éligibles.

Le masking est une transformation pure (sans I/O, sans DB, sans réseau).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Optional


ChatMessage = dict[str, object]


@dataclass(frozen=True)
class MaskPolicy:
    """Politique de masking Schéma 1.

    Attributes:
        enabled: Active/désactive le masking.
        window_turns: Nombre de derniers "tours tool" dont on conserve les tool results.
        keep_errors: Conserver intacts les tool results qui ressemblent à des erreurs.
        keep_last_k_per_tool: Exemption optionnelle: conserver les K derniers résultats
            pour chaque outil (même s'ils sortent de la fenêtre).
        placeholder_template: Template court (français) pour remplacer le contenu.
            Variables supportées: {tool_call_id}, {tool_name}, {original_chars}.
    """

    enabled: bool = False
    window_turns: int = 8
    keep_errors: bool = True
    keep_last_k_per_tool: int | None = None
    placeholder_template: str = (
        "[Observation masquée: résultat d’outil ancien (tool_call_id={tool_call_id}, "
        "outil={tool_name}, chars={original_chars})]"
    )


def mask_old_tool_results(messages: list[ChatMessage], policy: MaskPolicy) -> list[ChatMessage]:
    """Masque les anciens tool results (> window_turns tours tool).

    Note: si `policy.enabled` est False, retourne `messages` inchangé.
    """

    if not policy.enabled:
        return messages

    if policy.window_turns <= 0:
        return messages

    extraction = _extract_tool_turns(messages)
    if not extraction.turns:
        return messages

    keep_ids = _compute_keep_ids_by_window(extraction.turns, policy.window_turns)

    if policy.keep_last_k_per_tool is not None and policy.keep_last_k_per_tool > 0:
        keep_ids |= _compute_keep_ids_by_last_k_per_tool(
            messages,
            id_to_tool_name=extraction.id_to_tool_name,
            keep_last_k_per_tool=policy.keep_last_k_per_tool,
        )

    output: list[ChatMessage] = []
    for msg in messages:
        role = msg.get("role")
        if role != "tool":
            output.append(dict(msg))
            continue

        tool_call_id_obj = msg.get("tool_call_id")
        if not isinstance(tool_call_id_obj, str) or not tool_call_id_obj:
            output.append(dict(msg))
            continue

        # Fallback conservateur: tool_call_id orphelin => no-op
        if tool_call_id_obj not in extraction.id_to_turn_index:
            output.append(dict(msg))
            continue

        if tool_call_id_obj in keep_ids:
            output.append(dict(msg))
            continue

        content_obj = msg.get("content")
        if policy.keep_errors and _looks_like_error_tool_content(content_obj):
            output.append(dict(msg))
            continue

        if not isinstance(content_obj, str):
            # Format inattendu (multimodal, etc.) => no-op
            output.append(dict(msg))
            continue

        tool_name = extraction.id_to_tool_name.get(tool_call_id_obj) or "inconnu"
        placeholder = _render_placeholder(
            template=policy.placeholder_template,
            tool_call_id=tool_call_id_obj,
            tool_name=tool_name,
            original_chars=len(content_obj),
        )

        masked_msg = dict(msg)
        masked_msg["content"] = placeholder
        output.append(masked_msg)

    return output


@dataclass(frozen=True)
class _ToolTurnExtraction:
    turns: list[set[str]]
    id_to_turn_index: dict[str, int]
    id_to_tool_name: dict[str, str]


def _extract_tool_turns(messages: list[ChatMessage]) -> _ToolTurnExtraction:
    """Extrait les tours tool et le mapping id->tool_name, id->turn_index.

    Un tour tool = message assistant avec `tool_calls` list.
    """

    turns: list[set[str]] = []
    id_to_turn_index: dict[str, int] = {}
    id_to_tool_name: dict[str, str] = {}

    for msg in messages:
        if msg.get("role") != "assistant":
            continue

        tool_calls_obj = msg.get("tool_calls")
        if not isinstance(tool_calls_obj, list):
            continue

        call_ids: set[str] = set()
        for tc in tool_calls_obj:
            if not isinstance(tc, dict):
                continue

            tc_id = tc.get("id")
            if not isinstance(tc_id, str) or not tc_id:
                continue

            call_ids.add(tc_id)

            tool_name = _extract_tool_name_from_tool_call(tc)
            if tool_name is not None:
                id_to_tool_name[tc_id] = tool_name

        if not call_ids:
            continue

        turn_index = len(turns)
        turns.append(call_ids)
        for tc_id in call_ids:
            id_to_turn_index[tc_id] = turn_index

    return _ToolTurnExtraction(turns=turns, id_to_turn_index=id_to_turn_index, id_to_tool_name=id_to_tool_name)


def _extract_tool_name_from_tool_call(tool_call: dict[str, object]) -> Optional[str]:
    """Extrait `function.name` d'un tool_call OpenAI compatible."""

    function_obj = tool_call.get("function")
    if not isinstance(function_obj, dict):
        return None

    name_obj = function_obj.get("name")
    if isinstance(name_obj, str) and name_obj:
        return name_obj

    return None


def _compute_keep_ids_by_window(turns: list[set[str]], window_turns: int) -> set[str]:
    if window_turns <= 0:
        return set()

    start = max(0, len(turns) - window_turns)
    keep: set[str] = set()
    for turn_ids in turns[start:]:
        keep |= turn_ids
    return keep


def _compute_keep_ids_by_last_k_per_tool(
    messages: list[ChatMessage],
    *,
    id_to_tool_name: dict[str, str],
    keep_last_k_per_tool: int,
) -> set[str]:
    """Conserve au moins les K derniers tool results par tool_name."""

    keep: set[str] = set()
    seen_per_tool: dict[str, int] = {}

    # scan reverse for tool results
    for msg in reversed(messages):
        if msg.get("role") != "tool":
            continue

        tool_call_id_obj = msg.get("tool_call_id")
        if not isinstance(tool_call_id_obj, str) or not tool_call_id_obj:
            continue

        tool_name = id_to_tool_name.get(tool_call_id_obj)
        if tool_name is None:
            continue

        count = seen_per_tool.get(tool_name, 0)
        if count >= keep_last_k_per_tool:
            continue

        keep.add(tool_call_id_obj)
        seen_per_tool[tool_name] = count + 1

    return keep


def _looks_like_error_tool_content(content: object) -> bool:
    if not isinstance(content, str) or not content:
        return False

    # Heuristique 1: mots clés fréquents
    lowered = content.lower()
    if "traceback" in lowered:
        return True
    if "exception" in lowered:
        return True
    if "timeout" in lowered:
        return True
    if "connect_error" in lowered:
        return True
    if "connection refused" in lowered:
        return True

    # Attention aux faux positifs: tester patterns "error" plus stricts
    if "\nerror" in lowered or "\rerror" in lowered:
        return True

    # Heuristique 2: JSON {"error": ...} / {"status":"error"}
    stripped = content.lstrip()
    if not stripped:
        return False

    if stripped[0] not in "{[":
        return False

    try:
        parsed = json.loads(content)
    except Exception:
        return False

    if isinstance(parsed, dict):
        if "error" in parsed:
            return True
        status = parsed.get("status")
        if isinstance(status, str) and status.lower() == "error":
            return True

    return False


def _render_placeholder(
    *,
    template: str,
    tool_call_id: str,
    tool_name: str,
    original_chars: int,
) -> str:
    # Robustesse: si le template est invalide, fallback simple.
    try:
        return template.format(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            original_chars=original_chars,
        )
    except Exception:
        return (
            "[Observation masquée: résultat d’outil ancien "
            f"(tool_call_id={tool_call_id}, outil={tool_name}, chars={original_chars})]"
        )
