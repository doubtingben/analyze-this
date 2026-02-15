#!/usr/bin/env bash
# Script to run the Analyze This MCP Monitoring Server

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables if .env exists
if [ -f "$DIR/.env" ]; then
    export $(cat "$DIR/.env" | grep -v '^#' | xargs)
fi

# Set default APP_ENV if not set
if [ -z "$APP_ENV" ]; then
    export APP_ENV="production"
fi

echo "Starting Analyze This MCP Monitoring Server..."
echo "Environment: $APP_ENV"

# Run the MCP server
python3 "$DIR/mcp_server.py"
