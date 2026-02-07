"""
Tests for Web Search and Web Fetch
"""
import pytest


class TestSSRFProtection:
    """Test SSRF protection for web fetch."""
    
    def test_private_ip_detection(self):
        """Test detecting private IP addresses."""
        from backend.tools.web_fetch import is_private_ip
        
        # Private IPs
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("127.0.0.1") is True
        
        # Public IPs
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
    
    def test_safe_url_validation(self):
        """Test URL safety validation."""
        from backend.tools.web_fetch import is_safe_url
        
        # Safe URLs
        is_safe, _ = is_safe_url("https://example.com")
        assert is_safe is True
        
        is_safe, _ = is_safe_url("http://api.github.com/users")
        assert is_safe is True
        
        # Unsafe URLs
        is_safe, reason = is_safe_url("https://localhost/api")
        assert is_safe is False
        assert "localhost" in reason.lower()
        
        is_safe, reason = is_safe_url("https://127.0.0.1/")
        assert is_safe is False
        
        is_safe, reason = is_safe_url("ftp://example.com")
        assert is_safe is False
        assert "scheme" in reason.lower()
    
    def test_metadata_url_blocked(self):
        """Test that cloud metadata URLs are blocked."""
        from backend.tools.web_fetch import is_safe_url
        
        # AWS metadata
        is_safe, _ = is_safe_url("http://169.254.169.254/latest/meta-data/")
        assert is_safe is False


class TestHTMLExtraction:
    """Test HTML content extraction."""
    
    def test_extract_text_from_html(self):
        """Test extracting text from HTML."""
        from backend.tools.web_fetch import extract_text_from_html
        
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Hello World</h1>
                <p>This is a test paragraph.</p>
                <script>alert('ignored')</script>
                <style>.ignored { color: red; }</style>
            </body>
        </html>
        """
        
        text = extract_text_from_html(html, mode="text")
        
        # Should contain main content
        assert "Hello World" in text
        assert "test paragraph" in text
        
        # Should not contain script/style content
        assert "alert" not in text
        assert ".ignored" not in text


class TestWebFetchTool:
    """Test web fetch tool."""
    
    def test_tool_properties(self):
        """Test tool has correct properties."""
        from backend.tools.web_fetch import WebFetchTool
        
        tool = WebFetchTool()
        
        assert tool.name == "web_fetch"
        assert "fetch" in tool.description.lower()
        assert "url" in tool.parameters["properties"]
    
    @pytest.mark.asyncio
    async def test_blocked_url(self):
        """Test that blocked URLs are rejected."""
        from backend.tools.web_fetch import WebFetchTool
        
        tool = WebFetchTool(block_private_ips=True)
        
        result = await tool.execute(url="http://localhost/api")
        
        assert result.success is False
        assert "blocked" in result.output.lower()
    
    @pytest.mark.asyncio
    async def test_invalid_scheme(self):
        """Test that invalid schemes are rejected."""
        from backend.tools.web_fetch import WebFetchTool
        
        tool = WebFetchTool()
        
        result = await tool.execute(url="ftp://example.com/file")
        
        assert result.success is False
        assert "scheme" in result.output.lower() or "blocked" in result.output.lower()


class TestWebSearchProviders:
    """Test web search providers."""
    
    def test_search_tool_properties(self):
        """Test search tool has correct properties."""
        from backend.tools.web_search import WebSearchTool
        
        tool = WebSearchTool()
        
        assert tool.name == "web_search"
        assert "query" in tool.parameters["properties"]
        assert "provider" in tool.parameters["properties"]
    
    def test_provider_enum(self):
        """Test search provider enum."""
        from backend.tools.web_search import SearchProvider
        
        assert SearchProvider.DUCKDUCKGO == "duckduckgo"
        assert SearchProvider.BRAVE == "brave"
        assert SearchProvider.PERPLEXITY == "perplexity"
        assert SearchProvider.SERPER == "serper"
    
    @pytest.mark.asyncio
    async def test_search_missing_api_key(self):
        """Test search with missing API key."""
        from backend.tools.web_search import WebSearchTool
        import os
        
        # Clear any existing keys
        original = os.environ.get("BRAVE_API_KEY")
        if "BRAVE_API_KEY" in os.environ:
            del os.environ["BRAVE_API_KEY"]
        
        try:
            tool = WebSearchTool()
            result = await tool.execute(query="test", provider="brave")
            
            assert result.success is False
            assert "api key" in result.output.lower()
        finally:
            if original:
                os.environ["BRAVE_API_KEY"] = original
    
    def test_format_results(self):
        """Test result formatting."""
        from backend.tools.web_search import WebSearchTool
        
        tool = WebSearchTool()
        
        results = [
            {
                "title": "Test Result 1",
                "snippet": "This is the first result.",
                "url": "https://example.com/1"
            },
            {
                "title": "Test Result 2",
                "snippet": "This is the second result.",
                "url": "https://example.com/2"
            }
        ]
        
        formatted = tool._format_results("test query", results, "duckduckgo")
        
        assert formatted.success is True
        assert "Test Result 1" in formatted.output
        assert "Test Result 2" in formatted.output
        assert "https://example.com/1" in formatted.output
        assert len(formatted.data["results"]) == 2
    
    def test_format_perplexity_result(self):
        """Test Perplexity result formatting."""
        from backend.tools.web_search import WebSearchTool
        
        tool = WebSearchTool()
        
        result = {
            "content": "This is the AI-generated answer.",
            "citations": [
                "https://source1.com",
                "https://source2.com"
            ]
        }
        
        formatted = tool._format_perplexity_result("test query", result)
        
        assert formatted.success is True
        assert "AI-generated answer" in formatted.output
        assert "source1.com" in formatted.output
        assert formatted.data["provider"] == "perplexity"


    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_duckduckgo_search_live(self):
        """
        Live integration test for DuckDuckGo search.
        Strictly asserts that results are returned. Fails on network/parsing errors.
        """
        from backend.tools.web_search import search_duckduckgo
        
        # This will fail if network is down or library is broken
        results = await search_duckduckgo("python programming", count=3)
        
        assert isinstance(results, list)
        assert len(results) > 0, "Live search returned no results!"
        
        # Verify structure of first result
        first = results[0]
        assert "title" in first
        assert "snippet" in first
        assert "url" in first
        assert len(first["title"]) > 0
        assert len(first["url"]) > 0
