"""
Context Compaction
Token estimation and history summarization for managing context windows.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


# Average characters per token (rough estimate)
CHARS_PER_TOKEN = 4.0

# Default context window sizes for common models
MODEL_CONTEXT_WINDOWS = {
    "gemini-2.0-flash-exp": 1000000,
    "gemini-1.5-pro": 2000000,
    "gemini-1.5-flash": 1000000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
    "deepseek-chat": 64000,
    "deepseek-coder": 64000,
    "claude-3-opus": 200000,
    "claude-3-sonnet": 200000,
    "claude-3-haiku": 200000,
}

DEFAULT_CONTEXT_WINDOW = 128000


def estimate_tokens(text: str) -> int:
    """
    Estimate the number of tokens in a text string.
    
    Uses a simple character-based estimation. For more accurate
    estimation, use tiktoken or the model's native tokenizer.
    """
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def estimate_messages_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    Estimate total tokens in a list of messages.
    """
    total = 0
    for msg in messages:
        # Content tokens
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            # Handle multi-part content
            for part in content:
                if isinstance(part, str):
                    total += estimate_tokens(part)
                elif isinstance(part, dict) and "text" in part:
                    total += estimate_tokens(part["text"])
        
        # Role tokens (small overhead)
        total += 4
    
    return total


def get_context_window(model: str) -> int:
    """Get the context window size for a model."""
    # Check exact match
    if model in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model]
    
    # Check partial match
    model_lower = model.lower()
    for key, value in MODEL_CONTEXT_WINDOWS.items():
        if key.lower() in model_lower or model_lower in key.lower():
            return value
    
    return DEFAULT_CONTEXT_WINDOW


@dataclass
class CompactionResult:
    """Result of history compaction."""
    messages: List[Dict[str, Any]]
    summary: Optional[str] = None
    dropped_count: int = 0
    dropped_tokens: int = 0
    kept_tokens: int = 0
    was_compacted: bool = False


def prune_history(
    messages: List[Dict[str, Any]],
    max_tokens: int,
    preserve_recent: int = 10
) -> CompactionResult:
    """
    Prune history by dropping oldest messages.
    
    Args:
        messages: List of messages
        max_tokens: Maximum tokens to keep
        preserve_recent: Minimum number of recent messages to preserve
    
    Returns:
        CompactionResult with pruned messages
    """
    if not messages:
        return CompactionResult(messages=[], kept_tokens=0)
    
    total_tokens = estimate_messages_tokens(messages)
    
    if total_tokens <= max_tokens:
        return CompactionResult(
            messages=messages,
            kept_tokens=total_tokens,
            was_compacted=False
        )
    
    # Always preserve system message if present
    system_msg = None
    working_messages = messages.copy()
    
    if working_messages and working_messages[0].get("role") == "system":
        system_msg = working_messages.pop(0)
    
    # Calculate tokens for preserved messages
    preserved = working_messages[-preserve_recent:] if preserve_recent else []
    preserved_tokens = estimate_messages_tokens(preserved)
    
    if system_msg:
        preserved_tokens += estimate_messages_tokens([system_msg])
    
    # If preserved messages already exceed limit, just return them
    if preserved_tokens >= max_tokens:
        result_messages = [system_msg] if system_msg else []
        result_messages.extend(preserved)
        return CompactionResult(
            messages=result_messages,
            dropped_count=len(messages) - len(result_messages),
            dropped_tokens=total_tokens - preserved_tokens,
            kept_tokens=preserved_tokens,
            was_compacted=True
        )
    
    # Find how many additional messages we can keep
    budget = max_tokens - preserved_tokens
    older_messages = working_messages[:-preserve_recent] if preserve_recent else working_messages
    
    kept_older = []
    for msg in reversed(older_messages):
        msg_tokens = estimate_messages_tokens([msg])
        if msg_tokens <= budget:
            kept_older.insert(0, msg)
            budget -= msg_tokens
        else:
            break
    
    # Assemble result
    result_messages = []
    if system_msg:
        result_messages.append(system_msg)
    result_messages.extend(kept_older)
    result_messages.extend(preserved)
    
    kept_tokens = estimate_messages_tokens(result_messages)
    
    return CompactionResult(
        messages=result_messages,
        dropped_count=len(messages) - len(result_messages),
        dropped_tokens=total_tokens - kept_tokens,
        kept_tokens=kept_tokens,
        was_compacted=True
    )


def format_for_summarization(messages: List[Dict[str, Any]]) -> str:
    """Format messages for summarization prompt."""
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        if isinstance(content, str):
            lines.append(f"{role}: {content[:500]}{'...' if len(content) > 500 else ''}")
    return "\n\n".join(lines)


async def summarize_messages(
    messages: List[Dict[str, Any]],
    llm_fn: Any,
    previous_summary: Optional[str] = None,
    max_summary_tokens: int = 500
) -> str:
    """
    Summarize a list of messages using an LLM.
    
    Args:
        messages: Messages to summarize
        llm_fn: Async function to call LLM: (prompt) -> response
        previous_summary: Optional previous summary to incorporate
        max_summary_tokens: Target max tokens for summary
    
    Returns:
        Summary string
    """
    conversation_text = format_for_summarization(messages)
    
    prompt = f"""Summarize the following conversation, preserving:
- Key decisions made
- Important context and constraints
- Open questions or TODOs
- Any specific requirements mentioned

Keep the summary concise (under {max_summary_tokens * 4} characters).

"""
    
    if previous_summary:
        prompt += f"""Previous context:
{previous_summary}

New conversation to summarize:
"""
    
    prompt += f"""
{conversation_text}

Summary:"""
    
    try:
        summary = await llm_fn(prompt)
        return summary.strip()
    except Exception as e:
        logger.error(f"Failed to summarize messages: {e}")
        return previous_summary or "No summary available."


class ContextCompactor:
    """
    Manages context window compaction for long conversations.
    """
    
    def __init__(
        self,
        max_history_tokens: int = 50000,
        summarize_threshold: float = 0.7,
        preserve_recent: int = 10,
        llm_fn: Optional[Any] = None
    ):
        """
        Initialize the compactor.
        
        Args:
            max_history_tokens: Maximum tokens for history
            summarize_threshold: Fraction of max at which to trigger compaction
            preserve_recent: Number of recent messages to always keep
            llm_fn: Optional LLM function for summarization
        """
        self.max_history_tokens = max_history_tokens
        self.summarize_threshold = summarize_threshold
        self.preserve_recent = preserve_recent
        self.llm_fn = llm_fn
        self._summary: Optional[str] = None
    
    def set_llm(self, llm_fn: Any) -> None:
        """Set the LLM function for summarization."""
        self.llm_fn = llm_fn
    
    def needs_compaction(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if messages need compaction."""
        tokens = estimate_messages_tokens(messages)
        threshold = int(self.max_history_tokens * self.summarize_threshold)
        return tokens > threshold
    
    async def compact(
        self,
        messages: List[Dict[str, Any]],
        use_summary: bool = True
    ) -> CompactionResult:
        """
        Compact messages to fit within context limits.
        
        Args:
            messages: Messages to compact
            use_summary: Whether to generate a summary
        
        Returns:
            CompactionResult with compacted messages
        """
        if not self.needs_compaction(messages):
            return CompactionResult(
                messages=messages,
                summary=self._summary,
                kept_tokens=estimate_messages_tokens(messages),
                was_compacted=False
            )
        
        # First, try simple pruning
        result = prune_history(
            messages,
            self.max_history_tokens,
            self.preserve_recent
        )
        
        # Generate summary if enabled and we have an LLM
        if use_summary and self.llm_fn and result.dropped_count > 0:
            # Get the dropped messages
            dropped_messages = messages[:result.dropped_count]
            
            try:
                summary = await summarize_messages(
                    dropped_messages,
                    self.llm_fn,
                    self._summary
                )
                self._summary = summary
                result.summary = summary
                
                # Prepend summary as a system message if we have one
                if summary and result.messages:
                    summary_msg = {
                        "role": "system",
                        "content": f"[Previous conversation summary]\n{summary}"
                    }
                    
                    # Insert after existing system message or at start
                    if result.messages[0].get("role") == "system":
                        result.messages.insert(1, summary_msg)
                    else:
                        result.messages.insert(0, summary_msg)
                    
                    result.kept_tokens = estimate_messages_tokens(result.messages)
                    
            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")
        
        return result
    
    def get_summary(self) -> Optional[str]:
        """Get the current conversation summary."""
        return self._summary
    
    def set_summary(self, summary: str) -> None:
        """Set the conversation summary."""
        self._summary = summary
    
    def clear_summary(self) -> None:
        """Clear the conversation summary."""
        self._summary = None


# Global compactor instance
_compactor: Optional[ContextCompactor] = None


def get_compactor() -> ContextCompactor:
    """Get the global context compactor."""
    global _compactor
    if _compactor is None:
        from ..config import config
        compaction_config = getattr(config, 'compaction', None)
        if compaction_config:
            _compactor = ContextCompactor(
                max_history_tokens=getattr(compaction_config, 'max_history_tokens', 50000),
                summarize_threshold=getattr(compaction_config, 'summarize_threshold', 0.7),
                preserve_recent=getattr(compaction_config, 'preserve_recent', 10)
            )
        else:
            _compactor = ContextCompactor()
    return _compactor
