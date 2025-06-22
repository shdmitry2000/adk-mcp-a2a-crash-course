# Database Configuration Examples

## Using Environment Variables

Create a `.env` file in your project root:

```bash
# SQLite
DATABASE_URL="sqlite:///default_database.db"

# PostgreSQL with SSL
DATABASE_URL="postgresql://postgres.catkqzfqptcuuknktvrx:supbaseTest12345@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
DATABASE_SSL_CERT="/etc/ssl/certs/prod-ca-2021.crt"

# MySQL
DATABASE_URL="mysql://user:password@localhost:3306/mydatabase"
```

## Usage Examples

### Option 1: Using DATABASE_URL (Recommended)

```bash
# Set environment variables
export DATABASE_URL="sqlite:///db/default_database.db"
python -m mcp_db_server

# Or with PostgreSQL and SSL
export DATABASE_URL="postgresql://postgres.catkqzfqptcuuknktvrx:supbaseTest12345@aws-0-eu-west-2.pooler.supabase.com:6543/postgres"
export DATABASE_SSL_CERT="/etc/ssl/certs/prod-ca-2021.crt"
python -m mcp_db_server

# Or pass directly as argument
python -m mcp_db_server --database-url "sqlite:///db/generated_data.db"

# PostgreSQL with SSL certificate
python -m mcp_db_server \
  --database-url "postgresql://postgres.catkqzfqptcuuknktvrx:supbaseTest12345@aws-0-eu-west-2.pooler.supabase.com:6543/postgres" \
  --database-ssl-cert "/etc/ssl/certs/prod-ca-2021.crt"
```

### Option 2: Individual Parameters (Legacy)

```bash
# MySQL
python -m mcp_db_server --db-type mysql --db-host localhost --db-user root --db-password pass --db-database mydb

# PostgreSQL with SSL
python -m mcp_db_server --db-type postgresql --db-host localhost --db-user postgres --db-password pass --db-database mydb --database-ssl-cert /path/to/cert.crt

# SQLite
python -m mcp_db_server --db-type sqlite --db-database /path/to/database.db
```

## Supported DATABASE_URL Formats

### SQLite
```
sqlite:///absolute/path/to/database.db
sqlite://relative/path/to/database.db
sqlite:///default_database.db
```

### PostgreSQL
```
postgresql://username:password@hostname:port/database
postgres://username:password@hostname:port/database
```

### MySQL
```
mysql://username:password@hostname:port/database
```

## SSL Configuration

For PostgreSQL connections that require SSL certificates:

1. **Environment Variable**: Set `DATABASE_SSL_CERT` to the certificate file path
2. **Command Line**: Use `--database-ssl-cert /path/to/cert.crt`

The SSL certificate will be used with `sslmode=require` for PostgreSQL connections.

## Priority Order

The system checks configuration in this order:
1. Command line `--database-url` argument
2. `DATABASE_URL` environment variable
3. Individual command line parameters (`--db-type`, `--db-host`, etc.)

## Benefits of DATABASE_URL

- **Industry Standard**: Used by Heroku, Railway, Supabase, and many other platforms
- **Single Configuration**: One string contains all connection info
- **Environment Friendly**: Easy to set via environment variables
- **Secure**: Keeps credentials in environment rather than command line history