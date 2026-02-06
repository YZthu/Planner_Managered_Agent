# Creating Personas

This guide explains how to create a new persona for the agent platform.

## What is a Persona?

A persona defines the agent's **identity** and **capabilities** for a specific task or role. Each persona has:
- A **system prompt** that shapes the agent's behavior
- **Requirements** that declare plugin and tool dependencies

## Quick Start

1. Create a new file: `backend/personas/<your_persona>.py`
2. Define `REQUIREMENTS` and `SYSTEM_PROMPT`
3. Add your persona to `config.yaml` under `personas.enabled`

## File Structure

```python
"""
<Persona Name>
Brief description of what this persona does.
"""

# Dependencies required by this persona
REQUIREMENTS = {
    "plugins": ["core"],             # Required plugins
    "core_tools": ["web_search"],    # Standalone tools from backend/tools/
    "plugin_tools": [],              # Tools bundled inside plugins
}

SYSTEM_PROMPT = """You are a <Role Description>.

## Core Responsibilities
1. First responsibility
2. Second responsibility

## Tool Usage
- **tool_name**: When and how to use this tool

## Guidelines
- Important behavior guideline
"""
```

## Requirements Fields

| Field | Description | Examples |
| :--- | :--- | :--- |
| `plugins` | Plugins that must be enabled | `["core"]`, `["memory", "browser"]` |
| `core_tools` | Standalone tools in `backend/tools/` | `["web_search", "spawn_subagent"]` |
| `plugin_tools` | Tools bundled inside plugins | `["add_memory", "browser_navigate"]` |

### Available Plugins & Tools

| Plugin | Tools Provided |
| :--- | :--- |
| `core` | `web_search`, `spawn_subagent` |
| `memory` | `add_memory`, `query_memory` |
| `browser` | `browser_navigate`, `browser_content` |
| `network` | Network-related tools |

## Enabling Your Persona

Add to `config.yaml`:

```yaml
personas:
  enabled:
    - default
    - your_new_persona  # Add here
```

## Validation

Personas are validated at:
1. **App startup** — Warnings for ineligible personas
2. **Runtime** — `set_persona()` falls back to `default` if requirements aren't met

Test your persona:
```python
from backend.personas import validate_persona_with_registry

result = validate_persona_with_registry("your_persona")
print(f"Eligible: {result.eligible}")
print(f"Missing: {result.missing_plugins}, {result.missing_core_tools}, {result.missing_plugin_tools}")
```

## Examples

See existing personas:
- `default.py` — General assistant with subagent support
- `deep_research.py` — Research agent with browser tools
- `memory_manager.py` — Knowledge management with memory plugin
- `coder.py` — Software engineering focus
- `subagent.py` — Minimal persona for spawned subagents
