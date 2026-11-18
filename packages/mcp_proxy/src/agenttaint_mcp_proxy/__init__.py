"""AgentTaint MCP security proxy."""

from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import EnforcementResult, SecurityGateway
from agenttaint_mcp_proxy.server import build_gateway_from_paths, create_security_proxy

__all__ = [
    "EnforcementError",
    "EnforcementResult",
    "SecurityGateway",
    "build_gateway_from_paths",
    "create_security_proxy",
]
__version__ = "1.0.0"
