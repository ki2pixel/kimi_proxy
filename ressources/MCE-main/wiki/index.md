# MCE — Model Context Engine Wiki
Parent: None
Tags: #index, #documentation
---

Welcome to the **Model Context Engine (MCE)** LLM Wiki. This wiki is a persistent, compiled knowledge base describing the architecture, modules, and workflows of the MCE proxy.

## Core Map

### 1. Conceptual Foundation
*   [[mental_model]]: Conceptual architecture, request lifecycle diagram, and performance targets.

### 2. Main Orchestrator
*   [[proxy_server]]: The FastAPI reverse proxy (`core/proxy_server.py`) managing execution flow.

### 3. Pipeline Stages & Safeguards
*   [[circuit_breaker]]: Dynamic loop prevention and fuzzy token similarity matching (`engine/circuit_breaker.py`).
*   [[lazy_registrar]]: Dynamic capabilities registry and metadata meta-tools (`engine/lazy_registrar.py`).
*   [[token_economist]]: Evaluator for token spending limits and triggers (`engine/token_economist.py`).
*   [[squeezing]]: 3-layer reduction engine (pruner, semantic chunks, local LLM).
*   [[guardian]]: Security controls combining permission gates and drift sentinel (`engine/guardian/`).
*   [[time_machine]]: Time-travel checkpoints, branching, and state restoration (`engine/time_machine.py`).
*   [[skill_forge]]: Skill-based workflow triggers and constraints (`engine/skills/`).

### 4. Intelligence & Interfaces
*   [[memvault]]: In-memory SQLite persistence and memory-saving exports (`engine/intelligence/`).
*   [[cli]]: Typer suite for MCE commands (`cli/`).

### 5. Developer Guide
*   [[cookbook]]: Technical recipes for agents to implement codebase changes.

---
## Meta
*   [[schema]]: Rules and specifications for updating and formatting this wiki.
*   [[log]]: Append-only log of modifications to the knowledge base.
