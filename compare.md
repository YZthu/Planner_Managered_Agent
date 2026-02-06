# Feature Comparison: Agent Platform vs OpenClaw

This document provides a detailed technical comparison between the current **Agent Platform** and the reference **OpenClaw** architecture. It identifies gaps to guide future upgrades.

## Summary Status

| Feature Area | Status | Notes |
| :--- | :--- | :--- |
| **Agent Logic** | ✅ Parity | Thinking steps, Context Window, Tool use. |
| **Communication** | ✅ Parity | JSON-RPC 2.0 Gateway implemented. |
| **Extensibility** | ⚠️ Partial | Plugin Registry implemented; missing deep Hooks. |
| **Input Handling** | ✅ Parity | Message Debouncing implemented. |
| **Memory/RAG** | ❌ Missing | No vector database or long-term recall. |
| **Browser Control** | ❌ Missing | No Playwright/Sandbox integration. |
| **Channels** | ❌ Missing | Web-only; missing Discord/Slack/etc. |
| **Infrastructure** | ❌ Missing | No Tailscale/Bonjour; Localhost only. |
| **Security** | ❌ Missing | No Role-Based Access Control (RBAC). |

---

## Detailed Feature Breakdown

### 1. Memory & Knowledge (Major Gap)
**Key Function**: Long-term storage and retrieval of information using semantic search.
**Problem Solved**: Agents "forget" interactions outside the immediate context window. RAG allow agents to recall facts from days ago or query large document sets.
**OpenClaw**:
-   **Implementation**: `src/memory`
-   **Tech**: SQLite with Vector Extensions (`sqlite-vec`), dynamic embeddings (Gemini/OpenAI).
-   **Features**: Background indexing, atomic re-indexing, hybrid search.
**Agent Platform**:
-   **Current**: In-memory list (`_message_history`), lost on restart/session clear.
-   **Gap**: Need to implement a `MemoryManager` with a Vector DB backend (e.g., ChromaDB or SQLite-vec).

### 2. Browser Sandboxing (Major Gap)
**Key Function**: Ability to open, view, and interact with real websites in a controlled environment.
**Problem Solved**: "Web Search" tools only return text snippets. They cannot click buttons, fill forms, or see dynamic JS content.
**OpenClaw**:
-   **Implementation**: `src/browser`
-   **Tech**: Playwright (Headless Chrome), CDP (Chrome DevTools Protocol).
-   **Features**: `control-service` for remote browser driving, screenshots, session persistence.
**Agent Platform**:
-   **Current**: `WebSearchTool` (Text-based API search).
-   **Gap**: Need a `BrowserPlugin` that wraps Playwright/Selenium for specialized subagents.

### 3. Event Hooks & Lifecycle
**Key Function**: Trigger code execution at specific agent lifecycle events (Start, Stop, Error, Message Received).
**Problem Solved**: Enables complex plugins like "Email Watcher" or "Personality Injector" without modifying core agent code.
**OpenClaw**:
-   **Implementation**: `src/hooks`
-   **Features**: Global event bus, external triggers (Gmail watcher), soul/personality injection.
**Agent Platform**:
-   **Current**: Basic callbacks (`_on_event`) for UI streaming only.
-   **Gap**: Need a generalized `HookSystem` (e.g., `on_agent_start`, `on_tool_result`) within the Plugin Architecture.

### 4. Multi-Channel Support
**Key Function**: Interface with users on platforms other than the custom Web UI.
**Problem Solved**: Users want to talk to agents via Discord, Slack, SMS, etc.
**OpenClaw**:
-   **Implementation**: `src/discord`, `src/slack`, `src/telegram`.
-   **Features**: Adapters for various messaging platforms.
**Agent Platform**:
-   **Current**: REST/WebSocket API only.
-   **Gap**: Need `ChannelAdapters` in the Gateway or as Plugins to bridge external messaging protocols.

### 6. Infrastructure & Deployment (Major Gap)
**Key Function**: Service discovery, secure networking, and update management.
**Problem Solved**: Deploying agents securely across different networks and devices without exposing ports; self-updating capabilities.
**OpenClaw**:
-   **Implementation**: `src/infra`
-   **Tech**: Tailscale (Mesh Networking), Bonjour (mDNS Discovery), TLS/ACME.
-   **Features**:
    -   `tailscale.ts`: Built-in VPN/Mesh support for secure remote access.
    -   `bonjour.ts`: Local network discovery.
    -   `update-runner.ts`: Self-update mechanism.
**Agent Platform**:
-   **Current**: Basic localhost server.
-   **Gap**: No built-in secure networking or discovery. Agents are hard to access remotely without VPN setup.

### 7. Security & Auth (Major Gap)
**Key Function**: Granular permission control and secure identity.
**Problem Solved**: Controlling who can access the agent and what commands they can run.
**OpenClaw**:
-   **Implementation**: `src/security`, `src/commands`
-   **Features**:
    -   `command-gating.ts`: Fine-grained permissions per command.
    -   `sender-identity.ts`: Verifies who is sending the message.
    -   `audit.ts`: Detailed security logging.
**Agent Platform**:
-   **Current**: No auth or basic API key (if configured in Gateway, but generic).
-   **Gap**: Need a `SecurityModule` for Role-Based Access Control (RBAC) and Audit Logging.

### 8. System Integration & Daemon
**Key Function**: OS-level integration and background persistence.
**Problem Solved**: Agents running as system services, interacting with clipboard/screens.
**OpenClaw**:
-   **Implementation**: `src/daemon`, `src/infra/clipboard.ts`
-   **Features**: Systemd/Launchd integration, clipboard access, system presence detection.
**Agent Platform**:
-   **Current**: Simple Python script.
-   **Gap**: Helper scripts for system service installation and OS-level integrations.

### 9. Module Inventory & Feature Analysis

| Module (src/) | Key Features | Agent Platform Status | Importance (1-10) |
| :--- | :--- | :--- | :--- |
| **memory/** | SQLite Vector RAG, BG Indexing | ❌ Missing | **10** (Critical) |
| **browser/** | Playwright, Control Service, CDP | ❌ Missing | **9** (High) |
| **hooks/** | Global Event Bus, External Triggers | ⚠️ Partial (Basic Events) | **7** (Medium) |
| **cron/** | Job Scheduling, Delivery Reliability | ❌ Missing | **5** (Medium) |
| **daemon/** | Systemd/Launchd/Schtasks wrapper | ❌ Missing | **4** (Low) |
| **infra/** | Tailscale, Bonjour, TLS, Updates | ❌ Missing | **8** (High - Enterprise) |
| **security/** | Command Gating, Audit Logs | ❌ Missing | **6** (Medium) |
| **channels/** | Abstract Channel Logic | ❌ Missing | **4** (Low) |
| **discord/** | Discord Bot Adapter | ❌ Missing | **3** (Low) |
| **slack/** | Slack Bot Adapter | ❌ Missing | **3** (Low) |
| **commands/** | CLI/Chat Command Handling | ⚠️ Partial (Implicit) | **5** (Medium) |

---

## Upgrade Roadmap (Recommendation)

Based on the value/complexity ratio, here is the prioritized list:

1.  **Memory System (RAG)**: High Value (Score: 10). Enables "smart" agents that remember the user.
    *   *Plan*: Integrate `chromadb` or `lancedb` into a new `MemoryPlugin`.
2.  **Browser Control**: High Value (Score: 9). Enables "Action" agents (book flights, scrape data).
    *   *Plan*: Build a `BrowserPlugin` using `playwright`.
3.  **Infrastructure (Remote Access)**: High Value (Score: 8).
    *   *Plan*: Add `NetworkPlugin` (Tailscale/Bonjour) for easy remote access.
4.  **Hooks System**: Medium Value (Score: 7).
    *   *Plan*: Expand `plugin_registry` to support event subscriptions.
5.  **Security (RBAC)**: Medium Value (Score: 6).
    *   *Plan*: Add `AuthMiddleware` to Gateway.
