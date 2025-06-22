# mcp-sql-server: A SQL MCP Server

## Overview

A Model Context Protocol (MCP) server for interacting with SQL databases. This server provides tools to query and retrieve schema information from a SQL database via Large Language Models (LLMs). It's designed to be used with LLM-powered tools and applications that need to access and understand SQL data.

Please note that `mcp-db-server` is currently in early development. The functionality and available tools are subject to change and expansion as we continue to develop and improve the server.

### Tools

1.  `read_query`
    *   **Description:** Executes a `SELECT` query on the SQL database.
    *   **Input:**
        *   `query` (string): A valid `SELECT` SQL query to execute.
    *   **Returns:** The results of the query as a list of dictionaries, where each dictionary represents a row and the keys are the column names.
    *   **Restrictions:** Only `SELECT` queries are allowed. Other SQL commands (e.g., `INSERT`, `UPDATE`, `DELETE`) are not supported.

2.  `get_schema`
    *   **Description:** Retrieves the schema information for the database.
    *   **Input:** None.
    *   **Returns:** A JSON string representing the database schema. The schema includes table names, column names, data types, and other column properties.

## Installation

### Using uv (recommended)

When using `uv` no specific installation is needed. We will
use `uvx` to directly run *mcp-db-server*.

### Using PIP

Alternatively, you can install `mcp-db-server` via pip:

```bash
pip install mcp-db-server
```
After installation, you can run it as a script using:

```bash
python -m mcp_sql_server --db-host <your_db_host> --db-user <your_db_user> --db-password <your_db_password> --db-database <your_db_name>
```
*Note: Replace <your_db_host>, <your_db_user>, <your_db_password>, and <your_db_name> with your actual database credentials.

## Configuration

### Usage with Claude Desktop

Add this to your claude_desktop_config.json:

```json
"mcpServers": {
  "sql": {
    "command": "uvx",
    "args": ["mcp-sql-server", "--db-host", "<your_db_host>", "--db-user", "<your_db_user>", "--db-password", "<your_db_password>", "--db-database", "<your_db_name>"]
  }
}
```
* Note: replace '/Users/username' with the a path that you want to be accessible by this tool

```json
"mcpServers": {
  "sql": {
    "command": "docker",
    "args": ["run", "--rm", "-i", "--mount", "type=bind,src=/Users/username,dst=/Users/username", "mcp/sql", "--db-host", "<your_db_host>", "--db-user", "<your_db_user>", "--db-password", "<your_db_password>", "--db-database", "<your_db_name>"]
  }
}
```

```json
"mcpServers": {
  "sql": {
    "command": "python",
    "args": ["-m", "mcp_sql_server", "--db-host", "<your_db_host>", "--db-user", "<your_db_user>", "--db-password", "<your_db_password>", "--db-database", "<your_db_name>"]
  }
}
```
*Note: Replace <your_db_host>, <your_db_user>, <your_db_password>, and <your_db_name> with your actual database credentials.

### Usage with Zed

Add to your Zed settings.json:

```json
"context_servers": {
  "mcp-sql-server": {
    "command": {
      "path": "uvx",
      "args": ["mcp-sql-server", "--db-host", "<your_db_host>", "--db-user", "<your_db_user>", "--db-password", "<your_db_password>", "--db-database", "<your_db_name>"]
    }
  }
}
```
```json
"context_servers": {
  "mcp-sql-server": {
    "command": {
      "path": "python",
      "args": ["-m", "mcp_sql_server", "--db-host", "<your_db_host>", "--db-user", "<your_db_user>", "--db-password", "<your_db_password>", "--db-database", "<your_db_name>"]
    }
  }
}
```
*Note: Replace <your_db_host>, <your_db_user>, <your_db_password>, and <your_db_name> with your actual database credentials.

## Debugging

You can use the MCP inspector to debug the server. For uvx installations:

```bash
npx @modelcontextprotocol/inspector uvx mcp-sql-server --db-host <your_db_host> --db-user <your_db_user> --db-password <your_db_password> --db-database <your_db_name>
```
Or if you've installed the package in a specific directory or are developing on it:

```bash
cd path/to/project
npx @modelcontextprotocol/inspector uv run mcp-sql-server --db-host <your_db_host> --db-user <your_db_user> --db-password <your_db_password> --db-database <your_db_name>
```
Running tail -n 20 -f ~/Library/Logs/Claude/mcp*.log will show the logs from the server and may help you debug any issues.

## Development

If you are doing local development, there are two ways to test your changes:

Run the MCP inspector to test your changes. See Debugging for run instructions.

Test using the Claude desktop app. Add the following to your claude_desktop_config.json:

### Docker

```json
{
  "mcpServers": {
    "sql": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--mount", "type=bind,src=/Users/username/Desktop,dst=/projects/Desktop",
        "--mount", "type=bind,src=/path/to/other/allowed/dir,dst=/projects/other/allowed/dir,ro",
        "--mount", "type=bind,src=/path/to/file.txt,dst=/projects/path/to/file.txt",
        "mcp/sql",
        "--db-host", "<your_db_host>",
        "--db-user", "<your_db_user>",
        "--db-password", "<your_db_password>",
        "--db-database", "<your_db_name>"
      ]
    }
  }
}
```

### UVX

```json
{
"mcpServers": {
  "sql": {
    "command": "uv",
    "args": [ 
      "--directory",
      "/<path to mcp-servers>/mcp-servers/src/sql",
      "run",
      "mcp-sql-server",
      "--db-host", "<your_db_host>",
      "--db-user", "<your_db_user>",
      "--db-password", "<your_db_password>",
      "--db-database", "<your_db_name>"
    ]
  }
}
```
*Note: Replace <your_db_host>, <your_db_user>, <your_db_password>, and <your_db_name> with your actual database credentials.

## Build

### Docker build:

```bash
cd src/sql
docker build -t mcp/sql .
```

## License
This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.