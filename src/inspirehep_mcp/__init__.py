"""InspireHEP MCP Server - integrate high-energy physics literature with LLMs."""

from importlib.metadata import PackageNotFoundError, version


try:
    # pyproject.toml is the single source of truth for the release version.
    __version__ = version("inspirehep-mcp")
except PackageNotFoundError:  # pragma: no cover - only occurs from an unpacked checkout
    __version__ = "0+unknown"
