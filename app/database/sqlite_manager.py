import sqlite3
import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

class SQLiteManager:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name, check_same_thread=False)
            self.conn.row_factory = self._dict_factory
            logger.info(f"Successfully connected to SQLite database: {self.db_name}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to SQLite database: {e}")
            raise

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _create_tables(self):
        """Create tables if they don't exist and add new columns if missing."""
        try:
            with self.conn:
                # Create articles table if it doesn't exist
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    display_id TEXT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    source TEXT,
                    author TEXT,
                    date TEXT,
                    category TEXT,
                    description TEXT,
                    article_body TEXT,
                    image_url TEXT,
                    status TEXT DEFAULT 'pulled',
                    quality_score INTEGER,
                    sentiment_score REAL,
                    ai_tags TEXT,
                    ai_summary TEXT,
                    content_hash TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP
                );
                """)
                
                # Create activity_logs table
                self.conn.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    activity_type TEXT NOT NULL,
                    details TEXT,
                    status TEXT
                );
                """)
                
                # Add new columns to articles table if they don't exist (for backward compatibility)
                self._add_column_if_not_exists('articles', 'display_id', 'TEXT')
                self._add_column_if_not_exists('articles', 'published_at', 'TIMESTAMP')
                self._add_column_if_not_exists('articles', 'status', 'TEXT', "DEFAULT 'pulled'")
                
                logger.info("Tables and columns are up to date.")
        except sqlite3.Error as e:
            logger.error(f"Error creating/updating tables: {e}")

    def _add_column_if_not_exists(self, table_name: str, column_name: str, column_type: str, extras: str = ""):
        """Utility to add a column to a table if it's not already there."""
        try:
            # Temporarily disable dict_factory for this operation
            self.conn.row_factory = None
            cursor = self.conn.cursor()
            
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [info[1] for info in cursor.fetchall()]
            
            if column_name not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {extras}")
                logger.info(f"Added column '{column_name}' to table '{table_name}'.")

        except sqlite3.Error as e:
            logger.error(f"Error adding column {column_name} to {table_name}: {e}")
        finally:
            # Restore the default row factory
            self.conn.row_factory = self._dict_factory

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error executing query: {e}")
            return []

    def execute_update(self, query: str, params: tuple = ()) -> Optional[int]:
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute(query, params)
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error executing update: {e}")
            return None

    def commit(self):
        """Commit the current transaction."""
        if self.conn:
            try:
                self.conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Failed to commit transaction: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("SQLite connection closed.")

    def get_connection(self):
        return self.conn 