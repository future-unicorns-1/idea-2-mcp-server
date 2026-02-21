"""
Entry point for the MCP server.

Usage:
    python -m mcp_tools.mcp_server
    # or
    python -m mcp_tools.server
"""

from mcp_tools.server import server

if __name__ == "__main__":
    server.run(transport="streamable-http", debug=True)
