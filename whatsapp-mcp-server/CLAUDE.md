# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Python MCP (Model Context Protocol) server component of a WhatsApp integration system. It allows AI assistants like Claude to interact with WhatsApp - searching messages, reading conversations, and sending messages/media.

The full system consists of two components in the parent `whatsapp-mcp/` directory:
- **whatsapp-mcp-server/** (this directory): Python MCP server that exposes WhatsApp tools to Claude
- **whatsapp-bridge/**: Go application that connects to WhatsApp's web API via whatsmeow library

## Build & Run Commands

```bash
# Run the MCP server (from this directory)
uv run main.py

# Run the WhatsApp bridge (must be running for MCP server to work)
cd ../whatsapp-bridge && go run main.go

# Install dependencies
uv sync
```

## Architecture

### Communication Flow
1. Claude sends requests to the Python MCP server (`main.py`)
2. MCP server either:
   - Queries SQLite database directly for read operations (messages, chats, contacts)
   - Calls Go bridge REST API (`localhost:8080`) for write operations (send messages/media)
3. Go bridge maintains WhatsApp connection and keeps SQLite database synced

### Key Files
- `main.py`: FastMCP server entry point - defines all MCP tools (`@mcp.tool()` decorators)
- `whatsapp.py`: Core logic - database queries (SQLite), REST API calls to bridge, data classes (`Message`, `Chat`, `Contact`)
- `audio.py`: FFmpeg wrapper for converting audio files to Opus OGG format (required for voice messages)

### Data Storage
- SQLite database at `../whatsapp-bridge/store/messages.db`
- Tables: `chats` (jid, name, last_message_time), `messages` (id, chat_jid, sender, content, timestamp, media fields)
- Media files downloaded to `../whatsapp-bridge/store/{chat_jid}/`

### JID Format
- Individual chats: `{phone_number}@s.whatsapp.net`
- Group chats: `{group_id}@g.us`

## MCP Tools Exposed

Read operations (query SQLite directly):
- `search_contacts`, `list_messages`, `list_chats`, `get_chat`
- `get_direct_chat_by_contact`, `get_contact_chats`, `get_last_interaction`, `get_message_context`

Write operations (call Go bridge API):
- `send_message`, `send_file`, `send_audio_message`, `download_media`

## Dependencies

- Python 3.11+
- `mcp[cli]` - Model Context Protocol framework
- `httpx`, `requests` - HTTP clients for bridge communication
- Go bridge must be running on `localhost:8080`
- FFmpeg (optional) - for audio format conversion
