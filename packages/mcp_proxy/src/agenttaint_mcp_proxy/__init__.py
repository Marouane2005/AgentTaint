"""AgentTaint MCP security proxy."""

from agenttaint_mcp_proxy.errors import EnforcementError
from agenttaint_mcp_proxy.gateway import EnforcementResult, SecurityGateway
from agenttaint_mcp_proxy.server import create_security_proxy

__all__ = [
    "EnforcementError",
    "EnforcementResult",
    "SecurityGateway",
    "create_security_proxy",
]
__version__ = "0.1.0"
