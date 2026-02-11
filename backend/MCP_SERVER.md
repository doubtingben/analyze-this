# MCP Server for Analyze This Monitoring

This MCP (Model Context Protocol) server provides monitoring tools for the Analyze This application. It allows AI agents and other MCP clients to query user information, item status, worker queues, and error logs.

## Features

The server provides the following tools:

### 1. **get_users_info**
Get a summary of all users in the system.
- Shows total users
- Lists each user's email, total items, and last activity time
- Breaks down items by status for each user

**Parameters:**
- `limit` (optional, default: 100): Maximum number of items to scan per status

**Example:**
```json
{
  "limit": 100
}
```

### 2. **get_user_details**
Get detailed information for a specific user.
- User profile information
- Item counts by status with percentages
- Worker job counts by status
- User's tags

**Parameters:**
- `email` (required): User's email address

**Example:**
```json
{
  "email": "user@example.com"
}
```

### 3. **get_worker_queue_status**
View the current status of worker queues.
- Summary of jobs by type and status
- Individual job details including errors
- Supports filtering by job type and status

**Parameters:**
- `job_type` (optional): Filter by job type (e.g., 'analysis', 'follow_up', 'normalize')
- `status` (optional): Filter by status (e.g., 'queued', 'leased', 'completed', 'failed')
- `limit` (optional, default: 50): Maximum number of jobs to return

**Example:**
```json
{
  "job_type": "analysis",
  "status": "failed",
  "limit": 50
}
```

### 4. **get_errors**
Get error information from failed worker jobs.
- Groups errors by error message
- Shows frequency and affected users
- Provides sample job IDs for debugging

**Parameters:**
- `job_type` (optional): Filter by job type (e.g., 'analysis', 'follow_up', 'normalize')
- `limit` (optional, default: 50): Maximum number of failed jobs to analyze

**Example:**
```json
{
  "job_type": "analysis",
  "limit": 50
}
```

### 5. **get_items_by_status**
Get items filtered by their processing status.
- Lists items with given status
- Shows item details including title, user, type, and creation time
- Includes analysis overview when available

**Parameters:**
- `status` (required): Item status to filter by (e.g., 'new', 'analyzing', 'analyzed', 'timeline', 'follow_up', 'processed', 'error')
- `limit` (optional, default: 20): Maximum number of items to return

**Example:**
```json
{
  "status": "error",
  "limit": 20
}
```

## Running the Server

### Prerequisites

1. Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
# Development (uses SQLite)
export APP_ENV=development

# Production (uses Firestore)
export APP_ENV=production
```

### Start the Server

The MCP server runs over stdio (standard input/output):

```bash
cd backend
python mcp_server.py
```

### Using with MCP Clients

#### Claude Desktop Configuration

Add to your Claude Desktop MCP configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "analyze-this-monitor": {
      "command": "python",
      "args": ["/absolute/path/to/analyze-this/backend/mcp_server.py"],
      "env": {
        "APP_ENV": "production"
      }
    }
  }
}
```

#### Google ADK (Agent Development Kit)

When creating an agent with ADK, you can reference this MCP server in your agent configuration:

```python
# In your agent configuration
mcp_servers = {
    "analyze-this-monitor": {
        "command": "python",
        "args": ["/absolute/path/to/analyze-this/backend/mcp_server.py"],
        "env": {
            "APP_ENV": "production"
        }
    }
}
```

## Architecture

The MCP server:
- Uses the same database interface as the main application (`DatabaseInterface`)
- Supports both Firestore (production) and SQLite (development)
- Provides read-only access to monitoring data
- Formats output in human-readable text format

## Common Use Cases

### Monitoring User Activity
```
Use get_users_info to get an overview of all users
Then use get_user_details on specific users to drill down
```

### Debugging Worker Jobs
```
Use get_worker_queue_status to see queue state
Use get_errors to identify common failure patterns
Filter by job_type to focus on specific worker types
```

### Tracking Item Processing
```
Use get_items_by_status to find items stuck in certain states
Check 'new' status to see pending items
Check 'error' status to find failed items
```

### IRC Agent Integration
The MCP server is designed to work with IRC agents that answer questions about the application:
- "How many users do we have?"
- "What's the status of worker queues?"
- "Are there any errors in the analysis jobs?"
- "Show me items for user@example.com"

## Security Considerations

- The server provides read-only access to monitoring data
- It respects the same database access patterns as the main application
- No authentication is built into the MCP server itself; rely on transport-level security
- User emails and item content are visible through this interface

## Troubleshooting

### Server won't start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify environment variables are set correctly
- Check Python version (requires Python 3.9+)

### No data returned
- Verify APP_ENV is set correctly
- For production, ensure Firebase credentials are configured
- For development, ensure the SQLite database exists

### Database connection errors
- Check Firebase credentials in production
- Verify SQLite database path in development
- Review logs for specific error messages

## Development

To extend the server with new tools:

1. Add a new async function for your tool logic
2. Register the tool in `list_tools()`
3. Add a handler in `call_tool()`
4. Update this README with the new tool documentation

Example:
```python
async def my_new_tool(param: str) -> str:
    """Tool implementation."""
    database = await get_db()
    # Your logic here
    return "formatted output"

# In list_tools():
Tool(
    name="my_new_tool",
    description="What this tool does",
    inputSchema={...}
)

# In call_tool():
elif name == "my_new_tool":
    result = await my_new_tool(arguments.get("param"))
    return [TextContent(type="text", text=result)]
```
