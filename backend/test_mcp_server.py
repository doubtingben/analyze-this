#!/usr/bin/env python3
"""
Test script for the Analyze This MCP Monitoring Server
This script tests all available tools without running a full MCP client.
"""
import os
import asyncio
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import the tool functions
from mcp_server import (
    get_users_info,
    get_user_details,
    get_worker_queue_status,
    get_errors,
    get_items_by_status,
    get_db
)

# Load environment variables
load_dotenv()


async def test_get_users_info():
    """Test get_users_info tool."""
    print("\n" + "=" * 80)
    print("TEST: get_users_info")
    print("=" * 80)
    try:
        result = await get_users_info(limit=100)
        print(result)
        print("\n✓ Test passed")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_get_worker_queue_status():
    """Test get_worker_queue_status tool."""
    print("\n" + "=" * 80)
    print("TEST: get_worker_queue_status")
    print("=" * 80)
    try:
        result = await get_worker_queue_status(limit=10)
        print(result)
        print("\n✓ Test passed")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_get_errors():
    """Test get_errors tool."""
    print("\n" + "=" * 80)
    print("TEST: get_errors")
    print("=" * 80)
    try:
        result = await get_errors(limit=10)
        print(result)
        print("\n✓ Test passed")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_get_items_by_status():
    """Test get_items_by_status tool."""
    print("\n" + "=" * 80)
    print("TEST: get_items_by_status (status='new')")
    print("=" * 80)
    try:
        result = await get_items_by_status(status='new', limit=5)
        print(result)
        print("\n✓ Test passed")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_database_connection():
    """Test database connection."""
    print("\n" + "=" * 80)
    print("TEST: Database Connection")
    print("=" * 80)
    try:
        db = await get_db()
        print(f"Database type: {type(db).__name__}")
        print(f"Environment: {os.getenv('APP_ENV', 'production')}")
        print("\n✓ Database connection successful")
    except Exception as e:
        print(f"\n✗ Database connection failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    print("\n" + "#" * 80)
    print("# Analyze This MCP Monitoring Server - Test Suite")
    print("#" * 80)
    print(f"\nEnvironment: {os.getenv('APP_ENV', 'production')}")

    # Test database connection first
    await test_database_connection()

    # Test all tools
    await test_get_users_info()
    await test_get_worker_queue_status()
    await test_get_errors()
    await test_get_items_by_status()

    print("\n" + "#" * 80)
    print("# All Tests Complete")
    print("#" * 80)


if __name__ == "__main__":
    asyncio.run(main())
