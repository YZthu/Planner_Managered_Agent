#!/usr/bin/env python3
"""
CLI Chat Interface for Agent Platform
Allows interacting with the agent via terminal, useful for backend testing.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from backend.config import config
from backend.core.logging import configure_logging, get_logger
from backend.core.registry import registry
from backend.core.startup import initialize_plugins
from backend.core.agent import AgentExecutor

async def main():
    # 1. Configure Logging
    # We want console output to be visible
    # 1. Configure Logging
    # We want console output to be visible
    configure_logging(
        log_dir=config.logging.log_dir,
        log_level=config.logging.level,
        max_days=config.logging.max_days,
        json_format=config.logging.json_format,
        console_colors=config.logging.console_colors,
        timezone=config.logging.timezone
    )
    logger = get_logger("cli")
    
    print("\n🚀 Starting Agent CLI...")
    
    # 2. Initialize System
    await registry.initialize()
    await initialize_plugins()
    
    # 3. Create Agent
    logger.info("Initializing AgentExecutor...")
    agent = AgentExecutor(
        session_id="cli_session",
        is_subagent=False
    )
    
    print("\n✅ Agent ready! Type '/quit' to exit.\n")
    print("="*60)
    
    # 4. Chat Loop
    while True:
        try:
            user_input = input("\n👤 \033[1mYou\033[0m: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['/quit', '/exit', 'exit', 'quit']:
                print("👋 Goodbye!")
                break
            
            print("🤖 \033[1mAgent\033[0m: (Processing...)\n")
            
            # Run agent
            # The simplified logs (logger.info) we added to specific places 
            # will appear automatically in the console due to logging config.
            response = await agent.run(user_input)
            
            print(f"\n🤖 \033[1mAgent\033[0m: {response}\n")
            print("="*60)
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
