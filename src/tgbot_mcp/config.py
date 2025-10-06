"""Загрузка конфигурации Telegram из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SESSION_PATH = Path.home() / ".tgbot_mcp" / "telegram.session"

def _load_dotenv_if_available() -> None:
    """Подгружает файл .env, если установлен python-dotenv."""
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:  # pragma: no cover - зависимость не обязательна
        return

    load_dotenv()


@dataclass(slots=True)
class TelegramConfig:
    """Настройки подключения к Telegram."""

    api_id: int
    api_hash: str
    session_path: str | None = None
    session_string: str | None = None

    @classmethod
    def from_environment(cls) -> "TelegramConfig":
        """Создаёт конфигурацию из переменных окружения.

        Требуемые переменные:
            TELEGRAM_API_ID    – числовой идентификатор приложения
            TELEGRAM_API_HASH  – секретный ключ приложения

        Необязательные переменные:
            TELEGRAM_SESSION_STRING – строка сессии Telethon
            TELEGRAM_SESSION_PATH   – путь к файлу сессии (если строка не указана)
        """

        _load_dotenv_if_available()

        api_id_raw = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        session_string = os.getenv("TELEGRAM_SESSION_STRING")
        session_path = os.getenv("TELEGRAM_SESSION_PATH")

        missing: list[str] = []
        if not api_id_raw:
            missing.append("TELEGRAM_API_ID")
        if not api_hash:
            missing.append("TELEGRAM_API_HASH")

        if missing:
            hint = ", ".join(missing)
            raise RuntimeError(
                "Не найдены обязательные переменные окружения: "
                f"{hint}. Укажите их в окружении или файле .env."
            )

        try:
            api_id = int(api_id_raw)
        except ValueError as exc:  # pragma: no cover - валидируем явно
            raise RuntimeError("TELEGRAM_API_ID должен быть целым числом") from exc

        if not session_string and not session_path:
            session_path = str(DEFAULT_SESSION_PATH)

        return cls(
            api_id=api_id,
            api_hash=api_hash,
            session_path=session_path,
            session_string=session_string,
        )

    def resolve_session(self) -> Any:
        """Возвращает значение сессии для Telethon."""
        if self.session_string:
            from telethon.sessions import StringSession

            return StringSession(self.session_string)

        session_path = Path(self.session_path or DEFAULT_SESSION_PATH).expanduser()
        session_path.parent.mkdir(parents=True, exist_ok=True)
        return str(session_path)
