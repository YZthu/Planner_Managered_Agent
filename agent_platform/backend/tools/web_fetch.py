"""
Web Fetch Tool
Fetch and extract content from URLs with SSRF protection.
"""
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import ipaddress
import re
import httpx
import logging

from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


# Private IP ranges to block for SSRF protection
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Blocked hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",  # AWS metadata
}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_MAX_CHARS = 50000
DEFAULT_TIMEOUT = 30


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in PRIVATE_IP_RANGES)
    except ValueError:
        return False


def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Check if a URL is safe to fetch (SSRF protection).
    
    Returns:
        Tuple of (is_safe, reason)
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"
    
    # Check scheme
    if parsed.scheme not in ("http", "https"):
        return False, f"Invalid scheme: {parsed.scheme}"
    
    # Check hostname
    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"
    
    hostname_lower = hostname.lower()
    
    # Block known dangerous hostnames
    if hostname_lower in BLOCKED_HOSTNAMES:
        return False, f"Blocked hostname: {hostname}"
    
    # Check for IP addresses
    if is_private_ip(hostname):
        return False, f"Private IP address blocked: {hostname}"
    
    # Try to resolve and check
    try:
        import socket
        ips = socket.getaddrinfo(hostname, None)
        for ip_info in ips:
            ip_str = ip_info[4][0]
            if is_private_ip(ip_str):
                return False, f"Hostname resolves to private IP: {ip_str}"
    except socket.gaierror:
        # Can't resolve, might be a valid external hostname
        pass
    
    return True, "OK"


def extract_text_from_html(html: str, mode: str = "markdown") -> str:
    """
    Extract readable text from HTML content.
    
    Args:
        html: HTML content
        mode: "markdown" or "text"
    
    Returns:
        Extracted text content
    """
    # Try trafilatura first (best quality)
    try:
        import trafilatura
        
        if mode == "markdown":
            result = trafilatura.extract(html, output_format="markdown")
        else:
            result = trafilatura.extract(html, output_format="txt")
        
        if result:
            return result
    except ImportError:
        logger.debug("trafilatura not installed, falling back to basic extraction")
    
    # Fallback to basic extraction
    try:
        from html.parser import HTMLParser
        
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self._skip_tags = {"script", "style", "noscript", "header", "footer", "nav"}
                self._current_tag = None
                self._skip_content = False
            
            def handle_starttag(self, tag, attrs):
                self._current_tag = tag
                if tag in self._skip_tags:
                    self._skip_content = True
            
            def handle_endtag(self, tag):
                if tag in self._skip_tags:
                    self._skip_content = False
                if tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li"):
                    self.text_parts.append("\n")
            
            def handle_data(self, data):
                if not self._skip_content:
                    text = data.strip()
                    if text:
                        self.text_parts.append(text + " ")
        
        parser = TextExtractor()
        parser.feed(html)
        return "".join(parser.text_parts).strip()
        
    except Exception as e:
        logger.error(f"HTML extraction failed: {e}")
        # Last resort: remove tags with regex
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


class WebFetchTool(BaseTool):
    """Fetch and extract content from web URLs."""
    
    def __init__(
        self,
        max_chars: int = DEFAULT_MAX_CHARS,
        timeout_seconds: int = DEFAULT_TIMEOUT,
        block_private_ips: bool = True
    ):
        self.max_chars = max_chars
        self.timeout_seconds = timeout_seconds
        self.block_private_ips = block_private_ips
    
    @property
    def name(self) -> str:
        return "web_fetch"
    
    @property
    def description(self) -> str:
        return """Fetch content from a web URL and extract readable text.

Use this to read full web page content, documentation, articles, etc.
Returns extracted text in markdown or plain text format.

Note: Some websites may block automated access."""
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch (http or https)"
                },
                "extract_mode": {
                    "type": "string",
                    "enum": ["markdown", "text"],
                    "description": "Output format: 'markdown' or 'text' (default: markdown)"
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Maximum characters to return (default: {DEFAULT_MAX_CHARS})"
                }
            },
            "required": ["url"]
        }
    
    async def execute(
        self,
        url: str,
        extract_mode: str = "markdown",
        max_chars: Optional[int] = None,
        **kwargs
    ) -> ToolResult:
        """Fetch URL content."""
        try:
            # Validate URL
            if self.block_private_ips:
                is_safe, reason = is_safe_url(url)
                if not is_safe:
                    return ToolResult(
                        success=False,
                        output=f"URL blocked: {reason}",
                        data={"error": "ssrf_blocked", "reason": reason}
                    )
            
            # Determine max chars
            chars_limit = max_chars or self.max_chars
            
            # Fetch content
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                follow_redirects=True,
                max_redirects=5
            ) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": DEFAULT_USER_AGENT}
                )
            
            if response.status_code != 200:
                return ToolResult(
                    success=False,
                    output=f"HTTP error: {response.status_code}",
                    data={
                        "error": "http_error",
                        "status_code": response.status_code
                    }
                )
            
            # Get content type
            content_type = response.headers.get("content-type", "").lower()
            
            # Handle different content types
            if "text/html" in content_type:
                text = extract_text_from_html(response.text, extract_mode)
            elif "text/plain" in content_type:
                text = response.text
            elif "application/json" in content_type:
                import json
                text = json.dumps(response.json(), indent=2)
            elif "text/markdown" in content_type:
                text = response.text
            else:
                # Try to extract text anyway
                try:
                    text = extract_text_from_html(response.text, extract_mode)
                except Exception:
                    text = response.text
            
            # Truncate if needed
            truncated = False
            if len(text) > chars_limit:
                text = text[:chars_limit]
                truncated = True
            
            # Build output
            output = f"Fetched content from: {url}\n"
            if truncated:
                output += f"(Truncated to {chars_limit} characters)\n"
            output += "\n---\n\n"
            output += text
            
            return ToolResult(
                success=True,
                output=output,
                data={
                    "url": url,
                    "final_url": str(response.url),
                    "content_type": content_type,
                    "char_count": len(text),
                    "truncated": truncated
                }
            )
            
        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                output=f"Request timed out after {self.timeout_seconds}s",
                data={"error": "timeout"}
            )
        except httpx.RequestError as e:
            return ToolResult(
                success=False,
                output=f"Request failed: {str(e)}",
                data={"error": "request_error", "details": str(e)}
            )
        except Exception as e:
            logger.exception(f"Web fetch failed: {e}")
            return ToolResult(
                success=False,
                output=f"Fetch failed: {str(e)}",
                data={"error": str(e)}
            )
