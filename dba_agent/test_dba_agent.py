#!/usr/bin/env python3
"""
Test script for the DBA Agent.

This script demonstrates how to use the DBA agent to query a banking database
using the MCP server integration.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dba_agent.agent import (
    create_dba_agent, 
    query_database_with_context,
    get_cached_schema,
    set_cached_schema,
    analyze_bind_parameters
)

def test_sql_analysis():
    """Test the SQL analysis functionality."""
    test_queries = [
        "SELECT * FROM Account WHERE AccountID = :AccountID",
        "SELECT a.CurrentBalance FROM Account a JOIN Customer c ON a.CustomerID = c.CustomerID WHERE c.PersonID = :PersonID",
        "SELECT t.* FROM BankTransaction t JOIN Account a ON t.AccountID = a.AccountID WHERE a.CustomerID = :CustomerID AND t.TransactionDate >= :StartDate"
    ]
    
    print("🔍 Testing SQL Analysis:")
    for query in test_queries:
        print(f"\nQuery: {query}")
        analysis = analyze_bind_parameters(query)
        print(f"Parameters: {analysis['parameters']}")
        if analysis.get('tables_referenced'):
            print(f"Tables: {analysis['tables_referenced']}")

def test_agent_creation():
    """Test creating the DBA agent."""
    try:
        print("🤖 Creating DBA Agent...")
        agent = create_dba_agent()
        print(f"✅ Agent created successfully: {agent.name}")
        print(f"   Model: {agent.model}")
        print(f"   Tools: {len(agent.tools)} tool(s) available")
        return True
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        return False

def test_query_context():
    """Test the query function with user context."""
    print("\n💼 Testing Query with Context:")
    
    user_context = {
        "AccountID": 126,
        "CustomerID": 202,
        "PersonID": 59,
        "Email": "john.doe@email.com"
    }
    
    test_questions = [
        "What is my current balance?",
        "Show me my recent transactions",
        "Do I have any active loans?",
        "What cards do I have?"
    ]
    
    for question in test_questions:
        print(f"\n❓ Question: {question}")
        try:
            result = query_database_with_context(question, user_context)
            if result.get('success'):
                print(f"✅ SQL: {result.get('sql', 'N/A')}")
                print(f"📊 Response: {result.get('agent_response', 'N/A')}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
        except Exception as e:
            print(f"❌ Exception: {e}")

async def test_mcp_connection():
    """Test if the MCP server can be started and connected to."""
    print("\n🔌 Testing MCP Connection:")
    
    # Note: This would require the actual MCP server to be running
    # For now, just check if the configuration is correct
    try:
        agent = create_dba_agent()
        print("✅ Agent configured with MCP tools")
        
        # List available tools
        if hasattr(agent, 'tools') and agent.tools:
            toolset = agent.tools[0]  # First toolset
            print(f"   MCP Toolset configured with connection parameters")
            
        return True
    except Exception as e:
        print(f"❌ MCP connection test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 DBA Agent Test Suite")
    print("=" * 50)
    
    # Test 1: SQL Analysis
    test_sql_analysis()
    
    # Test 2: Agent Creation
    if not test_agent_creation():
        print("❌ Cannot proceed without agent creation")
        return
    
    # Test 3: MCP Connection
    asyncio.run(test_mcp_connection())
    
    # Test 4: Query with Context
    test_query_context()
    
    print("\n" + "=" * 50)
    print("✅ Test suite completed!")
    print("\n📝 Next Steps:")
    print("1. Start the MCP server: cd mcp && uv run mcp-db-server")
    print("2. Set up a test database with banking schema")
    print("3. Test real queries with actual data")

if __name__ == "__main__":
    main() 