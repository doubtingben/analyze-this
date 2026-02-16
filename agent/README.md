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
- Supports multiple MCP servers (SSE and stdio transports).
- Prefixes tool names with server name when multiple servers are configured.
- Powered by OpenRouter-compatible chat completions.
