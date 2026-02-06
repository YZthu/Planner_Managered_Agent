"""
Web Search Tool
Performs web searches using multiple providers: Brave, Perplexity, Serper, DuckDuckGo.
"""
from typing import Dict, Any, Optional, List
from enum import Enum
import os
import httpx
import logging

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class SearchProvider(str, Enum):
    """Supported search providers."""
    DUCKDUCKGO = "duckduckgo"
    BRAVE = "brave"
    PERPLEXITY = "perplexity"
    SERPER = "serper"


# Cache for search results
_search_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 3600  # 1 hour


def _get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider from environment or config."""
    env_keys = {
        "brave": "BRAVE_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "serper": "SERPER_API_KEY",
    }
    
    env_var = env_keys.get(provider.lower())
    if env_var:
        return os.environ.get(env_var)
    return None


async def search_brave(
    query: str,
    count: int = 5,
    api_key: Optional[str] = None,
    freshness: Optional[str] = None,
    country: Optional[str] = None,
    search_lang: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Search using Brave Search API.
    
    Args:
        query: Search query
        count: Number of results
        api_key: Brave API key
        freshness: Filter by date (pd=past day, pw=past week, pm=past month, py=past year)
        country: 2-letter country code for region-specific results (e.g., US, DE, JP)
        search_lang: ISO language code for search results (e.g., en, de, ja)
    """
    key = api_key or _get_api_key("brave")
    if not key:
        raise ValueError("Brave API key not configured")
    
    params = {
        "q": query,
        "count": min(count, 10),
    }
    
    if freshness:
        params["freshness"] = freshness
    
    if country:
        params["country"] = country.upper()
    
    if search_lang:
        params["search_lang"] = search_lang.lower()
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "X-Subscription-Token": key,
                "Accept": "application/json",
            },
            params=params,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise Exception(f"Brave API error: {response.status_code}")
        
        data = response.json()
        results = []
        
        for item in data.get("web", {}).get("results", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("description", ""),
                "url": item.get("url", ""),
                "age": item.get("age", "")
            })
        
        return results


async def search_perplexity(
    query: str,
    api_key: Optional[str] = None,
    model: str = "llama-3.1-sonar-small-128k-online"
) -> Dict[str, Any]:
    """
    Search using Perplexity API (AI-powered search).
    
    Returns both the answer and citations.
    """
    key = api_key or _get_api_key("perplexity")
    if not key:
        raise ValueError("Perplexity API key not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": query}
                ]
            },
            timeout=60.0
        )
        
        if response.status_code != 200:
            raise Exception(f"Perplexity API error: {response.status_code}")
        
        data = response.json()
        
        content = ""
        citations = []
        
        if "choices" in data and data["choices"]:
            choice = data["choices"][0]
            if "message" in choice:
                content = choice["message"].get("content", "")
        
        if "citations" in data:
            citations = data["citations"]
        
        return {
            "content": content,
            "citations": citations
        }


async def search_serper(
    query: str,
    count: int = 5,
    api_key: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Search using Serper API (Google Search).
    """
    key = api_key or _get_api_key("serper")
    if not key:
        raise ValueError("Serper API key not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": key,
                "Content-Type": "application/json",
            },
            json={
                "q": query,
                "num": count
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise Exception(f"Serper API error: {response.status_code}")
        
        data = response.json()
        results = []
        
        for item in data.get("organic", [])[:count]:
            results.append({
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "url": item.get("link", ""),
                "position": item.get("position")
            })
        
        return results


async def search_duckduckgo(query: str, count: int = 5) -> List[Dict[str, str]]:
    """Search using DuckDuckGo (no API key required)."""
    try:
        from duckduckgo_search import DDGS
        
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=count):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", "")
                })
        return results
    except ImportError:
        # Fallback to HTTP API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": query,
                    "format": "json",
                    "no_html": "1"
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", query),
                    "snippet": data.get("Abstract", ""),
                    "url": data.get("AbstractURL", "")
                })
            
            for topic in data.get("RelatedTopics", [])[:count-1]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", "")
                    })
            
            return results[:count]


class WebSearchTool(BaseTool):
    """Perform web searches using multiple providers."""
    
    def __init__(
        self,
        default_provider: str = "duckduckgo",
        brave_api_key: Optional[str] = None,
        perplexity_api_key: Optional[str] = None,
        serper_api_key: Optional[str] = None
    ):
        self.default_provider = default_provider.lower()
        self.api_keys = {
            "brave": brave_api_key,
            "perplexity": perplexity_api_key,
            "serper": serper_api_key,
        }
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return """Search the web for information on a topic.

Returns search results with titles, snippets, and URLs.
Use this to find current information, news, documentation, etc.

Providers:
- duckduckgo: Free, no API key needed (default)
- brave: High quality results, needs API key
- perplexity: AI-powered answers with citations, needs API key
- serper: Google search results, needs API key"""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "provider": {
                    "type": "string",
                    "enum": ["duckduckgo", "brave", "perplexity", "serper"],
                    "description": "Search provider to use (default: duckduckgo)"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-10, default: 5)"
                },
                "freshness": {
                    "type": "string",
                    "description": "Brave only: time filter (pd=day, pw=week, pm=month, py=year)"
                },
                "country": {
                    "type": "string",
                    "description": "2-letter country code for region-specific results (e.g., US, DE, JP, CN). Works with Brave."
                },
                "search_lang": {
                    "type": "string",
                    "description": "ISO language code for search results (e.g., en, de, ja, zh). Works with Brave."
                }
            },
            "required": ["query"]
        }
    
    async def execute(
        self,
        query: str,
        provider: Optional[str] = None,
        max_results: int = 5,
        freshness: Optional[str] = None,
        country: Optional[str] = None,
        search_lang: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """Execute web search."""
        provider = (provider or self.default_provider).lower()
        max_results = min(max(1, max_results), 10)
        
        try:
            if provider == "brave":
                api_key = self.api_keys.get("brave") or _get_api_key("brave")
                if not api_key:
                    return ToolResult(
                        success=False,
                        output="Brave API key not configured. Set BRAVE_API_KEY environment variable.",
                        data={"error": "missing_api_key"}
                    )
                
                results = await search_brave(
                    query, max_results, api_key, freshness,
                    country=country, search_lang=search_lang
                )
                return self._format_results(query, results, provider)
            
            elif provider == "perplexity":
                api_key = self.api_keys.get("perplexity") or _get_api_key("perplexity")
                if not api_key:
                    return ToolResult(
                        success=False,
                        output="Perplexity API key not configured. Set PERPLEXITY_API_KEY environment variable.",
                        data={"error": "missing_api_key"}
                    )
                
                result = await search_perplexity(query, api_key)
                return self._format_perplexity_result(query, result)
            
            elif provider == "serper":
                api_key = self.api_keys.get("serper") or _get_api_key("serper")
                if not api_key:
                    return ToolResult(
                        success=False,
                        output="Serper API key not configured. Set SERPER_API_KEY environment variable.",
                        data={"error": "missing_api_key"}
                    )
                
                results = await search_serper(query, max_results, api_key)
                return self._format_results(query, results, provider)
            
            else:  # duckduckgo (default)
                results = await search_duckduckgo(query, max_results)
                return self._format_results(query, results, "duckduckgo")
                
        except Exception as e:
            logger.exception(f"Search failed: {e}")
            return ToolResult(
                success=False,
                output=f"Search failed: {str(e)}",
                data={"error": str(e), "provider": provider}
            )
    
    def _format_results(
        self,
        query: str,
        results: List[Dict[str, str]],
        provider: str
    ) -> ToolResult:
        """Format search results."""
        if not results:
            return ToolResult(
                success=True,
                output="No search results found.",
                data={"results": [], "provider": provider}
            )
        
        formatted = []
        for i, result in enumerate(results, 1):
            entry = f"{i}. **{result['title']}**\n"
            entry += f"   {result['snippet']}\n"
            entry += f"   URL: {result['url']}"
            if result.get('age'):
                entry += f" ({result['age']})"
            formatted.append(entry)
        
        output = f"Found {len(results)} results for '{query}' ({provider}):\n\n"
        output += "\n\n".join(formatted)
        
        return ToolResult(
            success=True,
            output=output,
            data={"results": results, "provider": provider}
        )
    
    def _format_perplexity_result(
        self,
        query: str,
        result: Dict[str, Any]
    ) -> ToolResult:
        """Format Perplexity AI search result."""
        content = result.get("content", "No answer available.")
        citations = result.get("citations", [])
        
        output = f"**Perplexity AI answer for:** {query}\n\n"
        output += content
        
        if citations:
            output += "\n\n**Sources:**\n"
            for i, url in enumerate(citations, 1):
                output += f"{i}. {url}\n"
        
        return ToolResult(
            success=True,
            output=output,
            data={
                "content": content,
                "citations": citations,
                "provider": "perplexity"
            }
        )
