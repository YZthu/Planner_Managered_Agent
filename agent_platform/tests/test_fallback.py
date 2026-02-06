"""
Tests for Provider Fallback
"""
import pytest
import asyncio


class TestErrorClassification:
    """Test error classification for fallback."""
    
    def test_rate_limit_detection(self):
        """Test detecting rate limit errors."""
        from backend.providers.fallback import classify_error, FailoverReason
        
        error = Exception("Rate limit exceeded")
        reason, code = classify_error(error)
        assert reason == FailoverReason.RATE_LIMIT
        
        error = Exception("Error 429: Too many requests")
        reason, code = classify_error(error)
        assert reason == FailoverReason.RATE_LIMIT
        assert code == 429
    
    def test_timeout_detection(self):
        """Test detecting timeout errors."""
        from backend.providers.fallback import classify_error, FailoverReason
        
        error = Exception("Request timeout")
        reason, _ = classify_error(error)
        assert reason == FailoverReason.TIMEOUT
        
        error = asyncio.TimeoutError()
        reason, _ = classify_error(error)
        assert reason == FailoverReason.TIMEOUT
    
    def test_server_error_detection(self):
        """Test detecting server errors."""
        from backend.providers.fallback import classify_error, FailoverReason
        
        for code in [500, 502, 503, 504]:
            error = Exception(f"Server error: {code}")
            reason, detected_code = classify_error(error)
            assert reason == FailoverReason.SERVER_ERROR
            assert detected_code == code
    
    def test_auth_error_detection(self):
        """Test detecting auth errors."""
        from backend.providers.fallback import classify_error, FailoverReason
        
        error = Exception("Error 401: Unauthorized")
        reason, _ = classify_error(error)
        assert reason == FailoverReason.AUTH_ERROR
    
    def test_retryable_errors(self):
        """Test retryable error detection."""
        from backend.providers.fallback import is_retryable, FailoverReason
        
        # Retryable
        assert is_retryable(FailoverReason.RATE_LIMIT) is True
        assert is_retryable(FailoverReason.TIMEOUT) is True
        assert is_retryable(FailoverReason.SERVER_ERROR) is True
        assert is_retryable(FailoverReason.NETWORK_ERROR) is True
        
        # Not retryable
        assert is_retryable(FailoverReason.AUTH_ERROR) is False
        assert is_retryable(FailoverReason.INVALID_REQUEST) is False


class TestFallbackChain:
    """Test fallback chain resolution."""
    
    def test_resolve_fallback_chain(self):
        """Test resolving fallback candidates."""
        from backend.providers.fallback import resolve_fallback_chain
        
        candidates = resolve_fallback_chain("gemini", "gemini-2.0-flash")
        
        # Should have primary first
        assert candidates[0].provider == "gemini"
        assert candidates[0].model == "gemini-2.0-flash"
        
        # Should have other providers as fallbacks
        providers = [c.provider for c in candidates]
        assert len(providers) >= 2
    
    def test_custom_fallback_chain(self):
        """Test custom fallback chain."""
        from backend.providers.fallback import resolve_fallback_chain
        
        candidates = resolve_fallback_chain(
            "openai", "gpt-4o",
            fallback_list=["deepseek", "gemini"]
        )
        
        # Primary first
        assert candidates[0].provider == "openai"
        
        # Custom fallbacks
        providers = [c.provider for c in candidates[1:]]
        assert "deepseek" in providers
        assert "gemini" in providers


class TestRunWithFallback:
    """Test running with fallback."""
    
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """Test success on first try (no fallback)."""
        from backend.providers.fallback import run_with_fallback
        
        async def mock_run(provider, model):
            return f"Success with {provider}"
        
        result = await run_with_fallback(
            mock_run, "gemini", "gemini-2.0-flash"
        )
        
        assert result.result == "Success with gemini"
        assert result.provider == "gemini"
        assert result.had_fallback is False
        assert len(result.attempts) == 0
    
    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        """Test fallback when first provider fails."""
        from backend.providers.fallback import run_with_fallback
        
        call_count = 0
        
        async def mock_run(provider, model):
            nonlocal call_count
            call_count += 1
            if provider == "gemini":
                raise Exception("Rate limit exceeded")
            return f"Success with {provider}"
        
        result = await run_with_fallback(
            mock_run, "gemini", "gemini-2.0-flash",
            fallback_chain=["openai", "deepseek"]
        )
        
        assert "Success" in result.result
        assert result.provider != "gemini"  # Should have fallen back
        assert result.had_fallback is True
        assert len(result.attempts) == 1
        assert result.attempts[0].provider == "gemini"
    
    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        """Test when all providers fail."""
        from backend.providers.fallback import run_with_fallback
        
        async def mock_run(provider, model):
            raise Exception("Server error 500")
        
        with pytest.raises(RuntimeError, match="All.*attempts failed"):
            await run_with_fallback(
                mock_run, "gemini", "gemini-2.0-flash",
                fallback_chain=["openai"],
                max_retries=2
            )
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors don't trigger fallback."""
        from backend.providers.fallback import run_with_fallback
        
        async def mock_run(provider, model):
            raise Exception("Error 401: Invalid API key")
        
        with pytest.raises(Exception, match="401"):
            await run_with_fallback(
                mock_run, "gemini", "gemini-2.0-flash",
                fallback_chain=["openai", "deepseek"]
            )


class TestProviderFallbackManager:
    """Test the fallback manager."""
    
    @pytest.mark.asyncio
    async def test_manager_disabled(self):
        """Test manager when fallback is disabled."""
        from backend.providers.fallback import ProviderFallbackManager
        
        manager = ProviderFallbackManager(enabled=False)
        
        async def mock_run(provider, model):
            return "Direct call"
        
        result = await manager.run(mock_run, "gemini", "model")
        assert result.result == "Direct call"
        assert result.had_fallback is False
    
    @pytest.mark.asyncio
    async def test_manager_with_fallback(self):
        """Test manager with fallback enabled."""
        from backend.providers.fallback import ProviderFallbackManager
        
        manager = ProviderFallbackManager(
            enabled=True,
            fallback_chain=["openai", "deepseek"],
            max_retries=3
        )
        
        call_providers = []
        
        async def mock_run(provider, model):
            call_providers.append(provider)
            if provider == "gemini":
                raise Exception("Rate limit")
            return f"Success with {provider}"
        
        result = await manager.run(mock_run, "gemini", "model")
        
        assert "Success" in result.result
        assert result.had_fallback is True
        assert "gemini" in call_providers
