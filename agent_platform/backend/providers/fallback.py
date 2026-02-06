"""
Provider Fallback
Automatic retry with alternative LLM providers on errors.
"""
import asyncio
from typing import (
    TypeVar, Generic, Callable, Awaitable, 
    List, Optional, Dict, Any, Tuple
)
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class FailoverReason(str, Enum):
    """Reasons for failing over to another provider."""
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"
    AUTH_ERROR = "auth_error"
    INVALID_REQUEST = "invalid_request"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class FallbackAttempt:
    """Record of a fallback attempt."""
    provider: str
    model: str
    error: str
    reason: FailoverReason
    status_code: Optional[int] = None
    attempt_number: int = 0


@dataclass
class FallbackResult(Generic[T]):
    """Result of a fallback execution."""
    result: T
    provider: str
    model: str
    attempts: List[FallbackAttempt] = field(default_factory=list)
    
    @property
    def had_fallback(self) -> bool:
        """Whether fallback was used."""
        return len(self.attempts) > 0


# Common retryable HTTP status codes
RETRYABLE_STATUS_CODES = {
    429,  # Rate limit
    500,  # Internal server error
    502,  # Bad gateway
    503,  # Service unavailable
    504,  # Gateway timeout
}


def classify_error(error: Exception) -> Tuple[FailoverReason, Optional[int]]:
    """
    Classify an error to determine if it's retryable.
    
    Returns:
        Tuple of (FailoverReason, status_code or None)
    """
    error_str = str(error).lower()
    
    # Check for rate limiting
    if "rate" in error_str and "limit" in error_str:
        return FailoverReason.RATE_LIMIT, 429
    if "quota" in error_str:
        return FailoverReason.RATE_LIMIT, 429
    if "429" in error_str:
        return FailoverReason.RATE_LIMIT, 429
    
    # Check for timeout
    if "timeout" in error_str:
        return FailoverReason.TIMEOUT, None
    if isinstance(error, asyncio.TimeoutError):
        return FailoverReason.TIMEOUT, None
    
    # Check for auth errors
    if "401" in error_str or "403" in error_str:
        return FailoverReason.AUTH_ERROR, 401
    if "auth" in error_str or "key" in error_str:
        return FailoverReason.AUTH_ERROR, 401
    
    # Check for server errors
    for code in [500, 502, 503, 504]:
        if str(code) in error_str:
            return FailoverReason.SERVER_ERROR, code
    
    # Check for network errors
    if "connection" in error_str or "network" in error_str:
        return FailoverReason.NETWORK_ERROR, None
    
    # Check for invalid request (not retryable)
    if "400" in error_str or "invalid" in error_str:
        return FailoverReason.INVALID_REQUEST, 400
    
    return FailoverReason.UNKNOWN, None


def is_retryable(reason: FailoverReason) -> bool:
    """Check if an error reason is retryable with a different provider."""
    retryable = {
        FailoverReason.RATE_LIMIT,
        FailoverReason.TIMEOUT,
        FailoverReason.SERVER_ERROR,
        FailoverReason.NETWORK_ERROR,
    }
    return reason in retryable


@dataclass
class ProviderCandidate:
    """A provider/model candidate for fallback."""
    provider: str
    model: str


def resolve_fallback_chain(
    primary_provider: str,
    primary_model: str,
    fallback_list: Optional[List[str]] = None
) -> List[ProviderCandidate]:
    """
    Resolve the fallback chain for providers.
    
    Args:
        primary_provider: Primary provider name
        primary_model: Primary model name
        fallback_list: Optional list of fallback provider names
    
    Returns:
        List of ProviderCandidate in order of preference
    """
    # Default fallback chain
    default_fallbacks = ["openai", "deepseek", "gemini"]
    
    fallbacks = fallback_list or default_fallbacks
    
    # Build candidate list with primary first
    candidates = [ProviderCandidate(primary_provider, primary_model)]
    
    # Default models for each provider
    default_models = {
        "gemini": "gemini-2.0-flash-exp",
        "openai": "gpt-4o-mini",
        "deepseek": "deepseek-chat",
    }
    
    # Add fallbacks
    for provider in fallbacks:
        if provider.lower() != primary_provider.lower():
            model = default_models.get(provider.lower(), primary_model)
            candidates.append(ProviderCandidate(provider.lower(), model))
    
    return candidates


async def run_with_fallback(
    run_fn: Callable[[str, str], Awaitable[T]],
    primary_provider: str,
    primary_model: str,
    fallback_chain: Optional[List[str]] = None,
    max_retries: int = 3,
    on_error: Optional[Callable[[FallbackAttempt], Awaitable[None]]] = None
) -> FallbackResult[T]:
    """
    Run a function with automatic provider fallback on errors.
    
    Args:
        run_fn: Async function that takes (provider, model) and returns result
        primary_provider: Primary provider to try first
        primary_model: Primary model to use
        fallback_chain: List of fallback provider names
        max_retries: Maximum total attempts
        on_error: Optional callback for error handling
    
    Returns:
        FallbackResult with the result and attempt history
    """
    candidates = resolve_fallback_chain(
        primary_provider, primary_model, fallback_chain
    )
    
    attempts: List[FallbackAttempt] = []
    
    for attempt_num, candidate in enumerate(candidates[:max_retries]):
        try:
            logger.debug(
                f"Trying provider {candidate.provider} "
                f"(model: {candidate.model}, attempt {attempt_num + 1})"
            )
            
            result = await run_fn(candidate.provider, candidate.model)
            
            return FallbackResult(
                result=result,
                provider=candidate.provider,
                model=candidate.model,
                attempts=attempts
            )
            
        except Exception as e:
            reason, status_code = classify_error(e)
            
            attempt = FallbackAttempt(
                provider=candidate.provider,
                model=candidate.model,
                error=str(e),
                reason=reason,
                status_code=status_code,
                attempt_number=attempt_num + 1
            )
            attempts.append(attempt)
            
            logger.warning(
                f"Provider {candidate.provider} failed: {e} "
                f"(reason: {reason.value})"
            )
            
            if on_error:
                await on_error(attempt)
            
            # If not retryable, don't try other providers
            if not is_retryable(reason):
                logger.error(f"Error is not retryable: {reason.value}")
                raise
            
            # Continue to next provider
            continue
    
    # All providers failed
    error_msg = f"All {len(attempts)} provider attempts failed"
    logger.error(error_msg)
    raise RuntimeError(error_msg)


class ProviderFallbackManager:
    """
    Manager for provider fallback configuration and execution.
    """
    
    def __init__(
        self,
        enabled: bool = True,
        fallback_chain: Optional[List[str]] = None,
        max_retries: int = 3
    ):
        self.enabled = enabled
        self.fallback_chain = fallback_chain or ["gemini", "openai", "deepseek"]
        self.max_retries = max_retries
        self._stats: Dict[str, int] = {}  # Track fallback usage
    
    async def run(
        self,
        run_fn: Callable[[str, str], Awaitable[T]],
        provider: str,
        model: str
    ) -> FallbackResult[T]:
        """
        Run a function with fallback if enabled.
        """
        if not self.enabled:
            # No fallback, just run
            result = await run_fn(provider, model)
            return FallbackResult(
                result=result,
                provider=provider,
                model=model
            )
        
        async def on_error(attempt: FallbackAttempt):
            # Track stats
            key = f"{attempt.provider}:{attempt.reason.value}"
            self._stats[key] = self._stats.get(key, 0) + 1
        
        return await run_with_fallback(
            run_fn=run_fn,
            primary_provider=provider,
            primary_model=model,
            fallback_chain=self.fallback_chain,
            max_retries=self.max_retries,
            on_error=on_error
        )
    
    def get_stats(self) -> Dict[str, int]:
        """Get fallback statistics."""
        return dict(self._stats)
    
    def reset_stats(self) -> None:
        """Reset fallback statistics."""
        self._stats.clear()


# Global fallback manager
_fallback_manager: Optional[ProviderFallbackManager] = None


def get_fallback_manager() -> ProviderFallbackManager:
    """Get the global fallback manager."""
    global _fallback_manager
    if _fallback_manager is None:
        from ..config import config
        fallback_config = getattr(config, 'fallback', None)
        if fallback_config:
            _fallback_manager = ProviderFallbackManager(
                enabled=getattr(fallback_config, 'enabled', True),
                fallback_chain=getattr(fallback_config, 'chain', None),
                max_retries=getattr(fallback_config, 'max_retries', 3)
            )
        else:
            _fallback_manager = ProviderFallbackManager()
    return _fallback_manager
