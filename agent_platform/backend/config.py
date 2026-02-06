"""
Agent Platform Configuration
Loads configuration from config.yaml and API keys from .env
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import yaml
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


# Load .env from project root for API keys
PROJECT_ROOT = Path(__file__).parent.parent.parent
PLATFORM_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def load_yaml_config() -> Dict[str, Any]:
    """Load configuration from config.yaml"""
    config_path = PLATFORM_ROOT / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please create config.yaml in the agent_platform directory."
        )
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


# Load YAML config
_yaml_config = load_yaml_config()


class GeminiConfig(BaseModel):
    """Gemini provider configuration"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 8192
    api_key: Optional[str] = os.getenv("GOOGLE_API_KEY")


class DeepSeekConfig(BaseModel):
    """DeepSeek provider configuration"""
    model: str
    base_url: str = "https://api.deepseek.com"
    temperature: float = 0.7
    max_tokens: int = 4096
    api_key: Optional[str] = os.getenv("DEEPSEEK_API_KEY")


class OpenAIConfig(BaseModel):
    """OpenAI provider configuration"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")


class LLMConfig(BaseModel):
    """LLM Provider Configuration"""
    default_provider: str
    gemini: GeminiConfig
    deepseek: DeepSeekConfig
    openai: OpenAIConfig
    
    # Convenience properties for backward compatibility
    @property
    def google_api_key(self) -> Optional[str]:
        return self.gemini.api_key
    
    @property
    def gemini_model(self) -> str:
        return self.gemini.model
    
    @property
    def deepseek_api_key(self) -> Optional[str]:
        return self.deepseek.api_key
    
    @property
    def deepseek_model(self) -> str:
        return self.deepseek.model
    
    @property
    def deepseek_base_url(self) -> str:
        return self.deepseek.base_url
    
    @property
    def openai_api_key(self) -> Optional[str]:
        return self.openai.api_key
    
    @property
    def openai_model(self) -> str:
        return self.openai.model


class AgentConfig(BaseModel):
    """Agent Configuration"""
    max_concurrent_subagents: int = 4
    max_tool_calls_per_turn: int = 10
    max_history_messages: int = 10
    enable_thinking: bool = False
    subagent_timeout_seconds: int = 60
    debounce_ms: int = 1000


class MemoryConfig(BaseModel):
    enabled: bool = False
    collection_name: str = "agent_memory"
    persist_directory: str = "./data/memory"


class BrowserConfig(BaseModel):
    headless: bool = True
    user_agent: str = "AgentPlatform/1.0"
    viewport: Dict[str, int] = {"width": 1280, "height": 720}


class NetworkConfig(BaseModel):
    enable_mdns: bool = True
    hostname: str = "agent-platform"
    service_type: str = "_agent-platform._tcp.local."


class RoleConfig(BaseModel):
    allow: List[str] = []
    deny: List[str] = []

class SecurityConfig(BaseModel):
    enabled: bool = False
    default_role: str = "user"
    roles: Dict[str, RoleConfig] = {
        "admin": RoleConfig(allow=["*"]),
        "user": RoleConfig(allow=["*"], deny=["shell_execute", "file_delete"]),
        "guest": RoleConfig(allow=["web_search", "browser_content", "query_memory"], deny=["*"])
    }


class PersonasConfig(BaseModel):
    """Personas Configuration"""
    enabled: List[str] = ["default"]


class PluginsConfig(BaseModel):
    """Plugins Configuration"""
    enabled: List[str] = ["core"]


class ServerConfig(BaseModel):
    """Server Configuration"""
    host: str
    port: int
    cors_origins: List[str]


class LoggingConfig(BaseModel):
    """Logging Configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config(BaseModel):
    """Main Configuration - loaded from config.yaml"""
    llm: LLMConfig
    agent: AgentConfig
    memory: MemoryConfig = MemoryConfig()
    browser: BrowserConfig = BrowserConfig()
    network: NetworkConfig = NetworkConfig()
    security: SecurityConfig = SecurityConfig()
    personas: PersonasConfig = PersonasConfig()
    plugins: PluginsConfig = PluginsConfig()
    server: ServerConfig
    logging: LoggingConfig
    
    # Paths
    project_root: Path = PROJECT_ROOT
    platform_root: Path = PLATFORM_ROOT
    skills_dir: Path = PLATFORM_ROOT / "skills"
    data_dir: Path = PLATFORM_ROOT / "data"
    
    class Config:
        arbitrary_types_allowed = True


def create_config_from_yaml(yaml_data: Dict[str, Any]) -> Config:
    """Create Config object from YAML data"""
    # Build LLM config with API keys from env
    llm_data = yaml_data.get("llm", {})
    llm_config = LLMConfig(
        default_provider=llm_data.get("provider", "gemini"),
        gemini=GeminiConfig(**llm_data.get("gemini", {"model": "gemini-2.0-flash"})),
        deepseek=DeepSeekConfig(**llm_data.get("deepseek", {"model": "deepseek-chat"})),
        openai=OpenAIConfig(**llm_data.get("openai", {"model": "gpt-4o-mini"})),
    )
    
    # Build agent config
    agent_data = yaml_data.get("agent", {})
    agent_config = AgentConfig(
        max_concurrent_subagents=agent_data.get("max_concurrent_subagents", 4),
        subagent_timeout_seconds=agent_data.get("subagent_timeout_seconds", 120),
        max_tool_calls_per_turn=agent_data.get("max_tool_calls_per_turn", 10),
        max_history_messages=agent_data.get("max_history_messages", 20),
        enable_thinking=agent_data.get("enable_thinking", True),
        debounce_ms=agent_data.get("debounce_ms", 1000),
    )
    
    # Build server config
    server_data = yaml_data.get("server", {})
    server_config = ServerConfig(
        host=server_data.get("host", "0.0.0.0"),
        port=server_data.get("port", 8000),
        cors_origins=server_data.get("cors_origins", ["*"]),
    )
    
    # Build logging config
    logging_data = yaml_data.get("logging", {})
    logging_config = LoggingConfig(
        level=logging_data.get("level", "INFO"),
        format=logging_data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
    )
    
    # Build paths
    paths_data = yaml_data.get("paths", {})
    skills_dir = PLATFORM_ROOT / paths_data.get("skills_dir", "skills")
    data_dir = PLATFORM_ROOT / paths_data.get("data_dir", "data")
    
    # Build personas config
    personas_data = yaml_data.get("personas", {})
    personas_config = PersonasConfig(
        enabled=personas_data.get("enabled", ["default"])
    )
    
    # Build plugins config
    plugins_data = yaml_data.get("plugins", {})
    plugins_config = PluginsConfig(
        enabled=plugins_data.get("enabled", ["core"])
    )
    
    return Config(
        llm=llm_config,
        agent=agent_config,
        personas=personas_config,
        plugins=plugins_config,
        server=server_config,
        logging=logging_config,
        skills_dir=skills_dir,
        data_dir=data_dir,
    )


# Create global config instance
config = create_config_from_yaml(_yaml_config)

# Ensure data directory exists
config.data_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.logging.level.upper(), logging.INFO),
    format=config.logging.format
)


def reload_config():
    """Reload configuration from config.yaml"""
    global config, _yaml_config
    _yaml_config = load_yaml_config()
    config = create_config_from_yaml(_yaml_config)
    return config
