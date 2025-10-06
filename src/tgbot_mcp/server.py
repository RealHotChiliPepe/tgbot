"""Сборка MCP сервера для работы с Telegram."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from mcp import types as mcp_types
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server

from .config import TelegramConfig
from .telegram_service import TelegramService
from . import tools

SERVER_NAME = "telegram-mcp-bridge"
SERVER_INSTRUCTIONS = (
    "Инструменты предоставляют доступ к группам и перепискам вашего аккаунта Telegram. "
    "Используйте их ответственно и не передавайте конфиденциальные данные без необходимости."
)


LIST_GROUPS_SCHEMA = mcp_types.Tool(
    name="telegram_list_groups",
    description="Выводит список групп и каналов, где авторизованный пользователь состоит.",
    inputSchema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "description": "Максимальное количество элементов в ответе.",
            },
            "include_private": {
                "type": "boolean",
                "description": "Включать ли приватные группы без username.",
                "default": True,
            },
            "include_channels": {
                "type": "boolean",
                "description": "Добавлять ли каналы (broadcast).",
                "default": False,
            },
        },
        "additionalProperties": False,
    },
    outputSchema={
        "type": "object",
        "properties": {
            "groups": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "title": {"type": "string"},
                        "type": {"type": "string"},
                        "username": {"type": ["string", "null"]},
                        "is_megagroup": {"type": "boolean"},
                        "is_broadcast": {"type": "boolean"},
                        "participants": {"type": ["integer", "null"]},
                    },
                    "required": ["id", "title", "type"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["groups"],
        "additionalProperties": False,
    },
)

SEARCH_MESSAGES_SCHEMA = mcp_types.Tool(
    name="telegram_search_messages",
    description="Ищет сообщения в указанном чате по ключевым словам.",
    inputSchema={
        "type": "object",
        "properties": {
            "chat": {
                "type": "string",
                "description": "Идентификатор, username или точное название чата/канала.",
            },
            "query": {
                "type": "string",
                "description": "Поисковый запрос.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "Максимальное количество сообщений в выдаче.",
            },
        },
        "required": ["chat", "query"],
        "additionalProperties": False,
    },
    outputSchema={
        "type": "object",
        "properties": {
            "chat": {
                "type": "object",
                "properties": {
                    "id": {"type": ["integer", "null"]},
                    "type": {"type": "string"},
                    "title": {"type": "string"},
                    "username": {"type": ["string", "null"]},
                },
                "required": ["type", "title"],
                "additionalProperties": False,
            },
            "query": {"type": "string"},
            "messages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "date": {"type": ["string", "null"], "format": "date-time"},
                        "snippet": {"type": "string"},
                        "text": {"type": "string"},
                        "sender": {"type": ["string", "null"]},
                        "sender_id": {"type": ["integer", "null"]},
                        "link": {"type": ["string", "null"]},
                    },
                    "required": ["id", "snippet"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["chat", "query", "messages"],
        "additionalProperties": False,
    },
)


def build_server(config: TelegramConfig | None = None) -> Server:
    service = TelegramService(config)

    @asynccontextmanager
    async def lifespan(_: Server):
        await service.start()
        try:
            yield {"service": service}
        finally:
            await service.stop()

    server = Server(
        name=SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        lifespan=lifespan,
    )

    @server.list_tools()
    async def _list_tools(_: mcp_types.ListToolsRequest) -> mcp_types.ListToolsResult:
        return mcp_types.ListToolsResult(tools=[LIST_GROUPS_SCHEMA, SEARCH_MESSAGES_SCHEMA])

    @server.call_tool()
    async def _call_tool(tool_name: str, arguments: dict[str, Any]) -> tools.TextContent | tools.StructuredContent | tuple[
        tools.TextContent, tools.StructuredContent
    ]:
        service_ctx: TelegramService = server.request_context.lifespan_context["service"]

        if tool_name == LIST_GROUPS_SCHEMA.name:
            limit = max(1, min(int(arguments.get("limit", 50)), 500))
            include_private = bool(arguments.get("include_private", True))
            include_channels = bool(arguments.get("include_channels", False))
            return await tools.list_groups(
                service_ctx,
                limit=limit,
                include_private=include_private,
                include_channels=include_channels,
            )

        if tool_name == SEARCH_MESSAGES_SCHEMA.name:
            chat = str(arguments.get("chat", "").strip())
            query = str(arguments.get("query", "").strip())
            limit = max(1, min(int(arguments.get("limit", 20)), 100))
            return await tools.search_messages(
                service_ctx,
                chat=chat,
                query=query,
                limit=limit,
            )

        raise ValueError(f"Неизвестный инструмент: {tool_name}")

    return server


async def _run_stdio(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options(NotificationOptions())
        await server.run(read_stream, write_stream, init_options)


def run_stdio_server(config: TelegramConfig | None = None) -> None:
    server = build_server(config)
    asyncio.run(_run_stdio(server))
