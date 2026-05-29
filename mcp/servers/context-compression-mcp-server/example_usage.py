#!/usr/bin/env python3
"""
Example usage script for Context Compression MCP Server.

This script demonstrates how to interact with the MCP server programmatically.
Note: This is for demonstration purposes. In practice, you would use an MCP client.
"""

import json
import subprocess
import time
from typing import Dict, Any


def call_mcp_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate calling an MCP tool (for demonstration purposes).
    In practice, this would be handled by your MCP client.
    """
    print(f"Calling {tool_name} with params: {json.dumps(params, indent=2)}")
    
    # This is a simulation - replace with actual MCP client calls
    if tool_name == "store_context":
        return {
            "status": "success",
            "id": "ctx_example_123",
            "original_size": len(params.get("data", "")),
            "compressed_size": len(params.get("data", "")) // 3,  # Simulated compression
            "compression_ratio": 0.33,
            "compression_method": "zlib"
        }
    elif tool_name == "retrieve_context":
        return {
            "status": "success",
            "id": params["context_id"],
            "title": "Example Context",
            "data": "This is example context data that was stored and compressed.",
            "tags": ["example", "demo"],
            "metadata": {
                "original_size": 100,
                "compressed_size": 33,
                "compression_method": "zlib",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    else:
        return {"status": "error", "message": "Tool not implemented in example"}


def main():
    """Demonstrate basic usage patterns."""
    print("Context Compression MCP Server - Usage Example")
    print("=" * 50)
    
    # Example 1: Store context
    print("\n1. Storing context data...")
    store_result = call_mcp_tool("store_context", {
        "data": "This is a large piece of context data that would benefit from compression. " * 10,
        "title": "Example Large Context",
        "tags": ["example", "large", "demo"]
    })
    
    if store_result["status"] == "success":
        context_id = store_result["id"]
        print(f"✓ Context stored with ID: {context_id}")
        print(f"  Original size: {store_result['original_size']} bytes")
        print(f"  Compressed size: {store_result['compressed_size']} bytes")
        print(f"  Compression ratio: {store_result['compression_ratio']:.2%}")
    else:
        print(f"✗ Failed to store context: {store_result}")
        return
    
    # Example 2: Retrieve context
    print("\n2. Retrieving context data...")
    retrieve_result = call_mcp_tool("retrieve_context", {
        "context_id": context_id
    })
    
    if retrieve_result["status"] == "success":
        print(f"✓ Context retrieved: {retrieve_result['title']}")
        print(f"  Data length: {len(retrieve_result['data'])} characters")
        print(f"  Tags: {', '.join(retrieve_result['tags'])}")
        print(f"  Created: {retrieve_result['metadata']['created_at']}")
    else:
        print(f"✗ Failed to retrieve context: {retrieve_result}")
    
    # Example 3: Search contexts
    print("\n3. Searching contexts...")
    search_result = call_mcp_tool("search_contexts", {
        "query": "example",
        "limit": 5
    })
    
    if search_result.get("status") == "success":
        print(f"✓ Found {search_result.get('count', 0)} matching contexts")
    else:
        print("✗ Search not implemented in this example")
    
    print("\n" + "=" * 50)
    print("Example complete! In a real setup:")
    print("1. Start the MCP server: uv run fastmcp run server.py")
    print("2. Configure your MCP client with the server")
    print("3. Use the tools through your MCP client interface")


if __name__ == "__main__":
    main()