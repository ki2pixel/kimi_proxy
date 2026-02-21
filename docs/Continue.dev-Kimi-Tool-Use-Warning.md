# **Technical Analysis of Agentic Interoperability: Continue.dev Orchestration and NVIDIA NIM Kimi Model Capabilities**

The evolution of the integrated development environment has transitioned from basic syntax highlighting and static analysis toward a sophisticated agentic ecosystem where the editor acts as a dynamic participant in the software lifecycle. Central to this transformation is the Continue.dev framework, an open-source platform that enables the orchestration of large language models for complex coding tasks through autonomous tool usage, multi-step planning, and multimodal processing.1 A critical juncture in the performance of these systems is the interaction between the orchestration layer and the underlying model's capability to interpret and execute function calls, often referred to as tool use. The emergence of highly specialized reasoning models, such as the Moonshot AI Kimi K2.5, delivered via the NVIDIA NIM microservices infrastructure, has introduced new paradigms in agentic stability but also specific technical friction points, most notably manifested in the "Agent might not work well with this model" warning.3

## **Architectural Foundations of the Continue.dev Agentic Loop**

The operational logic of Continue.dev distinguishes between standard conversational modes and the specialized Agent mode, which provides the model with direct interfaces to the external world.1 In Chat mode, the interaction remains purely linguistic, where the model processes natural language and generates a response based on its internal weights and provided context. However, Agent mode introduces a sophisticated "tool handshake" mechanism. This protocol allows the model to receive a structured library of available actions, defined as JSON objects containing a name and an arguments schema, which it can then invoke to perform operations such as reading files, executing terminal commands, or modifying the codebase.1

The agentic cycle begins when the available tools are sent to the model along with the user's initial prompt. The model, acting as an orchestrator, evaluates whether its instructions require external information or actions. If so, it generates a response containing a tool call.1 The IDE then manages the execution of this call, often requiring user permission for high-risk operations unless a policy is established for automatic execution.1 The results of these operations—whether they are file contents from a read\_file tool or output from a run\_terminal\_command—are fed back to the model as context items, allowing it to synthesize the data and determine the next step in a potentially long-horizon task.1

### **Operational Modes and Tool Availability**

The categorization of model usage within Continue.dev is strictly divided into three tiers of capability, each designed to balance autonomy with safety and computational cost.6

| Mode | Tool Access Policy | Primary Functionality | Tool Support Requirements |
| :---- | :---- | :---- | :---- |
| Chat Mode | No tools included | Pure natural language conversation | None |
| Plan Mode | Read-only tools only | Safe exploration and project-wide planning | Basic reasoning |
| Agent Mode | All tools included | Implementation, bug fixing, and command execution | Native or System Tool Use |

The availability of these modes is contingent upon the model's supported capabilities. If the selected model or provider is not recognized by Continue.dev as supporting tool calling, the Agent and Plan modes may be disabled or accompanied by warnings indicating limited functionality.5 This autodetection failure is the primary trigger for the "Agent might not work well" alert, signaling to the developer that the model might not conform to the expected output formats for structured function calling.4

## **Mechanism of Tool Support and System Message Fallbacks**

To bridge the gap between models with native function-calling APIs and those lacking such features, Continue.dev utilizes a dual-path approach for tool implementation. For established models such as GPT-4, Claude 3.5, or Gemini 2.0, the framework leverages native tool-calling APIs.7 However, for a wider range of open-source and local models, the system employs an innovative strategy known as system message tools.7

The system message tool approach ensures universal compatibility by converting tool definitions into an XML format and embedding them directly into the model's system prompt. Instead of relying on specific API endpoints for tool calling, the model is instructed to generate structured XML blocks within its response. Continue.dev then parses these XML blocks and executes the corresponding functions.7 While this provides a consistent behavior across different providers—including OpenAI, Anthropic, and local instances—it relies heavily on the model's ability to follow complex formatting instructions. Models that struggle with structured output may produce malformed XML, leading to failures in the agentic loop.7

### **Comparative Advantages of Native vs. System Message Tools**

The choice between native and system message tools significantly impacts the reliability and latency of the agentic workflow.7

| Feature | Native Tool Calling | System Message Tools |
| :---- | :---- | :---- |
| **Compatibility** | Specific to API providers | Universal for any instruction-following model |
| **Reliability** | High, enforced by API schemas | Variable, dependent on model formatting |
| **Parsing** | Direct JSON extraction | XML parsing and regex-based extraction |
| **Ease of Use** | Automatic for supported models | Requires explicit configuration for some models |
| **Behavior** | Provider-dependent | Consistent across all platforms |

Despite the benefits of universal compatibility, Continue.dev identifies that models specifically trained for native tools often perform better with native implementations. System message tools are considered an experimental fallback for models that do not natively support function calling.5

## **Technical Profile of the NVIDIA NIM Kimi K2.5 Ecosystem**

The integration of Moonshot AI's Kimi model family into the NVIDIA NIM infrastructure represents a milestone in multimodal agentic AI. Kimi K2.5 is a native multimodal model built through continual pretraining on approximately 15 trillion visual and text tokens.9 Its architecture is a Mixture-of-Experts (MoE) design with 1 trillion total parameters, optimized for high-throughput inference on NVIDIA Hopper and Blackwell architectures.9

### **Architectural Specifications of Kimi K2.5**

The model's efficiency is derived from its extremely sparse activation rate, which allows it to maintain the depth of a trillion-parameter model while activating only a fraction of its weights during each token generation.10

| Architectural Attribute | Specification |
| :---- | :---- |
| Total Parameter Count | 1 Trillion |
| Activated Parameters | \~32.86 Billion |
| Expert Configuration | 384 Experts (8 selected per token) |
| Attention Mechanism | Multi-head Latent Attention (MLA) |
| Vocabulary Size | 160,000 Tokens (Vision-specific tokens included) |
| Context Window | 256,000 Tokens |
| Quantization | Native INT4 weight-only (Group size 32\) |

This architecture is supported by a native 200M parameter vision encoder, MoonViT, which allows the model to process image and video data directly into the latent space of the LLM.9 This integration is not a superficial "bolted-on" feature but is native to the training process, enabling the model to excel at vision-grounded tasks such as converting video demonstrations into code or performing visual debugging of UI components.9

## **Operational Paradigms: Thinking vs. Instant Modes**

One of the most distinctive features of the Kimi family—specifically the Kimi K2 Thinking and K2.5 variants—is the support for dual operational modes: Instant and Thinking.9

In Instant mode, the model generates direct responses without explicit reasoning traces, optimized for speed and low latency. This mode is recommended for straightforward conversational tasks and standard coding queries.9 In contrast, Thinking mode enables a chain-of-thought (CoT) process where the model generates interleaved reasoning steps before arriving at a final answer or tool call. This reasoning is returned in a separate reasoning\_content field in the API response.9

### **The Impact of Long-Horizon Agency**

Kimi K2 Thinking is designed to handle "long-horizon" agency, defined as the ability to maintain coherent, goal-directed behavior over hundreds of sequential actions. While many contemporary models experience reasoning drift or context loss after 30 to 50 steps, Kimi K2 is documented to maintain stable tool use across 200 to 300 consecutive calls.10

| Agency Metric | Standard LLM Performance | Kimi K2 Thinking Capability |
| :---- | :---- | :---- |
| Sequential Tool Call Stability | 30–50 calls | 200–300 calls |
| Context Window Length | 128K tokens (avg.) | 256K tokens |
| Reasoning Trace Retention | Intermittent | Interleaved and persistent |
| Tool Interaction Style | Reactive | Proactive and planned |

This capability is particularly relevant for autonomous research workflows and complex coding projects spanning hundreds of steps. By interleaving reasoning with tool calls, the model can adjust its strategy based on the success or failure of prior actions in real-time.15

## **Troubleshooting the "Agent Might Not Work Well" Warning**

The warning encountered by users of Continue.dev when utilizing NVIDIA NIM endpoints is fundamentally a result of a mismatch in the model's metadata and the IDE's internal capability detection logic.5 Continue.dev relies on a list of known models and providers to determine whether to enable tool-use features. If a model is accessed via a proxy such as OpenRouter or a custom deployment like NVIDIA NIM, the IDE may fail to recognize the tool\_use capability automatically.8

### **Autodetection Logic and Manual Overrides**

The IDE's detection mechanism, located in the toolSupport.ts logic, checks model names and providers against a whitelist.8 For instance, it automatically recognizes GPT-4, Claude 3.5, and Gemini models as supporting tools.5 If the model is not on this list, the "Agent might not work well" warning is triggered, and Agent mode might be grayed out.5

To resolve this, developers can manually override the autodetection by adding a capabilities array to their model configuration in config.yaml or config.json.8 This manually instructs Continue.dev to attempt tool-calling handshakes even if it does not recognize the model identifier.8

YAML

models:  
  \- name: "Kimi K2.5"  
    provider: "openai"  
    model: "moonshotai/kimi-k2.5"  
    apiBase: "https://integrate.api.nvidia.com/v1"  
    capabilities:  
      \- "tool\_use"  
      \- "image\_input"

It is important to understand that adding the tool\_use capability does not create tool-use functionality in a model that lacks it; rather, it enables the IDE to send the tool definitions and parse the responses.5 For Kimi K2.5, which natively supports function calling, this override simply closes the bridge between the model's actual ability and the IDE's configuration.3

## **Interoperability Challenges with the "reasoning\_content" Field**

A significant friction point for reasoning models like Kimi K2.5 is the divergence from standard OpenAI-compatible API response formats. Traditional models return the final response in the content field. However, Kimi and similar models like DeepSeek R1 often return their chain-of-thought in a specialized reasoning\_content field.19

### **Parser Failures and UI Anomalies**

When using these models through proxies like LiteLLM or in IDEs like Continue.dev, several technical issues often arise:

* **Null Content Hangs:** If a model produces only reasoning and then initiates a tool call, the content field may remain null. Some parsers interpret a null content field as an end-of-stream or a failed response, causing the agent to hang before executing the tool.21  
* **Tag Bleed in Editor:** In "Edit" mode, where the model is expected to provide code for direct insertion, models may include reasoning thoughts within \<think\> tags. If the IDE doesn't explicitly filter these out, the internal thoughts are written into the source code, rendering the edit unusable.22  
* **Missing Field Errors:** Some agentic implementations throw HTTP 400 errors if the reasoning\_content field is not present in the expected schema, or if the model's output doesn't match the strictly defined JSON structure required for tool calls.23

These issues are often exacerbated when using OpenRouter or LiteLLM, which may not always preserve the original model's specific response fields.8 Developers have reported that while Claude Code and Continue.dev have made strides in handling these fields, secondary tools like OpenCode may still struggle with the specialized response structure.21

## **Benchmarking Kimi K2.5 in Agentic Environments**

The performance of Kimi K2.5 across standard benchmarks demonstrates its readiness for production-level agentic tasks, particularly in comparison to established proprietary models.

| Benchmark | Model Version | Score/Result | Evaluation Domain |
| :---- | :---- | :---- | :---- |
| SWE-Bench Verified | Kimi K2.5 | 76.8% | Real-world bug fixing |
| LiveCodeBench v6 | Kimi K2.5 | 85.0% | Live programming challenges |
| MATH-500 | Kimi K2.5 | 97.4% | Mathematical reasoning |
| GPQA | Kimi K2.5 | 75.0% | General problem-solving |
| Humanity's Last Exam | Kimi K2 Thinking | 44.9% | High-level reasoning |

The model's performance on SWE-Bench Verified is particularly noteworthy, as it approaches the accuracy of Claude 3.5 Sonnet (80.9%) while significantly outperforming GPT-4.1 (54.6%) in single-attempt agentic settings.13 Its superior score on LiveCodeBench indicates a high degree of proficiency in modern coding syntax and logic, which directly supports its utility in an IDE context despite the initial capability warnings.24

### **The Agent Swarm Mechanism**

A differentiating feature of Kimi K2.5 is the "Agent Swarm" execution scheme. This paradigm shifts from single-agent scaling to a self-directed, coordinated execution of up to 100 parallel sub-agents.11 These sub-agents are dynamically instantiated for domain-specific tasks, such as research, planning, or execution, and then merged to provide a final result. This approach has been reported to cut execution time by 4.5 times compared to single-agent workflows, making it ideal for large-scale code transformations and multimodal layout iterations.11

## **Hardware and Performance Constraints for NIM Deployments**

The computational requirements for Kimi K2.5 are substantial, given its trillion-parameter MoE architecture. For developers choosing to host these models locally or on-premises using NVIDIA NIM containers, the hardware selection is a critical factor in maintaining the latency required for a responsive IDE experience.10

| Deployment Type | Minimum Hardware Requirement | VRAM Target | Inference Speed |
| :---- | :---- | :---- | :---- |
| Local (Quantized 1.8-bit) | 1x 24GB GPU \+ 256GB RAM | 24GB VRAM | \~10 tokens/s |
| Near Full Precision (4-bit) | 4x H200 GPUs | \~600GB VRAM | \>40 tokens/s |
| NVIDIA NIM Trial API | Cloud Hosted | N/A | Variable (Free access) |
| Enterprise Production | 8x H100 Cluster | 640GB+ VRAM | Optimized for Swarm |

To achieve the best performance in local environments using tools like llama.cpp, developers are encouraged to use specific offloading strategies, such as offloading MoE layers to system RAM to fit the non-MoE components onto a single GPU.12 This allows models that would otherwise require multiple H100s to run on more modest hardware, albeit at a lower token generation rate.12

## **Configuration Best Practices for Agentic Coding**

To optimize the interaction between Continue.dev and NVIDIA NIM, developers must move beyond basic setup and leverage the advanced configuration properties available in the config.yaml file.18

### **Advanced Model Properties**

The configuration schema supports several properties that can enhance the stability of Kimi models in an agentic role:

* **maxStopWords:** Setting limits on stop words prevents API errors during extensive generation loops.18  
* **embedOptions:** Configuring maxChunkSize (minimum 128 tokens) and maxBatchSize is essential for models that include a role in embedding, which is used for codebase indexing in Continue.dev.18  
* **completionOptions:** Parameters such as temperature and top\_p should be adjusted based on the mode. Moonshot AI recommends a temperature of 1.0 for Thinking mode and 0.6 for Instant mode.9  
* **requestOptions:** Custom headers and extraBodyProperties allow developers to pass specific flags to NIM, such as disabling thinking mode for "Edit" tasks to prevent tag bleed.9

YAML

models:  
  \- name: "Kimi K2.5 Instant"  
    provider: "openai"  
    model: "moonshotai/kimi-k2.5"  
    requestOptions:  
      extraBodyProperties:  
        chat\_template\_kwargs:  
          thinking: false

This specific configuration ensures that the model operates without reasoning traces, providing a faster and cleaner output for code-edit operations where the agent must modify existing files without inserting conversational filler.9

## **The Role of Model Context Protocol (MCP) in IDE Agency**

The Model Context Protocol (MCP) is increasingly becoming the standard for connecting AI agents to external tools and data sources. Continue.dev fully integrates with MCP servers, allowing Agent mode to access a broad range of capabilities beyond simple file system access.1

### **NeMo Agent Toolkit and MCP Integration**

NVIDIA's NeMo Agent Toolkit further extends these capabilities by acting as both an MCP client and server. This allows agents built with Kimi K2.5 to leverage a unified registry of tools, including RAG architectures, search engines, and observability trackers.29

| MCP Category | Example Tools | IDE Application |
| :---- | :---- | :---- |
| **Code Navigation** | File search, grep, git log | Understanding project structure and history |
| **Documentation** | Context7, DeepWiki | Retrieving framework-specific API details |
| **System Interaction** | Terminal execution, gh CLI | Running tests, managing pull requests |
| **Productivity** | PDF generation, web search | Synthesizing research or technical specs |

By utilizing MCP, Agent mode can explore repositories, find implementation patterns in external codebases (such as React or Next.js), and cite documentation when explaining concepts.28 This capability is what enables Kimi K2.5 to act as a "Thinking Agent" that reasons step-by-step while dynamically invoking tools to solve complex problems.15

## **Security and Permission Architectures for Agents**

Granting an AI model the ability to execute terminal commands and modify codebase files necessitates a rigorous security framework. Continue.dev implements several layers of protection to mitigate the risks associated with autonomous agency.6

The fundamental security principle employed is the requirement for manual approval. By default, the Agent mode will pause and request user permission before executing any tool call. This allows the developer to review the proposed action and its arguments before it impacts the workspace.6 For teams deploying agents in CI/CD environments via the Continue CLI (cn), the documentation recommends following the principle of least privilege, specifically limiting GitHub Actions permissions and environment variable access.27

| Security Layer | Recommendation | Rationale |
| :---- | :---- | :---- |
| **Human-in-the-Loop** | Keep tool policies manual for write operations | Prevents accidental or malicious file corruption |
| **Permission Scoping** | Use contents: read for analysis agents | Limits the blast radius of a compromised agent |
| **Local Sandboxing** | Run agents in isolated environments | Protects host system from experimental tool use |
| **Secret Management** | Use .env files for API keys | Avoids committing credentials to version control |

When running agents locally, developers can monitor all executed commands through the cn \--verbose flag, providing full transparency into the agent's decision-making process.27

## **Future Trajectories: The Rise of Multi-Agent Orchestration**

The shift from single-model agents to multi-agent "swarms" or "orchestrators" represents the next frontier in AI-assisted development. NVIDIA's Research into "ToolOrchestra" suggests a paradigm where a small, efficient orchestrator model manages a collection of larger, specialized models to achieve the highest accuracy at the lowest cost.31

This approach addresses the current limitations of monolithic LLMs, which may be "overqualified" and too slow for simple tool-use tasks while being "underqualified" for extremely complex reasoning. An orchestrator model can consider user preferences for speed and cost, dynamically routing tasks to the most appropriate agent in the swarm—potentially using Kimi K2.5 for multimodal UI tasks and a smaller, faster model for syntax checks.31

The "Agent might not work well" warning is, in this context, a symptom of the growing pains as the industry moves toward these compound AI systems. As IDEs like Continue.dev and providers like NVIDIA NIM further align their protocols—particularly around structured reasoning and standardized tool handshakes—the friction of manual configuration will likely give way to more seamless, autonomous coding environments.

## **Synthesis of Agentic Interaction and Interoperability**

The technical landscape of modern software development is increasingly defined by the synergy between high-capacity reasoning models and the orchestration frameworks that house them. The interaction between Continue.dev and NVIDIA NIM's Kimi model series serves as a prime example of this complex interoperability. While the "Agent might not work well" warning indicates a mismatch in recognized capabilities, the underlying technology of Kimi K2.5—with its trillion-parameter MoE architecture, native multimodality, and stable long-horizon agency—is fundamentally designed for the exact agentic workflows that the IDE aims to facilitate.

By meticulously configuring model capabilities, managing reasoning traces through extraBodyProperties, and leveraging protocols like MCP, developers can bypass the superficial limitations of autodetection. The result is a powerful, multimodal coding assistant capable of autonomously navigating codebases, reasoning through complex bugs, and coordinating parallel sub-tasks with the efficiency of an agent swarm. The persistence of these technical hurdles serves as a reminder of the necessary balance between the rapid innovation in model architectures and the need for standardized communication protocols in the agentic era.

#### **Sources des citations**

1. How Agent Mode Works | Continue Docs, consulté le février 21, 2026, [https://docs.continue.dev/ide-extensions/agent/how-it-works](https://docs.continue.dev/ide-extensions/agent/how-it-works)  
2. Personalization in Vibe Coding | Snyk, consulté le février 21, 2026, [https://snyk.io/articles/personalization-vibe-coding/](https://snyk.io/articles/personalization-vibe-coding/)  
3. Call Functions (Tools) — NVIDIA NIM for Vision Language Models, consulté le février 21, 2026, [https://docs.nvidia.com/nim/vision-language-models/latest/function-calling.html](https://docs.nvidia.com/nim/vision-language-models/latest/function-calling.html)  
4. Agent Mode \- model recommendations \#7158 \- GitHub, consulté le février 21, 2026, [https://github.com/continuedev/continue/discussions/7158](https://github.com/continuedev/continue/discussions/7158)  
5. FAQs | Continue Docs, consulté le février 21, 2026, [https://docs.continue.dev/faqs](https://docs.continue.dev/faqs)  
6. Quick Start \- Continue Docs, consulté le février 21, 2026, [https://docs.continue.dev/ide-extensions/agent/quick-start](https://docs.continue.dev/ide-extensions/agent/quick-start)  
7. Model Setup for Agent Mode \- Continue Docs, consulté le février 21, 2026, [https://docs.continue.dev/ide-extensions/agent/model-setup](https://docs.continue.dev/ide-extensions/agent/model-setup)  
8. How to Configure Model Capabilities in Continue, consulté le février 21, 2026, [https://docs.continue.dev/customize/deep-dives/model-capabilities](https://docs.continue.dev/customize/deep-dives/model-capabilities)  
9. kimi-k2.5 Model by Moonshotai \- NVIDIA NIM APIs, consulté le février 21, 2026, [https://build.nvidia.com/moonshotai/kimi-k2.5/modelcard](https://build.nvidia.com/moonshotai/kimi-k2.5/modelcard)  
10. Kimi K2 Thinking: what 200+ tool calls mean for production \- Lambda, consulté le février 21, 2026, [https://lambda.ai/blog/kimi-k2-thinking](https://lambda.ai/blog/kimi-k2-thinking)  
11. NVIDIA Launches GPU-Accelerated Endpoints for Moonshot AI's, consulté le février 21, 2026, [https://www.mexc.co/news/648736](https://www.mexc.co/news/648736)  
12. Kimi K2.5: How to Run Locally Guide | Unsloth Documentation, consulté le février 21, 2026, [https://unsloth.ai/docs/models/kimi-k2.5](https://unsloth.ai/docs/models/kimi-k2.5)  
13. Kimi K2.5: Everything We Know About Moonshot's Visual Agentic, consulté le février 21, 2026, [https://wavespeed.ai/blog/posts/kimi-k2-5-everything-we-know-about-moonshots-visual-agentic-model/](https://wavespeed.ai/blog/posts/kimi-k2-5-everything-we-know-about-moonshots-visual-agentic-model/)  
14. Is Kimi K2.5 open source? A 3-step guide to Kimi K2.5 API integration, consulté le février 21, 2026, [https://help.apiyi.com/en/kimi-k2-5-open-source-api-integration-guide-en.html](https://help.apiyi.com/en/kimi-k2-5-open-source-api-integration-guide-en.html)  
15. kimi-k2-thinking Model by Moonshotai \- NVIDIA NIM APIs, consulté le février 21, 2026, [https://build.nvidia.com/moonshotai/kimi-k2-thinking/modelcard](https://build.nvidia.com/moonshotai/kimi-k2-thinking/modelcard)  
16. moonshotai / kimi-k2-thinking \- NVIDIA API Documentation, consulté le février 21, 2026, [https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k2-thinking](https://docs.api.nvidia.com/nim/reference/moonshotai-kimi-k2-thinking)  
17. How to Configure OpenRouter with Continue, consulté le février 21, 2026, [https://docs.continue.dev/customize/model-providers/top-level/openrouter](https://docs.continue.dev/customize/model-providers/top-level/openrouter)  
18. config.yaml Reference | Continue Docs, consulté le février 21, 2026, [https://docs.continue.dev/reference](https://docs.continue.dev/reference)  
19. NVIDIA has made kimi-k2.5 available, and it can be used for free., consulté le février 21, 2026, [https://www.reddit.com/r/WritingWithAI/comments/1qr8pxw/nvidia\_has\_made\_kimik25\_available\_and\_it\_can\_be/](https://www.reddit.com/r/WritingWithAI/comments/1qr8pxw/nvidia_has_made_kimik25_available_and_it_can_be/)  
20. LM Studio 0.3.9, consulté le février 21, 2026, [https://lmstudio.ai/blog/lmstudio-v0.3.9](https://lmstudio.ai/blog/lmstudio-v0.3.9)  
21. Response terminates prematurely when using Gemini 3 via LiteLLM, consulté le février 21, 2026, [https://github.com/anomalyco/opencode/issues/6244](https://github.com/anomalyco/opencode/issues/6244)  
22. BUG: Edit mode with gpt-oss-120b inserts reasoning text into file, consulté le février 21, 2026, [https://github.com/continuedev/continue/issues/8990](https://github.com/continuedev/continue/issues/8990)  
23. Error: DeepSeek Coder \- 402 · Issue \#9142 · continuedev/continue, consulté le février 21, 2026, [https://github.com/continuedev/continue/issues/9142](https://github.com/continuedev/continue/issues/9142)  
24. Analysis of the Kimi K2 Open-Weight Language Model \- IntuitionLabs, consulté le février 21, 2026, [https://intuitionlabs.ai/articles/kimi-k2-open-weight-llm-analysis](https://intuitionlabs.ai/articles/kimi-k2-open-weight-llm-analysis)  
25. continue-dev \- Notes, consulté le février 21, 2026, [https://notes.jamesravey.me/continue-dev](https://notes.jamesravey.me/continue-dev)  
26. Visual Studio Code Local Assistant \- OpenVINO, consulté le février 21, 2026, [https://docs.openvino.ai/2025/model-server/ovms\_demos\_code\_completion\_vsc.html](https://docs.openvino.ai/2025/model-server/ovms_demos_code_completion_vsc.html)  
27. Run Agents Locally \- Continue Docs, consulté le février 21, 2026, [https://docs.continue.dev/guides/run-agents-locally](https://docs.continue.dev/guides/run-agents-locally)  
28. How to Make Agent mode Aware of Codebases and Documentation, consulté le février 21, 2026, [https://docs.continue.dev/guides/codebase-documentation-awareness](https://docs.continue.dev/guides/codebase-documentation-awareness)  
29. NVIDIA NeMo Agent Toolkit \- NVIDIA Developer, consulté le février 21, 2026, [https://developer.nvidia.com/nemo-agent-toolkit](https://developer.nvidia.com/nemo-agent-toolkit)  
30. NeMo Agent Toolkit as an MCP Server, consulté le février 21, 2026, [https://docs.nvidia.com/nemo/agent-toolkit/1.4/run-workflows/mcp-server.html](https://docs.nvidia.com/nemo/agent-toolkit/1.4/run-workflows/mcp-server.html)  
31. Train Small Orchestration Agents to Solve Big Problems \- NVidia, consulté le février 21, 2026, [https://developer.nvidia.com/blog/train-small-orchestration-agents-to-solve-big-problems/](https://developer.nvidia.com/blog/train-small-orchestration-agents-to-solve-big-problems/)