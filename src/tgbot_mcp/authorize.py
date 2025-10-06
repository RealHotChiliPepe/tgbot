"""Utility to create or refresh the Telegram session before running the MCP server."""

from __future__ import annotations

import asyncio
from getpass import getpass

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from .config import load_settings


async def _authorize() -> None:
    settings = load_settings()

    session_source: str | StringSession
    using_string_session = settings.session_string is not None
    if using_string_session:
        print("Using TELEGRAM_SESSION_STRING from the environment.")
        session_source = StringSession(settings.session_string)
    else:
        print(f"Using session file at {settings.session_file}.")
        session_source = str(settings.session_file)

    client = TelegramClient(session_source, settings.api_id, settings.api_hash)
    await client.connect()

    phone = input("Enter your phone number (international format, e.g. +123456789): ").strip()
    if not phone:
        raise RuntimeError("A phone number is required to authenticate with Telegram")

    if not await client.is_user_authorized():
        await client.send_code_request(phone)
        code = input("Enter the login code you received: ").strip()
        try:
            await client.sign_in(phone=phone, code=code)
        except SessionPasswordNeededError:
            password = getpass("Two-factor password: ")
            await client.sign_in(password=password)

    if using_string_session:
        string_session = client.session.save()
        print("\nCopy the following TELEGRAM_SESSION_STRING value into your environment:")
        print(string_session)
    else:
        client.session.save()
        print(f"Session file updated at {settings.session_file}")

    await client.disconnect()


def main() -> None:
    """Entry point for the `telegram-authorize` console script."""

    asyncio.run(_authorize())


if __name__ == "__main__":  # pragma: no cover
    main()
