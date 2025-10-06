"""Интеграция Telegram с Model Context Protocol."""

from .server import build_server, run_stdio_server

__all__ = ["build_server", "run_stdio_server"]
