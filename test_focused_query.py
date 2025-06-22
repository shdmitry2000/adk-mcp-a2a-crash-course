#!/usr/bin/env python3
"""
Focused test for the DBA agent to see if it properly gets schema and returns raw results.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dba_agent.agent import create_dba_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

async def test_account_balance_query():
    """Test a specific account balance query to see the agent workflow."""
    print('🔍 Testing: What is my account balance?')
    print('Expected: Agent should get schema, generate SQL with parameters, execute, return raw results')
    print('-' * 80)
    
    try:
        # Create the agent
        agent = create_dba_agent()
        print(f'✅ Agent created: {agent.name}')
        
        # Create ADK runner
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="dba_balance_test",
            session_service=session_service,
        )
        
        # Create session
        session_id = "balance_test_session"
        user_id = "test_user"
        
        await runner.session_service.create_session(
            app_name="dba_balance_test",
            user_id=user_id,
            session_id=session_id
        )
        
        # Test the account balance query
        question = "What is my current account balance? My AccountID is 126."
        
        print(f'🔍 User Question: {question}')
        print('-' * 80)
        
        step = 1
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=question)]),
        ):
            # Check for tool calls
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        print(f'📋 Step {step}: Tool Call')
                        print(f'   🔧 Function: {part.function_call.name}')
                        if part.function_call.args:
                            args = dict(part.function_call.args)
                            # Show query if it's a read_query call
                            if 'query' in args:
                                print(f'   📝 SQL: {args["query"]}')
                            if 'parameters' in args:
                                print(f'   🎯 Parameters: {args["parameters"]}')
                        step += 1
                    
                    if part.function_response:
                        print(f'   📊 Response from {part.function_response.name}:')
                        response_data = part.function_response.response
                        if isinstance(response_data, dict):
                            if 'error' in response_data:
                                print(f'      ❌ Error: {response_data["error"]}')
                            elif 'result' in response_data:
                                result = response_data["result"]
                                print(f'      ✅ Success: {type(result).__name__} with {len(str(result))} chars')
                                # Show first part of result if it's schema
                                if isinstance(result, str) and len(result) > 500:
                                    print(f'      📄 Preview: {result[:200]}...')
                                else:
                                    print(f'      📄 Data: {result}')
            
            # Check for final response
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response = "".join([p.text for p in event.content.parts if p.text])
                    print(f'\n📋 Final Agent Response:')
                    print(f'   {final_response}')
                break
        
        print('\n' + '=' * 80)
        print('✅ Test completed successfully!')
        
    except Exception as e:
        print(f'❌ Error during test: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_account_balance_query()) 