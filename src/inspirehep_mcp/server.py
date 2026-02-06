"""InspireHEP MCP Server - main entry point."""

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "InspireHEP",
    instructions="MCP server for searching and retrieving high-energy physics literature from InspireHEP",
)

INSPIREHEP_API_BASE = "https://inspirehep.net/api"


@mcp.tool()
async def ping() -> str:
    """Check that the InspireHEP MCP server is running."""
    return "InspireHEP MCP server is running."


def main() -> None:
    """Run the InspireHEP MCP server."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting InspireHEP MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
