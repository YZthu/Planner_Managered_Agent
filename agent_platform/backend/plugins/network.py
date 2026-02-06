"""
Network Infrastructure Plugin
Provides network discovery (mDNS) and status monitoring.
"""
import logging
import socket
import asyncio
from typing import List, Dict, Any, Optional

try:
    import netifaces
    from zeroconf import ServiceInfo, IPVersion
    from zeroconf.asyncio import AsyncZeroconf
    NETWORK_AVAILABLE = True
except ImportError:
    NETWORK_AVAILABLE = False

from ..core.plugins import BasePlugin
from ..tools.base import BaseTool, ToolResult
from ..config import config

logger = logging.getLogger(__name__)

class GetNetworkStatusTool(BaseTool):
    def __init__(self, plugin: "NetworkPlugin"):
        self.plugin = plugin
        
    @property
    def name(self) -> str:
        return "get_network_status"

    @property
    def description(self) -> str:
        return "Get current network status, including active interfaces and IP addresses."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> ToolResult:
        if not NETWORK_AVAILABLE:
             return ToolResult(success=False, output="Network monitoring dependencies not installed.")
        
        try:
            status = []
            interfaces = netifaces.interfaces()
            for iface in interfaces:
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info['addr']
                        # Identify Tailscale/VPN interfaces commonly named utun* or tailscale*
                        is_vpn = "utun" in iface.lower() or "tailscale" in iface.lower()
                        status.append(f"Interface: {iface} | IP: {ip} {'[VPN/Tailscale]' if is_vpn else ''}")
            
            mdns_status = "Running" if self.plugin.zeroconf else "Stopped"
            return ToolResult(
                success=True, 
                output=f"Network Status:\nmDNS Service: {mdns_status}\n" + "\n".join(status)
            )
        except Exception as e:
            return ToolResult(success=False, output=f"Failed to get network status: {str(e)}")


class NetworkPlugin(BasePlugin):
    zeroconf: Optional[Any] = None
    service_info: Optional[Any] = None

    @property
    def name(self) -> str:
        return "network"

    async def on_load(self):
        if not NETWORK_AVAILABLE:
            logger.warning("zeroconf/netifaces not installed. Network plugin disabled.")
            return

        try:
            # Load config
            net_conf = getattr(config, 'network', {})
            if isinstance(net_conf, dict):
                enable_mdns = net_conf.get("enable_mdns", True)
                hostname = net_conf.get("hostname", "agent-platform")
                service_type = net_conf.get("service_type", "_agent-platform._tcp.local.")
            else: # Pydantic model
                enable_mdns = getattr(net_conf, "enable_mdns", True)
                hostname = getattr(net_conf, "hostname", "agent-platform")
                service_type = getattr(net_conf, "service_type", "_agent-platform._tcp.local.")

            if enable_mdns:
                await self._start_mdns(hostname, service_type)
                
            logger.info("Network Plugin initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Network Plugin: {e}", exc_info=True)

    async def _start_mdns(self, hostname: str, service_type: str):
        try:
            self.zeroconf = AsyncZeroconf(ip_version=IPVersion.V4Only)
            
            # Get local IP
            local_ip = self._get_local_ip()
            if not local_ip:
                logger.warning("Could not determine local IP for mDNS")
                return

            # Helper to pack IP
            host_ip = socket.inet_aton(local_ip)
            
            # Determine port (from config if available, else default)
            port = getattr(config.server, "port", 8000)

            self.service_info = ServiceInfo(
                service_type,
                f"{hostname}.{service_type}",
                addresses=[host_ip],
                port=port,
                properties={
                    "version": "1.0.0",
                    "path": "/"
                },
                server=f"{hostname}.local.",
            )
            
            await self.zeroconf.async_register_service(self.service_info)
            logger.info(f"mDNS Service Registered: {hostname}.{service_type} on {local_ip}:{port}")
            
        except Exception as e:
            logger.error(f"Failed to start mDNS: {e}")

    def _get_local_ip(self) -> Optional[str]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return None

    async def cleanup(self):
        if self.zeroconf and self.service_info:
            await self.zeroconf.async_unregister_service(self.service_info)
            await self.zeroconf.async_close()
            self.zeroconf = None
            logger.info("mDNS Service Unregistered")

    def get_tools(self) -> List[BaseTool]:
        return [
            GetNetworkStatusTool(self)
        ]
