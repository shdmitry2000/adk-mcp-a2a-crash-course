import json
import os
import re
import sqlite3
import asyncio
import logging
from typing import Dict, List, Any, Optional
from google.adk.agents.llm_agent import Agent

from google.adk.models.lite_llm import LiteLlm
from mcp import StdioServerParameters

# Configure logging to prevent interference with user interaction
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Disable litellm debug logging
import litellm
litellm.set_verbose = False
os.environ['LITELLM_LOG'] = 'ERROR'

# Import the custom MCP toolset with timeout fixes
from utils.custom_adk_patches import CustomMCPToolset

from .prompt import dba_agent_prompt, get_dba_prompt_with_schema

# Try to import sqlglot for advanced SQL analysis
try:
    import sqlglot
    import sqlglot.expressions as exp
    SQLGLOT_AVAILABLE = True
except ImportError:
    SQLGLOT_AVAILABLE = False
    sqlglot = None
    exp = None

# Global schema cache
_schema_cache: Optional[str] = None
_schema_loaded: bool = False

def extract_sql_from_response(response: str) -> Optional[str]:
    """Extract the SQL statement from the model's response."""
    # Look for a code block or a line starting with 'SQL:'
    sql_match = re.search(r'SQL:\s*([\s\S]+?)(?:\n\n|$)', response, re.IGNORECASE)
    if sql_match:
        sql = sql_match.group(1).strip()
        # Remove markdown code block markers if present
        sql = re.sub(r'^```sql|```$', '', sql, flags=re.MULTILINE).strip()
        return sql
    
    # Fallback: look for SELECT statement in code blocks
    code_block_match = re.search(r'```(?:sql)?\s*(SELECT[\s\S]+?)```', response, re.IGNORECASE)
    if code_block_match:
        return code_block_match.group(1).strip()
    
    # Fallback: look for the first SELECT statement
    select_match = re.search(r'(SELECT[\s\S]+?;?)', response, re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()
    
    return None

def is_safe_sql(sql: str) -> bool:
    """Ensure only SELECT statements are executed."""
    return sql.strip().upper().startswith('SELECT')

def query_banking_sql(user_question: str, user_context: Optional[dict] = None) -> dict:
    """
    A simple tool function that demonstrates the old SQL workflow.
    This function takes a user question and context and returns a formatted response.
    It's designed to work as a tool within the ADK agent framework.
    
    Returns: {'status': 'success', 'message': ..., 'user_question': ..., 'user_context': ...}
    """
    try:
        logger.debug(f"Query processing started for: {user_question}")
        
        if user_context:
            logger.debug(f"Using user context: {user_context}")
        else:
            logger.debug("No user context provided - will need to establish context first")
        
        # This function now just demonstrates the workflow
        # The actual SQL generation and execution will be handled by the MCP tools
        # through the agent's normal workflow
        
        return {
            'status': 'success',
            'message': f'Query received: "{user_question}". Use get_schema to see database structure, then read_query to execute SQL.',
            'user_question': user_question,
            'user_context': user_context or {},
            'workflow_step': 'Use MCP tools: 1) get_schema, 2) generate SQL, 3) read_query'
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': f'Unexpected error in query_banking_sql: {str(e)}',
            'user_question': user_question,
            'user_context': user_context or {}
        }

def get_cached_schema() -> Optional[str]:
    """Get the cached schema if available."""
    return _schema_cache if _schema_loaded else None

def cache_schema(schema_text: str) -> None:
    """Cache the schema for future use."""
    global _schema_cache, _schema_loaded
    _schema_cache = schema_text
    _schema_loaded = True
    logger.info(f"Database schema cached ({len(schema_text)} characters)")

def auto_cache_schema_tool(schema_result: str) -> dict:
    """
    Tool function that automatically caches the schema when get_schema is called.
    This intercepts schema results and caches them for future use.
    """
    try:
        if schema_result and len(schema_result) > 100:  # Basic validation
            cache_schema(schema_result)
            return {
                'status': 'success',
                'message': f'Schema cached successfully ({len(schema_result)} characters)',
                'cached': True
            }
        else:
            return {
                'status': 'error', 
                'message': 'Invalid schema result received',
                'cached': False
            }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error caching schema: {str(e)}',
            'cached': False
        }

def set_user_context(account_id: Optional[int] = None, customer_id: Optional[int] = None, person_id: Optional[int] = None) -> dict:
    """
    Set the user context for the current session.
    
    Args:
        account_id: The user's account ID (optional)
        customer_id: The user's customer ID (optional)  
        person_id: The user's person ID (optional)
        
    Returns:
        Dict containing status and the context that was set
    """
    context = {}
    
    # Only include provided parameters
    if account_id is not None:
        context['AccountID'] = account_id
    if customer_id is not None:
        context['CustomerID'] = customer_id
    if person_id is not None:
        context['PersonID'] = person_id
    
    if not context:
        return {
            'status': 'error',
            'message': 'No user context provided. Please specify at least one of: account_id, customer_id, or person_id',
            'context': {}
        }
    
    # Create a readable message
    context_parts = []
    for key, value in context.items():
        context_parts.append(f"{key}={value}")
    
    return {
        'status': 'success',
        'message': f'User context set to {", ".join(context_parts)}',
        'context': context
    }

def create_dba_agent() -> Agent:
    """Create the DBA agent with MCP database tools and enhanced banking-specific prompts."""
    
    # Create MCP toolset with the database server
    mcp_toolset = CustomMCPToolset(
        connection_params=StdioServerParameters(
            command="uv",
            args=["run", "mcp-db-server"],
            cwd=os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp")
        ),
        tool_filter=["get_schema", "read_query"]
    )
    
    # Get the cached schema if available
    cached_schema = get_cached_schema()
    
    # Use the enhanced banking-specific prompt system
    # This includes comprehensive schema, security rules, examples, and banking domain knowledge
    if cached_schema:
        instruction = get_dba_prompt_with_schema(cached_schema)
        logger.info(f"Creating DBA agent with cached schema and banking-specific prompt ({len(cached_schema)} characters)")
    else:
        instruction = dba_agent_prompt
        logger.info("Creating DBA agent with banking-specific prompt - will load schema on first use")
    
    return Agent(
        name="dba_agent",
        model=LiteLlm(model="vertex_ai/gemini-2.5-flash"),
        description="A banking SQL assistant with comprehensive domain knowledge, security rules, and example patterns.",
        instruction=instruction,
        tools=[mcp_toolset, set_user_context, query_banking_sql, auto_cache_schema_tool],
    )

# Export the root agent for ADK CLI
root_agent = create_dba_agent()
