# Tech Spec — Schéma 1 « Observation Masking » (conversation-level)

Date: 2026-02-26

## 0) Objectif

Appliquer un **masking conversationnel** des anciens tool results (messages `role="tool"`) **avant** envoi au provider via `/chat/completions`, afin de réduire les tokens/coûts tout en préservant **strictement** l’intégrité du tool-calling.

Ce Schéma 1 est **distinct** du masking actuel du MCP Gateway (`src/kimi_proxy/features/mcp/gateway.py`) qui tronque des payloads JSON-RPC.

## 1) Format de messages ciblé (faits)

Le proxy supporte un format OpenAI-compatible:

- `assistant.tool_calls[]` est une liste d’objets `{ id, type: "function", function: { name, arguments } }`.
- Le résultat d’outil est un message `{ "role": "tool", "tool_call_id": "<id>", "content": "..." }`.

Source: `docs/chat-completion_nano_gpt.md`.

## 2) Définition: “tour tool”

### 2.1 Définition

Un **tour tool** est défini comme un message `role="assistant"` qui contient une clé `tool_calls` de type liste.

- Un tour tool peut contenir **plusieurs** `tool_calls` (cas `parallel_tool_calls=true`).
- Les messages `role="tool"` sont rattachés à un tour tool via `tool_call_id ∈ assistant.tool_calls[].id`.

### 2.2 Conséquence pour `windowTurns`

`windowTurns` (fenêtre) est comptée en **nombre de tours tool** (pas en nombre de messages).

- On conserve **intacts** les tool results rattachés aux `windowTurns` derniers tours tool.
- On masque les tool results rattachés aux tours tool plus anciens.

## 3) Invariants (contraintes non négociables)

### 3.1 Invariants structurels

Le masking ne doit jamais:

1) **Supprimer** ou **ajouter** des entrées dans `messages`.
2) **Réordonner** des messages.
3) Modifier `tool_call_id` dans un message `role="tool"`.
4) Modifier les `assistant.tool_calls` (ni leur contenu, ni leurs IDs).

### 3.2 Invariants d’intégrité tool-calling

- La relation `assistant.tool_calls[].id` ↔ `tool.tool_call_id` doit rester cohérente.
- Le masking remplace uniquement `message["content"]` pour `role="tool"` (et seulement quand éligible).

## 4) Politique: `MaskPolicy` (contrat)

### 4.1 Champs

Les paramètres de policy (configurables via TOML) :

- `enabled: bool`
- `window_turns: int` (recommandé: 5–10 ; défaut proposé: 8)
- `keep_errors: bool` (défaut: true)
- `keep_last_k_per_tool: int | None` (optionnel, défaut: null)
- `placeholder_template: str`

### 4.2 Placeholder (obligations)

Le placeholder doit être:

- **court** (minimiser les tokens)
- en **français**
- informatif: inclure au minimum `tool_call_id`, et idéalement `tool_name` si récupérable.

Exemple (template logique):

`[Observation masquée: résultat d’outil ancien (tool_call_id={tool_call_id}, outil={tool_name}, chars={original_chars})]`

Note: `{tool_name}` peut être `inconnu` si non résolvable.

## 5) Éligibilité au masking

### 5.1 Sélection des tool results à masquer

Un message est **candidat** si:

- `message["role"] == "tool"`
- `tool_call_id` est une string non vide
- `tool_call_id` appartient à un tour tool identifié
- le tour tool associé est **plus ancien** que les `window_turns` derniers tours tool

### 5.2 Comportements fallback (edge cases)

1) **Messages tool orphelins** (tool_call_id non présent dans aucun `assistant.tool_calls[].id`):
   - Comportement proposé: **no-op** (ne pas masquer) par défaut.
   - Rationale: on ne peut pas associer de “tour tool” → politique conservatrice pour éviter de masquer un artefact déjà incohérent.

2) `content` non-string (ex: list multimodale):
   - Comportement: **no-op** (ne pas masquer).
   - Rationale: ne pas casser des structures non prévues.

## 6) keepErrors: heuristique de détection d’erreurs (contrat)

Si `keep_errors=true`, un message `role="tool"` éligible **ne doit pas** être masqué si son `content` ressemble à une erreur.

Heuristique minimale (ordre recommandé):

1) Si `content` est une string contenant (case-sensitive ou insensitive):
   - `Traceback` (Python)
   - `Exception`
   - `Error` (attention aux faux positifs; préférer `\nError` ou `"error"` JSON)
   - `timeout` / `connect_error` / `connection refused`

2) Si `content` semble JSON (`startswith("{")` ou `startswith("[")`), tenter `json.loads` et détecter:
   - dict avec clé `"error"`
   - dict avec `"status" == "error"`

Si parsing JSON échoue, fallback sur (1).

## 7) `keep_last_k_per_tool` (optionnel)

Si `keep_last_k_per_tool` est fourni:

- Pour chaque `tool_name`, conserver au moins les `K` derniers tool results (non masqués), même s’ils sont hors fenêtre.

Note: cela nécessite un mapping `tool_call_id -> tool_name` via les `assistant.tool_calls`.

## 8) Signatures Python (typing strict, pas de `Any`)

### 8.1 Types minimaux (recommandés)

Objectif: rester compatible avec l’usage actuel de `dict` dans `proxy.py`, tout en évitant `Any`.

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


class ToolCallFunction(TypedDict):
    name: str
    arguments: str


class ToolCall(TypedDict):
    id: str
    type: str
    function: ToolCallFunction


ChatMessage = dict[str, object]


@dataclass(frozen=True)
class MaskPolicy:
    enabled: bool
    window_turns: int
    keep_errors: bool
    keep_last_k_per_tool: int | None
    placeholder_template: str


def mask_old_tool_results(
    messages: list[ChatMessage],
    policy: MaskPolicy,
) -> list[ChatMessage]:
    ...
```

Note: en implémentation, on peut rester sur `dict[str, object]` pour `messages` afin d’éviter une migration globale de typing.

## 9) Algorithme (pseudocode)

```text
mask_old_tool_results(messages, policy):
  if not enabled or window_turns <= 0:
    return messages

  # A) Extraire les tours tool (dans l’ordre)
  turns = []
  id_to_tool_name = {}
  id_to_turn_index = {}
  for msg in messages:
    if msg.role == assistant and tool_calls is list:
      ids = {tc.id for tc in tool_calls if tc.id is str}
      if ids not empty:
        turns.append(ids)
        for tc in tool_calls:
          id_to_tool_name[tc.id] = tc.function.name (if available)
          id_to_turn_index[tc.id] = len(turns)-1

  # B) Calculer le set d’IDs à conserver (fenêtre)
  keep_turn_start = max(0, len(turns) - window_turns)
  keep_ids = union(turns[keep_turn_start:])

  # C) Option keep_last_k_per_tool (si présent)
  #    - scan tool messages from end, count per tool_name
  #    - add eligible ids to keep_ids

  # D) Construire une nouvelle liste de messages
  out = []
  for msg in messages:
    if msg.role != tool:
      out.append(copy(msg))
      continue

    tool_call_id = msg.tool_call_id
    if tool_call_id not str:
      out.append(copy(msg))
      continue

    # Orphelin (pas de tour associé) => no-op
    if tool_call_id not in id_to_turn_index:
      out.append(copy(msg))
      continue

    if tool_call_id in keep_ids:
      out.append(copy(msg))
      continue

    # keepErrors
    if keep_errors and looks_like_error(msg.content):
      out.append(copy(msg))
      continue

    if msg.content is not str:
      out.append(copy(msg))
      continue

    placeholder = render_placeholder(tool_call_id, tool_name, len(original_content))
    masked_msg = copy(msg); masked_msg.content = placeholder
    out.append(masked_msg)

  return out
```

## 10) Plan de tests minimum (pour T5)

- Invariants:
  - `len(messages_before) == len(messages_after)`
  - ordre identique
  - tool_call_id identiques
  - assistant.tool_calls identiques

- Fenêtre:
  - >N tours tool: seuls les tool results plus anciens masqués
  - multi-tool calls dans un tour: tous les ids du tour respectent la fenêtre

- keepErrors:
  - tool content “Traceback …” non masqué
  - tool JSON `{ "error": ... }` non masqué

- Orphelins:
  - tool_call_id absent de tool_calls => non masqué

Fin du document.