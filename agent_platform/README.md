# Agent Platform

A multi-agent platform with LLM-as-Planner architecture, inspired by OpenClaw patterns.

## Features

- 🤖 **LLM-as-Planner Architecture**: The LLM dynamically spawns subagents for parallel work
- 🔄 **Multi-Agent Orchestration**: Up to 4 concurrent subagents with lane-based queue
- 🔍 **Web Search**: Built-in web search tool for information retrieval
- 🌐 **Real-time Updates**: WebSocket-powered live status updates
- 🎨 **Modern UI**: Dark theme with smooth animations

## Quick Start

### 1. Install Dependencies

```bash
cd agent_platform
pip install -r requirements.txt
```

### 2. Configure API Keys

Ensure your `.env` file in the project root has:

```env
GOOGLE_API_KEY=your_google_api_key
DEEPSEEK_API_KEY=your_deepseek_api_key  # Optional
```

### 3. Run the Server

```bash
cd agent_platform
python main.py
```

### 4. Open the UI

Navigate to `http://localhost:8000` in your browser.

### 5. Monitor Logs and Traces (Optional)

See [Observability Guide](docs/OBSERVABILITY.md) for details on simplified logging (`agent.log`), deep tracing (`traces/`), and timezone configuration.

### 6. CLI Chat Interface (Optional)

For faster backend testing, bypass the UI with the CLI chat tool:
```bash
python cli_chat.py
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Platform                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐│
│  │                   FastAPI Backend                        ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐  ││
│  │  │   Routes    │→ │   Agent     │→ │   Providers    │  ││
│  │  │  WebSocket  │  │  Executor   │  │ Gemini/DeepSeek│  ││
│  │  └─────────────┘  └─────────────┘  └────────────────┘  ││
│  │                         ↓                               ││
│  │  ┌─────────────────────────────────────────────────────┐││
│  │  │              Multi-Agent Core                       │││
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │││
│  │  │  │   Registry   │  │    Queue     │  │   Tools   │ │││
│  │  │  │  (SQLite)    │  │ (Concurrent) │  │(Web/Spawn)│ │││
│  │  │  └──────────────┘  └──────────────┘  └───────────┘ │││
│  │  └─────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────┘│
│                          ↑                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              Modern Web Frontend                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │  │
│  │  │   Chat   │  │ Subagent │  │  Real-time Updates   │ │  │
│  │  │Interface │  │  Panel   │  │   (WebSocket)        │ │  │
│  │  └──────────┘  └──────────┘  └──────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve frontend |
| `/api/chat` | POST | Send message, get response |
| `/api/status` | GET | Platform status |
| `/api/subagents/{id}` | GET | Subagent status for session |
| `/api/clear/{id}` | POST | Clear session history |
| `/api/ws/{id}` | WebSocket | Real-time updates |

## Example Prompts

- "Research the latest AI news and summarize in 3 bullet points"
- "Search for Python 3.13 features and explain the top 5"
- "What are the best practices for building multi-agent systems?"

## Configuration

Edit `backend/config.py` to customize:

- `max_concurrent_subagents`: Number of parallel subagents (default: 4)
- `subagent_timeout_seconds`: Subagent timeout (default: 120)
- `default_provider`: LLM provider ("gemini" or "deepseek")

## License

MIT
