# Integration Tests

Integration tests and utility scripts that require external dependencies or a running server.

## Test Files

| File | Description | Requirements |
|------|-------------|--------------|
| `e2e_test.py` | Full E2E test of personas and plugins | ChromaDB, Playwright |
| `test_server_debounce.py` | Server debounce integration test | Running server on :8000 |
| `sanity_check.py` | Quick import validation and API key check | None |

## Running Tests

```bash
# Quick sanity check (no external deps)
python tests/integration/sanity_check.py

# Full E2E test (requires ChromaDB, Playwright)
python tests/integration/e2e_test.py

# Server integration test (requires running server)
# Terminal 1:
python main.py
# Terminal 2:
python tests/integration/test_server_debounce.py
```

## vs Unit Tests

| Type | Location | Run with | Speed |
|------|----------|----------|-------|
| Unit tests | `tests/test_*.py` | `pytest tests/` | Fast (~1s) |
| Integration | `tests/integration/` | `python <script>` | Slow |

Unit tests use mocks and run in CI. Integration tests require real services.
