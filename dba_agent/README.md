# DBA Agent

A sophisticated SQL assistant agent built with Google ADK that connects to a banking database via MCP (Model Context Protocol) server.

## Features

- 🔍 **Automatic Schema Discovery**: Uses MCP `get_schema` tool to understand database structure
- 🛡️ **Safe SQL Generation**: Only generates SELECT statements for read-only operations
- 📊 **SQL Parameter Analysis**: Advanced analysis using sqlglot for parameter binding
- 🏦 **Banking Domain Expertise**: Specialized for banking data with built-in security constraints
- 💾 **Schema Caching**: Caches database schema for efficient repeated queries
- 🔧 **MCP Integration**: Seamless integration with database servers via MCP tools

## Architecture

```
User Question → DBA Agent → MCP Server → Database
                    ↑           ↓
              SQL Analysis ← Results
                    ↑
              Natural Language Summary
```

## Setup

### Prerequisites

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure OpenAI API**:
   The agent uses OpenAI GPT-4o via LiteLLM. Set your API key:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```
   Or add it to your `.env` file:
   ```
   OPENAI_API_KEY=your-openai-api-key
   ```

3. **Start MCP Database Server**:
   ```bash
   cd mcp
   uv run mcp-db-server
   ```

4. **Configure Database**: The MCP server should be configured with your banking database.

### Usage

#### Basic Usage

```python
from dba_agent.agent import create_dba_agent, query_database_with_context

# Create the agent
agent = create_dba_agent()

# Define user context
user_context = {
    "AccountID": 126,
    "CustomerID": 202,
    "PersonID": 59
}

# Query the database
result = query_database_with_context(
    "What is my current balance?",
    user_context
)

print(result['agent_response'])
```

#### Advanced SQL Analysis

```python
from dba_agent.agent import analyze_bind_parameters

sql = "SELECT * FROM Account WHERE AccountID = :AccountID"
analysis = analyze_bind_parameters(sql)

print(f"Parameters: {analysis['parameters']}")
print(f"Tables: {analysis['tables_referenced']}")
```

## Database Schema

The agent expects a banking database with the following core tables:

- **Person**: Customer personal information
- **Customer**: Customer business entities
- **Account**: Bank accounts
- **BankTransaction**: Account transactions
- **Loan**: Loan information
- **LoanPayment**: Loan payment history
- **AccountCards**: Credit/debit cards
- **AccountCardsTransactions**: Card transactions

## Security Features

### Read-Only Operations
- Only SELECT statements are allowed
- No INSERT, UPDATE, DELETE operations
- Automatic SQL safety validation

### Data Privacy
- Never exposes full credit card numbers
- Respects user data ownership boundaries
- Uses parameterized queries to prevent SQL injection

### Access Control
- Default user context: AccountID=126, CustomerID=202, PersonID=59
- Users can only access their own data
- Proper parameter binding for user context

## SQL Parameter Guidelines

The agent follows strict parameter naming conventions:

- `:AccountID` for account filtering
- `:PersonID` for person-based queries
- `:CustomerID` for customer-related data
- `:CardID` for card-specific operations

## Example Queries

### Balance Inquiry
```sql
SELECT a.AccountNumber, a.CurrentBalance 
FROM Account a 
JOIN Customer c ON a.CustomerID = c.CustomerID 
WHERE c.PersonID = :PersonID
```

### Transaction History
```sql
SELECT t.TransactionType, t.Amount, t.TransactionDate 
FROM BankTransaction t 
JOIN Account a ON t.AccountID = a.AccountID 
JOIN Customer c ON a.CustomerID = c.CustomerID 
WHERE c.PersonID = :PersonID 
ORDER BY t.TransactionDate DESC 
LIMIT 10
```

### Card Information
```sql
SELECT ac.CardType, ac.CardStatus, 
       SUBSTR(ac.CardNumber, -4) as LastFourDigits,
       ac.ExpiryDate 
FROM AccountCards ac 
WHERE ac.CardHlderId = :PersonID
```

## Testing

Run the test suite to verify functionality:

```bash
python dba_agent/test_dba_agent.py
```

This will test:
- Agent creation
- SQL analysis
- MCP connection
- Query generation with context

## Configuration

### MCP Server Connection
The agent connects to the MCP server using:
- Command: `uv run mcp-db-server`
- Port: `50051`
- Working Directory: `./mcp`

### Timeout Configuration
Uses custom MCP patches for extended timeout support (180 seconds) to handle complex queries.

## Troubleshooting

### Common Issues

1. **MCP Server Not Running**:
   ```bash
   cd mcp
   uv run mcp-db-server --port 50051
   ```

2. **Import Errors**:
   Ensure all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. **Schema Cache Issues**:
   The agent automatically retrieves schema on first use. If schema changes, restart the agent.

### Debug Mode

Enable debug logging for detailed MCP communication:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Development

### Adding New Query Types

1. Update the prompt in `prompt.py` with new examples
2. Add corresponding test cases in `test_dba_agent.py`
3. Consider new parameter patterns in SQL analysis

### Extending Schema Support

To support additional database types:
1. Update the MCP server configuration
2. Modify the schema caching logic
3. Update SQL dialect settings in sqlglot

## Integration

The DBA agent can be integrated into larger applications:

- **Web APIs**: Expose as REST endpoints
- **Chat Interfaces**: Natural language database queries
- **Analytics Dashboards**: Automated report generation
- **Customer Service**: Real-time account information

## License

This project follows the same license as the main repository. 