"""
Modified __init__.py to support multiple database types
"""
import asyncio
import argparse
import os
import sys
import logging
from . import server,bind_analyzer


def load_dotenv():
    """Load environment variables from .env file if it exists"""
    try:
        env_path = os.path.join(os.getcwd(), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            return True
    except Exception:
        pass
    return False


def main():
    """
    Main entry point for the mcp_sql_server package.

    Parses command-line arguments and starts the MCP SQL server.
    """
    # Load .env file if it exists
    load_dotenv()
    
    parser = argparse.ArgumentParser(description='Multi-Database MCP Server (read-only)')

    # Option 1: DATABASE_URL (preferred)
    parser.add_argument('--database-url',
                        help='Database URL (e.g., sqlite:///db.db, postgresql://user:pass@host:port/db)')
    
    # Option 2: Individual parameters (legacy support)
    parser.add_argument('--db-type', 
                        choices=['mysql', 'postgresql', 'sqlite'],
                        help='Database type (only needed if not using --database-url)')
    parser.add_argument('--db-host',
                        help='Database host (not used for SQLite)')
    parser.add_argument('--db-user',
                        help='Database user (not used for SQLite)')
    parser.add_argument('--db-password',
                        help='Database password (not used for SQLite)')
    parser.add_argument('--db-database',
                        help='Database name or SQLite file path')
    parser.add_argument('--db-port',
                        type=int,
                        help='Database port (optional)')
    
    # SSL configuration
    parser.add_argument('--database-ssl-cert',
                        help='Path to SSL certificate file (for PostgreSQL)')

    args = parser.parse_args()
    
    # Check for DATABASE_URL in environment variables if not provided as argument
    database_url = args.database_url or os.getenv('DATABASE_URL')
    ssl_cert = args.database_ssl_cert or os.getenv('DATABASE_SSL_CERT')
    
    if database_url:
        # Use DATABASE_URL
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        logger = logging.getLogger(__name__)
        logger.info(f"Using DATABASE_URL: {database_url[:20]}...")
        asyncio.run(server.main_with_url(database_url, ssl_cert))
    else:
        # Use individual parameters (legacy mode)
        if not args.db_type or not args.db_database:
            parser.error("Either --database-url or --db-type and --db-database are required")
        
        # Validate arguments based on database type
        if args.db_type in ['mysql', 'postgresql']:
            if not args.db_host or not args.db_user or not args.db_password:
                parser.error(f"--db-host, --db-user, and --db-password are required for {args.db_type}")
        
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)
        logger = logging.getLogger(__name__)
        logger.info(f"Starting server with args: {args}")
        asyncio.run(server.main(
            db_type=args.db_type,
            host=args.db_host,
            user=args.db_user,
            password=args.db_password,
            database=args.db_database,
            port=args.db_port,
            ssl_cert=ssl_cert
        ))


__all__ = ["main", "server"]

if __name__ == "__main__":
    main()