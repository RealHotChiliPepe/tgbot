"""Командный интерфейс для управления MCP-сервером."""

from __future__ import annotations

import asyncio
from getpass import getpass
from pathlib import Path
from typing import Optional

import typer
from telethon import TelegramClient
from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError
from telethon.sessions import StringSession

from .config import DEFAULT_SESSION_PATH
from .server import run_stdio_server
from .telegram_service import TelegramService

app = typer.Typer(add_completion=False, help="Управление мостом Telegram ↔ MCP")


async def _login_async(
    api_id: int,
    api_hash: str,
    *,
    session_path: Optional[str],
    as_string: bool,
) -> None:
    session: str | StringSession
    if as_string:
        session = StringSession()
    else:
        session_path = session_path or str(DEFAULT_SESSION_PATH)
        session_file = Path(session_path).expanduser()
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session = str(session_file)

    client = TelegramClient(session, api_id, api_hash, system_version="tgbot-mcp", device_model="CLI", lang_code="ru")
    await client.connect()

    if not await client.is_user_authorized():
        phone = typer.prompt("Введите номер телефона в формате +71234567890")
        try:
            await client.send_code_request(phone)
        except Exception as exc:  # pragma: no cover - зависит от сети
            await client.disconnect()
            raise typer.BadParameter(f"Не удалось отправить код: {exc}")

        code = typer.prompt("Введите код из Telegram (без пробелов)")
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            password = getpass("Двухфакторный пароль: ")
            await client.sign_in(password=password)
        except PhoneCodeInvalidError as exc:
            await client.disconnect()
            raise typer.BadParameter("Введён неверный код подтверждения") from exc
        except PhoneCodeExpiredError as exc:
            await client.disconnect()
            raise typer.BadParameter("Срок действия кода истёк, запросите новый") from exc

    session_value = client.session.save()
    await client.disconnect()

    if as_string:
        typer.echo("Скопируйте значение и установите TELEGRAM_SESSION_STRING:")
        typer.echo(session_value)
    else:
        assert session_path is not None
        typer.echo(f"Сессия сохранена: {session_path}")
        typer.echo("Установите переменную TELEGRAM_SESSION_PATH и TELEGRAM_API_ID/TELEGRAM_API_HASH для запуска сервера.")


@app.command()
def login(
    api_id: Optional[int] = typer.Option(None, help="Значение TELEGRAM_API_ID", envvar="TELEGRAM_API_ID"),
    api_hash: Optional[str] = typer.Option(None, help="Значение TELEGRAM_API_HASH", envvar="TELEGRAM_API_HASH"),
    session_path: Optional[str] = typer.Option(None, help="Путь для сохранения .session", envvar="TELEGRAM_SESSION_PATH"),
    as_string: bool = typer.Option(False, help="Вывести сессию как строку вместо файла"),
) -> None:
    """Проходит интерактивный вход в Telegram и сохраняет сессию."""

    if api_id is None:
        api_id = typer.prompt("Введите TELEGRAM_API_ID", type=int)
    if api_hash is None:
        api_hash = typer.prompt("Введите TELEGRAM_API_HASH", hide_input=True)

    asyncio.run(_login_async(api_id, api_hash, session_path=session_path, as_string=as_string))


@app.command()
def run() -> None:
    """Запускает MCP сервер по протоколу stdio (для ChatGPT)."""

    run_stdio_server()


@app.command()
def whoami() -> None:
    """Проверяет авторизацию и выводит данные текущего пользователя."""

    async def _whoami() -> None:
        service = TelegramService()
        client = await service.get_client()
        me = await client.get_me()
        name = " ".join(filter(None, [me.first_name, me.last_name])) if me else "Неизвестно"
        username = f"@{me.username}" if me and me.username else ""
        typer.echo(f"ID: {me.id if me else 'N/A'} {name} {username}".strip())
        await service.stop()

    try:
        asyncio.run(_whoami())
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
