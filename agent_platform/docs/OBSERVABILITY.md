# Observability Guide

The Agent Platform includes a comprehensive observability stack designed for both high-level monitoring and deep debugging.

## 1. Simplified Logging (`agent.log`)

High-level application events are logged to `logs/agent.log` in a human-readable JSON format.

- **Purpose**: Quick status checks (Is the agent running? Did the tool succeed?).
- **Location**: `./logs/agent.log` (rotated daily).
- **Format**: JSON lines (NDJSON).
- **Key Events**:
  - `Session Start/End`
  - `LLM Message Processing`
  - `Tool Execution (Success/Failure)`
  - `Startup System Checks`

**Example Entry:**
```json
{
  "timestamp": "2026-02-06T16:37:54.271802-08:00",
  "level": "INFO",
  "subsystem": "agent",
  "message": "Tool 'web_search' executed. Success: True"
}
```

## 2. Agent Tracing (`traces/`)

For detailed debugging of agent logic, we provide a full event trace system.

- **Purpose**: Deep analysis of agent reasoning, prompt inputs, and raw tool outputs.
- **Location**: `./traces/session-{session_id}/events.jsonl`.
- **Format**: JSON Lines.
- **Trace Events**:
  - `session.start` / `session.end`
  - `turn.start` / `turn.end`
  - `llm.request` (Full prompt + system instructions)
  - `llm.response` (Raw model output + thinking)
  - `tool.call` / `tool.result`

## 3. Configuration

### Timezone
You can configure the timezone used for all log timestamps in `config.yaml`.

```yaml
logging:
  timezone: "America/Los_Angeles"  # Uses standard IANA timezones
  level: "INFO"
  console_colors: true
```

### Trace Settings
Tracing is enabled by default but can be tuned in `config.yaml`:

```yaml
agent_trace:
  enabled: true
  trace_dir: "./traces"
  include_thinking: true  # Log internal reasoning
```

## 4. CLI Chat Interface

To test the backend without the web UI, use the provided CLI tool. It integrates fully with the logging system, displaying simplified logs in real-time.

```bash
# Start interactive chat
python cli_chat.py
```
