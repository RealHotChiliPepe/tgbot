"""Console script entry point for running the Telegram MCP server."""

from __future__ import annotations

from .server import main

__all__ = ["main"]

if __name__ == "__main__":  # pragma: no cover
    main()
