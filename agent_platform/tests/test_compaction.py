"""
Tests for Context Compaction
"""
import pytest


class TestTokenEstimation:
    """Test token estimation."""
    
    def test_estimate_tokens_empty(self):
        """Test estimating tokens for empty string."""
        from backend.core.compaction import estimate_tokens
        
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0
    
    def test_estimate_tokens_simple(self):
        """Test estimating tokens for simple text."""
        from backend.core.compaction import estimate_tokens
        
        # Rough estimate: ~4 chars per token
        tokens = estimate_tokens("Hello, world!")  # 13 chars
        assert 1 <= tokens <= 10
        
        tokens = estimate_tokens("A" * 100)  # 100 chars
        assert 20 <= tokens <= 30
    
    def test_estimate_messages_tokens(self):
        """Test estimating tokens for messages."""
        from backend.core.compaction import estimate_messages_tokens
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there! How can I help?"},
        ]
        
        tokens = estimate_messages_tokens(messages)
        assert tokens > 0
        assert tokens < 100  # Should be small for short messages


class TestContextWindow:
    """Test context window lookup."""
    
    def test_known_models(self):
        """Test context window for known models."""
        from backend.core.compaction import get_context_window
        
        assert get_context_window("gpt-4o") == 128000
        assert get_context_window("gpt-4") == 8192
        assert get_context_window("gemini-2.0-flash-exp") == 1000000
        assert get_context_window("deepseek-chat") == 64000
    
    def test_unknown_model(self):
        """Test default context window for unknown models."""
        from backend.core.compaction import get_context_window, DEFAULT_CONTEXT_WINDOW
        
        assert get_context_window("unknown-model-xyz") == DEFAULT_CONTEXT_WINDOW


class TestHistoryPruning:
    """Test history pruning."""
    
    def test_no_pruning_needed(self):
        """Test when history is within limits."""
        from backend.core.compaction import prune_history
        
        messages = [
            {"role": "user", "content": "Short message"},
            {"role": "assistant", "content": "Short response"},
        ]
        
        result = prune_history(messages, max_tokens=10000)
        
        assert result.was_compacted is False
        assert len(result.messages) == 2
        assert result.dropped_count == 0
    
    def test_pruning_drops_oldest(self):
        """Test that pruning drops oldest messages."""
        from backend.core.compaction import prune_history
        
        # Create messages with lots of content
        messages = [
            {"role": "user", "content": "X" * 1000},  # Old
            {"role": "assistant", "content": "Y" * 1000},  # Old
            {"role": "user", "content": "Recent message"},  # Recent
            {"role": "assistant", "content": "Recent response"},  # Recent
        ]
        
        # Force pruning with small limit
        result = prune_history(messages, max_tokens=500, preserve_recent=2)
        
        assert result.was_compacted is True
        assert result.dropped_count > 0
        
        # Recent messages should be preserved
        assert len(result.messages) >= 2
    
    def test_preserve_system_message(self):
        """Test that system message is always preserved."""
        from backend.core.compaction import prune_history
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "X" * 500},
            {"role": "assistant", "content": "Y" * 500},
            {"role": "user", "content": "Recent"},
        ]
        
        result = prune_history(messages, max_tokens=200, preserve_recent=1)
        
        # System message should be first
        if result.messages:
            assert result.messages[0]["role"] == "system"


class TestContextCompactor:
    """Test the context compactor."""
    
    def test_needs_compaction_false(self):
        """Test when compaction is not needed."""
        from backend.core.compaction import ContextCompactor
        
        compactor = ContextCompactor(max_history_tokens=10000)
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        
        assert compactor.needs_compaction(messages) is False
    
    def test_needs_compaction_true(self):
        """Test when compaction is needed."""
        from backend.core.compaction import ContextCompactor
        
        compactor = ContextCompactor(
            max_history_tokens=100,
            summarize_threshold=0.5
        )
        
        # Large messages
        messages = [
            {"role": "user", "content": "X" * 500},
            {"role": "assistant", "content": "Y" * 500},
        ]
        
        assert compactor.needs_compaction(messages) is True
    
    @pytest.mark.asyncio
    async def test_compact_without_llm(self):
        """Test compaction without LLM summarization."""
        from backend.core.compaction import ContextCompactor
        
        # Use smaller token limit to ensure compaction triggers
        compactor = ContextCompactor(
            max_history_tokens=100,
            summarize_threshold=0.3,
            preserve_recent=1
        )
        
        # Create messages that will definitely exceed the threshold
        messages = [
            {"role": "user", "content": "X" * 500},
            {"role": "assistant", "content": "Y" * 500},
            {"role": "user", "content": "Z" * 500},
            {"role": "assistant", "content": "W" * 500},
            {"role": "user", "content": "Recent"},
        ]
        
        result = await compactor.compact(messages, use_summary=False)
        
        # Should have compacted (dropped some messages)
        assert result.was_compacted is True or result.dropped_count > 0 or len(result.messages) < len(messages)
    
    @pytest.mark.asyncio
    async def test_compact_with_summary(self):
        """Test compaction with LLM summarization."""
        from backend.core.compaction import ContextCompactor
        
        async def mock_llm(prompt):
            return "Summary of previous conversation"
        
        # Use smaller token limit to ensure compaction triggers
        compactor = ContextCompactor(
            max_history_tokens=100,
            summarize_threshold=0.3,
            preserve_recent=1,
            llm_fn=mock_llm
        )
        
        # Create messages that will definitely exceed the threshold
        messages = [
            {"role": "user", "content": "X" * 500},
            {"role": "assistant", "content": "Y" * 500},
            {"role": "user", "content": "Z" * 500},
            {"role": "assistant", "content": "W" * 500},
            {"role": "user", "content": "Recent"},
        ]
        
        result = await compactor.compact(messages, use_summary=True)
        
        # Should have compacted (dropped some messages)
        assert result.was_compacted is True or result.dropped_count > 0 or len(result.messages) < len(messages)
    
    def test_set_and_get_summary(self):
        """Test manually setting and getting summary."""
        from backend.core.compaction import ContextCompactor
        
        compactor = ContextCompactor()
        
        assert compactor.get_summary() is None
        
        compactor.set_summary("Test summary")
        assert compactor.get_summary() == "Test summary"
        
        compactor.clear_summary()
        assert compactor.get_summary() is None
