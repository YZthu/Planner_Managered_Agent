# Agent Trace System

A dedicated JSONL-based tracing system for multi-turn LLM agent behavior analysis.

## Overview

The Agent Trace system captures structured events for debugging and analyzing agent behavior:
- Session lifecycle (start/end)
- Turn lifecycle (user input → agent output)
- LLM calls (request/response, tokens, latency)
- Tool executions (call/result)
- Thinking/reasoning (for o1/Claude extended thinking)

## Quick Start

```python
from backend.core.agent_trace import trace_session, trace_turn

# Simple usage with context managers
with trace_session(session_id="user-123") as session:
    with trace_turn(session, user_input="Hello!"):
        # Your agent logic here
        session.log_llm_request(model="gpt-4", messages=[...])
        session.log_llm_response(model="gpt-4", content="Hi!", tokens={...})
```

## Trace Events

| Event Type | When | Data Captured |
|------------|------|---------------|
| `session.start` | Session begins | metadata |
| `session.end` | Session ends | outcome, duration, total_turns |
| `turn.start` | User sends message | user_input |
| `turn.end` | Agent responds | output |
| `llm.request` | Before LLM call | model, messages, tools |
| `llm.response` | After LLM call | content, tokens, duration, thinking |
| `tool.call` | Tool invoked | tool_name, args |
| `tool.result` | Tool returns | success, result, duration |
| `thinking` | Reasoning step | content, stage, tokens |

## Output Format

```
traces/
└── session-{session_id}/
    ├── metadata.json      # Session metadata
    └── events.jsonl       # All events (one JSON per line)
```

### Sample Event (JSONL)
```json
{
  "timestamp": "2026-02-06T22:10:00.123Z",
  "event_type": "llm.response",
  "session_id": "user-123",
  "run_id": "run-abc123def456",
  "turn": 1,
  "duration_ms": 1500.0,
  "data": {
    "model": "gpt-4",
    "content": "Hello! How can I help?",
    "tokens": {"prompt": 100, "completion": 20}
  }
}
```

## Configuration

```yaml
# config.yaml
agent_trace:
  enabled: true
  trace_dir: "./traces"
  sample_rate: 1.0        # 1.0 = 100%, 0.1 = 10%
  include_messages: true   # Log full message content
  include_thinking: true   # Log thinking/reasoning
  max_content_length: 10000
```

## Analysis Examples

```bash
# Find all events for a session
cat traces/session-user-123/events.jsonl | jq .

# Find slowest LLM calls
find traces -name "events.jsonl" -exec cat {} \; | \
  jq 'select(.event_type=="llm.response") | {session: .session_id, ms: .duration_ms}' | \
  jq -s 'sort_by(.ms) | reverse | .[0:10]'

# Tool failure rate
find traces -name "events.jsonl" -exec cat {} \; | \
  jq 'select(.event_type=="tool.result")' | \
  jq -s 'group_by(.data.success) | map({success: .[0].data.success, count: length})'

# Token usage by model
find traces -name "events.jsonl" -exec cat {} \; | \
  jq 'select(.event_type=="llm.response" and .data.tokens) | 
      {model: .data.model, tokens: (.data.tokens.prompt + .data.tokens.completion)}' | \
  jq -s 'group_by(.model) | map({model: .[0].model, total: (map(.tokens) | add)})'

# Search for specific run
grep "run-abc123" traces/*/events.jsonl
```

---

## Upgrade Path

### Tier 1: Current (Custom JSONL)
- ✅ Zero dependencies
- ✅ Grep-friendly
- ✅ Python analysis with pandas
- ❌ No web UI
- ❌ No real-time alerts

### Tier 2: LangFuse (Recommended Next Step)

[LangFuse](https://langfuse.com) is an open-source LLM observability platform.

**Why LangFuse:**
- Open-source, self-hostable
- Web UI for trace visualization
- Session-level analytics
- OpenTelemetry backend support
- Easy migration from custom traces

**Integration:**
```python
from langfuse import Langfuse

langfuse = Langfuse()

# Replace our trace calls with LangFuse
trace = langfuse.trace(name="agent-session", session_id="user-123")
span = trace.span(name="llm-call", input=messages)
span.end(output=response, metadata={"tokens": tokens})
```

**Migration checklist:**
1. Install: `pip install langfuse`
2. Create adapter: wrap SessionTrace methods to also send to LangFuse
3. Dual-write during transition (JSONL + LangFuse)
4. Disable JSONL after validation

### Tier 3: OpenTelemetry (Enterprise Scale)

For distributed tracing across multiple services.

**When to use:**
- Multi-service architecture
- Need to correlate agent traces with backend services
- Enterprise observability stack (Jaeger, Grafana Tempo)

**Integration:**
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

tracer = trace.get_tracer("agent-platform")

with tracer.start_as_current_span("agent-session") as span:
    span.set_attribute("session_id", session_id)
    # ... agent logic
```

### Comparison

| Feature | JSONL (Current) | LangFuse | OpenTelemetry |
|---------|-----------------|----------|---------------|
| Setup | None | Easy | Complex |
| Web UI | ❌ | ✅ | Needs Jaeger/Tempo |
| Self-hosted | ✅ | ✅ | ✅ |
| Cost tracking | Manual | ✅ Built-in | Manual |
| Multi-service | ❌ | Limited | ✅ |
| Vendor lock-in | None | Low | None |

---

## Files

| File | Purpose |
|------|---------|
| `backend/core/agent_trace.py` | Core tracing module |
| `tests/test_agent_trace.py` | Unit tests |
| `docs/agent_trace.md` | This documentation |
