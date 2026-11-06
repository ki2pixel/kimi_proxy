# Diagramme d'architecture — Kimi Proxy Middleware MCP

```text
Client OpenAI-compatible (Cline, Continue, SDK)
  │
  │ POST /v1/chat/completions
  │ X-Target-Base-URL: https://provider.example/v1
  │ Authorization: Bearer <provider-key>
  ▼
┌──────────────────────────────────────────────┐
│ API FastAPI                                  │
│  /health                                     │
│  /models                                     │
│  /v1/chat/completions                        │
│  /api/mcp-gateway/{server}/rpc               │
│  /api/memory/*                               │
│  /api/mask, /api/sanitizer/stats             │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Features                                     │
│  tool fixing                                 │
│  observation masking (flag)                  │
│  context pruning (flag)                      │
│  mémoire MCP (SQLite + Qdrant)               │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Proxy                                        │
│  validation SSRF + DNS async                 │
│  headers provider                            │
│  HTTPX send / send_streaming                 │
│  relay SSE                                   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Core                                         │
│  SQLite : masked_content, mcp_memory_entries │
│  Tiktoken : comptage précis                  │
│  dataclasses MCP                             │
└──────────────────────────────────────────────┘
```

## Points importants

- Aucun endpoint WebSocket.
- Aucune route `/chat/completions`, `/api/sessions/*`, `/api/compaction/*`, `/api/compress/*`.
- Le streaming est un relay SSE pur ; la clé provider reste dans `Authorization`.
- Si `KIMI_ADMIN_KEY` est défini, l'administration passe par `X-Admin-Key`.
