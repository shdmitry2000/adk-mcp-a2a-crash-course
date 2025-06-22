
try:
    import sqlglot
    SQLGLOT_AVAILABLE = True
except ImportError:
    sqlglot = None
    SQLGLOT_AVAILABLE = False

import sqlite3
from typing import Dict, List, Tuple, Any, Optional
import re

def analyze_bind_parameters(
    query: str, 
    db_path: Optional[str] = None,
    connection: Optional[sqlite3.Connection] = None
) -> Dict[str, Any]:
    """
    Analyzes bind parameters from a SQLite SELECT statement and provides 
    information about their potential types and usage.
    
    Args:
        query: The SQLite SELECT statement with bind parameters (?, :name, @name, or $name)
        db_path: Optional path to the SQLite database file for schema validation
        connection: Optional SQLite connection object for schema validation

    Identifies multiple parameter styles:
        Positional parameters (?)
        Named parameters with colon (:name)
        Named parameters with at sign (@name)
        Named parameters with dollar sign ($name)


    Returns:
        Dictionary containing bind parameter information
    """
    # Result dictionary
    result = {
        "original_query": query,
        "parameters": [],
        "tables_referenced": [],
        "columns_referenced": [],
        "parameter_suggestions": {}
    }
    
    # Parse the query using SQLGlot
    try:
        parsed = sqlglot.parse_one(query, dialect='sqlite')
        
        # Get referenced tables from the query
        tables = []
        for table in parsed.find_all(sqlglot.exp.Table):
            tables.append(str(table))
        result["tables_referenced"] = list(set(tables))
        
        # Get referenced columns from the query
        columns = []
        for column in parsed.find_all(sqlglot.exp.Column):
            columns.append(str(column))
        result["columns_referenced"] = list(set(columns))
    except Exception as e:
        result["parse_error"] = str(e)
        
    # Regular expressions for different bind parameter styles
    param_patterns = {
        "positional": r'\?',
        "named_colon": r':([a-zA-Z0-9_]+)',
        "named_at": r'@([a-zA-Z0-9_]+)',
        "named_dollar": r'\$([a-zA-Z0-9_]+)'
    }
    
    # Find all bind parameters in the query
    for style, pattern in param_patterns.items():
        if style == "positional":
            pos_matches = re.findall(pattern, query)
            for i in range(len(pos_matches)):
                result["parameters"].append({
                    "type": "positional",
                    "position": i + 1,
                    "name": None,
                    "style": "?"
                })
        else:
            named_matches = re.findall(pattern, query)
            for name in named_matches:
                prefix = pattern[0]  # Get the prefix character (:, @, $)
                result["parameters"].append({
                    "type": "named",
                    "position": None,
                    "name": name,
                    "style": prefix + name
                })
    
    # If database file is provided, try to get schema information
    if db_path and result["tables_referenced"]:
        try:
            if connection:
                conn = connection
            else:
                conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            schema_info = {}
            
            # Get schema for each referenced table
            for table in result["tables_referenced"]:
                # Clean table name (remove quotes, aliases, etc.)
                clean_table = table.replace('"', '').replace('`', '').replace("'", "")
                if " AS " in clean_table.upper():
                    clean_table = clean_table.split(" AS ")[0]
                    
                try:
                    cursor.execute(f"PRAGMA table_info({clean_table})")
                    columns_info = cursor.fetchall()
                    schema_info[clean_table] = {
                        "columns": [
                            {
                                "name": col[1],
                                "type": col[2],
                                "notnull": bool(col[3]),
                                "primary_key": bool(col[5])
                            } for col in columns_info
                        ]
                    }
                except sqlite3.Error:
                    schema_info[clean_table] = {"error": "Table not found or not accessible"}
            
            result["schema_info"] = schema_info
            cursor.close()
            
            # Try to match parameters to WHERE clause columns for type suggestions
            if parsed is not None:
                where_conditions = list(parsed.find_all(sqlglot.exp.Where))
                param_suggestions = {}
                
                # Extract conditions from WHERE clause
                if where_conditions:
                    conditions = where_conditions[0].find_all(sqlglot.exp.Binary)
                    
                    for condition in conditions:
                        left = condition.left
                        right = condition.right
                        
                        # Check if this is a column = parameter condition
                        if isinstance(left, sqlglot.exp.Column) and isinstance(right, sqlglot.exp.Parameter):
                            col_name = str(left).split(".")[-1]
                            param_name = str(right)
                            
                            # Find matching parameter in our list
                            for param in result["parameters"]:
                                if param["style"] == param_name:
                                    # Look up column type in schema
                                    for table, table_info in schema_info.items():
                                        for column in table_info.get("columns", []):
                                            if column["name"] == col_name:
                                                param_suggestions[param_name] = {
                                                    "suggested_column": col_name,
                                                    "suggested_table": table,
                                                    "data_type": column["type"],
                                                    "is_primary_key": column["primary_key"],
                                                    "not_null": column["notnull"]
                                                }
                                    
                result["parameter_suggestions"] = param_suggestions
            
            if not connection:  
                conn.close()
            
        except sqlite3.Error as e:
            result["db_error"] = str(e)
    
    return result

# Example usage:
if __name__ == "__main__":
    # Example 1: Simple query with positional parameters
    query1 = """
    SELECT * FROM Account 
    WHERE CustomerID = ? AND AccountStatus = ? AND CurrentBalance > ?
    """
    
    # Example 2: Query with named parameters
    query2 = """
    SELECT p.FirstName, p.LastName, a.AccountNumber, a.CurrentBalance
    FROM Person p
    JOIN Customer c ON p.PersonID = c.PersonID
    JOIN Account a ON c.CustomerID = a.CustomerID
    WHERE a.AccountType = :acct_type AND a.CurrentBalance > :min_balance
    ORDER BY a.CurrentBalance DESC
    """
    
    # Example 3: Complex query with multiple parameter styles
    query3 = """
    SELECT bt.TransactionID, bt.TransactionType, bt.Amount, bt.TransactionDate
    FROM BankTransaction bt
    JOIN Account a ON bt.AccountID = a.AccountID
    JOIN Customer c ON a.CustomerID = c.CustomerID
    JOIN Person p ON c.PersonID = p.PersonID
    WHERE p.LastName LIKE :last_name
    AND bt.Amount > @min_amount
    AND bt.TransactionDate BETWEEN $start_date AND $end_date
    AND a.AccountType = ?
    """
    
    # Analyze queries
    # Replace 'banking.db' with your actual database path
    db_path = "llm2sql.db"
    
    # Basic analysis without database
    print("Analysis without database:")
    print(analyze_bind_parameters(query1))
    
    # Complete analysis with database
    print("\nAnalysis with database:")
    print(analyze_bind_parameters(query1, db_path))
    
