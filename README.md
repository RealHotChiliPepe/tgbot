# Telegram MCP Server

This project exposes your personal Telegram account through the Model Context Protocol (MCP) so that ChatGPT (or any MCP-compatible client) can list the chats you belong to, inspect their recent activity, search for messages, and send replies on your behalf.

> **Security warning:** You are granting an AI client access to your personal Telegram account. Only run the server on hardware you trust, review the available tools carefully, and consider restricting which chats the assistant can access by editing the code.

## Features

* Establishes a user session via the [Telethon](https://github.com/LonamiWebs/Telethon) library. The session can be stored either as a `.session` file or as an exported session string.
* Provides an MCP server with tools for:
  * Listing your chats and channels.
  * Retrieving metadata about a specific chat.
  * Fetching the most recent messages from a chat.
  * Searching messages in a chat.
  * Sending a message into a chat.
* Ships with a helper script (`telegram-authorize`) to create or update the Telegram session interactively before exposing it to ChatGPT.

## Prerequisites

1. Create a Telegram application to obtain an **API ID** and **API hash**: <https://my.telegram.org/apps>.
2. Install dependencies:

   ```bash
   pip install -e .
   ```

3. Create a `.env` file (or set environment variables) with your credentials:

   ```bash
   TELEGRAM_API_ID=123456
   TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
   TELEGRAM_SESSION_FILE=./telegram.session  # optional, defaults to ./telegram.session
   # TELEGRAM_SESSION_STRING=...             # optional alternative to the session file
   ```

## Authorize your account

The MCP server requires an already-authorized session. Run the helper script once to sign in and persist the session locally.

```bash
telegram-authorize
```

You will be asked for:

1. Your phone number in international format.
2. The login code sent by Telegram.
3. (Optional) Your 2FA password, if you have one enabled.

The script will either update the configured session file (`TELEGRAM_SESSION_FILE`) or print an updated session string if `TELEGRAM_SESSION_STRING` is set.

## Running the MCP server

You can launch the server in multiple transport modes depending on your MCP client:

```bash
telegram-mcp --transport stdio        # stdio transport (default)
telegram-mcp --transport sse          # SSE transport on http://127.0.0.1:8000/
telegram-mcp --transport streamable-http
```

For ChatGPT’s MCP integration you typically want the `stdio` mode. Configure ChatGPT with a command such as:

```json
{
  "command": "/usr/bin/env",
  "args": ["bash", "-lc", "cd /path/to/project && telegram-mcp --transport stdio"],
  "env": {
    "TELEGRAM_API_ID": "123456",
    "TELEGRAM_API_HASH": "0123456789abcdef0123456789abcdef",
    "TELEGRAM_SESSION_FILE": "/path/to/telegram.session"
  }
}
```

## Available MCP tools

| Tool | Description |
| --- | --- |
| `telegram_list_dialogs` | Returns chats, channels, and groups that match the provided filters. |
| `telegram_get_chat` | Retrieves metadata about a specific chat by ID or username. |
| `telegram_fetch_recent_messages` | Returns the most recent messages in a chat. |
| `telegram_search_messages` | Searches within a chat for messages matching a query string. |
| `telegram_send_message` | Sends a message to a chat. |

Each tool validates its arguments and returns structured JSON responses to make downstream processing inside ChatGPT straightforward.

## Development

* Run `ruff check .` to lint the project.
* Run `pytest` (future work) to execute tests.

## License

MIT
