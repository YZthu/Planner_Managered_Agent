import sys
import os
import asyncio

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.config import config
    print("[PASS] Import config instance")
except ImportError as e:
    print(f"[FAIL] Import config instance: {e}")
    sys.exit(1)

try:
    from backend.providers import create_openai_provider, create_deepseek_provider
    print("[PASS] Import provider factory functions")
except ImportError as e:
    print(f"[FAIL] Import provider factory functions: {e}")
    sys.exit(1)

async def main():
    print("Starting Sanity Check...")
    
    # 1. Test Config Loading
    try:
        # Config is already loaded on import
        if config:
             print(f"[PASS] Config loaded successfully")
             print(f"       Log Level: {config.logging.level}")
        else:
             print(f"[FAIL] Config object is None")
    except Exception as e:
        print(f"[FAIL] Config check: {e}")
        return

    # 2. Test Provider Factory
    try:
        # Check if we can access the factory functions
        if callable(create_openai_provider):
             print(f"[PASS] create_openai_provider is callable")
        else:
             print(f"[FAIL] create_openai_provider is not callable")
    except Exception as e:
        print(f"[FAIL] Provider check: {e}")

    # 3. Import Check for Agent
    try:
        from backend.core.agent import AgentExecutor
        print(f"[PASS] AgentExecutor class imported")
        
        # Try to instantiate AgentExecutor
        # This will verify if the default provider can be initialized
        try:
             # Create a dummy provider or rely on default
             # If config has no keys, default provider might fail
             agent = AgentExecutor(session_id="test_sanity")
             print(f"[PASS] AgentExecutor instantiated successfully")
        except Exception as e:
             print(f"[WARN] AgentExecutor instantiation failed (possibly missing API keys): {e}")

    except ImportError as e:
        print(f"[FAIL] AgentExecutor import: {e}")
        
    # 4. API Key Check (Masked)
    print("\nAPI Key Status:")
    if config:
        print(f"  Gemini: {'[SET]' if config.llm.google_api_key else '[MISSING]'}")
        print(f"  DeepSeek: {'[SET]' if config.llm.deepseek_api_key else '[MISSING]'}")
        print(f"  OpenAI: {'[SET]' if config.llm.openai_api_key else '[MISSING]'}")

    print("Sanity Check Complete.")

if __name__ == "__main__":
    asyncio.run(main())
