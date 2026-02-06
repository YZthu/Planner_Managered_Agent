# Examples

Demo scripts and interactive examples for the Agent Platform.

## Available Examples

| Script | Description | Requirements |
|--------|-------------|--------------|
| `demo_live_features.py` | Demo of context window, thinking, and tool timeouts | API keys |
| `demo_deep_research.py` | Demo of deep research persona with browser | API keys, Playwright |

## Running Examples

```bash
# Live features demo (context window, thinking, timeouts)
python examples/demo_live_features.py

# Deep research demo (uses browser tools)
python examples/demo_deep_research.py
```

## Notes

- These scripts make **real API calls** and require valid API keys in `.env`
- `demo_deep_research.py` uses mocked browser responses for testing without Playwright
- Output is printed to console with emoji indicators for events
