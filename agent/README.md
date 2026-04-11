# AnalyzeBot Agent

An IRC agent that connects to Ergo server, uses OpenRouter for LLM responses, and MCP servers for data access.

## Setup

1.  **Dependencies**: `npm install`
2.  **Configuration**: Copy `.env` and fill in details.
    ```env
    IRC_SERVER=chat.interestedparticipant.org
    IRC_PORT=6697
    IRC_NICK=AnalyzeBot
    IRC_CHANNEL=#analyze-this
    IRC_TYPING_ENABLED=true
    IRC_TYPING_INTERVAL_MS=3000
    OPENROUTER_API_KEY=your_openrouter_api_key
    OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free

    # GCP Auth (for Firestore MCP)
    # GOOGLE_APPLICATION_CREDENTIALS=/this-run/your-key.json
    # FIREBASE_STORAGE_BUCKET=your-app.appspot.com
    IRC_PASSWORD=your_irc_password (optional)
    ```
3.  **Build**: `npm run build`
4.  **Run**: `npm start`

### Docker Authentication (GCP)
If using the Firestore MCP server in Docker, you must provide service account credentials. 
1. Place your service account JSON in the project root.
2. In your `.env`, set the path **relative to the container mount**:
   ```env
   GOOGLE_APPLICATION_CREDENTIALS=/this-run/keys.json
   ```
3. Run the container with a volume mapping:
   ```bash
   docker run --env-file .env -v $(pwd):/this-run ghcr.io/doubtingben/back-channel/agent:latest
   ```

## MCP Server Configuration

The agent supports multiple MCP servers with different transport types. Configure via a JSON file or environment variable.

### Option 1: Config File (Recommended)

Set `MCP_CONFIG_FILE` to point to a JSON configuration file:

```env
MCP_CONFIG_FILE=./mcp-config.json
```

Example `mcp-config.json`:

```json
{
  "servers": {
    "firebase": {
      "type": "sse",
      "url": "http://localhost:3000/sse"
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    },
    "sqlite": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "./data.db"]
    }
  }
}
```

### Option 2: Legacy Single URL

For backwards compatibility, you can still use a single SSE server via environment variable:

```env
MCP_SERVER_URL=http://localhost:3000/sse
```

### Server Types

#### SSE (Server-Sent Events)

For HTTP-based MCP servers:

```json
{
  "type": "sse",
  "url": "http://localhost:3000/sse"
}
```

#### Stdio (Command-based)

For file-based/command MCP servers that communicate via stdin/stdout:

```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"],
  "env": {
    "OPTIONAL_ENV_VAR": "value"
  }
}
```

## Features

- Connects to IRC with TLS.
- Joins `#analyze-this`.
- Listens for messages addressing the bot.
- Emits IRCv3 typing notifications while the bot is working on a reply.
- Supports multiple MCP servers (SSE and stdio transports).
- Prefixes tool names with server name when multiple servers are configured.
- Includes local host tools for deployment, version checks, and journald log inspection.
- Powered by OpenRouter-compatible chat completions.

## Typing Notifications

The agent can advertise that it is working by sending IRCv3 `TAGMSG` messages with the client-only `+typing` tag while a reply is being generated.

Requirements:

- the IRC server must support `message-tags`
- the user client must display typing notifications

Configuration:

- `IRC_TYPING_ENABLED`: defaults to `true`; set to `false` to disable typing notifications
- `IRC_TYPING_INTERVAL_MS`: heartbeat interval in milliseconds; defaults to `3000` and is clamped to at least 3000ms to match the IRCv3 guidance

Behavior:

- when the bot starts working, it sends `@+typing=active TAGMSG <target>`
- while work continues, it refreshes the typing signal on the same target
- when the bot finishes or errors, it sends `@+typing=done TAGMSG <target>`
- in channels, this is visible to everyone in the channel

For WeeChat, enable display with:

```weechat
/set typing.look.enabled_nicks on
/set irc.look.typing_status_nicks on
```

## Local Host Tools

When deployed through the NixOS flake, the agent also exposes a local `get_service_logs` tool for reading recent journald logs from the host.

Supported targets:

- `backend`
- `worker`
- `worker_manager`
- `worker_analysis`
- `worker_normalization`
- `worker_follow_up`
- `worker_podcast_audio`

Parameters:

- `target` (required): service group or specific unit to inspect
- `lines` (optional): number of recent lines to return, default `100`, max `500`
- `since` (optional): journald-compatible time bound such as `15 minutes ago`
- `grep` (optional): `journalctl --grep` pattern for server-side filtering

Deployment requirement:

- the `analyze-agent` system user must have access to `journalctl`, and membership in `systemd-journal` so it can read logs without sudo
