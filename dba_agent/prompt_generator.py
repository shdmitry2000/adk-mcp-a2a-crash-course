#!/usr/bin/env python3
"""
Automatic Domain-Specific Prompt Generator for Database Agents

This module automatically analyzes database schemas and generates rich, domain-specific 
prompts similar to manually crafted ones, but for ANY database domain.
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from google.adk.models.lite_llm import LiteLlm
import logging

logger = logging.getLogger(__name__)

class DatabasePromptGenerator:
    """
    Automatically generates comprehensive domain-specific prompts by analyzing database schemas.
    """
    
    def __init__(self, model_name: str = "vertex_ai/gemini-2.5-flash"):
        self.llm = LiteLlm(model=model_name)
    
    async def analyze_and_generate_prompt(self, comprehensive_schema: str) -> str:
        """
        Analyze a comprehensive database schema and generate a domain-specific prompt.
        
        Args:
            comprehensive_schema: JSON string from get_schema_for_llm
            
        Returns:
            Complete domain-specific prompt ready for use
        """
        
        try:
            schema_data = json.loads(comprehensive_schema)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid schema JSON: {e}")
        
        # Step 1: Analyze the database domain and structure
        domain_analysis = await self._analyze_database_domain(schema_data)
        
        # Step 2: Generate table descriptions and relationships
        table_descriptions = await self._generate_table_descriptions(schema_data)
        
        # Step 3: Generate security rules based on data patterns
        security_rules = await self._generate_security_rules(schema_data, domain_analysis)
        
        # Step 4: Generate example queries
        example_queries = await self._generate_example_queries(schema_data, domain_analysis)
        
        # Step 5: Detect and document enum values
        enum_documentation = self._document_enum_values(schema_data)
        
        # Step 6: Generate common query patterns
        query_patterns = await self._generate_query_patterns(schema_data, domain_analysis)
        
        # Step 7: Assemble the complete prompt
        complete_prompt = self._assemble_complete_prompt(
            schema_data=schema_data,
            domain_analysis=domain_analysis,
            table_descriptions=table_descriptions,
            security_rules=security_rules,
            example_queries=example_queries,
            enum_documentation=enum_documentation,
            query_patterns=query_patterns
        )
        
        return complete_prompt
    
    async def _analyze_database_domain(self, schema_data: Dict) -> Dict[str, Any]:
        """Analyze the database to understand its business domain and purpose."""
        
        analysis_prompt = f"""
Analyze this database schema and provide a comprehensive domain analysis:

Schema Summary:
- Database Type: {schema_data.get('database_type', 'unknown')}
- Total Tables: {schema_data.get('database_summary', {}).get('total_tables', 0)}
- Estimated Domain: {schema_data.get('database_summary', {}).get('estimated_domain', 'unknown')}
- Key Patterns: {schema_data.get('database_summary', {}).get('key_patterns', [])}

Tables:
{json.dumps({name: {'columns': [col['name'] for col in info['columns']], 'business_purpose': info.get('business_purpose', 'unknown'), 'row_count': info.get('row_count', 0)} for name, info in schema_data.get('tables', {}).items()}, indent=2)}

Relationships:
{json.dumps(schema_data.get('relationships', []), indent=2)}

Provide a JSON response with:
{{
    "primary_domain": "e.g., financial_services, e_commerce, healthcare, etc.",
    "domain_description": "Brief description of what this system manages",
    "key_entities": ["list of main business entities"],
    "business_workflows": ["list of main business processes"],
    "security_considerations": ["list of security concerns based on data types"],
    "user_access_patterns": ["how users typically access this data"],
    "default_user_context": {{"suggested context for default user"}},
    "naming_conventions": {{"patterns found in table/column names"}},
    "temporal_patterns": ["how time-based data is handled"],
    "relationship_patterns": ["how entities relate to each other"]
}}
"""
        
        try:
            response = self.llm.generate(analysis_prompt)
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback analysis based on schema structure
                return self._fallback_domain_analysis(schema_data)
        except Exception as e:
            logger.warning(f"LLM domain analysis failed: {e}, using fallback")
            return self._fallback_domain_analysis(schema_data)
    
    def _fallback_domain_analysis(self, schema_data: Dict) -> Dict[str, Any]:
        """Fallback domain analysis based on naming patterns."""
        
        table_names = list(schema_data.get('tables', {}).keys())
        all_columns = []
        for table_info in schema_data.get('tables', {}).values():
            all_columns.extend([col['name'] for col in table_info.get('columns', [])])
        
        # Simple pattern matching
        domain = "general_business"
        if any(word in ' '.join(table_names).lower() for word in ['account', 'bank', 'loan', 'credit']):
            domain = "financial_services"
        elif any(word in ' '.join(table_names).lower() for word in ['order', 'product', 'inventory', 'cart']):
            domain = "e_commerce"
        elif any(word in ' '.join(table_names).lower() for word in ['patient', 'doctor', 'medical', 'treatment']):
            domain = "healthcare"
        
        return {
            "primary_domain": domain,
            "domain_description": f"A {domain.replace('_', ' ')} system",
            "key_entities": table_names[:5],
            "business_workflows": ["data_management", "reporting", "transactions"],
            "security_considerations": ["data_privacy", "access_control"],
            "user_access_patterns": ["query_by_id", "list_recent_items"],
            "default_user_context": {},
            "naming_conventions": {"uses_id_suffix": "ID" in ' '.join(all_columns)},
            "temporal_patterns": ["datetime_tracking"] if any('date' in col.lower() or 'time' in col.lower() for col in all_columns) else [],
            "relationship_patterns": ["foreign_key_relationships"] if schema_data.get('relationships', []) else []
        }
    
    async def _generate_table_descriptions(self, schema_data: Dict) -> Dict[str, str]:
        """Generate human-readable descriptions for each table."""
        
        table_descriptions = {}
        
        for table_name, table_info in schema_data.get('tables', {}).items():
            description_prompt = f"""
Analyze this database table and provide a clear, business-focused description:

Table: {table_name}
Business Purpose: {table_info.get('business_purpose', 'unknown')}
Row Count: {table_info.get('row_count', 0)}

Columns:
{json.dumps(table_info.get('columns', []), indent=2)}

Sample Data:
{json.dumps(table_info.get('sample_data', []), indent=2)}

Foreign Keys:
{json.dumps(table_info.get('foreign_keys', []), indent=2)}

Detected Enums:
{json.dumps(table_info.get('detected_enums', {}), indent=2)}

Provide a concise description (1-2 sentences) explaining what this table stores and its business purpose.
"""
            
            try:
                description = await self.llm.generate_async(description_prompt)
                # Clean up the description
                description = description.strip().replace('\n', ' ')
                if len(description) > 300:
                    description = description[:300] + "..."
                table_descriptions[table_name] = description
            except Exception as e:
                logger.warning(f"Failed to generate description for {table_name}: {e}")
                # Fallback description
                table_descriptions[table_name] = f"Table storing {table_name.lower().replace('_', ' ')} data with {len(table_info.get('columns', []))} columns."
        
        return table_descriptions
    
    async def _generate_security_rules(self, schema_data: Dict, domain_analysis: Dict) -> List[str]:
        """Generate security rules based on data patterns and domain."""
        
        security_prompt = f"""
Based on this database schema and domain analysis, generate specific security rules:

Domain: {domain_analysis.get('primary_domain', 'unknown')}
Security Considerations: {domain_analysis.get('security_considerations', [])}

Key Data Patterns Found:
"""
        
        # Analyze sensitive data patterns
        sensitive_patterns = []
        for table_name, table_info in schema_data.get('tables', {}).items():
            for col in table_info.get('columns', []):
                col_name_lower = col['name'].lower()
                if any(pattern in col_name_lower for pattern in ['password', 'ssn', 'tax', 'credit', 'card']):
                    sensitive_patterns.append(f"{table_name}.{col['name']} - {col['data_type']}")
                elif 'email' in col_name_lower:
                    sensitive_patterns.append(f"{table_name}.{col['name']} - PII")
        
        security_prompt += f"Sensitive Data Patterns: {sensitive_patterns}\n"
        
        try:
            response = await self.llm.generate_async(security_prompt + "\nProvide 5-10 specific security rules as a bullet list.")
            rules = []
            for line in response.split('\n'):
                if line.strip().startswith(('-', '•', '*')):
                    rules.append(line.strip().lstrip('-•* '))
            return rules[:10]  # Limit to 10 rules
        except Exception as e:
            logger.warning(f"Failed to generate security rules: {e}")
            return [
                "Only SELECT statements allowed, never INSERT/UPDATE/DELETE",
                "Never return data belonging to other users",
                "Always use parameterized queries to prevent SQL injection",
                "Mask sensitive data like credit card numbers or SSNs",
                "Filter data based on user context and permissions"
            ]
    
    async def _generate_example_queries(self, schema_data: Dict, domain_analysis: Dict) -> List[Dict[str, str]]:
        """Generate example queries for common use cases."""
        
        examples = []
        
        # Get main tables (those with most relationships or data)
        main_tables = sorted(
            schema_data.get('tables', {}).items(),
            key=lambda x: (len(x[1].get('foreign_keys', [])), x[1].get('row_count', 0)),
            reverse=True
        )[:3]
        
        for table_name, table_info in main_tables:
            example_prompt = f"""
Generate a realistic SQL example query for this table:

Table: {table_name}
Purpose: {table_info.get('business_purpose', 'unknown')}
Columns: {[col['name'] for col in table_info.get('columns', [])]}
Sample Data: {table_info.get('sample_data', [])}
Relationships: {table_info.get('foreign_keys', [])}

Domain: {domain_analysis.get('primary_domain', 'unknown')}

Provide:
1. A realistic user question
2. The corresponding SELECT query with named parameters
3. Brief explanation

Format:
User Question: "..."
SQL Query: SELECT ... FROM ... WHERE ... = :parameter_name
Explanation: "..."
"""
            
            try:
                response = await self.llm.generate_async(example_prompt)
                # Parse the response
                lines = response.split('\n')
                question = next((line.split(':', 1)[1].strip().strip('"') for line in lines if line.startswith('User Question')), '')
                query = next((line.split(':', 1)[1].strip() for line in lines if line.startswith('SQL Query')), '')
                explanation = next((line.split(':', 1)[1].strip() for line in lines if line.startswith('Explanation')), '')
                
                if question and query:
                    examples.append({
                        'user_question': question,
                        'sql_query': query,
                        'explanation': explanation
                    })
            except Exception as e:
                logger.warning(f"Failed to generate example for {table_name}: {e}")
        
        return examples
    
    def _document_enum_values(self, schema_data: Dict) -> Dict[str, List[str]]:
        """Document detected enum values from the schema."""
        
        all_enums = {}
        
        for table_name, table_info in schema_data.get('tables', {}).items():
            detected_enums = table_info.get('detected_enums', {})
            for col_name, values in detected_enums.items():
                enum_key = f"{table_name}.{col_name}"
                all_enums[enum_key] = values
        
        return all_enums
    
    async def _generate_query_patterns(self, schema_data: Dict, domain_analysis: Dict) -> List[str]:
        """Generate common query patterns for this database."""
        
        patterns = []
        
        # Analyze relationships for join patterns
        relationships = schema_data.get('relationships', [])
        if relationships:
            for rel in relationships[:5]:  # Top 5 relationships
                pattern = f"Get {rel['from_table'].lower()} with related {rel['to_table'].lower()}: SELECT * FROM {rel['from_table']} t1 JOIN {rel['to_table']} t2 ON t1.{rel['from_column']} = t2.{rel['to_column']} WHERE t1.{rel['from_column']} = :id"
                patterns.append(pattern)
        
        # Common patterns based on domain
        domain = domain_analysis.get('primary_domain', 'unknown')
        if domain == 'financial_services':
            patterns.extend([
                "Get user account balance: SELECT account_number, balance FROM accounts WHERE customer_id = :customer_id",
                "Get recent transactions: SELECT * FROM transactions WHERE account_id = :account_id AND date >= :start_date ORDER BY date DESC"
            ])
        elif domain == 'e_commerce':
            patterns.extend([
                "Get customer orders: SELECT * FROM orders WHERE customer_id = :customer_id ORDER BY order_date DESC",
                "Get order details: SELECT o.*, oi.* FROM orders o JOIN order_items oi ON o.order_id = oi.order_id WHERE o.order_id = :order_id"
            ])
        
        return patterns
    
    def _assemble_complete_prompt(self, schema_data: Dict, domain_analysis: Dict, 
                                table_descriptions: Dict, security_rules: List, 
                                example_queries: List, enum_documentation: Dict,
                                query_patterns: List) -> str:
        """Assemble all components into a complete domain-specific prompt."""
        
        # Build table schema section
        schema_section = "\n## DATABASE SCHEMA\n\n"
        schema_section += f"**Domain**: {domain_analysis.get('primary_domain', 'unknown').replace('_', ' ').title()}\n"
        schema_section += f"**Description**: {domain_analysis.get('domain_description', 'Database system')}\n\n"
        
        schema_section += "**Tables and Structure:**\n\n"
        
        for table_name, table_info in schema_data.get('tables', {}).items():
            schema_section += f"**{table_name}** - {table_descriptions.get(table_name, 'Data table')}\n"
            
            # Add column definitions
            for col in table_info.get('columns', []):
                nullable = "NULL" if col.get('is_nullable', True) else "NOT NULL"
                pk_marker = " (PRIMARY KEY)" if col.get('is_primary_key', False) else ""
                default = f" DEFAULT {col.get('default')}" if col.get('default') else ""
                schema_section += f"  - {col['name']} {col['data_type']} {nullable}{default}{pk_marker}\n"
            
            # Add foreign keys
            fks = table_info.get('foreign_keys', [])
            if fks:
                schema_section += "  Foreign Keys:\n"
                for fk in fks:
                    schema_section += f"    - {fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}\n"
            
            schema_section += "\n"
        
        # Build relationships section
        relationships_section = "\n**Relationships:**\n"
        for rel in schema_data.get('relationships', []):
            relationships_section += f"- {rel['from_table']}.{rel['from_column']} → {rel['to_table']}.{rel['to_column']}\n"
        
        # Build enum values section
        enum_section = "\n**System Codes and Enum Values:**\n"
        for enum_key, values in enum_documentation.items():
            enum_section += f"- {enum_key}: {values}\n"
        
        # Build security rules section
        security_section = "\n## SECURITY RULES\n\n"
        for rule in security_rules:
            security_section += f"- {rule}\n"
        
        # Build examples section
        examples_section = "\n## EXAMPLE QUERIES\n\n"
        for i, example in enumerate(example_queries, 1):
            examples_section += f"**Example {i}: {example['user_question']}**\n"
            examples_section += f"```sql\n{example['sql_query']}\n```\n"
            if example.get('explanation'):
                examples_section += f"{example['explanation']}\n"
            examples_section += "\n"
        
        # Build query patterns section
        patterns_section = "\n**Common Query Patterns:**\n"
        for pattern in query_patterns:
            patterns_section += f"- {pattern}\n"
        
        # Assemble the complete prompt
        complete_prompt = f"""You are an expert SQL assistant for a {domain_analysis.get('primary_domain', 'business').replace('_', ' ')} system that can interact with a database through MCP tools.

{schema_section}{relationships_section}{enum_section}{security_section}

## CRITICAL WORKFLOW - Follow these steps EXACTLY:

1. **UNDERSTAND USER CONTEXT**: 
   - Check for user context in session state or extract from user's question
   - Use appropriate context based on the domain and user's request
   - ALWAYS print what user context you're using
   - If no context is available, ask the user to provide necessary identifiers

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

{examples_section}{patterns_section}

## IMPORTANT GUIDELINES:
- **Named parameters**: Always use :parameter_name format
- **Data masking**: Apply appropriate masking for sensitive data
- **User isolation**: Never return data belonging to other users
- **Column relevance**: Return only columns that answer the user's question
- **Business context**: Understand the business meaning of the data you're querying

Available MCP Tools:
- `get_schema_for_llm`: Retrieves comprehensive database schema (use if you need to refresh schema)
- `read_query`: Executes a SELECT query with parameters and returns results

ALWAYS prioritize security and appropriate data access in your {domain_analysis.get('primary_domain', 'business').replace('_', ' ')} queries!
"""
        
        return complete_prompt

# Global instance for the prompt generator
_prompt_generator: Optional[DatabasePromptGenerator] = None

def get_prompt_generator() -> DatabasePromptGenerator:
    """Get the global prompt generator instance."""
    global _prompt_generator
    if _prompt_generator is None:
        _prompt_generator = DatabasePromptGenerator()
    return _prompt_generator

async def generate_domain_specific_prompt(comprehensive_schema: str) -> str:
    """
    Convenience function to generate a domain-specific prompt from a comprehensive schema.
    
    Args:
        comprehensive_schema: JSON string from get_schema_for_llm
        
    Returns:
        Complete domain-specific prompt ready for use
    """
    generator = get_prompt_generator()
    return await generator.analyze_and_generate_prompt(comprehensive_schema) 