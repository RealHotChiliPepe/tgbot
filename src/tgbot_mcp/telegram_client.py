"""Async helpers for interacting with Telegram via Telethon."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl import types
from telethon.utils import get_display_name, get_peer_id

from .config import (
    FetchMessagesRequest,
    GetChatRequest,
    ListDialogsRequest,
    SearchMessagesRequest,
    SendMessageRequest,
    TelegramSettings,
)


class TelegramClientManager:
    """Lazily creates a Telethon client and exposes high-level helpers."""

    def __init__(self, settings: TelegramSettings) -> None:
        self._settings = settings
        self._client: TelegramClient | None = None
        self._lock = asyncio.Lock()

    async def get_client(self) -> TelegramClient:
        """Return a connected `TelegramClient`, creating it if needed."""

        async with self._lock:
            if self._client is None:
                session_source: str | StringSession
                if self._settings.session_string:
                    session_source = StringSession(self._settings.session_string)
                else:
                    session_source = str(self._settings.session_file)

                self._client = TelegramClient(
                    session_source,
                    self._settings.api_id,
                    self._settings.api_hash,
                    connection_retries=self._settings.request_retries,
                )

            assert self._client is not None
            if not self._client.is_connected():
                await self._client.connect()

            if not await self._client.is_user_authorized():
                raise RuntimeError(
                    "The Telegram session is not authorized. Run `telegram-authorize` to sign in first."
                )

            return self._client

    async def list_dialogs(self, params: ListDialogsRequest) -> list[dict[str, Any]]:
        """Return dialogs that match the provided filters."""

        client = await self.get_client()
        dialogs: list[dict[str, Any]] = []

        async for dialog in client.iter_dialogs(limit=params.limit, ignore_migrated=True):
            if not self._should_include_dialog(dialog, params):
                continue

            entity = dialog.entity
            peer_id = str(get_peer_id(entity))
            title = get_display_name(entity)
            if params.search and params.search.lower() not in title.lower():
                continue

            dialogs.append(
                {
                    "id": peer_id,
                    "title": title,
                    "type": self._entity_type(entity),
                    "username": getattr(entity, "username", None),
                    "unread_count": dialog.unread_count,
                    "pinned": dialog.pinned,
                    "is_verified": getattr(entity, "verified", False),
                    "is_restricted": getattr(entity, "restricted", False),
                }
            )

        dialogs.sort(key=lambda item: item["title"].lower())
        return dialogs

    async def get_chat(self, params: GetChatRequest) -> dict[str, Any]:
        """Fetch detailed information about a chat."""

        entity = await self._resolve_chat(params.chat)
        return self._serialize_entity(entity)

    async def fetch_recent_messages(self, params: FetchMessagesRequest) -> list[dict[str, Any]]:
        """Return the most recent messages from a chat."""

        client = await self.get_client()
        entity = await self._resolve_chat(params.chat)
        messages: list[dict[str, Any]] = []

        async for message in client.iter_messages(
            entity,
            limit=params.limit,
            offset_id=params.offset_id,
        ):
            messages.append(self._serialize_message(message))

        return messages

    async def search_messages(self, params: SearchMessagesRequest) -> list[dict[str, Any]]:
        """Search messages within a chat."""

        client = await self.get_client()
        entity = await self._resolve_chat(params.chat)
        results: list[dict[str, Any]] = []

        async for message in client.iter_messages(
            entity,
            search=params.query,
            limit=params.limit,
            offset_id=params.offset_id,
        ):
            results.append(self._serialize_message(message))

        return results

    async def send_message(self, params: SendMessageRequest) -> dict[str, Any]:
        """Send a message to a chat and return the sent message."""

        client = await self.get_client()
        entity = await self._resolve_chat(params.chat)

        try:
            sent = await client.send_message(
                entity,
                params.message,
                reply_to=params.reply_to,
            )
        except FloodWaitError as exc:  # pragma: no cover - runtime guard
            raise RuntimeError(
                f"Telegram rate limited the request. Please retry after {exc.seconds} seconds"
            ) from exc

        return self._serialize_message(sent)

    async def close(self) -> None:
        """Disconnect the underlying Telethon client if it is running."""

        async with self._lock:
            if self._client and self._client.is_connected():
                await self._client.disconnect()

    async def _resolve_chat(self, chat: str | int) -> types.EntityLike:
        """Resolve a chat identifier into a Telethon entity."""

        client = await self.get_client()
        identifier: Any = chat

        if isinstance(chat, str):
            stripped = chat.strip()
            if stripped.startswith("@"):
                identifier = stripped
            else:
                try:
                    identifier = int(stripped)
                except ValueError:
                    identifier = stripped
        return await client.get_entity(identifier)

    @staticmethod
    def _entity_type(entity: types.TypeEntity) -> str:
        if isinstance(entity, types.User):
            return "user"
        if isinstance(entity, types.Channel):
            return "channel" if not entity.megagroup else "supergroup"
        if isinstance(entity, types.Chat):
            return "group"
        return entity.__class__.__name__.lower()

    def _should_include_dialog(self, dialog: Any, params: ListDialogsRequest) -> bool:
        if dialog.is_user and not params.include_private:
            return False
        if dialog.is_channel and not params.include_channels:
            return False
        return True

    @staticmethod
    def _serialize_message(message: types.Message) -> dict[str, Any]:
        reply_to = None
        if message.reply_to:
            reply_to = getattr(message.reply_to, "reply_to_msg_id", None)

        media_summary = None
        if message.media:
            media_summary = message.media.__class__.__name__

        peer_id = None
        if message.peer_id is not None:
            try:
                peer_id = str(get_peer_id(message.peer_id))
            except Exception:  # pragma: no cover - defensive fallback
                peer_id = None

        return {
            "id": message.id,
            "date": _format_datetime(message.date),
            "message": message.message or "",
            "sender_id": message.sender_id,
            "chat_id": peer_id,
            "is_outgoing": message.out,
            "reply_to": reply_to,
            "media": media_summary,
        }

    @staticmethod
    def _serialize_entity(entity: types.TypeEntity) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": str(get_peer_id(entity)),
            "title": get_display_name(entity),
            "type": TelegramClientManager._entity_type(entity),
            "username": getattr(entity, "username", None),
            "phone": getattr(entity, "phone", None),
        }

        if isinstance(entity, types.User):
            data.update(
                {
                    "first_name": entity.first_name,
                    "last_name": entity.last_name,
                    "bot": entity.bot,
                    "verified": entity.verified,
                }
            )
        elif isinstance(entity, types.Channel):
            data.update(
                {
                    "participants_count": getattr(entity, "participants_count", None),
                    "megagroup": entity.megagroup,
                    "verified": entity.verified,
                    "restricted": entity.restricted,
                    "scam": entity.scam,
                }
            )
        elif isinstance(entity, types.Chat):
            data.update(
                {
                    "participants_count": getattr(entity, "participants_count", None),
                }
            )

        return data


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=None).isoformat() + "Z"
