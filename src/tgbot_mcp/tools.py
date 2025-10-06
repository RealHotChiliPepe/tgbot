"""Реализация инструментов MCP, работающих поверх Telegram."""

from __future__ import annotations

import re
from datetime import timezone
from typing import Any

from mcp import types as mcp_types
from telethon.tl import types as tg_types

from .telegram_service import TelegramService

TextContent = list[mcp_types.TextContent]
StructuredContent = dict[str, Any]


def _text_response(text: str) -> TextContent:
    return [mcp_types.TextContent(type="text", text=text)]


def _entity_type(entity: Any) -> str:
    if isinstance(entity, tg_types.Channel):
        if getattr(entity, "megagroup", False):
            return "supergroup"
        if getattr(entity, "broadcast", False):
            return "channel"
        return "channel"
    if isinstance(entity, tg_types.Chat):
        return "group"
    if isinstance(entity, tg_types.User):
        return "user"
    if isinstance(entity, tg_types.ChatForbidden) or isinstance(entity, tg_types.ChannelForbidden):
        return "forbidden"
    return entity.__class__.__name__.lower()


def _entity_name(entity: Any) -> str:
    if isinstance(entity, (tg_types.Channel, tg_types.Chat)):
        return entity.title or "(без названия)"
    if isinstance(entity, tg_types.User):
        full = " ".join(filter(None, [entity.first_name, entity.last_name]))
        if full.strip():
            return full.strip()
        if entity.username:
            return f"@{entity.username}"
    return getattr(entity, "title", None) or getattr(entity, "username", "Неизвестный чат")


def _shorten(text: str, limit: int = 280) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


async def _resolve_dialog(service: TelegramService, reference: str) -> tg_types.TypeInputPeer:
    client = await service.get_client()

    ref = reference.strip()
    if not ref:
        raise ValueError("Параметр chat не может быть пустым")

    # Попытка распознать числовой идентификатор
    if re.fullmatch(r"-?\d+", ref):
        try:
            return await client.get_entity(int(ref))
        except Exception:
            pass

    # Имя пользователя @name или ссылка t.me/name
    cleaned = ref
    if cleaned.startswith("https://") or cleaned.startswith("http://"):
        cleaned = cleaned.split("/")[-1]
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]

    try:
        return await client.get_entity(cleaned)
    except Exception:
        pass

    # Попробуем найти по названию среди диалогов
    lower = ref.lower()
    async for dialog in client.iter_dialogs():
        if dialog.name.lower() == lower:
            return dialog.entity

    raise ValueError(
        "Не удалось найти чат по идентификатору/имени. Укажите username, ссылку, ID или точное название."
    )


async def list_groups(
    service: TelegramService,
    *,
    limit: int = 50,
    include_private: bool = True,
    include_channels: bool = False,
) -> tuple[TextContent, StructuredContent]:
    if limit <= 0:
        raise ValueError("limit должен быть положительным числом")

    client = await service.get_client()

    groups: list[dict[str, Any]] = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, tg_types.User):
            continue
        if isinstance(entity, tg_types.Channel):
            if entity.broadcast and not include_channels:
                continue
            entity_type = _entity_type(entity)
        elif isinstance(entity, tg_types.Chat):
            entity_type = _entity_type(entity)
        else:
            continue

        if not include_private and not getattr(entity, "username", None):
            continue

        groups.append(
            {
                "id": entity.id,
                "title": dialog.name,
                "type": entity_type,
                "username": getattr(entity, "username", None),
                "is_megagroup": getattr(entity, "megagroup", False),
                "is_broadcast": getattr(entity, "broadcast", False),
                "participants": getattr(entity, "participants_count", None),
            }
        )

        if len(groups) >= limit:
            break

    if groups:
        preview = "\n".join(
            f"• {item['title']} ({item['type']})" + (
                f" — @{item['username']}" if item.get("username") else ""
            )
            for item in groups[: min(len(groups), 5)]
        )
        text = (
            f"Найдено {len(groups)} групп/каналов."\
            "\n" + preview + ("\n…" if len(groups) > 5 else "")
        )
    else:
        text = "Группы не найдены. Убедитесь, что сессия авторизована."

    structured: StructuredContent = {"groups": groups}
    return _text_response(text), structured


async def search_messages(
    service: TelegramService,
    *,
    chat: str,
    query: str,
    limit: int = 20,
) -> tuple[TextContent, StructuredContent]:
    if not query.strip():
        raise ValueError("Параметр query не может быть пустым")
    if limit <= 0:
        raise ValueError("limit должен быть положительным числом")

    entity = await _resolve_dialog(service, chat)
    client = await service.get_client()

    messages: list[dict[str, Any]] = []
    async for message in client.iter_messages(entity, search=query, limit=limit):
        sender_name = None
        try:
            sender = await message.get_sender()
        except Exception:
            sender = None
        if sender:
            sender_name = _entity_name(sender)

        text = message.text or message.message or ""
        if message.date:
            if message.date.tzinfo is None:
                date_iso = message.date.replace(tzinfo=timezone.utc).isoformat()
            else:
                date_iso = message.date.astimezone(timezone.utc).isoformat()
        else:
            date_iso = None

        messages.append(
            {
                "id": message.id,
                "date": date_iso,
                "snippet": _shorten(text),
                "text": text,
                "sender": sender_name,
                "sender_id": message.sender_id,
                "link": message.link,
            }
        )

    entity_name = _entity_name(entity)
    entity_type = _entity_type(entity)

    if messages:
        preview = "\n".join(
            f"• {item['snippet']}" + (
                f" — {item['sender']}" if item.get("sender") else ""
            )
            for item in messages[: min(len(messages), 5)]
        )
        text = (
            f"В чате '{entity_name}' найдено {len(messages)} сообщений по запросу '{query}'."\
            "\n" + preview + ("\n…" if len(messages) > 5 else "")
        )
    else:
        text = f"В чате '{entity_name}' нет результатов по запросу '{query}'."

    structured: StructuredContent = {
        "chat": {
            "id": getattr(entity, "id", None),
            "type": entity_type,
            "title": entity_name,
            "username": getattr(entity, "username", None),
        },
        "query": query,
        "messages": messages,
    }
    return _text_response(text), structured
