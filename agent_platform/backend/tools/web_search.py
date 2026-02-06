"""
Web Search Tool
Performs web searches using DuckDuckGo.
"""
from typing import Dict, Any, Optional, List
import httpx

from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    """Perform web searches to find information"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return """Search the web for information on a topic.

Returns search results with titles, snippets, and URLs.
Use this to find current information, news, documentation, etc."""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)"
                }
            },
            "required": ["query"]
        }
    
    async def execute(
        self,
        query: str,
        max_results: int = 5,
        **kwargs
    ) -> ToolResult:
        """Execute web search"""
        try:
            # Use DuckDuckGo HTML search
            results = await self._search_duckduckgo(query, max_results)
            
            if not results:
                return ToolResult(
                    success=True,
                    output="No search results found.",
                    data={"results": []}
                )
            
            # Format results
            formatted = []
            for i, result in enumerate(results, 1):
                formatted.append(
                    f"{i}. **{result['title']}**\n"
                    f"   {result['snippet']}\n"
                    f"   URL: {result['url']}"
                )
            
            output = f"Found {len(results)} results for '{query}':\n\n" + "\n\n".join(formatted)
            
            return ToolResult(
                success=True,
                output=output,
                data={"results": results}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Search failed: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Search using DuckDuckGo API"""
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", "")
                    })
            return results
        except ImportError:
            # Fallback to simple HTTP request if duckduckgo_search not available
            return await self._search_http_fallback(query, max_results)
    
    async def _search_http_fallback(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Fallback HTTP-based search"""
        async with httpx.AsyncClient() as client:
            # Use DuckDuckGo instant answer API
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
            
            # Add abstract if available
            if data.get("Abstract"):
                results.append({
                    "title": data.get("Heading", query),
                    "snippet": data.get("Abstract", ""),
                    "url": data.get("AbstractURL", "")
                })
            
            # Add related topics
            for topic in data.get("RelatedTopics", [])[:max_results-1]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", "")
                    })
            
            return results[:max_results]
