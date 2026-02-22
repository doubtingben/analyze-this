#!/usr/bin/env python3
"""
MCP Server for Analyze This Application Monitoring
Provides tools to monitor users, items, worker queues, and errors.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from database import DatabaseInterface, FirestoreDatabase, SQLiteDatabase
from models import WorkerJobStatus, ItemStatus
from ticktick import TickTickClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
APP_ENV = os.getenv("APP_ENV", "production")

# Global database instance
db: Optional[DatabaseInterface] = None

# TickTick client (kanban board)
ticktick = TickTickClient()


async def get_db() -> DatabaseInterface:
    """Get or initialize database instance."""
    global db
    if db is None:
        if APP_ENV == "development":
            logger.info("Using SQLiteDatabase")
            db = SQLiteDatabase()
            if hasattr(db, 'init_db'):
                await db.init_db()
        else:
            logger.info("Using FirestoreDatabase")
            db = FirestoreDatabase()
    return db


def format_datetime(dt: Any) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def calculate_time_ago(dt: Any) -> str:
    """Calculate human-readable time ago string."""
    if dt is None:
        return "Never"
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except:
            return dt
    
    if not isinstance(dt, datetime):
        return str(dt)
    
    # Ensure timezone awareness
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds / 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}h ago"
    else:
        return f"{int(seconds / 86400)}d ago"


async def get_users_info(limit: int = 100) -> str:
    """Get information about all users with their items."""
    database = await get_db()
    
    # Get all users by querying items and aggregating
    # Since we don't have a direct "list all users" method, 
    # we'll need to query items and aggregate by user
    
    # For Firestore, we'll query items directly
    # For SQLite, we can query the users table
    
    # This is a workaround - ideally we'd have a list_users method
    # Let's query items with different statuses to find all users
    
    user_stats = {}
    
    # Get items for different statuses to find all users
    statuses = ['new', 'analyzing', 'analyzed', 'timeline', 'follow_up', 'processed', 'error', 'soft_deleted']
    
    for status in statuses:
        items = await database.get_items_by_status(status, limit=1000)
        for item in items:
            user_email = item.get('user_email')
            if user_email:
                if user_email not in user_stats:
                    user_stats[user_email] = {
                        'email': user_email,
                        'item_counts': {},
                        'last_activity': None,
                        'total_items': 0
                    }
                
                # Count by status
                user_stats[user_email]['item_counts'][status] = \
                    user_stats[user_email]['item_counts'].get(status, 0) + 1
                user_stats[user_email]['total_items'] += 1
                
                # Track last activity
                created_at = item.get('created_at')
                if created_at:
                    if user_stats[user_email]['last_activity'] is None:
                        user_stats[user_email]['last_activity'] = created_at
                    else:
                        if isinstance(created_at, datetime) and isinstance(user_stats[user_email]['last_activity'], datetime):
                            if created_at > user_stats[user_email]['last_activity']:
                                user_stats[user_email]['last_activity'] = created_at
    
    # Format output
    output_lines = [
        "=" * 80,
        f"USER SUMMARY (Total Users: {len(user_stats)})",
        "=" * 80,
        ""
    ]
    
    # Sort by total items descending
    sorted_users = sorted(user_stats.values(), key=lambda x: x['total_items'], reverse=True)
    
    for user in sorted_users:
        output_lines.append(f"User: {user['email']}")
        output_lines.append(f"  Total Items: {user['total_items']}")
        output_lines.append(f"  Last Activity: {calculate_time_ago(user['last_activity'])}")
        output_lines.append(f"  Items by Status:")
        for status, count in sorted(user['item_counts'].items()):
            output_lines.append(f"    - {status}: {count}")
        output_lines.append("")
    
    return "\n".join(output_lines)


async def get_user_details(email: str) -> str:
    """Get detailed information for a specific user."""
    database = await get_db()
    
    # Get user info
    user = await database.get_user(email)
    if not user:
        return f"User not found: {email}"
    
    # Get user's items
    items = await database.get_shared_items(email)
    
    # Get item counts by status
    item_counts = await database.get_user_item_counts_by_status(email)
    
    # Get worker job counts by status
    worker_counts = await database.get_user_worker_job_counts_by_status(email)
    
    # Get user tags
    tags = await database.get_user_tags(email)
    
    # Calculate last activity
    last_activity = None
    if items:
        last_activity = max((item.get('created_at') for item in items if item.get('created_at')), default=None)
    
    # Format output
    output_lines = [
        "=" * 80,
        f"USER DETAILS: {email}",
        "=" * 80,
        "",
        f"Name: {user.name or 'N/A'}",
        f"Timezone: {user.timezone}",
        f"Created: {format_datetime(user.created_at)}",
        f"Last Activity: {calculate_time_ago(last_activity)}",
        "",
        "ITEM COUNTS BY STATUS:",
    ]
    
    total_items = sum(item_counts.values())
    for status, count in sorted(item_counts.items()):
        percentage = (count / total_items * 100) if total_items > 0 else 0
        output_lines.append(f"  {status}: {count} ({percentage:.1f}%)")
    output_lines.append(f"  TOTAL: {total_items}")
    output_lines.append("")
    
    output_lines.append("WORKER JOB COUNTS BY STATUS:")
    total_jobs = sum(worker_counts.values())
    for status, count in sorted(worker_counts.items()):
        percentage = (count / total_jobs * 100) if total_jobs > 0 else 0
        output_lines.append(f"  {status}: {count} ({percentage:.1f}%)")
    output_lines.append(f"  TOTAL: {total_jobs}")
    output_lines.append("")
    
    if tags:
        output_lines.append(f"TAGS ({len(tags)}):")
        output_lines.append(f"  {', '.join(tags[:20])}")
        if len(tags) > 20:
            output_lines.append(f"  ... and {len(tags) - 20} more")
    else:
        output_lines.append("TAGS: None")
    
    return "\n".join(output_lines)


async def get_worker_queue_status(job_type: Optional[str] = None, status: Optional[str] = None, limit: int = 50) -> str:
    """Get worker queue status with optional filtering."""
    database = await get_db()
    
    # Get jobs by status
    if status == 'failed':
        jobs = await database.get_failed_worker_jobs(job_type=job_type, max_attempts=None)
        jobs = jobs[:limit]
    else:
        # We need to query jobs - let's use a workaround by getting items and checking their jobs
        # This is not ideal but works with current interface
        # For now, we'll focus on failed jobs which have a dedicated method
        if job_type:
            jobs = await database.get_failed_worker_jobs(job_type=job_type, max_attempts=None)
        else:
            jobs = await database.get_failed_worker_jobs(max_attempts=None)
        
        # Limit results
        jobs = jobs[:limit]
    
    # Format output
    output_lines = [
        "=" * 80,
        "WORKER QUEUE STATUS",
        "=" * 80,
        ""
    ]
    
    if job_type:
        output_lines.append(f"Job Type Filter: {job_type}")
    if status:
        output_lines.append(f"Status Filter: {status}")
    output_lines.append(f"Showing: {len(jobs)} jobs")
    output_lines.append("")
    
    # Group by status and job type
    stats = {}
    for job in jobs:
        job_status = job.get('status', 'unknown')
        jt = job.get('job_type', 'unknown')
        key = (jt, job_status)
        stats[key] = stats.get(key, 0) + 1
    
    output_lines.append("SUMMARY:")
    for (jt, js), count in sorted(stats.items()):
        output_lines.append(f"  {jt} / {js}: {count}")
    output_lines.append("")
    
    # Show individual jobs
    if jobs:
        output_lines.append("JOBS:")
        for job in jobs[:20]:  # Limit detail view to 20
            job_id = job.get('firestore_id', 'unknown')
            item_id = job.get('item_id', 'unknown')[:16] + "..."
            user = job.get('user_email', 'unknown')
            jt = job.get('job_type', 'unknown')
            js = job.get('status', 'unknown')
            attempts = job.get('attempts', 0)
            error = job.get('error', '')
            
            output_lines.append(f"  [{jt}] {js} - {user}")
            output_lines.append(f"    Job ID: {job_id}")
            output_lines.append(f"    Item ID: {item_id}")
            output_lines.append(f"    Attempts: {attempts}")
            if error:
                # Truncate long error messages
                error_preview = error[:100] + "..." if len(error) > 100 else error
                output_lines.append(f"    Error: {error_preview}")
            output_lines.append(f"    Created: {calculate_time_ago(job.get('created_at'))}")
            output_lines.append("")
        
        if len(jobs) > 20:
            output_lines.append(f"... and {len(jobs) - 20} more jobs")
    else:
        output_lines.append("No jobs found.")
    
    return "\n".join(output_lines)


async def get_errors(job_type: Optional[str] = None, limit: int = 50) -> str:
    """Get error information from failed worker jobs."""
    database = await get_db()
    
    # Get failed jobs
    failed_jobs = await database.get_failed_worker_jobs(job_type=job_type, max_attempts=None)
    
    # Limit results
    failed_jobs = failed_jobs[:limit]
    
    # Format output
    output_lines = [
        "=" * 80,
        "ERROR REPORT",
        "=" * 80,
        ""
    ]
    
    if job_type:
        output_lines.append(f"Job Type Filter: {job_type}")
    output_lines.append(f"Total Failed Jobs: {len(failed_jobs)}")
    output_lines.append("")
    
    # Group errors by error message
    error_groups = {}
    for job in failed_jobs:
        error_msg = job.get('error', 'Unknown error')
        jt = job.get('job_type', 'unknown')
        key = (jt, error_msg)
        
        if key not in error_groups:
            error_groups[key] = {
                'count': 0,
                'jobs': [],
                'job_type': jt,
                'error': error_msg
            }
        
        error_groups[key]['count'] += 1
        error_groups[key]['jobs'].append(job)
    
    # Sort by count descending
    sorted_errors = sorted(error_groups.values(), key=lambda x: x['count'], reverse=True)
    
    output_lines.append("ERRORS BY FREQUENCY:")
    output_lines.append("")
    
    for error_group in sorted_errors:
        count = error_group['count']
        jt = error_group['job_type']
        error_msg = error_group['error']
        
        # Truncate long error messages
        error_preview = error_msg[:200] + "..." if len(error_msg) > 200 else error_msg
        
        output_lines.append(f"[{jt}] Count: {count}")
        output_lines.append(f"  Error: {error_preview}")
        output_lines.append(f"  Affected Users:")
        
        # Show unique users affected
        users = set(job.get('user_email', 'unknown') for job in error_group['jobs'][:5])
        for user in users:
            output_lines.append(f"    - {user}")
        
        if len(error_group['jobs']) > 5:
            output_lines.append(f"    ... and {len(error_group['jobs']) - 5} more jobs")
        
        # Show sample job
        sample_job = error_group['jobs'][0]
        output_lines.append(f"  Sample Job ID: {sample_job.get('firestore_id', 'unknown')}")
        output_lines.append(f"  Last Occurrence: {calculate_time_ago(sample_job.get('updated_at'))}")
        output_lines.append("")
    
    if not sorted_errors:
        output_lines.append("No errors found!")
    
    return "\n".join(output_lines)


async def get_items_by_status(status: str, limit: int = 20) -> str:
    """Get items filtered by status."""
    database = await get_db()
    
    items = await database.get_items_by_status(status, limit=limit)
    
    # Format output
    output_lines = [
        "=" * 80,
        f"ITEMS WITH STATUS: {status}",
        "=" * 80,
        "",
        f"Total Items: {len(items)}",
        ""
    ]
    
    if items:
        for item in items:
            item_id = item.get('firestore_id', 'unknown')
            user = item.get('user_email', 'unknown')
            title = item.get('title', 'No title')
            item_type = item.get('type', 'unknown')
            created = item.get('created_at')
            
            # Truncate long titles
            title_preview = title[:60] + "..." if len(title) > 60 else title
            
            output_lines.append(f"[{item_type}] {title_preview}")
            output_lines.append(f"  ID: {item_id}")
            output_lines.append(f"  User: {user}")
            output_lines.append(f"  Created: {calculate_time_ago(created)}")
            
            # Show analysis overview if available
            analysis = item.get('analysis')
            if analysis and isinstance(analysis, dict):
                overview = analysis.get('overview', '')
                if overview:
                    overview_preview = overview[:100] + "..." if len(overview) > 100 else overview
                    output_lines.append(f"  Overview: {overview_preview}")
            
            output_lines.append("")
    else:
        output_lines.append(f"No items found with status '{status}'.")
    
    return "\n".join(output_lines)


# Create MCP server
server = Server("analyze-this-monitor")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available monitoring tools."""
    return [
        Tool(
            name="get_users_info",
            description="Get summary information about all users including their item counts and last activity",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of items to scan per status (default: 100)",
                        "default": 100
                    }
                }
            }
        ),
        Tool(
            name="get_user_details",
            description="Get detailed information for a specific user including items, worker jobs, and tags",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "User email address"
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="get_worker_queue_status",
            description="View worker queue status with optional filtering by job type and status",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_type": {
                        "type": "string",
                        "description": "Filter by job type (e.g., 'analysis', 'follow_up', 'normalize')",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'queued', 'leased', 'completed', 'failed')",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of jobs to return (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="get_errors",
            description="Get error information from failed worker jobs, grouped by error message",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_type": {
                        "type": "string",
                        "description": "Filter by job type (e.g., 'analysis', 'follow_up', 'normalize')",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of failed jobs to analyze (default: 50)",
                        "default": 50
                    }
                }
            }
        ),
        Tool(
            name="get_items_by_status",
            description="Get items filtered by status",
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Item status to filter by (e.g., 'new', 'analyzing', 'analyzed', 'timeline', 'follow_up', 'processed', 'error')"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of items to return (default: 20)",
                        "default": 20
                    }
                },
                "required": ["status"]
            }
        ),
        # ---- TickTick Kanban Board Tools ----
        Tool(
            name="ticktick_list_columns",
            description="List all kanban columns/sections in the TickTick project",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="ticktick_list_tasks",
            description="List tasks in the TickTick kanban board, optionally filtered by column",
            inputSchema={
                "type": "object",
                "properties": {
                    "column_id": {
                        "type": "string",
                        "description": "Optional column/section ID to filter tasks by"
                    }
                }
            }
        ),
        Tool(
            name="ticktick_get_task",
            description="Get details of a specific task from the TickTick kanban board",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="ticktick_create_task",
            description="Create a new task in the TickTick kanban board",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title"
                    },
                    "content": {
                        "type": "string",
                        "description": "Task description/content"
                    },
                    "column_id": {
                        "type": "string",
                        "description": "Column/section ID to place the task in"
                    },
                    "priority": {
                        "type": "number",
                        "description": "Priority level (0=none, 1=low, 3=medium, 5=high)",
                        "default": 0
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in ISO 8601 format (e.g., '2025-12-31T00:00:00+0000')"
                    }
                },
                "required": ["title"]
            }
        ),
        Tool(
            name="ticktick_update_task",
            description="Update an existing task's fields in the TickTick kanban board",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New task title"
                    },
                    "content": {
                        "type": "string",
                        "description": "New task description/content"
                    },
                    "priority": {
                        "type": "number",
                        "description": "New priority level (0=none, 1=low, 3=medium, 5=high)"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "New due date in ISO 8601 format"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="ticktick_delete_task",
            description="Delete a task from the TickTick kanban board",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to delete"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="ticktick_complete_task",
            description="Mark a task as complete in the TickTick kanban board",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to complete"
                    }
                },
                "required": ["task_id"]
            }
        ),
        Tool(
            name="ticktick_move_task",
            description="Move a task to a different kanban column in TickTick",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to move"
                    },
                    "column_id": {
                        "type": "string",
                        "description": "The target column/section ID"
                    }
                },
                "required": ["task_id", "column_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "get_users_info":
            limit = arguments.get("limit", 100)
            result = await get_users_info(limit=limit)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_user_details":
            email = arguments.get("email")
            if not email:
                return [TextContent(type="text", text="Error: email parameter is required")]
            result = await get_user_details(email=email)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_worker_queue_status":
            job_type = arguments.get("job_type")
            status = arguments.get("status")
            limit = arguments.get("limit", 50)
            result = await get_worker_queue_status(job_type=job_type, status=status, limit=limit)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_errors":
            job_type = arguments.get("job_type")
            limit = arguments.get("limit", 50)
            result = await get_errors(job_type=job_type, limit=limit)
            return [TextContent(type="text", text=result)]
        
        elif name == "get_items_by_status":
            status = arguments.get("status")
            if not status:
                return [TextContent(type="text", text="Error: status parameter is required")]
            limit = arguments.get("limit", 20)
            result = await get_items_by_status(status=status, limit=limit)
            return [TextContent(type="text", text=result)]
        
        # ---- TickTick Kanban Board Tools ----
        elif name == "ticktick_list_columns":
            result = await ticktick.list_columns()
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_list_tasks":
            column_id = arguments.get("column_id")
            result = await ticktick.list_tasks(column_id=column_id)
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_get_task":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(type="text", text="Error: task_id parameter is required")]
            result = await ticktick.get_task(task_id=task_id)
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_create_task":
            title = arguments.get("title")
            if not title:
                return [TextContent(type="text", text="Error: title parameter is required")]
            result = await ticktick.create_task(
                title=title,
                content=arguments.get("content"),
                column_id=arguments.get("column_id"),
                priority=arguments.get("priority", 0),
                due_date=arguments.get("due_date"),
            )
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_update_task":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(type="text", text="Error: task_id parameter is required")]
            result = await ticktick.update_task(
                task_id=task_id,
                title=arguments.get("title"),
                content=arguments.get("content"),
                priority=arguments.get("priority"),
                due_date=arguments.get("due_date"),
            )
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_delete_task":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(type="text", text="Error: task_id parameter is required")]
            result = await ticktick.delete_task(task_id=task_id)
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_complete_task":
            task_id = arguments.get("task_id")
            if not task_id:
                return [TextContent(type="text", text="Error: task_id parameter is required")]
            result = await ticktick.complete_task(task_id=task_id)
            return [TextContent(type="text", text=result)]

        elif name == "ticktick_move_task":
            task_id = arguments.get("task_id")
            column_id = arguments.get("column_id")
            if not task_id:
                return [TextContent(type="text", text="Error: task_id parameter is required")]
            if not column_id:
                return [TextContent(type="text", text="Error: column_id parameter is required")]
            result = await ticktick.move_task(task_id=task_id, column_id=column_id)
            return [TextContent(type="text", text=result)]

        else:
            return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
