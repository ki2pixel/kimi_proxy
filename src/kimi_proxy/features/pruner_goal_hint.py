"""kimi_proxy.features.pruner_goal_hint

Heuristiques déterministes pour dériver un `goal_hint` à partir d'une liste de
messages style OpenAI.

Contraintes (Lot B1):
- Couche Features uniquement (pas d'I/O, pas d'appels réseau)
- Strict typing (pas de Any)
- Déterministe (aucun appel LLM)

Objectif:
- Exploiter les signaux de planification (Plan/TODO/Mission) et le dernier
  message utilisateur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, TypedDict


MessageRole = Literal["system", "user", "assistant", "tool", "function"]


class ChatMessage(TypedDict, total=False):
    role: MessageRole
    content: object


@dataclass(frozen=True)
class GoalHintConfig:
    default_goal_hint: str = "objectif principal"
    max_lines: int = 3
    max_chars: int = 280
    plan_markers: tuple[str, ...] = (
        "plan",
        "todo",
        "mission",
        "objectif",
        "objectifs",
        "next step",
        "next steps",
    )


def derive_goal_hint(messages: list[ChatMessage], cfg: GoalHintConfig | None = None) -> str:
    """Dérive un goal_hint à partir de messages.

    Règles (ordre):
    1) Si des lignes de planification existent (Plan/TODO/Mission...), extraire
       les premières lignes utiles.
    2) Sinon, utiliser le dernier message utilisateur (string) non vide.
    3) Sinon, retourner `cfg.default_goal_hint`.
    """

    config = cfg or GoalHintConfig()

    plan = _extract_plan_lines(messages, config)
    if plan:
        return _finalize_hint("\n".join(plan), config)

    last_user = _last_user_text(messages)
    if last_user:
        return _finalize_hint(last_user, config)

    return _finalize_hint(config.default_goal_hint, config)


def _extract_plan_lines(messages: list[ChatMessage], cfg: GoalHintConfig) -> list[str]:
    """Extrait des lignes à forte densité d'intention (Plan/TODO/Mission)."""

    text_blocks: list[str] = []
    for msg in messages:
        role = msg.get("role")
        if role not in {"user", "assistant", "system"}:
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            text_blocks.append(content)

    if not text_blocks:
        return []

    combined = "\n".join(text_blocks)
    lines = [ln.strip() for ln in combined.splitlines()]

    marker_re = re.compile(r"^\s*(?:" + "|".join(re.escape(m) for m in cfg.plan_markers) + r")\s*[:\-–—]?\s*$", re.IGNORECASE)
    bullet_re = re.compile(r"^\s*(?:[-*•]|\d+\.|\d+\))\s+(.*)\s*$")

    out: list[str] = []
    in_plan_section = False

    for ln in lines:
        if not ln:
            if in_plan_section:
                # Une ligne vide termine la section de plan pour garder un comportement stable.
                in_plan_section = False
            continue

        if marker_re.match(ln):
            in_plan_section = True
            continue

        if not in_plan_section:
            # Marker inline (ex: "Plan: ...")
            for m in cfg.plan_markers:
                prefix = m.lower()
                if ln.lower().startswith(prefix + ":"):
                    value = ln[len(prefix) + 1 :].strip()
                    if value:
                        out.append(value)
                    in_plan_section = True
                    break
            if out:
                continue

        if in_plan_section:
            m = bullet_re.match(ln)
            if m:
                item = m.group(1).strip()
                if item:
                    out.append(item)
            else:
                out.append(ln)

        if len(out) >= max(1, cfg.max_lines):
            break

    # Nettoyage basique
    cleaned: list[str] = []
    for ln in out:
        ln2 = re.sub(r"\s+", " ", ln).strip()
        if ln2 and ln2 not in cleaned:
            cleaned.append(ln2)
    return cleaned[: max(1, cfg.max_lines)]


def _last_user_text(messages: list[ChatMessage]) -> str | None:
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _finalize_hint(value: str, cfg: GoalHintConfig) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return cfg.default_goal_hint
    if cfg.max_chars > 0 and len(cleaned) > cfg.max_chars:
        return cleaned[: cfg.max_chars].rstrip()
    return cleaned
