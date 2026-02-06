# Test Suite

This directory contains the comprehensive test suite for the Agent Platform.

## Running Tests

### Run All Tests
```bash
cd agent_platform
python -m pytest tests/ -v
```

### Run Specific Test Module
```bash
python -m pytest tests/test_personas.py -v
python -m pytest tests/test_config.py -v
python -m pytest tests/test_agent.py -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=backend --cov-report=html
```

### Run Legacy E2E Tests
```bash
python tests/e2e_test.py
```

## Test Structure

```
tests/
├── conftest.py          # Pytest fixtures (shared across all tests)
├── test_config.py       # Configuration system tests
├── test_personas.py     # Persona loading, requirements, validation
├── test_providers.py    # LLM provider tests
├── test_agent.py        # AgentExecutor tests
├── test_startup.py      # Plugin init and startup sequence
├── test_tools.py        # Core and memory tools
├── test_plugins.py      # Plugin system tests
├── test_security.py     # RBAC and access control
├── test_gateway.py      # JSON-RPC gateway
├── test_memory.py       # Memory plugin functional tests
├── test_browser.py      # Browser plugin tests (requires Playwright)
├── test_network.py      # Network plugin tests
├── test_hooks.py        # Plugin hooks system
├── e2e_test.py          # Legacy end-to-end tests
└── sanity_check.py      # Quick health checks
```

## Test Categories

### Unit Tests
- `test_config.py` — Configuration loading and validation
- `test_providers.py` — LLM provider instantiation
- `test_tools.py` — Tool interface and schema validation

### Integration Tests
- `test_personas.py` — Persona system with requirements validation
- `test_agent.py` — AgentExecutor with plugin integration
- `test_startup.py` — Full startup sequence

### Functional Tests
- `test_memory.py` — Add/query memory operations
- `test_browser.py` — Browser automation (requires Playwright)
- `test_security.py` — RBAC enforcement

### End-to-End Tests
- `e2e_test.py` — Full platform workflow

## Fixtures

Key fixtures defined in `conftest.py`:

| Fixture | Scope | Description |
| :--- | :--- | :--- |
| `config` | session | Platform configuration |
| `initialized_plugins` | module | Plugin registry with loaded plugins |
| `core_plugin` | function | CorePlugin instance |
| `memory_plugin` | function | Initialized MemoryPlugin |
| `browser_plugin` | function | Initialized BrowserPlugin (skips if unavailable) |
| `agent_executor` | function | Fresh AgentExecutor instance |
| `enabled_plugins` | function | List of enabled plugin names |
| `enabled_personas` | function | List of enabled persona names |

## Skipping Tests

Some tests are automatically skipped when dependencies are not available:

- **Browser tests** — Skipped if Playwright not installed
- **Network tests** — Skipped if zeroconf/netifaces not installed
- **Provider tests** — Skipped if API keys not set

## Writing New Tests

1. Create a new file: `tests/test_<module>.py`
2. Import fixtures from `conftest.py`
3. Use `@pytest.mark.asyncio` for async tests
4. Group related tests in classes

Example:
```python
import pytest

class TestMyFeature:
    def test_basic(self, config):
        assert config is not None
    
    @pytest.mark.asyncio
    async def test_async(self, initialized_plugins):
        # Test with initialized plugins
        pass
```
