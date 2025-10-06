"""Асинхронный доступ к Telegram через Telethon."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from telethon import TelegramClient

from .config import TelegramConfig


@dataclass(slots=True)
class TelegramService:
    """Управляет подключением Telethon и повторно использует одно соединение."""

    _config: TelegramConfig | None = None

    def __post_init__(self) -> None:
        self._client: TelegramClient | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> TelegramClient:
        """Создаёт подключение, если оно ещё не активно."""
        return await self._ensure_client()

    async def stop(self) -> None:
        """Отключается от Telegram."""
        async with self._lock:
            if self._client and self._client.is_connected():
                await self._client.disconnect()
            self._client = None

    async def get_client(self) -> TelegramClient:
        """Возвращает активный клиент Telethon."""
        return await self._ensure_client()

    async def _ensure_client(self) -> TelegramClient:
        if self._client and self._client.is_connected():
            return self._client

        async with self._lock:
            if self._client and self._client.is_connected():  # double check после ожидания
                return self._client

            config = self._config or TelegramConfig.from_environment()
            client = TelegramClient(
                config.resolve_session(),
                config.api_id,
                config.api_hash,
                system_version="tgbot-mcp",
                device_model="MCP bridge",
                lang_code="ru",
            )

            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise RuntimeError(
                    "Telegram сессия не авторизована. Выполните `tgbot-mcp login` "
                    "и убедитесь, что указаны TELEGRAM_API_ID/TELEGRAM_API_HASH."
                )

            self._config = config
            self._client = client
            return client


async def create_service(config: Optional[TelegramConfig] = None) -> TelegramService:
    """Фабрика, которую можно использовать в lifespan."""
    service = TelegramService(config)
    await service.start()
    return service
