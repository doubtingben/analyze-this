#!/usr/bin/env python3
"""
MCP Server providing an Agentic Workspace for AnalyzeBot.
Allows the bot to read/write files, run python scripts, execute commands,
and maintain git repositories for debugging scraping strategies.
"""
import os
import sys
import subprocess
import tempfile
import asyncio
import logging
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

server = Server("analyze-workspace")

REPOSITORIES = [
    "https://github.com/doubtingben/analyze-this.git",
    "https://git.sr.ht/~doubtingben/framework-13"
]

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available workspace tools."""
    return [
        Tool(
            name="workspace_run_python_script",
            description="Executes a python script in the workspace using the backend's environment. Useful for testing scraping logic.",
            inputSchema={
                "type": "object",
                "properties": {
                    "script_content": {
                        "type": "string",
                        "description": "The python code to execute"
                    }
                },
                "required": ["script_content"]
            }
        ),
        Tool(
            name="workspace_run_command",
            description="Executes a shell command in the workspace (e.g. bash, git, curl). Max timeout is 60s.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="workspace_read_file",
            description="Reads the contents of a file in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute path to the file"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="workspace_write_file",
            description="Writes text content to a file in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute path to the file"
                    },
                    "content": {
                        "type": "string",
                        "description": "Text content to write"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="workspace_init_repos",
            description="Clones or updates the main repositories (analyze-this and framework-13) in the workspace.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "workspace_run_python_script":
            script_content = arguments.get("script_content")
            if not script_content:
                return [TextContent(type="text", text="Error: script_content is required")]
            
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as fp:
                fp.write(script_content)
                temp_path = fp.name
                
            try:
                result = subprocess.run(
                    [sys.executable, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.getcwd()
                )
                output = f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                return [TextContent(type="text", text=output)]
            except subprocess.TimeoutExpired:
                return [TextContent(type="text", text="Error: Script execution timed out after 60 seconds.")]
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        elif name == "workspace_run_command":
            command = arguments.get("command")
            if not command:
                return [TextContent(type="text", text="Error: command is required")]
                
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=os.getcwd()
                )
                output = f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
                return [TextContent(type="text", text=output)]
            except subprocess.TimeoutExpired:
                return [TextContent(type="text", text="Error: Command execution timed out after 60 seconds.")]
                
        elif name == "workspace_read_file":
            path = arguments.get("path")
            if not path:
                return [TextContent(type="text", text="Error: path is required")]
                
            p = Path(path)
            if not p.exists():
                return [TextContent(type="text", text=f"Error: File {path} not found.")]
            if not p.is_file():
                return [TextContent(type="text", text=f"Error: Path {path} is not a file.")]
                
            content = p.read_text(encoding="utf-8", errors="replace")
            return [TextContent(type="text", text=content)]
            
        elif name == "workspace_write_file":
            path = arguments.get("path")
            content = arguments.get("content")
            if not path or content is None:
                return [TextContent(type="text", text="Error: path and content are required")]
                
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return [TextContent(type="text", text=f"Successfully wrote {len(content)} characters to {path}")]
            
        elif name == "workspace_init_repos":
            output = []
            for repo_url in REPOSITORIES:
                repo_name = repo_url.rstrip('/').split('/')[-1]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
                    
                repo_path = Path(os.getcwd()) / repo_name
                
                if repo_path.exists() and (repo_path / ".git").exists():
                    try:
                        res = subprocess.run(["git", "pull"], cwd=str(repo_path), capture_output=True, text=True, timeout=30)
                        output.append(f"Updated {repo_name}: {res.stdout.strip() or res.stderr.strip()}")
                    except Exception as e:
                        output.append(f"Failed to update {repo_name}: {e}")
                else:
                    try:
                        res = subprocess.run(["git", "clone", repo_url], cwd=os.getcwd(), capture_output=True, text=True, timeout=60)
                        output.append(f"Cloned {repo_name} successfully.")
                    except Exception as e:
                        output.append(f"Failed to clone {repo_name}: {e}")
                        
            return [TextContent(type="text", text="\n".join(output))]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main entry point for the MCP workspace server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
