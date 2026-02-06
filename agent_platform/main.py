"""
Agent Platform - Main Entry Point
FastAPI application with CORS and static file serving.
"""
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api.routes import router
from backend.core.registry import registry
from backend.core.startup import initialize_plugins, validate_enabled_personas
from backend.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    print("🚀 Starting Agent Platform...")
    await registry.initialize()
    print(f"✅ Registry initialized at {registry.db_path}")
    print(f"📡 LLM Provider: {config.llm.default_provider}")
    print(f"🔧 Max concurrent subagents: {config.agent.max_concurrent_subagents}")
    
    # Initialize plugins
    await initialize_plugins()
    print(f"🔌 Plugins initialized: {config.plugins.enabled}")
    
    # Validate personas
    print(f"🎭 Validating enabled personas: {config.personas.enabled}")
    persona_status = validate_enabled_personas()
    for persona, eligible in persona_status.items():
        if eligible:
            print(f"  ✅ {persona}: eligible")
        else:
            print(f"  ⚠️  {persona}: NOT eligible")
    
    yield
    
    # Shutdown
    print("👋 Shutting down Agent Platform...")


# Create FastAPI app
app = FastAPI(
    title="Agent Platform",
    description="Multi-agent platform with LLM-as-Planner architecture",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve frontend static files
frontend_dir = Path(__file__).parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
async def root():
    """Serve the frontend"""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Agent Platform API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.server.host,
        port=config.server.port,
        reload=True
    )
