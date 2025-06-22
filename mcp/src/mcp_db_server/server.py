"""
Modified server.py to support multiple database types
"""
import json
import logging
import os
from contextlib import closing
from typing import Any, Optional
from abc import ABC, abstractmethod
from urllib.parse import urlparse, parse_qs

from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio

# Configure logging to prevent interference with stdio MCP communication
logging.basicConfig(
    level=logging.WARNING,  # Use WARNING level to reduce noise
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('mcp_db_server')

# Disable litellm debug logging
try:
    import litellm
    litellm.set_verbose = False
    os.environ['LITELLM_LOG'] = 'ERROR'
except ImportError:
    pass

# Try to import bind analyzer, make it optional
try:
    from .bind_analyzer import analyze_bind_parameters
    BIND_ANALYZER_AVAILABLE = True
except ImportError:
    analyze_bind_parameters = None
    BIND_ANALYZER_AVAILABLE = False

logger.warning("Starting MCP SQL Server")  # Use warning level for important startup messages


class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""
    
    @abstractmethod
    def get_schema_for_llm(self) -> str:
        """Get database schema in JSON format"""
        pass
    
    @abstractmethod
    def execute_query(self, query: str) -> list[dict]:
        """Execute a SQL query and return results"""
        pass

    def execute_improved_query(self, query: str, query_parameters: dict) -> list[dict]:
        """Execute a SQL query with improved parameters and return results"""
        pass
        

class MySQLAdapter(DatabaseAdapter):
    """MySQL database adapter"""
    
    def __init__(self, host: str, user: str, password: str, database: str, port: Optional[int] = None, ssl_cert: Optional[str] = None):
        import pymysql
        self.connection_params = {
            'host': host,
            'user': user,
            'password': password,
            'database': database
        }
        if port:
            self.connection_params['port'] = port
        if ssl_cert:
            self.connection_params['ssl_ca'] = ssl_cert
        self.pymysql = pymysql
    
    def get_schema_for_llm(self) -> str:
        connection = self.pymysql.connect(**self.connection_params)
        schema = {}
        
        try:
            with connection.cursor() as cursor:
                query = """
                SELECT 
                    TABLE_NAME, 
                    COLUMN_NAME, 
                    DATA_TYPE, 
                    COLUMN_TYPE,
                    IS_NULLABLE, 
                    COLUMN_DEFAULT, 
                    COLUMN_KEY, 
                    EXTRA
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME, ORDINAL_POSITION;
                """
                
                cursor.execute(query, (self.connection_params['database'],))
                results = cursor.fetchall()
                
                for row in results:
                    table_name = row[0]
                    column_info = {
                        "name": row[1],
                        "data_type": row[2],
                        "column_type": row[3],
                        "is_nullable": row[4],
                        "default": row[5],
                        "key": row[6],
                        "extra": row[7]
                    }
                    
                    if table_name not in schema:
                        schema[table_name] = []
                    
                    schema[table_name].append(column_info)
        
        finally:
            connection.close()
        
        return json.dumps(schema, indent=2)
    
    def execute_query(self, query: str) -> list[dict]:
        connection = self.pymysql.connect(**self.connection_params)
        try:
            with connection.cursor(self.pymysql.cursors.DictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                return results
        except Exception as e:
            raise ValueError(f"Error executing query: {str(e)}")
        finally:
            connection.close()


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter"""
    
    def __init__(self, host: str, user: str, password: str, database: str, port: Optional[int] = None, ssl_cert: Optional[str] = None):
        import psycopg2
        import psycopg2.extras
        self.connection_params = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'port': port or 5432
        }
        if ssl_cert:
            self.connection_params['sslmode'] = 'require'
            self.connection_params['sslrootcert'] = ssl_cert
        self.psycopg2 = psycopg2
    
    def get_schema_for_llm(self) -> str:
        connection = self.psycopg2.connect(**self.connection_params)
        schema = {}
        
        try:
            with connection.cursor() as cursor:
                query = """
                SELECT 
                    table_name,
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default,
                    ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
                """
                
                cursor.execute(query)
                results = cursor.fetchall()
                
                for row in results:
                    table_name = row[0]
                    column_info = {
                        "name": row[1],
                        "data_type": row[2],
                        "max_length": row[3],
                        "is_nullable": row[4],
                        "default": row[5],
                        "position": row[6]
                    }
                    
                    if table_name not in schema:
                        schema[table_name] = []
                    
                    schema[table_name].append(column_info)
        
        finally:
            connection.close()
        
        return json.dumps(schema, indent=2)
    
    def execute_query(self, query: str) -> list[dict]:
        connection = self.psycopg2.connect(**self.connection_params)
        try:
            with connection.cursor(cursor_factory=self.psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except Exception as e:
            raise ValueError(f"Error executing query: {str(e)}")
        finally:
            connection.close()


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter"""
    
    def __init__(self, database_path: str):
        import sqlite3
        self.database_path = database_path
        self.sqlite3 = sqlite3
        # if not os.path.exists(database_path):
        #     raise FileNotFoundError(f"Database file not found: {database_path}")
    
    
    def get_schema_for_llm(self) -> str:
        """
        Get comprehensive database schema information for LLM analysis.
        Includes tables, columns, relationships, constraints, sample data, and detected patterns.
        """
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Database file not found: {self.database_path}")
    
        connection = self.sqlite3.connect(self.database_path)
        comprehensive_schema = {
            "database_type": "sqlite",
            "database_path": self.database_path,
            "tables": {},
            "relationships": [],
            "database_summary": {
                "total_tables": 0,
                "estimated_domain": "unknown",
                "key_patterns": []
            }
        }
        
        try:
            connection.row_factory = self.sqlite3.Row
            cursor = connection.cursor()
            
            # Get all tables
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = cursor.fetchall()
            comprehensive_schema["database_summary"]["total_tables"] = len(tables)
            
            for table in tables:
                table_name = table['name']
                table_sql = table['sql']
                
                comprehensive_schema["tables"][table_name] = {
                    "columns": [],
                    "creation_sql": table_sql,
                    "primary_keys": [],
                    "foreign_keys": [],
                    "unique_constraints": [],
                    "check_constraints": [],
                    "sample_data": [],
                    "row_count": 0,
                    "detected_enums": {},
                    "business_purpose": "unknown"
                }
                
                # Get column information
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                
                for col in columns:
                    column_info = {
                        "name": col['name'],
                        "data_type": col['type'],
                        "is_nullable": not col['notnull'],
                        "default": col['dflt_value'],
                        "is_primary_key": bool(col['pk']),
                        "ordinal_position": col['cid']
                    }
                    comprehensive_schema["tables"][table_name]["columns"].append(column_info)
                    
                    if column_info["is_primary_key"]:
                        comprehensive_schema["tables"][table_name]["primary_keys"].append(col['name'])
                
                # Get foreign key information
                cursor.execute(f"PRAGMA foreign_key_list({table_name});")
                foreign_keys = cursor.fetchall()
                
                for fk in foreign_keys:
                    fk_info = {
                        "column": fk['from'],
                        "referenced_table": fk['table'],
                        "referenced_column": fk['to'],
                        "on_delete": fk['on_delete'],
                        "on_update": fk['on_update']
                    }
                    comprehensive_schema["tables"][table_name]["foreign_keys"].append(fk_info)
                    
                    # Add to relationships
                    relationship = {
                        "from_table": table_name,
                        "from_column": fk['from'],
                        "to_table": fk['table'],
                        "to_column": fk['to'],
                        "relationship_type": "one_to_many"  # Default assumption
                    }
                    comprehensive_schema["relationships"].append(relationship)
                
                # Get row count
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table_name};")
                    row_count = cursor.fetchone()['count']
                    comprehensive_schema["tables"][table_name]["row_count"] = row_count
                except:
                    comprehensive_schema["tables"][table_name]["row_count"] = 0
                
                # Get sample data (first 5 rows)
                try:
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                    sample_rows = cursor.fetchall()
                    comprehensive_schema["tables"][table_name]["sample_data"] = [dict(row) for row in sample_rows]
                except:
                    comprehensive_schema["tables"][table_name]["sample_data"] = []
                
                # Detect enum-like columns by analyzing unique values
                for col in columns:
                    col_name = col['name']
                    if col['type'].upper() in ['VARCHAR', 'TEXT', 'CHAR']:
                        try:
                            cursor.execute(f"SELECT DISTINCT {col_name} FROM {table_name} WHERE {col_name} IS NOT NULL LIMIT 20;")
                            unique_values = [row[col_name] for row in cursor.fetchall()]
                            
                            # If few unique values, likely an enum
                            if len(unique_values) <= 15 and len(unique_values) > 0:
                                comprehensive_schema["tables"][table_name]["detected_enums"][col_name] = unique_values
                        except:
                            pass
                
                # Detect business purpose based on table/column names
                table_lower = table_name.lower()
                column_names = [col['name'].lower() for col in columns]
                
                # Common business domain patterns
                if any(word in table_lower for word in ['user', 'customer', 'person', 'account']):
                    comprehensive_schema["tables"][table_name]["business_purpose"] = "user_management"
                elif any(word in table_lower for word in ['order', 'purchase', 'transaction', 'payment']):
                    comprehensive_schema["tables"][table_name]["business_purpose"] = "transaction_management"
                elif any(word in table_lower for word in ['product', 'item', 'inventory', 'catalog']):
                    comprehensive_schema["tables"][table_name]["business_purpose"] = "product_management"
                elif any(word in table_lower for word in ['loan', 'credit', 'debit', 'bank']):
                    comprehensive_schema["tables"][table_name]["business_purpose"] = "financial_services"
                elif any(word in table_lower for word in ['employee', 'staff', 'department', 'branch']):
                    comprehensive_schema["tables"][table_name]["business_purpose"] = "organizational_management"
            
            # Analyze overall database domain
            business_purposes = [table_info["business_purpose"] for table_info in comprehensive_schema["tables"].values()]
            purpose_counts = {}
            for purpose in business_purposes:
                purpose_counts[purpose] = purpose_counts.get(purpose, 0) + 1
            
            if purpose_counts:
                most_common_purpose = max(purpose_counts, key=purpose_counts.get)
                comprehensive_schema["database_summary"]["estimated_domain"] = most_common_purpose
            
            # Detect key patterns
            all_table_names = list(comprehensive_schema["tables"].keys())
            all_column_names = []
            for table_info in comprehensive_schema["tables"].values():
                all_column_names.extend([col["name"] for col in table_info["columns"]])
            
            # Pattern detection
            patterns = []
            if any("ID" in name for name in all_column_names):
                patterns.append("uses_id_pattern")
            if any("date" in name.lower() or "time" in name.lower() for name in all_column_names):
                patterns.append("includes_temporal_data")
            if any("status" in name.lower() or "state" in name.lower() for name in all_column_names):
                patterns.append("uses_status_fields")
            if len(comprehensive_schema["relationships"]) > 0:
                patterns.append("has_relationships")
            
            comprehensive_schema["database_summary"]["key_patterns"] = patterns
        
        finally:
            connection.close()
        
        return json.dumps(comprehensive_schema, indent=2, default=str)
    
    # def execute_query(self, query: str) -> list[dict]:
    #     if not os.path.exists(self.database_path):
    #         raise FileNotFoundError(f"Database file not found: {self.database_path}")
    
    #     connection = self.sqlite3.connect(self.database_path)
    #     try:
    #         connection.row_factory = self.sqlite3.Row
    #         cursor = connection.cursor()
    #         cursor.execute(query)
    #         results = cursor.fetchall()
    #         return [dict(row) for row in results]
    #     except Exception as e:
    #         raise ValueError(f"Error executing query: {str(e)}")
    #     finally:
    #         connection.close()
            
    def execute_query(self, query: str, query_parameters: dict=None) -> list[dict]:
        if not os.path.exists(self.database_path):
            raise FileNotFoundError(f"Database file not found: {self.database_path}")
    
        old_represantation = True
        
        connection = self.sqlite3.connect(self.database_path)
        try:
            # Use bind analyzer if available, otherwise use parameters directly
            if BIND_ANALYZER_AVAILABLE and analyze_bind_parameters:
                analysis_result = analyze_bind_parameters(query, connection=connection)
                if analysis_result.get('db_error'):
                    raise ValueError(f"Error analyzing query: {analysis_result.get('db_error')}")

                parameters = dict()
                # Only process parameters if query_parameters is provided and not None
                if query_parameters:
                    for p in analysis_result.get('parameters', []):
                        if p['type'] == 'named' and p['name'] in query_parameters:
                            parameters[p['name']] = query_parameters.get(p['name'])
            else:
                # Simple fallback: use parameters as provided
                parameters = query_parameters or {}
                 
            if old_represantation:
                cursor = connection.cursor()  
                cursor.execute(query, parameters)
                columns = [desc[0] for desc in cursor.description]
                results = cursor.fetchall()
                return {'columns': columns, 'rows': results}

            else:
                connection.row_factory = self.sqlite3.Row
                cursor = connection.cursor()  
                cursor.execute(query, parameters)
                results = cursor.fetchall()
                return [dict(row) for row in results]
            
                                
        except Exception as e:
            raise ValueError(f"Error analyzing query: {str(e)}")
        finally:
            connection.close()
        
        
        

class SqlReadOnlyServer:
    """
    A read-only server for interacting with multiple database types.
    """
    
    def __init__(self, db_adapter: DatabaseAdapter):
        self.db_adapter = db_adapter
    
    def _get_schema_for_llm(self) -> str:
        return self.db_adapter.get_schema_for_llm()
    
    def _execute_query(self, query: str) -> list[dict]:
        return self.db_adapter.execute_query(query)


def create_database_adapter(db_type: str, host: str = None, user: str = None, 
                          password: str = None, database: str = None, port: int = None, ssl_cert: str = None) -> DatabaseAdapter:
    """Factory function to create the appropriate database adapter"""
    
    if db_type == 'mysql':
        return MySQLAdapter(host, user, password, database, port, ssl_cert)
    elif db_type == 'postgresql':
        return PostgreSQLAdapter(host, user, password, database, port, ssl_cert)
    elif db_type == 'sqlite':
        return SQLiteAdapter(database)  # database is the file path for SQLite
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def parse_database_url(database_url: str) -> dict:
    """Parse DATABASE_URL into connection parameters"""
    parsed = urlparse(database_url)
    
    # Extract basic info
    scheme = parsed.scheme
    host = parsed.hostname
    port = parsed.port
    user = parsed.username
    password = parsed.password
    database = parsed.path.lstrip('/')
    
    # Handle different database types
    if scheme == 'sqlite':
        # For SQLite, the entire path after sqlite:// is the database file
        # Handle both sqlite:///path and sqlite://path formats
        if database_url.startswith('sqlite:///'):
            database_path = database_url[10:]  # Remove 'sqlite://'
        else:
            database_path = database_url[9:]   # Remove 'sqlite:/'
        return {
            'db_type': 'sqlite',
            'database': database_path
        }
    elif scheme in ['postgresql', 'postgres']:
        return {
            'db_type': 'postgresql',
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }
    elif scheme == 'mysql':
        return {
            'db_type': 'mysql',
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }
    else:
        raise ValueError(f"Unsupported database scheme: {scheme}")


def create_database_adapter_from_url(database_url: str, ssl_cert: str = None) -> DatabaseAdapter:
    """Create database adapter from DATABASE_URL"""
    params = parse_database_url(database_url)
    
    if params['db_type'] == 'sqlite':
        return SQLiteAdapter(params['database'])
    elif params['db_type'] == 'postgresql':
        return PostgreSQLAdapter(
            host=params['host'],
            user=params['user'],
            password=params['password'],
            database=params['database'],
            port=params['port'],
            ssl_cert=ssl_cert
        )
    elif params['db_type'] == 'mysql':
        return MySQLAdapter(
            host=params['host'],
            user=params['user'],
            password=params['password'],
            database=params['database'],
            port=params['port'],
            ssl_cert=ssl_cert
        )
    else:
        raise ValueError(f"Unsupported database type: {params['db_type']}")


async def main(db_type: str, host: str = None, user: str = None, password: str = None, 
               database: str = None, port: int = None, ssl_cert: str = None):
    """
    Main function to start the MCP SQL server with individual parameters (legacy mode).
    """
    
    # Create the appropriate database adapter
    db_adapter = create_database_adapter(db_type, host, user, password, database, port, ssl_cert)
    db = SqlReadOnlyServer(db_adapter)
    
    await run_server(db, db_type)


async def main_with_url(database_url: str, ssl_cert: str = None):
    """
    Main function to start the MCP SQL server with DATABASE_URL.
    """
    
    # Create the appropriate database adapter from URL
    db_adapter = create_database_adapter_from_url(database_url, ssl_cert)
    db = SqlReadOnlyServer(db_adapter)
    
    # Extract db_type for logging
    params = parse_database_url(database_url)
    db_type = params['db_type']
    
    await run_server(db, db_type)


async def run_server(db: SqlReadOnlyServer, db_type: str):
    """
    Main function to start the MCP SQL server with multi-database support.
    """
    
    # # Create the appropriate database adapter
    # db_adapter = create_database_adapter(db_type, host, user, password, database, port)
    # db = SqlReadOnlyServer(db_adapter)
    
    server = Server("mcp-db-server")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """
        Lists the available tools provided by the server.
        """
        return [
            types.Tool(
                name="read_query",
                description="Execute a SELECT query on the SQL database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "SELECT SQL query to execute"},
                        "parameters": {"type": "object", "description": "Parameters for the SQL query (optional)"},
                    },
                    "required": ["query"],
                },
            ),
            types.Tool(
                name="get_schema",
                description="Get the basic schema information for the database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            types.Tool(
                name="get_schema_for_llm",
                description="Get comprehensive database schema information for LLM analysis, including tables, relationships, constraints, sample data, detected enums, and business patterns",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str, arguments: dict[str, Any] | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """
        Handles the execution of a tool.
        """
        try:
            if name == "get_schema":
                results = db._get_schema_for_llm()
                return [types.TextContent(type="text", text=str(results))]
            
            if name == "get_schema_for_llm":
                # Use the comprehensive schema method
                results = db.db_adapter.get_schema_for_llm()
                return [types.TextContent(type="text", text=str(results))]

            if not arguments:
                raise ValueError("Missing arguments")

            if name == "read_query":
                if not arguments["query"].strip().upper().startswith("SELECT"):
                    raise ValueError("Only SELECT queries are allowed for read_query")
                
                # Get parameters if provided
                parameters = arguments.get("parameters", None)
                
                # Use the database adapter directly to pass parameters
                results = db.db_adapter.execute_query(arguments["query"], parameters)
                return [types.TextContent(type="text", text=str(results))]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info(f"Server running with {db_type} database and stdio transport")
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="sql",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
        
if __name__ == "__main__":
    
    print("Testing LLM SQL Agent...")
    
    # question = "List all accounts for customer with customer_id :CustomerID. The requested data is related to customer_id 202."
    # user_context = {
    #     'AccountID': 126, 
    #     'user': 'test_user', 
    #     'fqdn': 'test_fqdn', 
    #     'CustomerID': 202, 
    #     'PersonID': 59
    # }
    
    question = "List all my accounts."
    user_context = {
        'AccountID': 126, 
        'user': 'test_user', 
        'fqdn': 'test_fqdn', 
        'CustomerID': 202, 
        'PersonID': 59
    }
    
    print(f"Question: {question}")
    print(f"Context: {user_context}")
    print("-" * 50)
    
    try:
        sql_adapter = SQLiteAdapter(database_path="/Users/dmitrysh/code/tal/dev_poc/LLM2SQL/llm2sql.db")
        query="""
        SELECT AccountID,AccountNumber,AccountType,CurrentBalance,DateOpened,DateClosed,AccountStatus
        FROM Account
        WHERE CustomerID = :CustomerID;
        """
        
        output = sql_adapter.execute_query(query, user_context)
        
        if 'error' in output:
            print(f"Error: {output['error']}")
            if 'model_response' in output:
                print(f"Model Response: {output['model_response']}")
        else:
            # print(f"Generated SQL: {output['out']}")
            # print(f"Results: {output['results']}")
            print(f"out: {output}")
        
        
        print("-" * 50)
        print("Test completed.")
    except Exception as e:
        print(f"Error: {str(e)}")
        raise e
        
