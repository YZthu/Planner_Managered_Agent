"""
Test Suite for LLM Providers
Tests provider instantiation and interface compliance.
"""
import pytest
from backend.providers.base import BaseLLMProvider, Message, Role


class TestProviderBase:
    """Tests for base provider interface."""
    
    def test_message_creation(self):
        """Message dataclass should work correctly."""
        msg = Message(role=Role.USER, content="Hello")
        assert msg.role == Role.USER
        assert msg.content == "Hello"
    
    def test_role_enum(self):
        """Role enum should have required values."""
        assert Role.SYSTEM is not None
        assert Role.USER is not None
        assert Role.ASSISTANT is not None
        assert Role.TOOL is not None


class TestGeminiProvider:
    """Tests for Gemini provider."""
    
    def test_gemini_instantiation(self, config):
        """Gemini provider should instantiate."""
        from backend.providers.gemini import GeminiProvider
        
        if not config.llm.gemini.api_key:
            pytest.skip("GOOGLE_API_KEY not set")
        
        provider = GeminiProvider()
        assert provider is not None
        assert isinstance(provider, BaseLLMProvider)
    
    def test_gemini_model_config(self, config):
        """Gemini should use config model."""
        from backend.providers.gemini import GeminiProvider
        
        if not config.llm.gemini.api_key:
            pytest.skip("GOOGLE_API_KEY not set")
        
        provider = GeminiProvider()
        assert provider.model == config.llm.gemini.model


class TestDeepSeekProvider:
    """Tests for DeepSeek provider (OpenAI-compatible)."""
    
    def test_deepseek_factory(self, config):
        """DeepSeek factory should create provider."""
        from backend.providers import create_deepseek_provider
        
        if not config.llm.deepseek.api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")
        
        provider = create_deepseek_provider()
        assert provider is not None
        assert isinstance(provider, BaseLLMProvider)
    
    def test_deepseek_base_url(self, config):
        """DeepSeek should use correct base URL."""
        from backend.providers import create_deepseek_provider
        
        if not config.llm.deepseek.api_key:
            pytest.skip("DEEPSEEK_API_KEY not set")
        
        provider = create_deepseek_provider()
        assert "deepseek" in provider._base_url.lower()


class TestOpenAIProvider:
    """Tests for OpenAI provider."""
    
    def test_openai_factory(self, config):
        """OpenAI factory should create provider."""
        from backend.providers import create_openai_provider
        
        if not config.llm.openai.api_key:
            pytest.skip("OPENAI_API_KEY not set")
        
        provider = create_openai_provider()
        assert provider is not None
        assert isinstance(provider, BaseLLMProvider)


class TestOpenAICompatibleProvider:
    """Tests for the unified OpenAI-compatible provider."""
    
    def test_custom_provider_creation(self):
        """Custom OpenAI-compatible provider should work."""
        from backend.providers.openai_compatible import OpenAICompatibleProvider
        
        # Create with mock API key (won't make actual calls)
        provider = OpenAICompatibleProvider(
            provider_name="test-provider",
            api_key="test-key",
            model="test-model",
            base_url="https://api.test.com/v1"
        )
        assert provider is not None
        assert provider.model == "test-model"
        assert provider._base_url == "https://api.test.com/v1"
