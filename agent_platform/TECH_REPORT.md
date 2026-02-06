# Agent Platform - Technical Report

A modular, multi-agent platform implementing the **LLM-as-Planner** architecture pattern with support for multiple LLM providers, dynamic persona switching, plugin-based tool systems, and hierarchical subagent coordination.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [LLM Providers](#llm-providers)
4. [Plugin System](#plugin-system)
5. [Persona System](#persona-system)
6. [Tools](#tools)
7. [API Layer](#api-layer)
8. [Security](#security)
9. [Configuration](#configuration)
10. [Directory Structure](#directory-structure)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Server                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ REST Routes │  │  WebSocket  │  │   JSON-RPC Gateway  │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼───────────────┼───────────────────┼───────────────┘
          │               │                    │
          ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent Executor                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              LLM-as-Planner Loop                    │    │
│  │  User → LLM → Tool Calls → Execute → LLM → Response │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Personas   │  │   Providers  │  │  Plugin Registry │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          │               │                    │
          ▼               ▼                    ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│  System Prompts │ │  Gemini/DeepSeek│ │  Core/Memory/Browser│
│  (Personalities)│ │  /OpenAI APIs   │ │  /Network Plugins   │
└─────────────────┘ └─────────────────┘ └─────────────────────┘
```

### Design Principles

| Principle | Implementation |
| :--- | :--- |
| **Modularity** | Plugin-based tools, swappable providers, configurable personas |
| **Extensibility** | Easy to add new LLM providers, tools, and personas |
| **Configuration-Driven** | YAML config + `.env` for secrets |
| **Dependency Validation** | Personas declare requirements; validated at startup and runtime |

---

## Core Components

### AgentExecutor (`backend/core/agent.py`)

The central execution engine implementing the **LLM-as-Planner** pattern.

**Key Methods:**
| Method | Description |
| :--- | :--- |
| `run(user_message, max_iterations)` | Main entry point for processing user messages |
| `set_persona(persona)` | Switching agent personality with validation |
| `set_provider(provider_name)` | Hot-swap LLM providers at runtime |
| `run_subagent(task, run_id)` | Execute as a child agent for parallel tasks |
| `clear_history()` | Reset conversation context |

**Execution Flow:**
```
1. Receive user message
2. Build conversation history with system prompt
3. Send to LLM provider
4. If LLM returns tool calls:
   a. Execute tools in parallel (with RBAC checks)
   b. Append tool results to history
   c. Loop back to step 3
5. Return final text response
```

**Configuration:**
```yaml
agent:
  max_concurrent_subagents: 4
  max_tool_calls_per_turn: 10
  max_history_messages: 10
  enable_thinking: true
  subagent_timeout_seconds: 60
```

### Plugin Registry (`backend/core/plugins.py`)

Singleton registry for managing plugin lifecycle.

**Features:**
- Dynamic plugin registration
- Async initialization with `on_load()` / `on_shutdown()` hooks
- Tool aggregation across all plugins
- Event hook system for inter-plugin communication

**API:**
```python
plugin_registry.register_plugin(CorePlugin())
await plugin_registry.initialize()
tools = plugin_registry.get_all_tools()
tool_names = plugin_registry.get_available_tool_names()
```

### Subagent System (`backend/core/registry.py`, `queue.py`)

Hierarchical multi-agent coordination for parallel task execution.

**Components:**
- **Registry** — SQLite-backed tracking of subagent runs
- **Queue** — Async task queue with status tracking
- **SpawnSubAgentTool** — Tool for the main agent to spawn children

**States:** `pending` → `running` → `completed` / `failed`

---

## LLM Providers

### Provider Architecture (`backend/providers/`)

All providers implement `BaseLLMProvider`:

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        ...
    ) -> LLMResponse
```

### Supported Providers

| Provider | Model | Features | Config Key |
| :--- | :--- | :--- | :--- |
| **Gemini** | `gemini-2.0-flash-exp` | Native tool calling, search grounding | `llm.gemini` |
| **DeepSeek** | `deepseek-chat` | OpenAI-compatible, reasoning | `llm.deepseek` |
| **OpenAI** | `gpt-4o` | Industry standard, function calling | `llm.openai` |

### OpenAI-Compatible Provider (`backend/providers/openai_compatible.py`)

Unified implementation for all OpenAI-format APIs:
- Automatic tool call parsing
- Streaming support
- Configurable base URL for custom endpoints

**Factory Functions:**
```python
from backend.providers import create_deepseek_provider, create_openai_provider

provider = create_deepseek_provider()  # Uses config from YAML
```

---

## Plugin System

### Plugin Types (`backend/plugins/`)

| Plugin | Tools Provided | Dependencies |
| :--- | :--- | :--- |
| **CorePlugin** | `web_search`, `spawn_subagent` | None |
| **MemoryPlugin** | `add_memory`, `query_memory` | ChromaDB |
| **BrowserPlugin** | `browser_navigate`, `browser_content` | Playwright |
| **NetworkPlugin** | Discovery, remote access | zeroconf, netifaces |

### Creating a Plugin

```python
class MyPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "my_plugin"
    
    async def on_load(self):
        # Initialize resources
        pass
    
    def get_tools(self) -> List[BaseTool]:
        return [MyTool()]
```

### Memory Plugin (RAG)

ChromaDB-backed persistent memory:
- **add_memory** — Store information with metadata
- **query_memory** — Semantic search retrieval

```yaml
memory:
  enabled: true
  collection_name: "agent_memory"
  persist_directory: "./data/memory"
```

### Browser Plugin

Playwright-based web automation:
- Headless Chrome control
- DOM content extraction
- Navigation and interaction

```yaml
browser:
  headless: true
  viewport: { width: 1280, height: 720 }
```

---

## Persona System

### Overview (`backend/personas/`)

Personas define agent identity through:
1. **System Prompt** — Behavioral instructions
2. **Requirements** — Plugin and tool dependencies

### Persona Structure

```python
REQUIREMENTS = {
    "plugins": ["core", "memory"],      # Required plugins
    "core_tools": ["web_search"],       # Standalone tools
    "plugin_tools": ["add_memory"],     # Plugin-bundled tools
}

SYSTEM_PROMPT = """You are a specialized agent..."""
```

### Available Personas

| Persona | Purpose | Key Requirements |
| :--- | :--- | :--- |
| `default` | General assistant | `core` plugin |
| `deep_research` | Exhaustive research | `browser` plugin |
| `coder` | Software engineering | `spawn_subagent` tool |
| `memory_manager` | Knowledge management | `memory` plugin |
| `subagent` | Task worker (minimal) | None |

### Validation System

Personas are validated at:
1. **Startup** — All enabled personas checked
2. **Runtime** — `set_persona()` validates before switching

```python
from backend.personas import validate_persona_with_registry

result = validate_persona_with_registry("deep_research")
# result.eligible, result.missing_plugins, result.missing_core_tools, result.missing_plugin_tools
```

---

## Tools

### Tool Architecture (`backend/tools/`)

All tools extend `BaseTool`:

```python
class BaseTool(ABC):
    @property
    def name(self) -> str: ...
    
    @property
    def description(self) -> str: ...
    
    @property
    def parameters(self) -> Dict: ...  # JSON Schema
    
    async def execute(self, **kwargs) -> ToolResult: ...
```

### Core Tools

| Tool | Location | Description |
| :--- | :--- | :--- |
| `web_search` | `tools/web_search.py` | Google Custom Search API |
| `spawn_subagent` | `tools/spawn_subagent.py` | Create child agents for parallel tasks |

### Tool Execution

```python
result = await tool.execute(**arguments)
# result.success, result.output, result.error
```

---

## API Layer

### REST Endpoints (`backend/api/routes.py`)

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/chat` | POST | Send message, get response |
| `/api/chat/stream` | POST | SSE streaming response |
| `/api/session/{id}` | DELETE | Clear session history |
| `/api/subagents` | GET | List subagent runs |
| `/api/personas` | GET | List available personas |
| `/api/config` | GET | Get current configuration |

### WebSocket (`backend/api/websocket.py`)

Real-time bidirectional communication:
```javascript
ws.send(JSON.stringify({ type: "chat", message: "Hello" }))
ws.onmessage = (event) => { /* streaming updates */ }
```

### JSON-RPC Gateway (`backend/api/gateway.py`)

Structured RPC interface:
```json
{ "method": "chat.send", "params": { "message": "..." }, "id": "1" }
```

**Registered Methods:**
- `chat.send` — Send message
- `session.clear` — Clear history
- `agent.stop` — Interrupt execution
- `system.ping` — Health check

---

## Security

### Role-Based Access Control (`backend/security/`)

Tool execution is gated by RBAC:

```yaml
security:
  enabled: true
  default_role: "user"
  roles:
    admin:
      allow: ["*"]
    user:
      allow: ["*"]
      deny: ["shell_execute", "file_delete"]
    guest:
      allow: ["web_search", "query_memory"]
      deny: ["*"]
```

**Enforcement:**
```python
from backend.security import AccessControl

access = AccessControl(role="user")
if access.can_use_tool("shell_execute"):
    # Execute
```

---

## Configuration

### config.yaml

Central configuration file:

```yaml
llm:
  default_provider: "gemini"
  gemini:
    model: "gemini-2.0-flash-exp"
    temperature: 0.7
  deepseek:
    model: "deepseek-chat"
  openai:
    model: "gpt-4o"

agent:
  max_concurrent_subagents: 4
  enable_thinking: true

plugins:
  enabled: ["core", "memory", "browser", "network"]

personas:
  enabled: ["default", "deep_research", "coder", "memory_manager"]

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins: ["*"]
```

### Environment Variables (.env)

API keys (kept separate for security):
```
GOOGLE_API_KEY=...
DEEPSEEK_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_CSE_ID=...      # Custom Search Engine ID
GOOGLE_CSE_API_KEY=... # Custom Search API Key
```

### Configuration Classes (`backend/config.py`)

Pydantic models with validation:
- `LLMConfig` — Provider settings
- `AgentConfig` — Execution parameters
- `PluginsConfig` / `PersonasConfig` — Enabled modules
- `SecurityConfig` — RBAC rules

---

## Directory Structure

```
agent_platform/
├── main.py                    # FastAPI entry point
├── config.yaml                # Configuration file
├── backend/
│   ├── api/
│   │   ├── routes.py          # REST endpoints
│   │   ├── websocket.py       # WebSocket handler
│   │   └── gateway.py         # JSON-RPC gateway
│   ├── core/
│   │   ├── agent.py           # AgentExecutor
│   │   ├── plugins.py         # Plugin registry
│   │   ├── registry.py        # Subagent tracking (SQLite)
│   │   ├── queue.py           # Async task queue
│   │   └── startup.py         # Initialization functions
│   ├── personas/
│   │   ├── README.md          # Persona creation guide
│   │   ├── __init__.py        # Persona loader + validator
│   │   ├── default.py
│   │   ├── deep_research.py
│   │   ├── coder.py
│   │   ├── memory_manager.py
│   │   └── subagent.py
│   ├── plugins/
│   │   ├── core.py            # CorePlugin
│   │   ├── memory.py          # MemoryPlugin (ChromaDB)
│   │   ├── browser.py         # BrowserPlugin (Playwright)
│   │   └── network.py         # NetworkPlugin (mDNS)
│   ├── providers/
│   │   ├── base.py            # BaseLLMProvider
│   │   ├── gemini.py          # Gemini provider
│   │   └── openai_compatible.py # DeepSeek/OpenAI
│   ├── prompts/
│   │   └── system_prompts.py  # Legacy prompts
│   ├── security/
│   │   └── access_control.py  # RBAC implementation
│   ├── tools/
│   │   ├── base.py            # BaseTool
│   │   ├── web_search.py
│   │   └── spawn_subagent.py
│   └── config.py              # Configuration loader
├── frontend/                  # Web UI (if present)
├── tests/
│   ├── e2e_test.py            # End-to-end tests
│   └── sanity_check.py        # Quick health checks
└── data/
    └── memory/                # ChromaDB persistence
```

---

## Summary

The Agent Platform provides a production-ready foundation for building AI agents with:

- **Multi-provider LLM support** (Gemini, DeepSeek, OpenAI)
- **Plugin architecture** for extensible tools
- **Persona system** with dependency validation
- **Hierarchical multi-agent** coordination
- **RAG memory** with ChromaDB
- **Role-based security** for tool access
- **Multiple API interfaces** (REST, WebSocket, JSON-RPC)
- **Configuration-driven** design for easy customization

Built with Python 3.11+, FastAPI, Pydantic, and async/await throughout.
