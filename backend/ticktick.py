"""
TickTick Kanban Board API client.

Wraps the TickTick Open API v1 to manage tasks and columns (sections)
within a kanban project. Designed for MCP tool consumption.
"""

import os
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.ticktick.com/open/v1"

TICKTICK_ACCESS_TOKEN = os.getenv("TICKTICK_ACCESS_TOKEN", "")
TICKTICK_PROJECT_ID = os.getenv("TICKTICK_PROJECT_ID", "")


class TickTickClient:
    """Async client for the TickTick Open API v1."""

    def __init__(
        self,
        access_token: str = TICKTICK_ACCESS_TOKEN,
        project_id: str = TICKTICK_PROJECT_ID,
    ):
        self.access_token = access_token
        self.project_id = project_id
        self._headers = {"Authorization": f"Bearer {self.access_token}"}

    def _check_config(self) -> Optional[str]:
        """Return an error string if not configured, else None."""
        if not self.access_token:
            return "Error: TICKTICK_ACCESS_TOKEN is not set"
        if not self.project_id:
            return "Error: TICKTICK_PROJECT_ID is not set"
        return None

    async def _get_project_data(self) -> dict:
        """Fetch full project data (tasks + sections)."""
        url = f"{BASE_URL}/project/{self.project_id}/data"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Columns (sections)
    # ------------------------------------------------------------------

    async def list_columns(self) -> str:
        """List all kanban columns/sections in the project."""
        if err := self._check_config():
            return err

        try:
            data = await self._get_project_data()
            columns = data.get("columns", [])
            if not columns:
                return "No columns found in the project."

            lines = [f"Kanban Columns ({len(columns)}):"]
            for col in columns:
                col_id = col.get("id", "?")
                col_name = col.get("name", "Untitled")
                lines.append(f"  - {col_name} (id: {col_id})")
            return "\n".join(lines)
        except Exception as e:
            logger.error("Failed to list columns: %s", e)
            return f"Error listing columns: {e}"

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    async def list_tasks(self, column_id: Optional[str] = None) -> str:
        """List tasks, optionally filtered by column."""
        if err := self._check_config():
            return err

        try:
            data = await self._get_project_data()
            tasks = data.get("tasks", [])

            if column_id:
                tasks = [t for t in tasks if t.get("columnId") == column_id]

            if not tasks:
                suffix = f" in column {column_id}" if column_id else ""
                return f"No tasks found{suffix}."

            # Build a section lookup for display
            columns = {c["id"]: c.get("name", "?") for c in data.get("columns", [])}

            lines = [f"Tasks ({len(tasks)}):"]
            for t in tasks:
                tid = t.get("id", "?")
                title = t.get("title", "Untitled")
                col_name = columns.get(t.get("columnId", ""), "None")
                priority = t.get("priority", 0)
                status_icon = "x" if t.get("status", 0) == 2 else " "
                lines.append(f"  [{status_icon}] {title}")
                lines.append(f"      id: {tid} | column: {col_name} | priority: {priority}")
            return "\n".join(lines)
        except Exception as e:
            logger.error("Failed to list tasks: %s", e)
            return f"Error listing tasks: {e}"

    async def get_task(self, task_id: str) -> str:
        """Get details of a specific task."""
        if err := self._check_config():
            return err

        try:
            data = await self._get_project_data()
            columns = {c["id"]: c.get("name", "?") for c in data.get("columns", [])}
            tasks = data.get("tasks", [])
            task = next((t for t in tasks if t.get("id") == task_id), None)

            if not task:
                return f"Task '{task_id}' not found."

            col_name = columns.get(task.get("columnId", ""), "None")
            status_label = "Complete" if task.get("status", 0) == 2 else "Open"
            lines = [
                f"Task: {task.get('title', 'Untitled')}",
                f"  ID:       {task.get('id')}",
                f"  Status:   {status_label}",
                f"  Column:   {col_name}",
                f"  Priority: {task.get('priority', 0)}",
            ]
            if task.get("content"):
                lines.append(f"  Content:  {task['content']}")
            if task.get("dueDate"):
                lines.append(f"  Due:      {task['dueDate']}")
            if task.get("tags"):
                lines.append(f"  Tags:     {', '.join(task['tags'])}")
            return "\n".join(lines)
        except Exception as e:
            logger.error("Failed to get task: %s", e)
            return f"Error getting task: {e}"

    async def create_task(
        self,
        title: str,
        content: Optional[str] = None,
        column_id: Optional[str] = None,
        priority: int = 0,
        due_date: Optional[str] = None,
    ) -> str:
        """Create a new task in the kanban board."""
        if err := self._check_config():
            return err

        try:
            payload: dict = {
                "title": title,
                "projectId": self.project_id,
                "priority": priority,
            }
            if content:
                payload["content"] = content
            if column_id:
                payload["columnId"] = column_id
            if due_date:
                payload["dueDate"] = due_date

            url = f"{BASE_URL}/task"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()
                task = resp.json()

            return f"Created task: {task.get('title', title)} (id: {task.get('id', '?')})"
        except Exception as e:
            logger.error("Failed to create task: %s", e)
            return f"Error creating task: {e}"

    async def update_task(
        self,
        task_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        priority: Optional[int] = None,
        due_date: Optional[str] = None,
    ) -> str:
        """Update an existing task's fields."""
        if err := self._check_config():
            return err

        try:
            # Fetch current task data first
            data = await self._get_project_data()
            tasks = data.get("tasks", [])
            task = next((t for t in tasks if t.get("id") == task_id), None)
            if not task:
                return f"Task '{task_id}' not found."

            # Build update payload from current task, overriding supplied fields
            payload = {
                "id": task_id,
                "projectId": self.project_id,
                "title": title if title is not None else task.get("title", ""),
            }
            if content is not None:
                payload["content"] = content
            elif task.get("content"):
                payload["content"] = task["content"]
            if priority is not None:
                payload["priority"] = priority
            else:
                payload["priority"] = task.get("priority", 0)
            if due_date is not None:
                payload["dueDate"] = due_date
            elif task.get("dueDate"):
                payload["dueDate"] = task["dueDate"]
            # Preserve column assignment
            if task.get("columnId"):
                payload["columnId"] = task["columnId"]

            url = f"{BASE_URL}/task/{task_id}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()
                updated = resp.json()

            return f"Updated task: {updated.get('title', '')} (id: {task_id})"
        except Exception as e:
            logger.error("Failed to update task: %s", e)
            return f"Error updating task: {e}"

    async def delete_task(self, task_id: str) -> str:
        """Delete a task."""
        if err := self._check_config():
            return err

        try:
            url = f"{BASE_URL}/task/{self.project_id}/{task_id}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(url, headers=self._headers)
                resp.raise_for_status()
            return f"Deleted task {task_id}."
        except Exception as e:
            logger.error("Failed to delete task: %s", e)
            return f"Error deleting task: {e}"

    async def complete_task(self, task_id: str) -> str:
        """Mark a task as complete."""
        if err := self._check_config():
            return err

        try:
            url = f"{BASE_URL}/project/{self.project_id}/task/{task_id}/complete"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, headers=self._headers)
                resp.raise_for_status()
            return f"Completed task {task_id}."
        except Exception as e:
            logger.error("Failed to complete task: %s", e)
            return f"Error completing task: {e}"

    async def move_task(self, task_id: str, column_id: str) -> str:
        """Move a task to a different kanban column."""
        if err := self._check_config():
            return err

        try:
            # Fetch current task data
            data = await self._get_project_data()
            tasks = data.get("tasks", [])
            task = next((t for t in tasks if t.get("id") == task_id), None)
            if not task:
                return f"Task '{task_id}' not found."

            # Update with new column
            payload = {
                "id": task_id,
                "projectId": self.project_id,
                "title": task.get("title", ""),
                "columnId": column_id,
            }
            if task.get("content"):
                payload["content"] = task["content"]
            payload["priority"] = task.get("priority", 0)

            url = f"{BASE_URL}/task/{task_id}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=self._headers)
                resp.raise_for_status()

            columns = {c["id"]: c.get("name", "?") for c in data.get("columns", [])}
            col_name = columns.get(column_id, column_id)
            return f"Moved task '{task.get('title', task_id)}' to column '{col_name}'."
        except Exception as e:
            logger.error("Failed to move task: %s", e)
            return f"Error moving task: {e}"
