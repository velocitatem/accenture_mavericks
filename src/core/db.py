import os
from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool


class DatabaseConnection:
    """PostgreSQL database connection manager with connection pooling."""

    def __init__(self, min_conn=1, max_conn=10):
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'mavericks'),
            'user': os.getenv('POSTGRES_USER', 'mavericks'),
            'password': os.getenv('POSTGRES_PASSWORD', 'mavericks')
        }
        self.pool = SimpleConnectionPool(min_conn, max_conn, **self.db_config)

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.pool.putconn(conn)

    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """Context manager for database cursors with dict results."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()

    def execute_query(self, query, params=None):
        """Execute a query and return results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query, params=None):
        """Execute an update/insert/delete query."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount

    def close_all(self):
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()


db = DatabaseConnection()
