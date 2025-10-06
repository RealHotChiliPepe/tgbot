"""Telegram MCP server package."""

from importlib.metadata import version

__all__ = ["__version__"]

try:
    __version__ = version("telegram-mcp")
except Exception:  # pragma: no cover - during development when package isn't installed
    __version__ = "0.0.0"
