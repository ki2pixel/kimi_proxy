> ## Documentation Index
> Fetch the complete documentation index at: https://docs.nano-gpt.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Chat Completion

> Creates a chat completion for the provided messages

<Note>
  If you are on a NanoGPT subscription and want to keep requests limited to subscription-included models (or you have no prepaid balance), use the subscription base URL: `https://nano-gpt.com/api/subscription/v1/chat/completions` (swap `/api/v1` for `/api/subscription/v1`).
</Note>

<Note>
  Provider selection is available for pay-as-you-go requests on supported open-source models. Set the `X-Provider` header or save preferences to choose a provider. If you are on a subscription and want provider selection for a subscription-included model, force paid routing with the pay-as-you-go billing override (`billing_mode: "paygo"` or `X-Billing-Mode: paygo`). See [Provider Selection](/api-reference/miscellaneous/provider-selection) and [Pay-As-You-Go Billing Override](/api-reference/miscellaneous/billing-override).
</Note>

## Page map

Use the jump list below to navigate the long-form reference quickly.

<AccordionGroup>
  <Accordion title="Basics">
    * [Tool calling](#tool-calling)
    * [Overview](#overview)
  </Accordion>

  <Accordion title="Sampling & decoding">
    * [Sampling & Decoding Controls](#sampling-decoding-controls)
    * [Temperature & Nucleus](#temperature-nucleus)
    * [Length & Stopping](#length-stopping)
    * [Penalties & Repetition Guards](#penalties-repetition-guards)
    * [Logit Shaping & Determinism](#logit-shaping-determinism)
    * [Sampling example request](#example-request-1)
  </Accordion>

  <Accordion title="Structured outputs">
    * [Structured Outputs (response\_format)](#structured-outputs-response-format)
    * [Supported Formats](#supported-formats)
    * [JSON Object Mode](#json-object-mode)
    * [JSON Schema Mode](#json-schema-mode-structured-outputs)
    * [Schema Requirements](#schema-requirements)
    * [Example Request](#example-request-2)
    * [Example Response](#example-response)
    * [Vercel AI SDK](#usage-with-vercel-ai-sdk)
  </Accordion>

  <Accordion title="Web search">
    * [Web Search](#web-search)
    * [Option A: model suffixes](#option-a-model-suffixes)
    * [Option B: request body configuration](#option-b-request-body-configuration-recommended)
    * [Brave Answers and Research models](#brave-answers-and-research-models)
    * [Brave-specific request fields](#brave-specific-request-fields)
    * [Provider-specific options](#provider-specific-options-set-inside-websearch)
    * [Examples](#examples)
    * [Pricing by provider](#pricing-by-provider)
    * [Bring your own key (BYOK)](#bring-your-own-key-byok)
  </Accordion>

  <Accordion title="Images & caching">
    * [Image Input](#image-input)
    * [Supported Forms](#supported-forms)
    * [Message Shape](#message-shape)
    * [cURL - Image URL](#curl-image-url-non-streaming)
    * [cURL - Base64 Data URL](#curl-base64-data-url-non-streaming)
    * [cURL - Streaming SSE](#curl-streaming-sse)
    * [Prompt Caching (Claude Models)](#prompt-caching-claude-models)
    * [Cache Consistency](#cache-consistency-with-stickyprovider)
    * [Troubleshooting](#troubleshooting)
  </Accordion>

  <Accordion title="Memory & reasoning">
    * [Context Memory](#context-memory)
    * [Custom Context Size Override](#custom-context-size-override)
    * [Reasoning Streams](#reasoning-streams)
    * [Endpoint variants](#endpoint-variants)
    * [Streaming payload format](#streaming-payload-format)
    * [Showing or hiding reasoning](#showing-or-hiding-reasoning)
    * [Reasoning Effort](#reasoning-effort)
    * [Model suffix: :reasoning-exclude](#model-suffix-reasoning-exclude)
    * [Legacy delta field compatibility](#legacy-delta-field-compatibility)
  </Accordion>

  <Accordion title="Other">
    * [Service tiers (priority)](#service-tiers-priority)
    * [YouTube Transcripts](#youtube-transcripts)
    * [Performance Benchmarks](#performance-benchmarks)
    * [Important Notes](#important-notes)
  </Accordion>
</AccordionGroup>

## Tool calling

The `/api/v1/chat/completions` endpoint supports OpenAI-compatible function calling. You can describe callable functions in the `tools` array, control when the model may invoke them, and continue the conversation by echoing `tool` role messages that reference the assistant's chosen call.

### Request parameters

* `tools` (optional array): Each entry must be `{ "type": "function", "function": { "name": string, "description"?: string, "parameters"?: JSON-Schema object } }`. Only `function` tools are accepted. The serialized `tools` payload is limited to 200 KB (overrides via `TOOL_SPEC_MAX_BYTES`); violating the shape or size yields a 400 with `tool_spec_too_large`, `invalid_tool_spec`, or `invalid_tool_spec_parse`.
* `tool_choice` (optional string or object): Defaults to `auto`. Set `"none"` to guarantee no tool calls (the server also drops the `tools` payload upstream), `"required"` to force the next response to be a tool call, or `{ "type": "function", "function": { "name": "your_function" } }` to pin the exact function.
* `parallel_tool_calls` (optional boolean): When `true` the flag is forwarded to providers that support issuing multiple tool calls in a single turn. Models that ignore the flag fall back to sequential calls.
* `messages[].tool_calls` (assistant role): Persist the tool call metadata returned by the model so future turns can see which functions were invoked. Each item uses the OpenAI shape `{ id, type: "function", function: { name, arguments } }`.
* `messages[]` with `role: "tool"`: Respond to the model by sending `{ "role": "tool", "tool_call_id": "<assistant tool_calls id>", "content": "<JSON or text payload>" }`. The server drops any tool response that references an unknown `tool_call_id`, so keep the IDs in sync.
* Validation behavior: If you send `tool_choice: "none"` with a `tools` array the request is accepted but the tools are omitted before hitting the model; invalid schemas or oversize payloads return the error codes above.

### Example request

```http  theme={null}
POST /api/v1/chat/completions
{
  "model": "google/gemini-3-flash-preview",
  "messages": [
    { "role": "user", "content": "What's the temperature in San Francisco right now?" }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "lookup_weather",
        "description": "Fetch the current weather for a city.",
        "parameters": {
          "type": "object",
          "properties": {
            "city": { "type": "string" },
            "unit": { "type": "string", "enum": ["c", "f"] }
          },
          "required": ["city"]
        }
      }
    }
  ],
  "tool_choice": "auto",
  "parallel_tool_calls": true
}
```

### Example assistant/tool turn

```json  theme={null}
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "lookup_weather",
        "arguments": "{\"city\":\"San Francisco\",\"unit\":\"f\"}"
      }
    }
  ]
}
```

```json  theme={null}
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "{\"city\":\"San Francisco\",\"temperatureF\":58,\"conditions\":\"foggy\"}"
}
```

Streaming responses emit delta events that mirror OpenAI's `tool_calls` schema, so consumers can reuse their existing parsing logic without changes.

## Overview

The Chat Completion endpoint provides OpenAI-compatible chat completions.

## Sampling & Decoding Controls

The `/api/v1/chat/completions` endpoint accepts a full set of sampling and decoding knobs. All fields are optional; omit any you want to leave at provider defaults.

### Temperature & Nucleus

| Parameter                       | Range/Default          | Description                                                                                                                                       |
| ------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `temperature`                   | 0–2 (provider default) | Classic randomness control; higher values explore more. If omitted, NanoGPT does not force a value and the routed provider/model default applies. |
| `top_p`                         | 0–1 (default 1)        | Nucleus sampling that trims to the smallest set above `top_p` cumulative probability.                                                             |
| `top_k`                         | 1+                     | Sample only from the top-k tokens each step.                                                                                                      |
| `top_a`                         | provider default       | Blends temperature and nucleus behavior; set only if a model calls for it.                                                                        |
| `min_p`                         | 0–1                    | Require each candidate token to exceed a probability floor.                                                                                       |
| `tfs`                           | 0–1                    | Tail free sampling; 1 disables.                                                                                                                   |
| `eta_cutoff` / `epsilon_cutoff` | provider default       | Drop tokens once they fall below the tail thresholds.                                                                                             |
| `typical_p`                     | 0–1                    | Entropy-based nucleus sampling; keeps tokens whose surprise matches expected entropy.                                                             |
| `mirostat_mode`                 | 0/1/2                  | Enable Mirostat sampling; set tau/eta when active.                                                                                                |
| `mirostat_tau` / `mirostat_eta` | provider default       | Target entropy and learning rate for Mirostat.                                                                                                    |

### Length & Stopping

| Parameter                    | Range/Default           | Description                                                                                                                              |
| ---------------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `max_tokens`                 | 1+ (provider default)   | Upper bound on generated tokens. If omitted, NanoGPT does not enforce an explicit default and the routed provider/model default applies. |
| `min_tokens`                 | 0+ (default 0)          | Minimum completion length when provider supports it.                                                                                     |
| `stop`                       | string or string\[]     | Stop sequences passed upstream.                                                                                                          |
| `stop_token_ids`             | int\[]                  | Stop generation on specific token IDs (limited provider support).                                                                        |
| `include_stop_str_in_output` | boolean (default false) | Keep the stop sequence in the final text where supported.                                                                                |
| `ignore_eos`                 | boolean (default false) | Continue even if the model predicts EOS internally.                                                                                      |

### Penalties & Repetition Guards

| Parameter              | Range/Default      | Description                                                    |
| ---------------------- | ------------------ | -------------------------------------------------------------- |
| `frequency_penalty`    | -2 – 2 (default 0) | Penalize tokens proportional to prior frequency.               |
| `presence_penalty`     | -2 – 2 (default 0) | Penalize tokens based on whether they appeared at all.         |
| `repetition_penalty`   | -2 – 2             | Provider-agnostic repetition modifier; >1 discourages repeats. |
| `no_repeat_ngram_size` | 0+                 | Forbid repeating n-grams of the given size (limited support).  |
| `custom_token_bans`    | int\[]             | Fully block listed token IDs.                                  |

### Logit Shaping & Determinism

| Parameter         | Range/Default  | Description                                               |
| ----------------- | -------------- | --------------------------------------------------------- |
| `logit_bias`      | object         | Map token IDs to additive logits (OpenAI-compatible).     |
| `logprobs`        | boolean or int | Return token-level logprobs where supported.              |
| `prompt_logprobs` | boolean        | Request logprobs on the prompt when available.            |
| `seed`            | integer        | Make completions repeatable where the provider allows it. |

### Usage notes

* Parameters can be combined (e.g., `temperature` + `top_p` + `top_k`), but overly narrow settings may lead to early stops.
* Invalid ranges yield a 400 before reaching the provider.
* Provider defaults apply to any omitted field.

### Example request

```bash  theme={null}
curl -X POST https://nano-gpt.com/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-3-flash-preview",
    "messages": [
      {"role": "user", "content": "Write a creative story about space exploration"}
    ],
    "temperature": 0.8,
    "top_p": 0.9,
    "top_k": 40,
    "tfs": 0.8,
    "typical_p": 0.95,
    "mirostat_mode": 2,
    "mirostat_tau": 5,
    "mirostat_eta": 0.1,
    "max_tokens": 500,
    "frequency_penalty": 0.3,
    "presence_penalty": 0.1,
    "repetition_penalty": 1.1,
    "stop": ["###"],
    "seed": 42
  }'
```

## Structured Outputs (response\_format)

The `/api/v1/chat/completions` endpoint supports OpenAI-compatible structured outputs via the `response_format` parameter. This ensures the model returns valid JSON matching your specified schema.

### Supported Formats

| Type          | Description                                                |
| ------------- | ---------------------------------------------------------- |
| `json_object` | Forces the model to return valid JSON                      |
| `json_schema` | Forces the model to return JSON matching a specific schema |
| `text`        | Default text output (no constraint)                        |

### JSON Object Mode

Request valid JSON output without a specific schema:

```json  theme={null}
{
  "model": "openai/gpt-5.1",
  "messages": [{"role": "user", "content": "List 3 colors as JSON"}],
  "response_format": {"type": "json_object"}
}
```

### JSON Schema Mode (Structured Outputs)

Request JSON that conforms to a specific schema:

```json  theme={null}
{
  "model": "openai/gpt-5.1",
  "messages": [{"role": "user", "content": "What is 2+2?"}],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "math_answer",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "answer": {"type": "number"},
          "explanation": {"type": "string"}
        },
        "required": ["answer", "explanation"],
        "additionalProperties": false
      }
    }
  }
}
```

### Schema Requirements

When using `strict: true`:

* All properties must be listed in `required`
* Set `additionalProperties: false`
* NanoGPT automatically transforms optional properties to be nullable for OpenAI compatibility

### Supported Models

JSON schema mode works with most models including:

* OpenAI models (GPT-5.1, GPT-5.2, etc.)
* Anthropic Claude models
* Google Gemini models
* Many open-source models

### Example Request

<CodeGroup>
  ```bash cURL theme={null}
  curl -X POST https://nano-gpt.com/api/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "openai/gpt-5.1",
      "messages": [
        {"role": "user", "content": "Generate a person profile"}
      ],
      "response_format": {
        "type": "json_schema",
        "json_schema": {
          "name": "person",
          "strict": true,
          "schema": {
            "type": "object",
            "properties": {
              "name": {"type": "string"},
              "age": {"type": "number"},
              "skills": {
                "type": "array",
                "items": {"type": "string"}
              }
            },
            "required": ["name", "age", "skills"],
            "additionalProperties": false
          }
        }
      },
      "stream": false
    }'
  ```

  ```python Python theme={null}
  import requests

  response = requests.post(
      "https://nano-gpt.com/api/v1/chat/completions",
      headers={
          "Authorization": "Bearer YOUR_API_KEY",
          "Content-Type": "application/json"
      },
      json={
          "model": "openai/gpt-5.1",
          "messages": [
              {"role": "user", "content": "Generate a person profile"}
          ],
          "response_format": {
              "type": "json_schema",
              "json_schema": {
                  "name": "person",
                  "strict": True,
                  "schema": {
                      "type": "object",
                      "properties": {
                          "name": {"type": "string"},
                          "age": {"type": "number"},
                          "skills": {
                              "type": "array",
                              "items": {"type": "string"}
                          }
                      },
                      "required": ["name", "age", "skills"],
                      "additionalProperties": False
                  }
              }
          }
      }
  )

  data = response.json()
  print(data["choices"][0]["message"]["content"])
  # Output: {"name": "Alice Chen", "age": 28, "skills": ["Python", "Machine Learning", "Data Analysis"]}
  ```

  ```javascript JavaScript theme={null}
  const response = await fetch("https://nano-gpt.com/api/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": "Bearer YOUR_API_KEY",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model: "openai/gpt-5.1",
      messages: [
        { role: "user", content: "Generate a person profile" }
      ],
      response_format: {
        type: "json_schema",
        json_schema: {
          name: "person",
          strict: true,
          schema: {
            type: "object",
            properties: {
              name: { type: "string" },
              age: { type: "number" },
              skills: {
                type: "array",
                items: { type: "string" }
              }
            },
            required: ["name", "age", "skills"],
            additionalProperties: false
          }
        }
      }
    })
  });

  const data = await response.json();
  console.log(data.choices[0].message.content);
  // Output: {"name": "Alice Chen", "age": 28, "skills": ["Python", "Machine Learning", "Data Analysis"]}
  ```
</CodeGroup>

### Example Response

```json  theme={null}
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1769278225,
  "model": "openai/gpt-5.1",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"name\":\"Alice Chen\",\"age\":28,\"skills\":[\"Python\",\"Machine Learning\",\"Data Analysis\"]}"
      },
      "finish_reason": "stop"
    }
  ]
}
```

### Usage with Vercel AI SDK

The `response_format` parameter is compatible with Vercel AI SDK's `generateObject`:

```typescript  theme={null}
import { generateObject } from 'ai';
import { createOpenAI } from '@ai-sdk/openai';
import { z } from 'zod';

const nanogpt = createOpenAI({
  baseURL: 'https://nano-gpt.com/api/v1',
  apiKey: 'YOUR_API_KEY',
});

const { object } = await generateObject({
  model: nanogpt('openai/gpt-5.1'),
  schema: z.object({
    name: z.string(),
    age: z.number(),
    skills: z.array(z.string()),
  }),
  prompt: 'Generate a person profile',
});

console.log(object);
// { name: "Alice Chen", age: 28, skills: ["Python", "Machine Learning", "Data Analysis"] }
```

### Usage Notes

* Works with both streaming and non-streaming requests
* The `name` field in `json_schema` is required and should describe the output
* Response content is a JSON string; parse it with `JSON.parse()` in your application
* Some provider-specific limitations may apply; if you encounter issues with a specific model, try an alternative

## Web Search

Enable web search in two ways: model suffixes or a `webSearch` object in the request body. The legacy `linkup` object is still supported as an alias. If `webSearch.enabled` (or `linkup.enabled`) is `true`, it takes precedence over any model suffix.

OpenAI native web search: GPT-5+ / o1 / o3 / o4 models use OpenAI's built-in web search automatically. No suffix is required; you can still set `webSearch.search_context_size` and `webSearch.user_location`. To force a different provider, specify a provider or suffix.

<Note>
  Brave appears in this section in two different ways:

  1. `:online/brave` / `webSearch.provider = "brave"` uses the Web Search integration (raw results injected into another model).
  2. `model: "brave"` / `model: "brave-pro"` / `model: "brave-research"` uses Brave's own Answers pipeline (search + generation in one model).
</Note>

### Option A: model suffixes

Append one of these to your `model` value:

* `:online` (default web search, standard depth)
* `:online/linkup` (Linkup, standard)
* `:online/linkup-deep` (Linkup, deep)
* `:online/tavily` (Tavily, standard)
* `:online/tavily-deep` (Tavily, deep)
* `:online/brave` (Brave, standard)
* `:online/brave-deep` (Brave, deep)
* `:online/exa-fast` (Exa, fast)
* `:online/exa-auto` (Exa, auto)
* `:online/exa-neural` (Exa, neural)
* `:online/exa-deep` (Exa, deep)
* `:online/kagi` (Kagi, standard, search)
* `:online/kagi-web` (Kagi, standard, web)
* `:online/kagi-news` (Kagi, standard, news)
* `:online/kagi-search` (Kagi, deep, search)
* `:online/perplexity` (Perplexity, standard)
* `:online/perplexity-deep` (Perplexity, deep)
* `:online/valyu` (Valyu, standard, all sources)
* `:online/valyu-deep` (Valyu, deep, all sources)
* `:online/valyu-web` (Valyu, standard, web only)
* `:online/valyu-web-deep` (Valyu, deep, web only)

`:online` without an explicit provider uses the default web search backend (Linkup).

### Option B: request body configuration (recommended)

Send a `webSearch` object in the request body. The legacy `linkup` object is accepted as an alias. This works with or without a model suffix and controls web search across all providers.

`webSearch` fields:

* `enabled` (boolean, required to activate web search)
* `provider` (string): `linkup` | `tavily` | `brave` | `exa` | `kagi` | `perplexity` | `valyu`
* `depth` (string):
  * Linkup/Tavily/Brave/Perplexity/Valyu: `standard` or `deep`
  * Exa: `fast`, `auto`, `neural`, `deep` (use `standard` if you want `auto`)
  * Kagi: `standard` or `deep` (`search` source only)
* `search_context_size` or `searchContextSize` (string, OpenAI native): `low` | `medium` | `high` (default: `medium`)
* `user_location` or `userLocation` (object, OpenAI native): `{ type: "approximate", country, city, region }`
* `searchType` (string, Valyu only): `all` | `web`
* `kagiSource` or `kagi_source` (string, Kagi only): `web` | `news` | `search`

Legacy alias example:

```json  theme={null}
{
  "linkup": {
    "enabled": true,
    "provider": "tavily",
    "search_context_size": "medium"
  }
}
```

### Brave Answers and Research models

NanoGPT also exposes three Brave-powered text models that combine web search with generation. Use them by setting the `model` directly:

| Model ID         | Description                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| `brave`          | Brave (Answers). Single web search + LLM answer. Fast (\~4.5s), low cost.                            |
| `brave-pro`      | Brave (Pro). Premium tier with higher quality answers, more search depth, and priority processing.   |
| `brave-research` | Brave (Research). Multi-search deep research with reasoning. Slower (can take minutes), higher cost. |

These models are separate from the Web Search integration (`:online/*` suffixes and the `webSearch` object).

<Note>
  Brave also offers an LLM Context API (search-derived, relevance-ranked chunks for LLM workflows). NanoGPT does not currently integrate this mode; current Brave integrations in this endpoint are Web Search injection and the Brave Answers model family above.
</Note>

#### Brave-specific request fields

When using `model: "brave"`, `model: "brave-pro"`, or `model: "brave-research"`, you can pass these optional top-level fields in the request body (OpenAI SDK `extra_body` style):

#### Core parameters

| Parameter               | Type    | Default (`brave`/`brave-pro`) | Default (`brave-research`) | Description                                                                               |
| ----------------------- | ------- | ----------------------------- | -------------------------- | ----------------------------------------------------------------------------------------- |
| `enable_research`       | boolean | `false`                       | `true`                     | Enables multi-search deep research mode with reasoning. Requires streaming.               |
| `enable_citations`      | boolean | `false`                       | `false`                    | Includes `<citation>` markup in the response text linking to sources. Requires streaming. |
| `enable_entities`       | boolean | `false`                       | `false`                    | Includes entity metadata in the response. Requires streaming.                             |
| `country`               | string  | —                             | —                          | Country code for search localization (for example `"US"` or `"GB"`).                      |
| `language`              | string  | —                             | —                          | Language code for response language (for example `"en"` or `"fr"`).                       |
| `max_completion_tokens` | integer | —                             | —                          | Maximum number of tokens to generate in the completion.                                   |
| `seed`                  | integer | —                             | —                          | Optional deterministic seed for repeatability where supported.                            |
| `stream`                | boolean | `false`                       | auto-streaming             | Streams SSE responses. `brave-research` automatically uses streaming when omitted.        |
| `safesearch`            | string  | `moderate`                    | `moderate`                 | Safe search filtering level. Supported values: `off`, `moderate`, `strict`.               |
| `metadata`              | object  | —                             | —                          | Optional metadata to attach to the request.                                               |

#### Research tuning parameters

These parameters control `enable_research` mode (`brave-research` by default, or any Brave model when `enable_research: true`).

| Parameter                                      | Type    | Range      | Description                                                                                       |
| ---------------------------------------------- | ------- | ---------- | ------------------------------------------------------------------------------------------------- |
| `research_allow_thinking`                      | boolean | —          | Allow the research model to show its thinking/reasoning process in the response. Default: `true`. |
| `research_maximum_number_of_iterations`        | integer | 1-5        | Maximum number of research iterations (rounds of search + analysis).                              |
| `research_maximum_number_of_queries`           | integer | 1-50       | Maximum number of search queries to issue during research.                                        |
| `research_maximum_number_of_results_per_query` | integer | 1-60       | Maximum number of search results to analyze per query.                                            |
| `research_maximum_number_of_seconds`           | integer | 1-300      | Maximum time in seconds for the research process.                                                 |
| `research_maximum_number_of_tokens_per_query`  | integer | 1024-16384 | Maximum tokens to process per search query.                                                       |

#### Web search options (Brave models)

For `model: "brave"`, `model: "brave-pro"`, and `model: "brave-research"`, pass these as a top-level `web_search_options` object in the same chat completions request body.

| Parameter                                      | Type   | Description                                                                                           |
| ---------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------- |
| `web_search_options`                           | object | Nested object to configure web search behavior.                                                       |
| `web_search_options.search_context_size`       | string | Amount of search context: `"low"`, `"medium"`, or `"high"` (when omitted, Brave defaults to `"low"`). |
| `web_search_options.user_location`             | object | User location for localized results.                                                                  |
| `web_search_options.user_location.type`        | enum   | Must be `"approximate"`.                                                                              |
| `web_search_options.user_location.approximate` | object | Required location object containing `city`, `country`, `region`, and `timezone` (nullable strings).   |

Minimal Brave example:

```json  theme={null}
{
  "model": "brave",
  "messages": [{ "role": "user", "content": "What's new in battery tech?" }],
  "stream": true,
  "web_search_options": {
    "search_context_size": "high"
  }
}
```

**Streaming requirement:** `enable_research`, `enable_citations`, and `enable_entities` require `stream: true`. The `brave-research` model is streaming-first and will use streaming even if `stream` is omitted (recommended: always set `stream: true` explicitly).

Basic research query:

```json  theme={null}
{
  "model": "brave-research",
  "messages": [
    { "role": "user", "content": "What are the latest developments in fusion energy?" }
  ],
  "stream": true
}
```

Research with tuning parameters:

```json  theme={null}
{
  "model": "brave-research",
  "messages": [
    { "role": "user", "content": "Compare the top 5 JavaScript frameworks in 2026" }
  ],
  "stream": true,
  "research_allow_thinking": true,
  "research_maximum_number_of_iterations": 3,
  "research_maximum_number_of_queries": 20,
  "research_maximum_number_of_seconds": 120
}
```

Standard model with research enabled and web search options:

```json  theme={null}
{
  "model": "brave",
  "messages": [
    { "role": "user", "content": "Best restaurants in Tokyo" }
  ],
  "enable_research": true,
  "stream": true,
  "web_search_options": {
    "search_context_size": "high",
    "user_location": {
      "type": "approximate",
      "approximate": {
        "city": "Tokyo",
        "country": "JP",
        "timezone": "Asia/Tokyo"
      }
    }
  }
}
```

Brave (Pro) with citations:

```json  theme={null}
{
  "model": "brave-pro",
  "messages": [
    { "role": "user", "content": "Explain quantum computing" }
  ],
  "stream": true,
  "enable_citations": true,
  "safesearch": "moderate"
}
```

#### Provider-specific options (set inside `webSearch`)

##### Perplexity

```json  theme={null}
{
  "maxResults": 1-20,
  "maxTokensPerPage": number,
  "maxTokens": 1-1000000,
  "country": "string",
  "searchDomainFilter": ["domain1.com", "domain2.com"],
  "searchLanguageFilter": ["en", "de"]
}
```

Limits: `searchDomainFilter` max 20 entries; `searchLanguageFilter` max 10 entries (ISO 639-1).

##### Valyu

```json  theme={null}
{
  "searchType": "all" | "web",
  "fastMode": boolean,
  "maxNumResults": 1-50,
  "maxPrice": number,
  "relevanceThreshold": 0-1,
  "responseLength": "short" | "medium" | "large" | "max" | number,
  "countryCode": "US",
  "includedSources": ["source1.com"],
  "excludedSources": ["source2.com"],
  "urlOnly": boolean,
  "category": "string"
}
```

`countryCode` uses a 2-letter ISO country code.

##### Tavily

```json  theme={null}
{
  "maxResults": 0-20,
  "includeAnswer": boolean | "basic" | "advanced",
  "includeRawContent": boolean | "markdown" | "text",
  "includeImages": boolean,
  "includeImageDescriptions": boolean,
  "includeFavicon": boolean,
  "topic": "general" | "news" | "finance",
  "timeRange": "day" | "week" | "month" | "year",
  "startDate": "YYYY-MM-DD",
  "endDate": "YYYY-MM-DD",
  "chunksPerSource": 1-3,
  "country": "string"
}
```

##### Exa

```json  theme={null}
{
  "numResults": 1-100,
  "category": "company" | "research paper" | "news" | "pdf" | "github" | "tweet" | "personal site" | "people" | "financial report",
  "userLocation": "US",
  "additionalQueries": ["query2"],
  "startCrawlDate": "ISO 8601",
  "endCrawlDate": "ISO 8601",
  "startPublishedDate": "ISO 8601",
  "endPublishedDate": "ISO 8601",
  "includeText": ["pattern"],
  "excludeText": ["pattern"],
  "livecrawl": "never" | "fallback" | "always" | "preferred",
  "livecrawlTimeout": number,
  "subpages": number,
  "subpageTarget": "string" | ["strings"]
}
```

##### OpenAI native (GPT-5.2)

```json  theme={null}
{
  "search_context_size": "low" | "medium" | "high",
  "user_location": {
    "type": "approximate",
    "country": "US",
    "city": "San Francisco",
    "region": "California"
  }
}
```

### Examples

<CodeGroup>
  ```python Python theme={null}
  import requests
  import json

  BASE_URL = "https://nano-gpt.com/api/v1"
  API_KEY = "YOUR_API_KEY"

  headers = {
      "Authorization": f"Bearer {API_KEY}",
      "Content-Type": "application/json"
  }

  # Suffix-based standard web search
  data = {
      "model": "openai/gpt-5.2:online",
      "messages": [
          {"role": "user", "content": "What are the latest developments in AI?"}
      ]
  }

  response = requests.post(
      f"{BASE_URL}/chat/completions",
      headers=headers,
      json=data
  )

  # Request-body configuration (Exa neural)
  data_search = {
      "model": "openai/gpt-5.2",
      "messages": [
          {"role": "user", "content": "Provide a comprehensive analysis of recent AI breakthroughs"}
      ],
      "webSearch": {
          "enabled": True,
          "provider": "exa",
          "depth": "neural",
          "numResults": 10
      }
  }
  ```

  ```javascript JavaScript theme={null}
  const BASE_URL = "https://nano-gpt.com/api/v1";
  const API_KEY = "YOUR_API_KEY";

  // Suffix-based standard web search
  const response = await fetch(`${BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'application/json'
      },
      body: JSON.stringify({
          model: 'openai/gpt-5.2:online',
          messages: [
              { role: 'user', content: 'What are the latest developments in AI?' }
          ]
      })
  });

  // Request-body configuration (Exa neural)
  const searchResponse = await fetch(`${BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
          'Authorization': `Bearer ${API_KEY}`,
          'Content-Type': 'application/json'
      },
      body: JSON.stringify({
          model: 'openai/gpt-5.2',
          messages: [
              { role: 'user', content: 'Provide a comprehensive analysis of recent AI breakthroughs' }
          ],
          webSearch: {
              enabled: true,
              provider: 'exa',
              depth: 'neural',
              numResults: 10
          }
      })
  });
  ```

  ```bash cURL theme={null}
  # Suffix-based standard web search
  curl -X POST https://nano-gpt.com/api/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "openai/gpt-5.2:online",
      "messages": [
        {"role": "user", "content": "What are the latest developments in AI?"}
      ]
    }'

  # Request-body configuration (Exa neural)
  curl -X POST https://nano-gpt.com/api/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "openai/gpt-5.2",
      "messages": [
        {"role": "user", "content": "Provide a comprehensive analysis of recent AI breakthroughs"}
      ],
      "webSearch": {
        "enabled": true,
        "provider": "exa",
        "depth": "neural",
        "numResults": 10
      }
    }'
  ```
</CodeGroup>

### Pricing by provider

| Provider      | Standard          | Deep           | Notes                            |
| ------------- | ----------------- | -------------- | -------------------------------- |
| Linkup        | \$0.006           | \$0.06         | Default provider                 |
| Tavily        | \$0.008           | \$0.016        | Good value, free tier available  |
| Exa           | \$0.005 base      | + \$0.001/page | For contents retrieval           |
| Kagi Web/News | \$0.002           | N/A            | Cheapest for enrichment          |
| Kagi Search   | \$0.025           | N/A            | Full search mode                 |
| Perplexity    | \$0.005           | N/A            | Flat rate                        |
| Valyu         | \~\$0.0015/result | Variable       | Dynamic pricing                  |
| Brave         | \$0.005           | \$0.005        | Flat rate                        |
| OpenAI Native | \$0.01 + tokens   | N/A            | Per-call fee + model token costs |

For standard NanoGPT usage, Brave credentials are handled automatically.

### Bring your own key (BYOK)

BYOK lets you route requests through your own upstream provider credentials.

* Configure keys once: [https://nano-gpt.com/byok](https://nano-gpt.com/byok)
* Opt in per request via `x-use-byok: true` or `byok.enabled: true`
* Optionally force the provider via `x-byok-provider` or `byok.provider`
* BYOK usage includes a **5% platform fee** (your provider bills you directly for usage)

See: [Bring Your Own Key (BYOK)](/api-reference/miscellaneous/byok)

#### Web search BYOK

Web search BYOK availability is provider-dependent and can change over time. See the BYOK reference for the current support matrix.

#### Brave terms highlights (updated February 11, 2026)

* No caching beyond transient storage.
* No AI training on Brave search results.
* No redistribution or reselling of Brave results.
* Termination: Brave may terminate with 10 days' notice; customer may terminate with 30 days' notice.
* Liability cap: limited to fees paid in the prior 12 months.

### Advanced behavior (optional)

* **Provider routing**: For GPT-5+ / o1 / o3 / o4 models, `:online` without an explicit provider uses OpenAI native web search. If you set `webSearch.provider` or use an explicit `:online/<provider>` suffix, that provider is used instead.
* **Model suffix normalization**: `:online` (and provider/depth suffixes) are stripped from the model name before routing to the base model; the suffix only controls search behavior.
* **Query formation (non-OpenAI providers)**: The search query is derived from your latest user message and may include the previous user message if the latest is short. If you need full control over the query or raw results, use the Web Search endpoint (`/api/web`).
* **`scraping: true` URL handling**: When enabled, NanoGPT scans messages for public `http(s)` URLs, ignores local/private URLs, de-duplicates, and caps at 5. If no eligible URLs are found, scraping is skipped. Inline scraping in chat is billed at **\$0.0015 per successfully scraped URL**. For explicit URL lists and the standalone endpoint price (**\$0.001 per URL**), use `/scrape-urls`.

## Image Input

Send images using the OpenAI‑compatible chat format. Provide image parts alongside text in the `messages` array.

### Supported Forms

* Remote URL: `{"type":"image_url","image_url":{"url":"https://..."}}`
* Base64 data URL: `{"type":"image_url","image_url":{"url":"data:image/png;base64,...."}}`

Notes:

* Prefer HTTPS URLs; some upstreams reject non‑HTTPS. If in doubt, use base64 data URLs.
* Accepted mime types: `image/png`, `image/jpeg`, `image/jpg`, `image/webp`.
* Inline markdown images in plain text (e.g., `![alt](data:image/...;base64,...)`) are auto‑normalized into structured parts server‑side.

### Message Shape

```json  theme={null}
{
  "role": "user",
  "content": [
    { "type": "text", "text": "What is in this image?" },
    { "type": "image_url", "image_url": { "url": "https://example.com/image.jpg" } }
  ]
}
```

### cURL — Image URL (non‑streaming)

```bash  theme={null}
curl -sS \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -X POST https://nano-gpt.com/api/v1/chat/completions \
  --data '{
    "model": "google/gemini-3-flash-preview",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Describe this image in three words."},
          {"type": "image_url", "image_url": {"url": "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg"}}
        ]
      }
    ],
    "stream": false
  }'
```

### cURL — Base64 Data URL (non‑streaming)

Embed your image as a data URL. Replace `...BASE64...` with your image bytes.

```bash  theme={null}
curl -sS \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type": "application/json" \
  -X POST https://nano-gpt.com/api/v1/chat/completions \
  --data '{
    "model": "google/gemini-3-flash-preview",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "What is shown here?"},
          {"type": "image_url", "image_url": {"url": "data:image/png;base64,...BASE64..."}}
        ]
      }
    ],
    "stream": false
  }'
```

### cURL — Streaming SSE

See also: [Streaming Protocol (SSE)](/api-reference/miscellaneous/streaming-protocol).

```bash  theme={null}
curl -N \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -X POST https://nano-gpt.com/api/v1/chat/completions \
  --data '{
    "model": "google/gemini-3-flash-preview",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "Two words only."},
          {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
      }
    ],
    "stream": true,
    "stream_options": { "include_usage": true }
  }'
```

The response streams `data: { ... }` lines until a final terminator. Usage metrics appear only when requested: set `stream_options.include_usage` to `true` for streaming responses, or send `"include_usage": true` on non-streaming calls.

*Note: Prompt-caching helpers implicitly force `include_usage`, so cached requests still receive usage data without extra flags.*

### Prompt Caching (Claude Models)

For the full guide (supported models, thresholds, pricing, and usage fields), see [Prompt Caching](/api-reference/miscellaneous/prompt-caching).

Claude caching works exactly like Anthropic's `/v1/messages`: you must place `cache_control` objects on the content blocks you want the model to reuse, or instruct NanoGPT to do it for you via the `prompt_caching` helper.

> **Note:** NanoGPT's automatic failover system ensures high availability but may occasionally cause cache misses. If you're seeing unexpected cache misses in your usage logs, see the "Cache Consistency with `stickyProvider`" section below.

The `prompt_caching` / `promptCaching` helper accepts these options:

| Parameter                 | Type    | Default | Description                                                                                                                      |
| ------------------------- | ------- | ------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `enabled`                 | boolean | —       | Enable prompt caching                                                                                                            |
| `ttl`                     | string  | `"5m"`  | Cache time-to-live: `"5m"` or `"1h"`                                                                                             |
| `cut_after_message_index` | integer | —       | Zero-based index; cache all messages up to and including this index                                                              |
| `stickyProvider`          | boolean | `false` | **New:** When `true`, disable automatic failover to preserve cache consistency. Returns 503 error instead of switching services. |

```python  theme={null}
headers = {
  "Authorization": "Bearer YOUR_API_KEY",
  "Content-Type": "application/json",
  "anthropic-beta": "prompt-caching-2024-07-31"
}

payload = {
  "model": "anthropic/claude-opus-4.5",
  "messages": [
    {
      "role": "system",
      "content": [
        {
          "type": "text",
          "text": "Reference handbook + rules of engagement.",
          "cache_control": {"type": "ephemeral", "ttl": "5m"}
        }
      ]
    },
    {"role": "user", "content": "Live request goes here"}
  ]
}

requests.post("https://nano-gpt.com/api/v1/chat/completions", headers=headers, json=payload)
```

* Each `cache_control` marker caches the full prefix up to that block. Place them on every static chunk (system messages, tool definitions, large contexts) you plan to reuse.
* Anthropic currently supports TTLs of `5m` (1.25× one-time billing) and `1h` (2× one-time). Replays show the discounted tokens inside `usage.prompt_tokens_details.cached_tokens`.
* The `anthropic-beta: prompt-caching-2024-07-31` header is mandatory on requests that include caching metadata.

For a simpler experience, send the helper fields and NanoGPT will stamp the first *N* messages for you before reaching Anthropic:

```ts  theme={null}
await client.chat.completions.create(
  {
    model: 'anthropic/claude-opus-4.5',
    messages: [
      { role: 'system', content: 'Static rubric lives here.' },
      { role: 'user', content: 'Additional reusable context.' },
      { role: 'user', content: 'This turn is not cached.' },
    ],
    prompt_caching: {
      enabled: true,
      ttl: '1h',
      cut_after_message_index: 1,
    },
  },
  {
    headers: { 'anthropic-beta': 'prompt-caching-2024-07-31' },
  },
);
```

`cut_after_message_index` is zero-based. If omitted, NanoGPT will select a cache boundary automatically; set it explicitly if you need full control. Switch back to explicit `cache_control` blocks if you need multiple cache breakpoints or mixed TTLs in the same payload.

### Cache Consistency with `stickyProvider`

NanoGPT automatically fails over to backup services when the primary service is temporarily unavailable. While this ensures high availability, it can break your prompt cache because **each backend service maintains its own separate cache**.

If cache consistency is more important than availability for your use case, you can enable the `stickyProvider` option:

```json  theme={null}
{
  "model": "anthropic/claude-sonnet-4.5",
  "messages": [...],
  "prompt_caching": {
    "enabled": true,
    "ttl": "5m",
    "stickyProvider": true
  }
}
```

**Behavior:**

* **`stickyProvider: false` (default)** — If the primary service fails, NanoGPT automatically retries with a backup service. Your request succeeds, but the cache may be lost (you'll pay full price for that request and need to rebuild the cache).
* **`stickyProvider: true`** — If the primary service fails, NanoGPT returns a 503 error instead of failing over. Your cache remains intact for when the service recovers.

**When to use `stickyProvider: true`:**

* You have very large cached contexts where cache misses are expensive
* You prefer to retry failed requests yourself rather than pay for cache rebuilds
* Cost predictability is more important than request success rate

**When to use `stickyProvider: false` (default):**

* You prefer requests to always succeed when possible
* Occasional cache misses are acceptable
* You're using shorter contexts where cache rebuilds are inexpensive

**Error response when stickyProvider blocks a failover:**

```json  theme={null}
{
  "error": {
    "message": "Service is temporarily unavailable. Fallback disabled to preserve prompt cache consistency. Switching services would invalidate your cached tokens. Remove stickyProvider option or retry later.",
    "status": 503,
    "type": "service_unavailable",
    "code": "fallback_blocked_for_cache_consistency"
  }
}
```

### Troubleshooting

* 400 unsupported image: ensure the image is a valid PNG/JPEG/WebP, not a tiny 1×1 pixel, and either HTTPS URL or a base64 data URL.
* 503 after fallbacks: try a different model, verify API key/session, and prefer base64 data URL for local or protected assets.
* Missing usage events: confirm `include_usage` is `true` in the payload or that prompt caching is enabled.

## Context Memory

Enable unlimited-length conversations with lossless, hierarchical memory.

* Append `:memory` to any model name
* Or send header `memory: true`
* Can be combined with web search: `:online:memory`
* Retention: default 30 days; configure via `:memory-<days>` (1..365) or header `memory_expiration_days: <days>`; header takes precedence

<CodeGroup>
  ```python Python theme={null}
  import requests

  BASE_URL = "https://nano-gpt.com/api/v1"
  API_KEY = "YOUR_API_KEY"

  headers = {
      "Authorization": f"Bearer {API_KEY}",
      "Content-Type": "application/json"
  }

  # Suffix-based
  payload = {
      "model": "openai/gpt-5.2:memory",
      "messages": [{"role": "user", "content": "Keep our previous discussion in mind and continue."}]
  }
  requests.post(f"{BASE_URL}/chat/completions", headers=headers, json=payload)
  ```

  ```javascript JavaScript theme={null}
  const BASE_URL = "https://nano-gpt.com/api/v1";
  const API_KEY = "YOUR_API_KEY";

  // Header-based (with optional retention override)
  await fetch(`${BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json',
      'memory': 'true',
      'memory_expiration_days': '45'
    },
    body: JSON.stringify({
      model: 'openai/gpt-5.2',
      messages: [{ role: 'user', content: 'Continue with full history awareness.' }]
    })
  });
  ```

  ```bash cURL theme={null}
  # Combine with web search (and set retention to 90 days via suffix)
  curl -X POST https://nano-gpt.com/api/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "openai/gpt-5.2:online:memory-90",
      "messages": [
        {"role": "user", "content": "Research and continue our plan without losing context."}
      ]
    }'

  # Header-based retention override (header takes precedence)
  curl -X POST https://nano-gpt.com/api/v1/chat/completions \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -H "memory: true" \
    -H "memory_expiration_days: 45" \
    -d '{
      "model": "openai/gpt-5.2",
      "messages": [
        {"role": "user", "content": "Use memory with 45-day retention."}
      ]
    }'
  ```
</CodeGroup>

### Custom Context Size Override

When Context Memory is enabled, you can override the model-derived context size used for the memory compression step with `model_context_limit`.

* Parameter: `model_context_limit` (number or numeric string)
* Default: Derived from the selected model’s context size
* Minimum: Values below 10,000 are clamped internally
* Scope: Only affects memory compression; does not change the target model’s own window

Examples:

```bash  theme={null}
# Enable memory via header; use model default context size
curl -s -X POST \
  -H "Authorization: Bearer $NANOGPT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "memory: true" \
  https://nano-gpt.com/api/v1/chat/completions \
  -d '{
    "model": "google/gemini-3-flash-preview",
    "messages": [{"role":"user","content":"Briefly say hello."}],
    "stream": false
  }'

# Explicit numeric override
curl -s -X POST \
  -H "Authorization: Bearer $NANOGPT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "memory: true" \
  https://nano-gpt.com/api/v1/chat/completions \
  -d '{
    "model": "google/gemini-3-flash-preview",
    "messages": [{"role":"user","content":"Briefly say hello."}],
    "model_context_limit": 20000,
    "stream": false
  }'

# String override (server coerces to number)
curl -s -X POST \
  -H "Authorization: Bearer $NANOGPT_API_KEY" \
  -H "Content-Type: application/json" \
  -H "memory: true" \
  https://nano-gpt.com/api/v1/chat/completions \
  -d '{
    "model": "google/gemini-3-flash-preview",
    "messages": [{"role":"user","content":"Briefly say hello."}],
    "model_context_limit": "30000",
    "stream": false
  }'
```

## Reasoning Streams

The Chat Completions endpoint separates the model’s visible answer from its internal reasoning. By default, reasoning is included and delivered alongside normal content so that clients can decide whether to display it. Requests that use the `thinking` model suffix (for example `:thinking` or `-thinking:8192`) are normalized before dispatch, but the response contract remains the same.

See also: [Extended Thinking (Reasoning)](/api-reference/miscellaneous/extended-thinking).

### Endpoint variants

Choose the base path that matches how your client consumes reasoning streams:

* `https://nano-gpt.com/api/v1/chat/completions` — default endpoint that streams internal thoughts through `choices[0].delta.reasoning` (and repeats them in `message.reasoning` on completion). Recommended for apps like SillyTavern that understand the modern response shape.
* `https://nano-gpt.com/api/v1legacy/chat/completions` — legacy contract that swaps the field name to `choices[0].delta.reasoning_content` / `message.reasoning_content` for older OpenAI-compatible clients. Use this for LiteLLM’s OpenAI adapter to avoid downstream parsing errors.
* `https://nano-gpt.com/api/v1thinking/chat/completions` — reasoning-aware models write everything into the normal `choices[0].delta.content` stream so clients that ignore reasoning fields still see the full conversation transcript. This is the preferred base URL for JanitorAI.

### Streaming payload format

Server-Sent Event (SSE) streams emit the answer in `choices[0].delta.content` and the thought process in `choices[0].delta.reasoning` (plus optional `delta.reasoning_details`). Reasoning deltas are dispatched before or alongside regular content, letting you render both panes in real-time.

```text  theme={null}
data: {
  "choices": [{
    "delta": {
      "reasoning": "Assessing possible tool options…"
    }
  }]
}
data: {
  "choices": [{
    "delta": {
      "content": "Let me walk you through the solution."
    }
  }]
}
```

When streaming completes, the formatter aggregates the collected values and repeats them in the final payload: `choices[0].message.content` contains the assistant reply and `choices[0].message.reasoning` (plus `reasoning_details` when available) contains the full chain-of-thought. Non-streaming requests reuse the same formatter, so the reasoning block is present as a dedicated field.

### Showing or hiding reasoning

Send `reasoning: { "exclude": true }` to strip the reasoning payload from both streaming deltas and the final message. With this flag set, `delta.reasoning` and `message.reasoning` are omitted entirely.

```bash  theme={null}
curl -X POST https://nano-gpt.com/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-opus-4.5",
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "reasoning": {"exclude": true}
  }'
```

**Without reasoning.exclude**:

```json  theme={null}
{
  "choices": [{
    "message": {
      "content": "The answer is 4.",
      "reasoning": "The user is asking for a simple addition. 2+2 equals 4."
    }
  }]
}
```

**With reasoning.exclude**:

```json  theme={null}
{
  "choices": [{
    "message": {
      "content": "The answer is 4."
    }
  }]
}
```

### Reasoning Effort

Control how much computational effort the model puts into reasoning before generating a response. Higher values result in more thorough reasoning but slower responses and higher costs. Only applicable to reasoning-capable models.

#### Parameter: `reasoning_effort`

| Value     | Description                                                                      |
| --------- | -------------------------------------------------------------------------------- |
| `none`    | Disables reasoning entirely                                                      |
| `minimal` | Allocates \~10% of max\_tokens for reasoning                                     |
| `low`     | Allocates \~20% of max\_tokens for reasoning                                     |
| `medium`  | Allocates \~50% of max\_tokens for reasoning (default when reasoning is enabled) |
| `high`    | Allocates \~80% of max\_tokens for reasoning                                     |

#### Usage

The `reasoning_effort` parameter can be passed at the top level:

```bash  theme={null}
curl -X POST https://nano-gpt.com/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-opus-4.5",
    "messages": [
      {"role": "user", "content": "Explain quantum entanglement step by step"}
    ],
    "reasoning_effort": "high",
    "max_tokens": 4096
  }'
```

Alternatively, pass it as part of the `reasoning` object:

```json  theme={null}
{
  "model": "anthropic/claude-opus-4.5",
  "messages": [{"role": "user", "content": "Solve this complex math problem..."}],
  "reasoning": {
    "effort": "high"
  }
}
```

Both formats are equivalent.

#### Combining effort with exclude

You can control both reasoning depth and visibility:

```json  theme={null}
{
  "model": "anthropic/claude-opus-4.5",
  "messages": [{"role": "user", "content": "..."}],
  "reasoning": {
    "effort": "high",
    "exclude": false
  }
}
```

Sending `reasoning_effort` to models that don't support reasoning will have no effect (the parameter is ignored).

### Model suffix: `:reasoning-exclude`

You can toggle the filter without altering your JSON body by appending `:reasoning-exclude` to the `model` name.

* Equivalent to sending `{ "reasoning": { "exclude": true } }`
* Only the `:reasoning-exclude` suffix is stripped before the request is routed; other suffixes remain active
* Works for streaming and non-streaming responses on both Chat Completions and Text Completions

```json  theme={null}
{
  "model": "anthropic/claude-opus-4.5:reasoning-exclude",
  "messages": [{ "role": "user", "content": "What is 2+2?" }]
}
```

#### Combine with other suffixes

`:reasoning-exclude` composes safely with the other routing suffixes you already use:

* `:thinking` (and variants like `…-thinking:8192`)
* `:online` and `:online/linkup-deep`
* `:memory` and `:memory-<days>`

Examples:

* `anthropic/claude-sonnet-4.5:thinking:8192:reasoning-exclude`
* `openai/gpt-5.2:online:reasoning-exclude`
* `anthropic/claude-opus-4.5:memory-30:online/linkup-deep:reasoning-exclude`

### Legacy delta field compatibility

Older clients that expect the legacy `reasoning_content` field can opt in per request. Set `reasoning.delta_field` to `"reasoning_content"`, or use the top-level shorthands `reasoning_delta_field` / `reasoning_content_compat` if updating nested objects is difficult. When the toggle is active, every streaming and non-streaming response exposes `reasoning_content` instead of `reasoning`, and the modern key is omitted. The compatibility pass is skipped if `reasoning.exclude` is `true`, because no reasoning payload is emitted. If you cannot change the request payload, target `https://nano-gpt.com/api/v1legacy/chat/completions` instead—the legacy endpoint keeps `reasoning_content` without extra flags. LiteLLM’s OpenAI adapter should point here to maintain compatibility. For clients that ignore reasoning-specific fields entirely, use `https://nano-gpt.com/api/v1thinking/chat/completions` so the full text appears in the standard content stream; this is the correct choice for JanitorAI.

```json  theme={null}
{
  "model": "openai/gpt-5.2",
  "messages": [...],
  "reasoning": {
    "delta_field": "reasoning_content"
  }
}
```

#### Notes and limitations

* GPU-TEE models (`phala/*`) require byte-for-byte SSE passthrough for signature verification. For those models, streaming cannot be filtered; the suffix has no effect on the streaming bytes.
* When assistant content is an array (e.g., vision/text parts), only text parts are filtered; images and tool/metadata content are untouched.

## Service tiers (priority)

Set `service_tier: "priority"` to request priority processing on providers that support service tiers.

Behavior notes:

* When `service_tier` is `"priority"`, NanoGPT prefers routing to providers that support service tiers (for example, routing away from providers that do not).
* Priority tiers are gated on the routed provider, not just the model name.
* Not all providers support service tiers, so priority requests may be routed differently than non-priority requests.
* Header provider overrides (like `X-Provider`) and explicit provider selection are honored for pricing and x402 estimates.
* Provider-native web search can force routing; priority pricing follows that routing.
* If you explicitly force a provider that does not support service tiers, priority tiers may be ignored by the upstream provider.

Billing note:

* Priority requests are billed at priority rates when routed to providers with priority pricing.

Response note:

* Responses now include a top-level `service_tier` field when it is provided on the request.

### Example: priority tier

```json  theme={null}
{
  "model": "gpt-5.2",
  "messages": [
    { "role": "user", "content": "Give me a concise release note." }
  ],
  "service_tier": "priority"
}
```

## YouTube Transcripts

Automatically fetch and prepend YouTube video transcripts when the latest user message contains YouTube links.

### Defaults

* Parameter: `youtube_transcripts` (boolean)
* Default: `false` (opt-in)
* Opt-in: set `youtube_transcripts` to `true` (string `"true"` is also accepted) to fetch transcripts
* Limit: Up to 3 YouTube URLs processed per request
* Higher volume: Use the standalone [`POST /api/youtube-transcribe`](/api-reference/endpoint/youtube-transcribe) endpoint for up to 10 URLs per request
* Injection: Transcripts are added as a system message before your messages
* Billing: \$0.01 per transcript fetched

### Enable automatic transcripts

By default, YouTube links are ignored. Set `youtube_transcripts` to `true` when you want the system to retrieve and bill for transcripts.

```bash  theme={null}
curl -X POST https://nano-gpt.com/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-3-flash-preview",
    "messages": [
      {"role": "user", "content": "Summarize this: https://youtu.be/dQw4w9WgXcQ"}
    ],
    "youtube_transcripts": true
  }'
```

### Notes

* Web scraping is separate. To scrape non‑YouTube URLs, set `scraping: true`. YouTube transcripts do not require `scraping: true`.
* When not requested, YouTube links are ignored for transcript fetching and are not billed.
* If your balance is insufficient when enabled, the request may be blocked with a 402.

## Performance Benchmarks

LinkUp achieves state-of-the-art performance on OpenAI's SimpleQA benchmark:

| Provider               | Score  |
| ---------------------- | ------ |
| LinkUp Deep Search     | 90.10% |
| Exa                    | 90.04% |
| Perplexity Sonar Pro   | 86%    |
| LinkUp Standard Search | 85%    |
| Perplexity Sonar       | 77%    |
| Tavily                 | 73%    |

## Important Notes

* Web search increases input token count, which affects total cost
* Models gain access to real-time information published less than a minute ago
* Internet connectivity can provide up to 10x improvement in factuality
* All models support web search - append a suffix or send a `webSearch` object (`linkup` is supported as an alias)


## OpenAPI

````yaml POST /v1/chat/completions
openapi: 3.1.0
info:
  title: NanoGPT API
  description: >-
    API documentation for the NanoGPT language, image, video, speech-to-text,
    and text-to-speech generation services
  license:
    name: MIT
  version: 1.0.0
servers:
  - url: https://nano-gpt.com/api
    description: NanoGPT API Server
security: []
paths:
  /v1/chat/completions:
    post:
      description: Creates a chat completion for the provided messages
      parameters:
        - name: X-Provider
          in: header
          description: >-
            Optional provider override for pay-as-you-go requests on supported
            open-source models (case-insensitive). Subscription requests ignore
            this header.
          required: false
          schema:
            type: string
        - name: X-Billing-Mode
          in: header
          description: >-
            Optional billing override to force pay-as-you-go (e.g., paygo).
            Header name is case-insensitive.
          required: false
          schema:
            type: string
      requestBody:
        description: Parameters for chat completion
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ChatCompletionRequest'
        required: true
      responses:
        '200':
          description: Chat completion response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ChatCompletionResponse'
        '400':
          description: Unexpected error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'
      security:
        - bearerAuth: []
components:
  schemas:
    ChatCompletionRequest:
      type: object
      required:
        - model
        - messages
      properties:
        model:
          type: string
          description: >-
            The model to use for completion. Append ':online' for web search
            ($0.005/request) or ':online/linkup-deep' for deep web search
            ($0.05/request)
          default: openai/gpt-5.2
          examples:
            - openai/gpt-5.2
            - openai/gpt-5.2:online
            - openai/gpt-5.2:online/linkup-deep
            - anthropic/claude-opus-4.5:online
        billing_mode:
          type: string
          description: >-
            Billing override to force pay-as-you-go. Accepted values
            (case-insensitive): paygo, pay-as-you-go, pay_as_you_go, paid, payg.
        billingMode:
          type: string
          description: Alias for billing_mode.
        messages:
          type: array
          description: Array of message objects with role and content
          default:
            - role: user
              content: Testing, please reply!
          items:
            type: object
            required:
              - role
              - content
            properties:
              role:
                type: string
                description: The role of the message author
                enum:
                  - system
                  - user
                  - assistant
              content:
                description: >-
                  Message content as a simple string or an array of multimodal
                  parts
                oneOf:
                  - type: string
                  - type: array
                    items:
                      $ref: '#/components/schemas/MessageContentPart'
        stream:
          type: boolean
          description: Whether to stream the response
          default: false
        service_tier:
          type: string
          enum:
            - auto
            - default
            - flex
            - priority
          description: >-
            Optional service tier. Set to "priority" to request priority
            processing when supported by the routed provider
        temperature:
          type: number
          description: >-
            Classic randomness control. Accepts any decimal between 0-2. If
            omitted, NanoGPT does not force a value and the routed
            provider/model default applies
          minimum: 0
          maximum: 2
        max_tokens:
          type: integer
          description: >-
            Upper bound on generated tokens. If omitted, NanoGPT does not
            enforce an explicit default and the routed provider/model default
            applies
          minimum: 1
        top_p:
          type: number
          description: >-
            Nucleus sampling. When set below 1.0, trims candidate tokens to the
            smallest set whose cumulative probability exceeds top_p. Works well
            as an alternative to tweaking temperature
          minimum: 0
          maximum: 1
          default: 1
        frequency_penalty:
          type: number
          description: >-
            Penalizes tokens proportionally to how often they appeared
            previously. Negative values encourage repetition; positive values
            discourage it
          minimum: -2
          maximum: 2
          default: 0
        presence_penalty:
          type: number
          description: >-
            Penalizes tokens based on whether they appeared at all. Good for
            keeping the model on topic without outright banning words
          minimum: -2
          maximum: 2
          default: 0
        repetition_penalty:
          type: number
          description: >-
            Provider-agnostic repetition modifier (distinct from OpenAI
            penalties). Values >1 discourage repetition
          minimum: -2
          maximum: 2
        top_k:
          type: integer
          description: Caps sampling to the top-k highest probability tokens per step
        top_a:
          type: number
          description: >-
            Combines top-p and temperature behavior; leave unset unless a model
            description explicitly calls for it
        min_p:
          type: number
          description: >-
            Ensures each candidate token probability exceeds a floor (0-1).
            Helpful for stopping models from collapsing into low-entropy loops
          minimum: 0
          maximum: 1
        tfs:
          type: number
          description: >-
            Tail free sampling. Values between 0-1 let you shave the long tail
            of the distribution; 1.0 disables the feature
          minimum: 0
          maximum: 1
        eta_cutoff:
          type: number
          description: >-
            Cut probabilities as soon as they fall below the specified tail
            threshold
        epsilon_cutoff:
          type: number
          description: >-
            Cut probabilities as soon as they fall below the specified tail
            threshold
        typical_p:
          type: number
          description: >-
            Typical sampling (aka entropy-based nucleus). Works like top_p but
            preserves tokens whose surprise matches the expected entropy
          minimum: 0
          maximum: 1
        mirostat_mode:
          type: integer
          description: >-
            Enables Mirostat sampling for models that support it. Set to 1 or 2
            to activate
          enum:
            - 0
            - 1
            - 2
        mirostat_tau:
          type: number
          description: >-
            Mirostat target entropy parameter. Used when mirostat_mode is
            enabled
        mirostat_eta:
          type: number
          description: Mirostat learning rate parameter. Used when mirostat_mode is enabled
        min_tokens:
          type: integer
          description: >-
            For providers that support it, enforces a minimum completion length
            before stop conditions fire
          default: 0
          minimum: 0
        stop:
          description: >-
            Stop sequences. Accepts string or array of strings. Values are
            passed directly to upstream providers
          oneOf:
            - type: string
            - type: array
              items:
                type: string
        stop_token_ids:
          type: array
          description: >-
            Numeric array that lets callers stop generation on specific token
            IDs. Not supported by many providers
          items:
            type: integer
        include_stop_str_in_output:
          type: boolean
          description: >-
            When true, keeps the stop sequence in the final text. Not supported
            by many providers
          default: false
        ignore_eos:
          type: boolean
          description: >-
            Allows completions to continue even if the model predicts EOS
            internally. Useful for long creative writing runs
          default: false
        no_repeat_ngram_size:
          type: integer
          description: >-
            Extension that forbids repeating n-grams of the given size. Not
            supported by many providers
          minimum: 0
        custom_token_bans:
          type: array
          description: List of token IDs to fully block
          items:
            type: integer
        logit_bias:
          type: object
          description: >-
            Object mapping token IDs to additive logits. Works just like
            OpenAI's version
          additionalProperties:
            type: number
        logprobs:
          description: >-
            When true or a number, forwards the request to providers that
            support returning token-level log probabilities
          oneOf:
            - type: boolean
            - type: integer
        prompt_logprobs:
          type: boolean
          description: >-
            Requests logprobs on the prompt itself when the upstream API allows
            it
        seed:
          type: integer
          description: >-
            Numeric seed. Wherever supported, passes the value to make
            completions repeatable
        prompt_caching:
          type: object
          description: >-
            Helper to tag the leading messages for Claude prompt caching.
            NanoGPT injects cache_control blocks on each message up to the
            specified index before forwarding upstream. If
            cut_after_message_index is omitted, NanoGPT selects a cache boundary
            automatically.
          properties:
            enabled:
              type: boolean
              description: Whether to enable prompt caching on this request
              default: false
            ttl:
              type: string
              description: Cache time-to-live ('5m' or '1h')
              enum:
                - 5m
                - 1h
              example: 5m
            cut_after_message_index:
              type: integer
              minimum: 0
              description: >-
                Zero-based index of the last message that should be cached. All
                messages up to and including this index receive the same
                cache_control block.
            stickyProvider:
              type: boolean
              description: >-
                When true, avoids failover to preserve prompt cache consistency.
                If a fallback would be required, the request can return 503
                instead.
              default: false
        reasoning_effort:
          type: string
          description: Controls reasoning depth for reasoning-capable models
          enum:
            - none
            - minimal
            - low
            - medium
            - high
        reasoning:
          type: object
          description: >-
            Reasoning configuration. Use exclude to hide reasoning output,
            effort to control reasoning depth, and delta_field to switch to
            legacy reasoning_content fields.
          additionalProperties: true
          properties:
            exclude:
              type: boolean
              description: When true, omits reasoning fields from the response
            effort:
              type: string
              description: Alias for reasoning_effort
              enum:
                - none
                - minimal
                - low
                - medium
                - high
            delta_field:
              type: string
              description: >-
                When set to "reasoning_content", uses legacy reasoning_content
                fields instead of reasoning
              enum:
                - reasoning_content
        reasoning_delta_field:
          type: string
          description: Shorthand for reasoning.delta_field
          enum:
            - reasoning_content
        reasoning_content_compat:
          type: boolean
          description: Shorthand to force legacy reasoning_content fields in the response
    ChatCompletionResponse:
      type: object
      properties:
        id:
          type: string
          description: Unique identifier for the completion
        object:
          type: string
          description: Object type, always 'chat.completion'
        created:
          type: integer
          description: Unix timestamp of when the completion was created
        choices:
          type: array
          description: Array of completion choices
          items:
            type: object
            properties:
              index:
                type: integer
                description: Index of the choice
              message:
                type: object
                properties:
                  role:
                    type: string
                    description: Role of the completion message
                    enum:
                      - assistant
                  content:
                    type: string
                    description: Content of the completion message
                  reasoning:
                    type: string
                    description: >-
                      Optional reasoning output (when supported and not
                      excluded)
                  reasoning_content:
                    type: string
                    description: >-
                      Legacy alias of reasoning (only present when legacy
                      compatibility is enabled)
                  reasoning_details:
                    type: array
                    description: Optional structured reasoning metadata (when available)
                    items:
                      type: object
                      additionalProperties: true
              finish_reason:
                type: string
                description: Reason why the completion finished
                enum:
                  - stop
                  - length
                  - content_filter
        usage:
          type: object
          properties:
            prompt_tokens:
              type: integer
              description: Number of tokens in the prompt
            prompt_tokens_details:
              type: object
              description: Optional details about prompt token accounting
              properties:
                cached_tokens:
                  type: integer
                  description: Cached input tokens (when prompt caching is used)
            cache_creation_input_tokens:
              type: integer
              description: >-
                Input tokens written to cache on this request (when prompt
                caching is used)
            cache_read_input_tokens:
              type: integer
              description: >-
                Input tokens read from cache on this request (when prompt
                caching is used)
            completion_tokens:
              type: integer
              description: Number of tokens in the completion
            completion_tokens_details:
              type: object
              description: Optional breakdown of completion token accounting
              additionalProperties: true
              properties:
                reasoning_tokens:
                  type: integer
                  description: Reasoning tokens within the completion (when reported)
            reasoning_tokens:
              type: integer
              description: Reasoning tokens within the completion (when reported)
            total_tokens:
              type: integer
              description: Total number of tokens used
        service_tier:
          type: string
          description: Service tier used (echoed when provided on the request)
    Error:
      required:
        - error
        - message
      type: object
      properties:
        error:
          type: integer
          format: int32
        message:
          type: string
    MessageContentPart:
      type: object
      required:
        - type
      additionalProperties: true
      properties:
        type:
          type: string
          description: Content block type
          enum:
            - text
            - image_url
            - input_text
            - input_audio
            - input_video
            - tool_use
            - tool_result
        text:
          type: string
          description: Text content when type is 'text'
        image_url:
          type: object
          description: Image reference for multimodal prompts
          properties:
            url:
              type: string
              description: HTTPS URL or base64 data URL for the image
            detail:
              type: string
              description: Requested image resolution detail
              enum:
                - low
                - high
                - auto
        input_audio:
          type: object
          description: Inline audio input payload
          properties:
            data:
              type: string
              description: Base64 encoded audio bytes
            format:
              type: string
              description: Audio format (e.g. wav, mp3)
        input_video:
          type: object
          description: Inline video reference
          properties:
            video_url:
              type: string
              description: HTTPS URL or data URL for the video
        cache_control:
          type: object
          description: >-
            Claude-only prompt caching control applied to this block. When
            present, NanoGPT forwards it unchanged to Anthropic.
          properties:
            type:
              type: string
              enum:
                - ephemeral
              description: >-
                Cache type. Claude currently exposes the 'ephemeral' tier for
                5m/1h TTLs.
            ttl:
              type: string
              enum:
                - 5m
                - 1h
              description: Optional TTL override for this block.
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer

````
