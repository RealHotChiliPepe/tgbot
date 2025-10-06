"""MCP server that exposes Telegram automation tools."""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .config import (
    FetchMessagesRequest,
    GetChatRequest,
    ListDialogsRequest,
    SearchMessagesRequest,
    SendMessageRequest,
    TelegramSettings,
    load_settings,
)
from .telegram_client import TelegramClientManager


def build_server(settings: TelegramSettings | None = None) -> FastMCP:
    """Construct the MCP server instance and register tools."""

    cfg = settings or load_settings()
    manager = TelegramClientManager(cfg)

    @asynccontextmanager
    async def _lifespan(_server: FastMCP):
        try:
            yield None
        finally:
            await manager.close()

    server = FastMCP(
        name="telegram-mcp",
        instructions=(
            "Tools that operate on the owner's personal Telegram account. "
            "Use them cautiously and avoid leaking private information."
        ),
        lifespan=lambda app: _lifespan(app),
    )

    @server.tool(
        name="telegram_list_dialogs",
        description=(
            "List Telegram dialogs available to the authenticated user. "
            "Supports optional filtering and pagination."
        ),
        structured_output=True,
    )
    async def telegram_list_dialogs(
        limit: int | None = None,
        search: str | None = None,
        include_private: bool = False,
        include_channels: bool = True,
    ) -> list[dict[str, object]]:
        request = ListDialogsRequest(
            limit=limit or cfg.default_page_size,
            search=search,
            include_private=include_private,
            include_channels=include_channels,
        )
        return await manager.list_dialogs(request)

    @server.tool(
        name="telegram_get_chat",
        description="Retrieve metadata about a chat, group, or channel by identifier.",
        structured_output=True,
    )
    async def telegram_get_chat(chat: str) -> dict[str, object]:
        request = GetChatRequest(chat=chat)
        return await manager.get_chat(request)

    @server.tool(
        name="telegram_fetch_recent_messages",
        description="Fetch the most recent messages from a chat.",
        structured_output=True,
    )
    async def telegram_fetch_recent_messages(
        chat: str,
        limit: int | None = None,
        offset_id: int | None = None,
    ) -> list[dict[str, object]]:
        request = FetchMessagesRequest(
            chat=chat,
            limit=limit or cfg.default_page_size,
            offset_id=offset_id,
        )
        return await manager.fetch_recent_messages(request)

    @server.tool(
        name="telegram_search_messages",
        description="Search for messages in a chat that match a text query.",
        structured_output=True,
    )
    async def telegram_search_messages(
        chat: str,
        query: str,
        limit: int | None = None,
        offset_id: int | None = None,
    ) -> list[dict[str, object]]:
        request = SearchMessagesRequest(
            chat=chat,
            query=query,
            limit=limit or cfg.default_page_size,
            offset_id=offset_id,
        )
        return await manager.search_messages(request)

    @server.tool(
        name="telegram_send_message",
        description="Send a message to a chat and return the sent message.",
        structured_output=True,
    )
    async def telegram_send_message(
        chat: str,
        message: str,
        reply_to: int | None = None,
    ) -> dict[str, object]:
        request = SendMessageRequest(chat=chat, message=message, reply_to=reply_to)
        return await manager.send_message(request)

    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Telegram MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport to use (default: taken from TELEGRAM_DEFAULT_TRANSPORT or stdio)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings()
    server = build_server(settings)

    transport = args.transport or settings.default_transport
    server.run(transport=transport)


if __name__ == "__main__":  # pragma: no cover
    main()
