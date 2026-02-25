# **Architectural Integration and Transport Troubleshooting of Model Context Protocol Servers in Continue.dev**

**TL;DR**: si tu utilises des serveurs MCP en stdio (filesystem-agent, ripgrep-agent, shrimp-task-manager) et qu’ils écrivent des bannières/logs sur stdout, Continue peut casser le parsing JSON-RPC. Dans ce repo, la solution recommandée est `scripts/mcp_bridge.py` (relay + filtrage stdout). Voir: `docs/troubleshooting/MCP_Bridge_Stdio_Servers.md`.

The Model Context Protocol (MCP) represents a foundational shift in how large language models (LLMs) interact with external data sources and computational tools. As an open standard proposed by Anthropic, MCP provides a universal "USB-C for AI," enabling a standardized interface between AI agents and diverse capabilities such as filesystem access, database querying, and external API orchestration.1 Within the Continue.dev ecosystem, these capabilities are integrated directly into the developer workflow, allowing models to serve as agentic entities capable of autonomous reasoning and tool execution.4 However, the transition from local process-based communication to network-oriented HTTP transports introduces significant complexity, often resulting in connectivity failures such as the "SSE error: Non-200 status code (404)" observed when configuring local servers on specific ports.6

## **Evolutionary Context of the Model Context Protocol**

The development of the Model Context Protocol was necessitated by the fragmented landscape of LLM tool-calling. Prior to its inception, each AI assistant or IDE required bespoke integrations for every new tool, leading to high maintenance overhead and limited portability.2 MCP standardizes this interaction through the use of JSON-RPC 2.0 messages, which are transport-agnostic and can be delivered via standard input/output (stdio) or over HTTP-based channels.1

The protocol's architecture distinguishes between the MCP Host (the client, such as Continue.dev) and the MCP Server (the provider of tools and resources).3 The host is responsible for discovering the server's capabilities, managing the connection lifecycle, and presenting a user interface for granting consent for tool execution.3 The server, conversely, exposes tools (executable functions), resources (read-only data), and prompts (reusable templates).3

### **Protocol Lifecycle and Handshake Mechanics**

A successful MCP connection begins with a structured handshake. The client initiates an initialize request, detailing its protocol version, capabilities, and client information.2 The server responds with its own capabilities and confirms the protocol version.2 Following this exchange, the client sends an initialized notification, signaling that it is ready to proceed with normal operations, such as listing tools via tools/list or calling a specific tool via tools/call.2

A critical aspect of this lifecycle is that the server and client must strictly adhere to the initialization sequence. Any request sent before the initialized notification—other than a ping or a logging notification—is considered a violation of the protocol and must be rejected.2 This ensures that both parties have negotiated their capabilities and are prepared for the intended interaction patterns.2

| Interaction Phase | Message Type | Purpose | ID Required |
| :---- | :---- | :---- | :---- |
| Handshake | Request (initialize) | Negotiate protocol version and capabilities | Yes |
| Handshake | Response (initialize) | Server confirms capabilities and version | Yes |
| Handshake | Notification (initialized) | Client confirms readiness for normal operation | No |
| Discovery | Request (tools/list) | Client retrieves the list of available tools | Yes |
| Execution | Request (tools/call) | Client invokes a specific function with parameters | Yes |
| Health Check | Request (ping) | Monitor connection stability and latency | Yes |

1

## **Deconstructing the 404 SSE Error in Continue.dev**

The "SSE error: Non-200 status code (404)" is a common friction point when configuring local HTTP-based MCP servers.6 This error indicates that while the network connection to the specified port is successful, the specific resource or endpoint requested by the client does not exist on the server.6 In the context of Continue.dev and the MCP SDK, this often occurs during the initial probing phase or due to a mismatch in session management.6

### **The Initialization Probe and Path Mismatches**

Modern MCP clients perform an initial probe to determine if an endpoint supports Server-Sent Events (SSE). This is done by sending an HTTP GET request to the configured URL with an Accept header including text/event-stream.6 According to the specification, if the server supports SSE, it should respond by initiating a stream.15 If it does not support SSE at that specific path, it must return an HTTP 405 Method Not Allowed.6

However, many server implementations return a 404 Not Found if they are not explicitly configured to handle the GET method at that endpoint.6 When the client receives a 404, it interprets this as a failure to locate the MCP service entirely, leading to the connection termination.6 This is particularly relevant for the user's servers on ports 8002-8005, which are using a path of /rpc.6 If the underlying MCP SDK or the specific tool logic expects the interaction to occur at /mcp or /sse, the resulting mismatch triggers the 404\.6

### **Session Identification and Multi-Process Issues**

Another prevalent cause of 404 errors is related to session persistence. When using HTTP-based transports, the server must maintain state to correlate incoming POST requests with established client sessions.9 This is typically managed via an Mcp-Session-Id header.12

If a server is running in a multi-process environment—such as a Kubernetes cluster or a multi-worker Gunicorn setup—session state stored in local memory is not shared across processes.20 If a client sends an initialize request to Worker A, but a subsequent tool call is routed to Worker B, Worker B will not find the session ID in its memory and will return a 404\.20 For local development on ports 8002-8005, this can also happen if the server process restarts and the client attempts to reuse a stale session ID without performing a new handshake.12

## **Configuration Schema and Transport Selection**

Continue.dev utilizes a config.yaml file for its core configuration, which replaces the legacy config.json format.22 The mcpServers section of this file allows for the definition of various servers, each with its own transport configuration.5

### **The Importance of the 'type' Key**

A fundamental point of confusion in MCP configuration is the distinction between transport keywords across different IDEs. While some applications use transport, Continue.dev's YAML schema requires the type key to specify the transport protocol.5 The supported types are stdio, sse, and streamable-http.5

The user's provided configuration utilizes transport: http, which is not a recognized keyword in the Continue.dev YAML schema.5 This mismatch likely causes the extension to ignore the transport setting entirely or attempt to fall back to a default that does not match the server's actual protocol.5

| Transport Type | Use Case | Key Configuration Properties |
| :---- | :---- | :---- |
| stdio | Local scripts and CLI tools | command, args, env, cwd |
| sse | Legacy remote streaming over HTTP | url, requestOptions.headers |
| streamable-http | Modern unified HTTP transport | url, requestOptions.headers |

5

### **Correcting the Local Server Configuration**

To fix the errors associated with the servers on ports 8002-8005, the config.yaml must be updated to use the correct type identifiers and ensure the URL paths align with the server's expected endpoints.6 If the servers are built using the standard MCP SDKs, they generally default to /mcp for streamable HTTP and /sse for legacy SSE.10

A revised configuration for the user's setup would look as follows:

YAML

mcpServers:  
  \- name: task-master-ai  
    url: "http://localhost:8002/rpc"  
    type: streamable-http \# Changed from transport: http

  \- name: sequential-thinking  
    url: "http://localhost:8003/rpc"  
    type: streamable-http

  \- name: fast-filesystem  
    url: "http://localhost:8004/rpc"  
    type: streamable-http

  \- name: json-query  
    url: "http://localhost:8005/rpc"  
    type: streamable-http

If the servers on these ports do not support the modern Streamable HTTP transport, type: sse should be used as a fallback, provided the server implements the separate /messages endpoint required by the legacy specification.15

## **Local Process Transport: stdio Mechanics**

For many local automation tasks, the stdio transport remains the preferred choice due to its simplicity and low latency.30 In this mode, Continue.dev launches the MCP server as a child process and communicates via the standard input and output streams.1

### **Execution Environments: npx vs uvx**

The configuration of stdio servers often involves runners like npx (for Node.js) or uvx (for Python).5 These tools provide isolated execution environments, ensuring that dependencies do not conflict with the host system.10

However, using these runners can introduce environment-related issues. On macOS, the extension may fail to spawn the process with an ENAMETOOLONG error if the system environment is too large.30 The recommended workaround is to provide the absolute path to the executable, such as /usr/local/bin/npx, rather than relying on PATH resolution.30

### **Managing Filesystem Context**

Local servers like the filesystem-agent require specific arguments to define the directories they are allowed to access.5 This provides a layer of security, ensuring that the AI agent can only interact with files in approved workspace paths.2

YAML

\- name: filesystem-agent  
  command: npx  
  args:  
    \- "-y"  
    \- "@modelcontextprotocol/server-filesystem"  
    \- "/home/kidpixel"  
  env:  
    PATH: "/usr/bin:/bin:/usr/local/bin"

In this example, the \-y flag is crucial for npx to auto-confirm package installation in non-interactive environments like an IDE subprocess.5 The env block is used to ensure the server has the necessary system paths to find underlying binaries like git or bash.5

## **HTTP Transport and Remote Orchestration**

As MCP moves toward distributed architectures, HTTP-based transports become essential.3 This allows MCP servers to be hosted in the cloud, enabling shared tool sets across multiple users and machines.32

### **Streamable HTTP: The Modern Standard**

The March 2025 specification update introduced Streamable HTTP as the primary replacement for the legacy SSE transport.15 This transport simplifies infrastructure by using a single HTTP endpoint that can handle both standard request-response cycles and upgraded streaming connections.15

When a client sends a request to a Streamable HTTP server, the server can decide whether to return a standard JSON response or to initiate a stream if the task is long-running.15 This flexibility makes it ideal for remote deployment on platforms like Google Cloud Run or Northflank.37

### **Authorization and Headers**

Remote servers frequently require authentication to protect sensitive tools and data.9 Continue.dev supports this through the requestOptions field, which allows for the definition of custom headers.24

YAML

\- name: render-signal-mcp  
  url: "https://mcp.render.com/mcp"  
  type: streamable-http  
  requestOptions:  
    headers:  
      Authorization: "Bearer API"

In the user's provided snippet, the headers were placed directly under the server object.26 To comply with the YAML schema, these should be nested within requestOptions to be correctly recognized by the Continue.dev fetch client.24

| Feature | stdio | sse (Legacy) | streamable-http (Modern) |
| :---- | :---- | :---- | :---- |
| Endpoints | N/A | Two (SSE \+ POST) | One (Unified) |
| State | Inherited | Session IDs | Session IDs or Stateless |
| Streaming | Native | Unidirectional | Bidirectional |
| Complexity | Low | High | Medium |
| Scaling | Local only | Difficult | Highly Scalable |

1

## **Database and Application-Specific MCP Agents**

The integration of database-specific servers, such as those for PostgreSQL or Redis, represents one of the most powerful use cases for MCP.2 These servers allow the AI agent to query schemas, inspect records, and perform data transformations directly within the IDE context.2

### **Persistent Database Integration**

The user's configuration includes multiple postgres-mcp servers using uvx.5 These are typically configured with connection URIs passed as environment variables.5 Ensuring the \--access-mode=unrestricted flag is correctly passed is vital for allowing the agent to perform write operations or complex joins that might otherwise be blocked by security defaults.5

YAML

\- name: photomaton-postgres  
  command: uvx  
  args:  
    \- "--python"  
    \- "3.12"  
    \- "postgres-mcp"  
    \- "--access-mode=unrestricted"  
  env:  
    DATABASE\_URI: "postgresql://neondb\_owner:npg\_..."

The use of specific Python versions (e.g., 3.12) ensures that the uvx runner uses a compatible runtime for the MCP package.5 If the database URI contains sensitive credentials, these should ideally be managed through Continue.dev's secret management system using the ${{ secrets.VAR }} syntax.5

### **Redis Integration and Real-Time Context**

Similarly, the redis-mcp-server allows for interaction with key-value stores.5 This can be used to provide the model with real-time state information or to manage shared memory across different agent sessions.2 As with the PostgreSQL setup, the uvx command should use absolute paths if connection stability issues arise.30

## **Advanced Troubleshooting and Diagnostics**

When MCP servers fail to load or exhibit erratic behavior, a structured debugging approach is necessary to isolate the cause.27

### **IDE Logging and Console Inspection**

The primary diagnostic tool for Continue.dev is the IDE's developer console.30 In VS Code, this is accessed via the command "Developer: Toggle Developer Tools".30 The "Console" tab will display detailed error messages, including stack traces for failed connections and the specific HTTP status codes returned by remote servers.30

For a deeper look at the core logic, Continue.dev provides a dedicated console view that can be focused via the command palette ("Continue: Focus on Continue Console View").30 This view often contains logs from the internal MCP host, showing the initialization handshake and any JSON-RPC parsing errors.2

### **Validating with External Tools**

If an MCP server works with curl but fails in the IDE, the issue is often related to the headers or the specific sequence of requests.6 The "MCP Inspector" is a standalone utility provided by the protocol authors to test servers in isolation.10

By starting the local server and pointing the Inspector at it, developers can verify if the server correctly handles the initialize request and subsequent tool calls.10 If the Inspector succeeds while the IDE fails, the problem is likely in the config.yaml syntax or the IDE's specific transport implementation.5

### **Addressing Platform-Specific Constraints**

The execution of MCP servers can vary significantly across operating systems and environments.30 For instance, running Continue.dev in a WSL (Windows Subsystem for Linux) workspace can lead to issues where the extension attempts to invoke Windows-specific commands like cmd.exe inside the Linux environment.46

In such cases, ensuring the command field uses Linux-native shells like bash and setting the correct working directory (cwd) is essential.36 For remote SSH workspaces, Continue.dev must correctly resolve whether a server is "local" to the remote host or "local" to the user's desktop machine, which can often be clarified by using explicit IP addresses instead of localhost.36

## **Security Considerations for Local and Remote Transport**

The Model Context Protocol includes several security principles designed to protect the user's system and data.2

### **User Consent and Tool Authorization**

One of the core features of MCP is the requirement for user consent.3 When a model attempts to call a tool—especially one with destructive potential like filesystem modification—the host IDE should prompt the user for approval.2

In the YAML configuration, certain tools can be annotated with hints like destructiveHint to ensure the IDE provides appropriate warnings.2 For database servers, using the \--access-mode flag carefully is a key part of maintaining a secure environment.5

### **Preventing DNS Rebinding and Cross-Site Attacks**

For HTTP-based servers running on localhost, the protocol specification mandates the validation of the Origin header.15 This prevents malicious websites from using the user's browser as a proxy to interact with local MCP servers.15

Servers must also bind to the loopback address (127.0.0.1) rather than 0.0.0.0 unless explicitly intended for network access.15 If the server detects an invalid Origin or is accessed from a disallowed network interface, it must reject the connection with a 403 Forbidden.15

## **Synthesis of Configuration Best Practices**

Successfully integrating MCP servers into Continue.dev requires a disciplined approach to configuration management and an understanding of the underlying protocol requirements.3

### **Recommended Configuration Workflow**

1. **Define the Transport Type**: Use the type key to explicitly set stdio, sse, or streamable-http.5  
2. **Verify Path Suffixes**: Ensure that HTTP URLs include the correct path for the protocol (e.g., /mcp or /sse).6  
3. **Use Absolute Paths**: For local stdio servers, prefer absolute paths to runners like npx or uvx to avoid environment-related spawning errors.30  
4. **Nest Headers Correctly**: Custom headers for remote servers must be placed inside the requestOptions.headers object.24  
5. **Enable Agent Mode**: Remember that MCP tools are only available when Continue.dev is switched to Agent Mode.5

### **Strategic Outlook for MCP in IDEs**

The adoption of the Model Context Protocol is poised to transform the AI-assisted development experience.3 By providing a standardized way to connect models to the tools of production, MCP enables a future where AI agents can not only write code but also deploy applications, manage infrastructure, and interact with the full breadth of the developer's ecosystem.2

As the protocol matures and more tools adopt the modern Streamable HTTP transport, the friction of configuration will likely decrease.17 However, for the current generation of developers, a deep understanding of transport mechanics and YAML schema requirements remains the key to unlocking the full potential of Continue.dev's agentic capabilities.3

The "404 SSE error" serves as a reminder of the complexity involved in bridging the gap between local processes and network protocols.6 By correctly aligning the client's expectations with the server's capabilities, developers can build robust, context-rich environments that significantly enhance their productivity and the intelligence of their AI assistants.5

#### **Sources des citations**

1. Transports \- Model Context Protocol （MCP）, consulté le février 20, 2026, [https://modelcontextprotocol.info/specification/draft/basic/transports/](https://modelcontextprotocol.info/specification/draft/basic/transports/)  
2. Model Context Protocol (MCP) Server Development Guide … \- GitHub, consulté le février 20, 2026, [https://github.com/cyanheads/model-context-protocol-resources/blob/main/guides/mcp-server-development-guide.md](https://github.com/cyanheads/model-context-protocol-resources/blob/main/guides/mcp-server-development-guide.md)  
3. Continuum with MCP Server: A Deep Dive for AI Engineers, consulté le février 20, 2026, [https://skywork.ai/skypage/en/Continuum-with-MCP-Server-A-Deep-Dive-for-AI-Engineers/1971079151310204928](https://skywork.ai/skypage/en/Continuum-with-MCP-Server-A-Deep-Dive-for-AI-Engineers/1971079151310204928)  
4. Introduction to Configs | Continue Docs, consulté le février 20, 2026, [https://docs.continue.dev/mission-control/configs/intro](https://docs.continue.dev/mission-control/configs/intro)  
5. How to Set Up Model Context Protocol (MCP) in Continue, consulté le février 20, 2026, [https://docs.continue.dev/customize/deep-dives/mcp](https://docs.continue.dev/customize/deep-dives/mcp)  
6. Not Found Streamable HTTP error: Failed to open SSE stream: Not, consulté le février 20, 2026, [https://github.com/cline/cline/issues/7577](https://github.com/cline/cline/issues/7577)  
7. SSE Server drops client connection at 5 min. · Issue \#414 \- GitHub, consulté le février 20, 2026, [https://github.com/modelcontextprotocol/java-sdk/issues/414](https://github.com/modelcontextprotocol/java-sdk/issues/414)  
8. MCP over SSE not working in any of the clients in Self-Hosted \- GitHub, consulté le février 20, 2026, [https://github.com/gitroomhq/postiz-app/issues/984](https://github.com/gitroomhq/postiz-app/issues/984)  
9. How to MCP \- The Complete Guide to Understanding Model Context, consulté le février 20, 2026, [https://simplescraper.io/blog/how-to-mcp](https://simplescraper.io/blog/how-to-mcp)  
10. modelcontextprotocol/python-sdk \- GitHub, consulté le février 20, 2026, [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)  
11. Build an MCP server \- Model Context Protocol, consulté le février 20, 2026, [https://modelcontextprotocol.io/docs/develop/build-server](https://modelcontextprotocol.io/docs/develop/build-server)  
12. Deep Dive: MCP Servers with Streamable HTTP Transport \- Medium, consulté le février 20, 2026, [https://medium.com/@shsrams/deep-dive-mcp-servers-with-streamable-http-transport-0232f4bb225e](https://medium.com/@shsrams/deep-dive-mcp-servers-with-streamable-http-transport-0232f4bb225e)  
13. Support for Streamable HTTP MCP · Issue \#1453 \- GitHub, consulté le février 20, 2026, [https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1453](https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1453)  
14. 大语言模型（LLM）应用调用可观测MCP服务实现日志查询与分析, consulté le février 20, 2026, [https://help.aliyun.com/zh/sls/large-language-model-llm-application-calls-observable-mcp-service-to-implement-log-query-and-analysis](https://help.aliyun.com/zh/sls/large-language-model-llm-application-calls-observable-mcp-service-to-implement-log-query-and-analysis)  
15. Transports \- Model Context Protocol, consulté le février 20, 2026, [https://modelcontextprotocol.io/specification/2025-11-25/basic/transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)  
16. mcp-proxy \- NPM, consulté le février 20, 2026, [https://www.npmjs.com/package/mcp-proxy](https://www.npmjs.com/package/mcp-proxy)  
17. Why MCP Deprecated SSE and Went with Streamable HTTP \- fka.dev, consulté le février 20, 2026, [https://blog.fka.dev/blog/2025-06-06-why-mcp-deprecated-sse-and-go-with-streamable-http/?ref=blog.globalping.io](https://blog.fka.dev/blog/2025-06-06-why-mcp-deprecated-sse-and-go-with-streamable-http/?ref=blog.globalping.io)  
18. Fatal SSE error, not retrying: 404 Not Found from GET http ... \- GitHub, consulté le février 20, 2026, [https://github.com/alibaba/spring-ai-alibaba/issues/651](https://github.com/alibaba/spring-ai-alibaba/issues/651)  
19. MCP (Model Context Protocol) | Midway \- MidwayJS, consulté le février 20, 2026, [https://midwayjs.org/en/docs/next/extensions/mcp](https://midwayjs.org/en/docs/next/extensions/mcp)  
20. MCP Server Session Lost in Multi-Worker Environment \#520 \- GitHub, consulté le février 20, 2026, [https://github.com/modelcontextprotocol/python-sdk/issues/520](https://github.com/modelcontextprotocol/python-sdk/issues/520)  
21. \[BUG\] 404 for Invalid Session ID should trigger a new session \#8338, consulté le février 20, 2026, [https://github.com/anthropics/claude-code/issues/8338](https://github.com/anthropics/claude-code/issues/8338)  
22. How to Configure Continue, consulté le février 20, 2026, [https://docs.continue.dev/customize/deep-dives/configuration](https://docs.continue.dev/customize/deep-dives/configuration)  
23. Migrating Config to YAML | Continue Docs, consulté le février 20, 2026, [https://docs.continue.dev/reference/yaml-migration](https://docs.continue.dev/reference/yaml-migration)  
24. Document requestOptions.headers and transport-specific properties, consulté le février 20, 2026, [https://github.com/continuedev/continue/issues/7595](https://github.com/continuedev/continue/issues/7595)  
25. Client compatibility \- Stacklok Docs, consulté le février 20, 2026, [https://docs.stacklok.com/toolhive/reference/client-compatibility](https://docs.stacklok.com/toolhive/reference/client-compatibility)  
26. config.yaml Reference | Continue Docs, consulté le février 20, 2026, [https://docs.continue.dev/reference](https://docs.continue.dev/reference)  
27. FAQs | Continue Docs, consulté le février 20, 2026, [https://docs.continue.dev/faqs](https://docs.continue.dev/faqs)  
28. Build MCP Servers: Using FastMCP v2 \- Daniel Ecer, consulté le février 20, 2026, [https://danielecer.com/posts/mcp-fastmcp-v2/](https://danielecer.com/posts/mcp-fastmcp-v2/)  
29. Understanding MCP Recent Change Around HTTP+SSE, consulté le février 20, 2026, [https://blog.christianposta.com/ai/understanding-mcp-recent-change-around-http-sse/](https://blog.christianposta.com/ai/understanding-mcp-recent-change-around-http-sse/)  
30. Troubleshooting | Continue Docs, consulté le février 20, 2026, [https://docs.continue.dev/troubleshooting](https://docs.continue.dev/troubleshooting)  
31. Running Your Server \- FastMCP, consulté le février 20, 2026, [https://gofastmcp.com/deployment/running-server](https://gofastmcp.com/deployment/running-server)  
32. Building Remote MCP Servers: From Local Development to Cloud, consulté le février 20, 2026, [https://atalupadhyay.wordpress.com/2025/12/28/building-remote-mcp-servers-from-local-development-to-cloud-deployment/](https://atalupadhyay.wordpress.com/2025/12/28/building-remote-mcp-servers-from-local-development-to-cloud-deployment/)  
33. Continue Documentation MCP Server, consulté le février 20, 2026, [https://docs.continue.dev/reference/continue-mcp](https://docs.continue.dev/reference/continue-mcp)  
34. Project Configuration \- FastMCP, consulté le février 20, 2026, [https://gofastmcp.com/deployment/server-configuration](https://gofastmcp.com/deployment/server-configuration)  
35. connect-mcp-server \- Skill \- Smithery, consulté le février 20, 2026, [https://smithery.ai/skills/ronnycoding/connect-mcp-server](https://smithery.ai/skills/ronnycoding/connect-mcp-server)  
36. Problem MCP on remote server · Issue \#8732 · continuedev/continue, consulté le février 20, 2026, [https://github.com/continuedev/continue/issues/8732](https://github.com/continuedev/continue/issues/8732)  
37. Building a Secure MCP Server with Python, Cloud Run, and Gemini, consulté le février 20, 2026, [https://medium.com/@xbill999/building-a-secure-mcp-server-with-python-cloud-run-and-gemini-cli-71376aea7101](https://medium.com/@xbill999/building-a-secure-mcp-server-with-python-cloud-run-and-gemini-cli-71376aea7101)  
38. How to build and deploy a Model Context Protocol (MCP) server | Blog, consulté le février 20, 2026, [https://northflank.com/blog/how-to-build-and-deploy-a-model-context-protocol-mcp-server](https://northflank.com/blog/how-to-build-and-deploy-a-model-context-protocol-mcp-server)  
39. Authorization \- Model Context Protocol （MCP）, consulté le février 20, 2026, [https://modelcontextprotocol.info/specification/draft/basic/authorization/](https://modelcontextprotocol.info/specification/draft/basic/authorization/)  
40. MCP in Red Hat Developer Hub: Chat with your catalog, consulté le février 20, 2026, [https://developers.redhat.com/articles/2025/11/10/mcp-red-hat-developer-hub-chat-your-catalog](https://developers.redhat.com/articles/2025/11/10/mcp-red-hat-developer-hub-chat-your-catalog)  
41. Model Context Protocol (MCP) with Continue.dev | by Ashfaq \- Medium, consulté le février 20, 2026, [https://medium.com/@ashfaqbs/model-context-protocol-mcp-with-continue-dev-95f04752299a](https://medium.com/@ashfaqbs/model-context-protocol-mcp-with-continue-dev-95f04752299a)  
42. Building a Custom MCP Server in Continue: A Step-by-Step Guide, consulté le février 20, 2026, [https://dev.to/anita\_ihuman/building-a-custom-mcp-server-in-continue-a-step-by-step-guide-1p71](https://dev.to/anita_ihuman/building-a-custom-mcp-server-in-continue-a-step-by-step-guide-1p71)  
43. Configuring Models, Rules, and Tools \- Continue Docs, consulté le février 20, 2026, [https://docs.continue.dev/guides/configuring-models-rules-tools](https://docs.continue.dev/guides/configuring-models-rules-tools)  
44. MCP \- LibreChat, consulté le février 20, 2026, [https://www.librechat.ai/docs/features/mcp](https://www.librechat.ai/docs/features/mcp)  
45. Runalyze MCP Server \- LobeHub, consulté le février 20, 2026, [https://lobehub.com/mcp/floriankimmel-runalyze-mcp-server](https://lobehub.com/mcp/floriankimmel-runalyze-mcp-server)  
46. Continue VS Code extension fails to start MCP servers in WSL, consulté le février 20, 2026, [https://github.com/continuedev/continue/issues/9151](https://github.com/continuedev/continue/issues/9151)