#!/usr/bin/env python3
"""
Auto-Generating Domain-Specific DBA Agent

This agent automatically analyzes database schemas and generates rich, 
domain-specific prompts for ANY database domain, then saves them to 
persistent memory for future use.
"""

import json
import os
import hashlib
import asyncio
from typing import Dict, List, Any, Optional
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from mcp import StdioServerParameters

# Import the custom MCP toolset
from utils.custom_adk_patches import CustomMCPToolset
from .prompt_generator import generate_domain_specific_prompt

import logging
logger = logging.getLogger(__name__)

# Memory storage for generated prompts
PROMPT_MEMORY_DIR = "prompt_memory"
DEFAULT_PROMPT_CACHE_FILE = os.path.join(PROMPT_MEMORY_DIR, "generated_prompts.json")

class AutoPromptAgent:
    """
    An agent that automatically generates domain-specific prompts by analyzing database schemas.
    """
    
    def __init__(self, mcp_config_path: str = None):
        """
        Initialize the auto-prompt agent.
        
        Args:
            mcp_config_path: Path to MCP server configuration
        """
        self.mcp_config_path = mcp_config_path or os.path.join(os.path.dirname(os.path.dirname(__file__)), "mcp")
        self.generated_prompts_cache = {}
        self.current_database_schema_hash = None
        self.current_domain_prompt = None
        
        # Ensure memory directory exists
        os.makedirs(PROMPT_MEMORY_DIR, exist_ok=True)
        
        # Load existing generated prompts from memory
        self._load_prompt_memory()
    
    def _load_prompt_memory(self):
        """Load previously generated prompts from persistent storage."""
        try:
            if os.path.exists(DEFAULT_PROMPT_CACHE_FILE):
                with open(DEFAULT_PROMPT_CACHE_FILE, 'r', encoding='utf-8') as f:
                    self.generated_prompts_cache = json.load(f)
                logger.info(f"Loaded {len(self.generated_prompts_cache)} cached prompts from memory")
            else:
                self.generated_prompts_cache = {}
                logger.info("No cached prompts found, starting fresh")
        except Exception as e:
            logger.warning(f"Failed to load prompt memory: {e}")
            self.generated_prompts_cache = {}
    
    def _save_prompt_memory(self):
        """Save generated prompts to persistent storage."""
        try:
            with open(DEFAULT_PROMPT_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.generated_prompts_cache, f, indent=2)
            logger.info(f"Saved {len(self.generated_prompts_cache)} prompts to memory")
        except Exception as e:
            logger.warning(f"Failed to save prompt memory: {e}")
    
    def _get_schema_hash(self, comprehensive_schema: str) -> str:
        """Generate a hash for the database schema to detect changes."""
        return hashlib.md5(comprehensive_schema.encode('utf-8')).hexdigest()
    
    async def get_or_generate_domain_prompt(self) -> str:
        """
        Get or generate a domain-specific prompt based on the current database schema.
        
        Returns:
            Domain-specific prompt string
        """
        
        # Step 1: Get comprehensive schema from MCP server
        logger.info("🔍 Step 1: Analyzing database schema...")
        
        try:
            comprehensive_schema = await self._get_comprehensive_schema()
        except Exception as e:
            logger.error(f"Failed to get comprehensive schema: {e}")
            return self._get_fallback_prompt()
        
        # Step 2: Check if we have a cached prompt for this schema
        schema_hash = self._get_schema_hash(comprehensive_schema)
        self.current_database_schema_hash = schema_hash
        
        if schema_hash in self.generated_prompts_cache:
            logger.info(f"✅ Found cached domain-specific prompt for schema hash: {schema_hash[:8]}...")
            self.current_domain_prompt = self.generated_prompts_cache[schema_hash]['prompt']
            return self.current_domain_prompt
        
        # Step 3: Generate new domain-specific prompt
        logger.info("🚀 Step 3: Generating new domain-specific prompt using LLM analysis...")
        
        try:
            schema_data = json.loads(comprehensive_schema)
            estimated_domain = schema_data.get('database_summary', {}).get('estimated_domain', 'unknown')
            total_tables = schema_data.get('database_summary', {}).get('total_tables', 0)
            
            logger.info(f"Database analysis: {estimated_domain} domain with {total_tables} tables")
            
            # For now, use a simplified generation approach until we fix the LiteLlm integration
            domain_prompt = await self._generate_simplified_prompt(comprehensive_schema, schema_data)
            
            # Step 4: Cache the generated prompt
            self.generated_prompts_cache[schema_hash] = {
                'prompt': domain_prompt,
                'generated_timestamp': str(asyncio.get_event_loop().time()),
                'schema_summary': {
                    'domain': estimated_domain,
                    'tables': total_tables,
                    'database_type': schema_data.get('database_type', 'unknown')
                }
            }
            
            self._save_prompt_memory()
            self.current_domain_prompt = domain_prompt
            
            logger.info(f"✅ Generated and cached new domain-specific prompt ({len(domain_prompt)} characters)")
            return domain_prompt
            
        except Exception as e:
            logger.error(f"Failed to generate domain prompt: {e}")
            return self._get_fallback_prompt()
    
    async def _get_comprehensive_schema(self) -> str:
        """Get comprehensive schema from the MCP server."""
        
        # Create MCP toolset to get schema
        mcp_toolset = CustomMCPToolset(
            connection_params=StdioServerParameters(
                command="uv",
                args=["run", "mcp-db-server"],
                cwd=self.mcp_config_path
            ),
            tool_filter=["get_schema_for_llm"]
        )
        
        # Call the comprehensive schema tool
        try:
            # Use the MCP toolset to get comprehensive schema
            tools = mcp_toolset.tools
            schema_tool = None
            
            for tool in tools:
                if tool.name == "get_schema_for_llm":
                    schema_tool = tool
                    break
            
            if not schema_tool:
                raise ValueError("get_schema_for_llm tool not found")
            
            # Execute the tool (this is a simplified approach)
            # In a real implementation, you'd call the tool properly through the agent framework
            result = await self._call_mcp_tool_directly()
            return result
            
        except Exception as e:
            logger.error(f"Failed to get comprehensive schema via MCP: {e}")
            raise
    
    async def _call_mcp_tool_directly(self) -> str:
        """
        Directly call the MCP server to get comprehensive schema.
        This is a simplified approach for demonstration.
        """
        
        # This would normally be done through the proper MCP framework
        # For now, we'll create a mock comprehensive schema
        mock_schema = {
            "database_type": "sqlite",
            "database_path": "/path/to/database.db",
            "tables": {
                "customers": {
                    "columns": [
                        {"name": "customer_id", "data_type": "INTEGER", "is_primary_key": True},
                        {"name": "email", "data_type": "VARCHAR", "is_nullable": False},
                        {"name": "status", "data_type": "VARCHAR", "is_nullable": False}
                    ],
                    "business_purpose": "user_management",
                    "detected_enums": {"status": ["ACTIVE", "INACTIVE"]},
                    "row_count": 1000
                }
            },
            "relationships": [],
            "database_summary": {
                "total_tables": 1,
                "estimated_domain": "business_management",
                "key_patterns": ["uses_id_pattern", "has_status_fields"]
            }
        }
        
        return json.dumps(mock_schema, indent=2)
    
    async def _generate_simplified_prompt(self, comprehensive_schema: str, schema_data: Dict) -> str:
        """
        Generate a simplified domain-specific prompt without complex LLM calls.
        This is a fallback approach that still creates rich prompts.
        """
        
        domain = schema_data.get('database_summary', {}).get('estimated_domain', 'business')
        tables = schema_data.get('tables', {})
        relationships = schema_data.get('relationships', [])
        
        # Build schema section
        schema_section = f"\n## DATABASE SCHEMA\n\n"
        schema_section += f"**Domain**: {domain.replace('_', ' ').title()}\n"
        schema_section += f"**Database Type**: {schema_data.get('database_type', 'unknown')}\n\n"
        
        schema_section += "**Tables and Structure:**\n\n"
        
        for table_name, table_info in tables.items():
            # Generate table description based on business purpose
            purpose = table_info.get('business_purpose', 'unknown')
            if purpose == 'user_management':
                desc = f"Stores user/customer information and account details"
            elif purpose == 'transaction_management':
                desc = f"Records financial transactions and payment data"
            elif purpose == 'product_management':
                desc = f"Manages product catalog and inventory information"
            elif purpose == 'organizational_management':
                desc = f"Handles organizational structure and employee data"
            else:
                desc = f"Stores {table_name.lower().replace('_', ' ')} data"
            
            schema_section += f"**{table_name}** - {desc}\n"
            
            # Add columns
            for col in table_info.get('columns', []):
                nullable = "NULL" if col.get('is_nullable', True) else "NOT NULL"
                pk_marker = " (PRIMARY KEY)" if col.get('is_primary_key', False) else ""
                schema_section += f"  - {col['name']} {col['data_type']} {nullable}{pk_marker}\n"
            
            # Add enum values
            enums = table_info.get('detected_enums', {})
            if enums:
                schema_section += "  Enum Values:\n"
                for enum_col, values in enums.items():
                    schema_section += f"    - {enum_col}: {values}\n"
            
            schema_section += "\n"
        
        # Generate security rules based on domain
        security_rules = [
            "Only SELECT statements allowed, never INSERT/UPDATE/DELETE",
            "Never return data belonging to other users",
            "Always use named parameters with colon (:parameter_name)",
            "Apply appropriate data masking for sensitive information"
        ]
        
        if domain == 'financial_services':
            security_rules.extend([
                "Never expose full credit card or account numbers",
                "Mask sensitive financial data appropriately",
                "Filter by user context (customer_id, account_id)"
            ])
        elif 'user' in domain or 'customer' in domain:
            security_rules.extend([
                "Protect personally identifiable information (PII)",
                "Never expose email addresses or phone numbers to unauthorized users"
            ])
        
        # Generate example based on main table
        main_table = list(tables.keys())[0] if tables else "table"
        example_section = f"""
## EXAMPLE QUERIES

**Example 1: Get user data**
User: "Show my information"
```sql
SELECT * FROM {main_table} WHERE id = :user_id
```

**Example 2: List recent items**
User: "Show recent records"
```sql
SELECT * FROM {main_table} 
ORDER BY created_date DESC 
LIMIT 10
```
"""
        
        # Assemble complete prompt
        complete_prompt = f"""You are an expert SQL assistant for a {domain.replace('_', ' ')} system that can interact with a database through MCP tools.

{schema_section}
## SECURITY RULES

{chr(10).join(f'- {rule}' for rule in security_rules)}

## CRITICAL WORKFLOW - Follow these steps EXACTLY:

1. **ESTABLISH USER CONTEXT** (if not already set): 
   - Check session state for existing user context
   - If NO context exists, ask the user to provide their identification:
     * "Please provide your account ID, customer ID, or other identifier so I can help you with your data"
   - Extract context from user's response or question  
   - Store context in session state for future queries
   - ALWAYS print what user context you're using: "Using user context: [identifier]=[value]"

2. **GENERATE DOMAIN-SPECIFIC SQL QUERY**: 
   - **SECURITY RULES:**
     * Only SELECT statements, never INSERT/UPDATE/DELETE
     * Never return data belonging to other users
     * Always use named parameters with colon (:parameter_name)
     * Apply appropriate data masking for sensitive information
   
   - **SQL GENERATION RULES:**
     * Use table and column names exactly as defined in the schema above
     * Follow the relationship patterns defined in the schema
     * Use enum values as documented above
     * Return only columns relevant to the user's question
   
   - **ALWAYS print the exact SQL you generated:**
     ```
     Generated SQL:
     [your SQL here with named parameters]
     ```

3. **EXECUTE SQL WITH PARAMETERS**: 
   - Use `read_query` tool with your SQL AND the actual parameter values
   - Provide both query and parameters in the tool call
   - CRITICAL: You MUST use the "parameters" field in the read_query tool call
   - Print "Executing SQL with parameters: [parameter values]"

4. **RETURN RESULTS**: 
   - Return the query results clearly formatted
   - Apply appropriate data masking for sensitive fields
   - Provide helpful context about what the data represents

{example_section}

## IMPORTANT GUIDELINES:
- **Named parameters**: Always use :parameter_name format
- **Data masking**: Apply appropriate masking for sensitive data
- **User isolation**: Never return data belonging to other users
- **Column relevance**: Return only columns that answer the user's question
- **Business context**: Understand the business meaning of the data you're querying

Available MCP Tools:
- `get_schema_for_llm`: Retrieves comprehensive database schema (use if you need to refresh schema)
- `read_query`: Executes a SELECT query with parameters and returns results

ALWAYS prioritize security and appropriate data access in your {domain.replace('_', ' ')} queries!
"""
        
        return complete_prompt
    
    def _get_fallback_prompt(self) -> str:
        """Get a basic fallback prompt when schema analysis fails."""
        
        return """You are an expert SQL assistant that can interact with a database through MCP tools.

## CRITICAL WORKFLOW - Follow these steps EXACTLY:

1. **GET DATABASE SCHEMA**: 
   - **ALWAYS use `get_schema_for_llm` tool first** to retrieve comprehensive database structure
   - Analyze the returned schema to understand table relationships and data types

2. **UNDERSTAND USER CONTEXT**: 
   - Extract context from user's question or ask for necessary identifiers
   - ALWAYS print what user context you're using

3. **GENERATE SQL QUERY**: 
   - Use only the table and column names from the schema
   - Write safe SELECT queries with named parameters (:parameter_name)
   - ALWAYS print the exact SQL you generated

4. **EXECUTE SQL WITH PARAMETERS**: 
   - Use `read_query` tool with SQL and parameter values
   - CRITICAL: Use the "parameters" field in the tool call

5. **RETURN RESULTS**: 
   - Return query results clearly formatted
   - Apply data masking for sensitive information

Available MCP Tools:
- `get_schema_for_llm`: Retrieves comprehensive database schema
- `read_query`: Executes SELECT queries with parameters

ALWAYS prioritize security and user data isolation!
"""
    
    async def create_agent(self) -> Agent:
        """
        Create the auto-generating DBA agent with domain-specific prompt.
        
        Returns:
            Agent instance with automatically generated domain-specific instruction
        """
        
        # Generate domain-specific prompt
        domain_prompt = await self.get_or_generate_domain_prompt()
        
        # Create MCP toolset
        mcp_toolset = CustomMCPToolset(
            connection_params=StdioServerParameters(
                command="uv",
                args=["run", "mcp-db-server"],
                cwd=self.mcp_config_path
            ),
            tool_filter=["get_schema_for_llm", "read_query"]
        )
        
        # Create agent with auto-generated prompt
        agent = Agent(
            name="auto_dba_agent",
            model=LiteLlm(model="vertex_ai/gemini-2.5-pro"),
            description="An automatically-configured domain-specific SQL assistant that adapts to any database schema.",
            instruction=domain_prompt,
            tools=[mcp_toolset],
        )
        
        logger.info(f"🎉 Created auto-generating DBA agent with {len(domain_prompt)} character domain-specific prompt")
        return agent
    
    def get_cached_prompts_summary(self) -> Dict[str, Any]:
        """Get a summary of cached prompts for debugging/monitoring."""
        
        summary = {
            "total_cached_prompts": len(self.generated_prompts_cache),
            "current_schema_hash": self.current_database_schema_hash,
            "cached_prompts": []
        }
        
        for schema_hash, prompt_info in self.generated_prompts_cache.items():
            summary["cached_prompts"].append({
                "schema_hash": schema_hash[:8] + "...",
                "domain": prompt_info.get('schema_summary', {}).get('domain', 'unknown'),
                "tables": prompt_info.get('schema_summary', {}).get('tables', 0),
                "prompt_length": len(prompt_info.get('prompt', '')),
                "generated_timestamp": prompt_info.get('generated_timestamp', 'unknown')
            })
        
        return summary

# Convenience functions for easy usage
async def create_auto_prompt_agent(mcp_config_path: str = None) -> Agent:
    """
    Convenience function to create an auto-generating domain-specific DBA agent.
    
    Args:
        mcp_config_path: Path to MCP server configuration
        
    Returns:
        Agent instance with automatically generated domain-specific instruction
    """
    auto_agent = AutoPromptAgent(mcp_config_path)
    return await auto_agent.create_agent()

def get_prompt_cache_summary(mcp_config_path: str = None) -> Dict[str, Any]:
    """
    Get a summary of cached domain-specific prompts.
    
    Args:
        mcp_config_path: Path to MCP server configuration
        
    Returns:
        Summary of cached prompts
    """
    auto_agent = AutoPromptAgent(mcp_config_path)
    return auto_agent.get_cached_prompts_summary() 