"""
SQLite Database Manager with security best practices.

Security features:
- Parameterized queries to prevent SQL injection
- Input validation before database operations
- Transaction support for data integrity
- Backup functionality
- Schema migration for upgrades
"""
import sqlite3
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for asset inventory.
    Supports schema migration for seamless upgrades.
    """

    # Current schema version
    SCHEMA_VERSION = 2

    def __init__(self, db_path: str = None):
        if db_path is None:
            base_dir = Path(__file__).parent.parent
            db_path = str(base_dir / "inventory.db")
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the database schema and run migrations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create assets table with full schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    serial_number TEXT DEFAULT '',
                    estimated_value REAL NOT NULL CHECK(estimated_value >= 0),
                    location TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    purchase_price REAL DEFAULT NULL,
                    purchase_date TEXT DEFAULT NULL,
                    warranty_expiration TEXT DEFAULT NULL,
                    condition TEXT DEFAULT 'Good',
                    brand TEXT DEFAULT '',
                    model_number TEXT DEFAULT '',
                    tags TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create asset_photos table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS asset_photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    is_primary INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
                )
            ''')

            # Create activity_log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id INTEGER,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE SET NULL
                )
            ''')

            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_location ON assets(location)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_item_name ON assets(item_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_photos_asset_id ON asset_photos(asset_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_asset_id ON activity_log(asset_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at)')

            # Run migrations for existing databases
            self._migrate_schema(conn)

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def _migrate_schema(self, conn):
        """Add new columns to existing databases that lack them."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(assets)")
        existing_columns = {row['name'] for row in cursor.fetchall()}

        new_columns = {
            'purchase_price': 'REAL DEFAULT NULL',
            'purchase_date': 'TEXT DEFAULT NULL',
            'warranty_expiration': 'TEXT DEFAULT NULL',
            'condition': "TEXT DEFAULT 'Good'",
            'brand': "TEXT DEFAULT ''",
            'model_number': "TEXT DEFAULT ''",
            'tags': "TEXT DEFAULT ''",
        }

        for col_name, col_def in new_columns.items():
            if col_name not in existing_columns:
                cursor.execute(f'ALTER TABLE assets ADD COLUMN {col_name} {col_def}')
                logger.info(f"Added column: {col_name}")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    # =========================================================================
    # Asset CRUD
    # =========================================================================

    def add_asset(self, item_name: str, category: str, serial_number: str,
                  estimated_value: float, location: str, notes: str = "",
                  purchase_price: float = None, purchase_date: str = None,
                  warranty_expiration: str = None, condition: str = "Good",
                  brand: str = "", model_number: str = "",
                  tags: str = "") -> int:
        """Add a new asset. Returns the new asset ID."""
        if not item_name or not item_name.strip():
            raise ValueError("Item name is required")
        if not category or not category.strip():
            raise ValueError("Category is required")
        if not location or not location.strip():
            raise ValueError("Location is required")
        if estimated_value < 0:
            raise ValueError("Estimated value cannot be negative")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO assets (
                    item_name, category, serial_number, estimated_value,
                    location, notes, purchase_price, purchase_date,
                    warranty_expiration, condition, brand, model_number,
                    tags, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_name.strip(), category.strip(),
                serial_number.strip() if serial_number else "",
                round(estimated_value, 2), location.strip(),
                notes.strip() if notes else "",
                round(purchase_price, 2) if purchase_price is not None else None,
                purchase_date.strip() if purchase_date else None,
                warranty_expiration.strip() if warranty_expiration else None,
                condition.strip() if condition else "Good",
                brand.strip() if brand else "",
                model_number.strip() if model_number else "",
                tags.strip() if tags else "",
                datetime.now(), datetime.now()
            ))
            conn.commit()
            asset_id = cursor.lastrowid
            logger.info(f"Added asset: {item_name} (ID: {asset_id})")
            return asset_id

    def get_asset(self, asset_id: int) -> Optional[dict]:
        """Get a single asset by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, item_name, category, serial_number,
                       estimated_value, location, notes,
                       purchase_price, purchase_date, warranty_expiration,
                       condition, brand, model_number, tags,
                       created_at, updated_at
                FROM assets WHERE id = ?
            ''', (asset_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_assets(self, order_by: str = "created_at",
                       descending: bool = True) -> List[dict]:
        """Get all assets from the database."""
        allowed_columns = {
            'id', 'item_name', 'category', 'serial_number',
            'estimated_value', 'location', 'created_at', 'updated_at',
            'purchase_date', 'condition', 'brand', 'tags'
        }
        if order_by not in allowed_columns:
            order_by = 'created_at'
        direction = "DESC" if descending else "ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT id, item_name, category, serial_number,
                       estimated_value, location, notes,
                       purchase_price, purchase_date, warranty_expiration,
                       condition, brand, model_number, tags,
                       created_at, updated_at
                FROM assets ORDER BY {order_by} {direction}
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def update_asset(self, asset_id: int, item_name: str, category: str,
                     serial_number: str, estimated_value: float,
                     location: str, notes: str = "",
                     purchase_price: float = None, purchase_date: str = None,
                     warranty_expiration: str = None, condition: str = "Good",
                     brand: str = "", model_number: str = "",
                     tags: str = "") -> bool:
        """Update an existing asset. Returns True if successful."""
        if not item_name or not item_name.strip():
            raise ValueError("Item name is required")
        if not category or not category.strip():
            raise ValueError("Category is required")
        if not location or not location.strip():
            raise ValueError("Location is required")
        if estimated_value < 0:
            raise ValueError("Estimated value cannot be negative")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE assets SET
                    item_name = ?, category = ?, serial_number = ?,
                    estimated_value = ?, location = ?, notes = ?,
                    purchase_price = ?, purchase_date = ?,
                    warranty_expiration = ?, condition = ?,
                    brand = ?, model_number = ?, tags = ?,
                    updated_at = ?
                WHERE id = ?
            ''', (
                item_name.strip(), category.strip(),
                serial_number.strip() if serial_number else "",
                round(estimated_value, 2), location.strip(),
                notes.strip() if notes else "",
                round(purchase_price, 2) if purchase_price is not None else None,
                purchase_date.strip() if purchase_date else None,
                warranty_expiration.strip() if warranty_expiration else None,
                condition.strip() if condition else "Good",
                brand.strip() if brand else "",
                model_number.strip() if model_number else "",
                tags.strip() if tags else "",
                datetime.now(), asset_id
            ))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Updated asset ID: {asset_id}")
            return success

    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM assets WHERE id = ?', (asset_id,))
            conn.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info(f"Deleted asset ID: {asset_id}")
            return success

    def search_assets(self, query: str, category: str = None,
                      location: str = None, min_value: float = None,
                      max_value: float = None) -> List[dict]:
        """Search assets with various filters using parameterized queries."""
        conditions = []
        params = []

        if query:
            conditions.append(
                "(item_name LIKE ? OR brand LIKE ? OR model_number LIKE ? "
                "OR serial_number LIKE ? OR tags LIKE ? OR notes LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q, q, q, q, q])

        if category:
            conditions.append("category = ?")
            params.append(category)

        if location:
            conditions.append("location = ?")
            params.append(location)

        if min_value is not None:
            conditions.append("estimated_value >= ?")
            params.append(min_value)

        if max_value is not None:
            conditions.append("estimated_value <= ?")
            params.append(max_value)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT id, item_name, category, serial_number,
                       estimated_value, location, notes,
                       purchase_price, purchase_date, warranty_expiration,
                       condition, brand, model_number, tags,
                       created_at, updated_at
                FROM assets
                WHERE {where_clause}
                ORDER BY item_name ASC
            ''', params)
            return [dict(row) for row in cursor.fetchall()]

    def get_categories(self) -> List[str]:
        """Get list of unique categories."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT category FROM assets
                WHERE category != '' ORDER BY category
            ''')
            return [row['category'] for row in cursor.fetchall()]

    def get_locations(self) -> List[str]:
        """Get list of unique locations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT location FROM assets
                WHERE location != '' ORDER BY location
            ''')
            return [row['location'] for row in cursor.fetchall()]

    def get_summary(self) -> dict:
        """Get inventory summary statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT COUNT(*) as count,
                       COALESCE(SUM(estimated_value), 0) as total,
                       COALESCE(AVG(estimated_value), 0) as avg_value,
                       COALESCE(MAX(estimated_value), 0) as max_value
                FROM assets
            ''')
            row = cursor.fetchone()

            cursor.execute('''
                SELECT category, COUNT(*) as count,
                       SUM(estimated_value) as value
                FROM assets GROUP BY category ORDER BY value DESC
            ''')
            categories = [dict(r) for r in cursor.fetchall()]

            cursor.execute('''
                SELECT location, COUNT(*) as count,
                       SUM(estimated_value) as value
                FROM assets GROUP BY location ORDER BY value DESC
            ''')
            locations = [dict(r) for r in cursor.fetchall()]

            # Condition breakdown
            cursor.execute('''
                SELECT condition, COUNT(*) as count
                FROM assets GROUP BY condition ORDER BY count DESC
            ''')
            conditions = [dict(r) for r in cursor.fetchall()]

            # Warranty stats
            cursor.execute('''
                SELECT COUNT(*) as count FROM assets
                WHERE warranty_expiration IS NOT NULL
                AND warranty_expiration >= date('now')
            ''')
            active_warranties = cursor.fetchone()['count']

            cursor.execute('''
                SELECT COUNT(*) as count FROM assets
                WHERE warranty_expiration IS NOT NULL
                AND warranty_expiration < date('now')
            ''')
            expired_warranties = cursor.fetchone()['count']

            return {
                'total_items': row['count'],
                'total_value': row['total'],
                'avg_value': row['avg_value'],
                'max_value': row['max_value'],
                'categories': categories,
                'locations': locations,
                'conditions': conditions,
                'active_warranties': active_warranties,
                'expired_warranties': expired_warranties,
            }

    # =========================================================================
    # Photo Management
    # =========================================================================

    def add_photo(self, asset_id: int, filename: str,
                  original_filename: str, is_primary: bool = False) -> int:
        """Add a photo record for an asset."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # If this is set as primary, unset any existing primary
            if is_primary:
                cursor.execute(
                    'UPDATE asset_photos SET is_primary = 0 WHERE asset_id = ?',
                    (asset_id,)
                )

            # If this is the first photo, make it primary
            cursor.execute(
                'SELECT COUNT(*) as count FROM asset_photos WHERE asset_id = ?',
                (asset_id,)
            )
            if cursor.fetchone()['count'] == 0:
                is_primary = True

            cursor.execute('''
                INSERT INTO asset_photos (asset_id, filename, original_filename, is_primary, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (asset_id, filename, original_filename, 1 if is_primary else 0, datetime.now()))
            conn.commit()
            return cursor.lastrowid

    def get_photos(self, asset_id: int) -> List[dict]:
        """Get all photos for an asset."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, asset_id, filename, original_filename, is_primary, created_at
                FROM asset_photos WHERE asset_id = ?
                ORDER BY is_primary DESC, created_at ASC
            ''', (asset_id,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_photo(self, photo_id: int) -> Optional[str]:
        """Delete a photo record. Returns the filename for file cleanup."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filename, asset_id, is_primary FROM asset_photos WHERE id = ?', (photo_id,))
            row = cursor.fetchone()
            if not row:
                return None

            filename = row['filename']
            asset_id = row['asset_id']
            was_primary = row['is_primary']

            cursor.execute('DELETE FROM asset_photos WHERE id = ?', (photo_id,))

            # If the deleted photo was primary, promote another
            if was_primary:
                cursor.execute(
                    'UPDATE asset_photos SET is_primary = 1 WHERE asset_id = ? LIMIT 1',
                    (asset_id,)
                )

            conn.commit()
            return filename

    def set_primary_photo(self, asset_id: int, photo_id: int) -> bool:
        """Set a photo as the primary photo for an asset."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE asset_photos SET is_primary = 0 WHERE asset_id = ?',
                (asset_id,)
            )
            cursor.execute(
                'UPDATE asset_photos SET is_primary = 1 WHERE id = ? AND asset_id = ?',
                (photo_id, asset_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_photo_count(self, asset_id: int) -> int:
        """Get photo count for an asset."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) as count FROM asset_photos WHERE asset_id = ?',
                (asset_id,)
            )
            return cursor.fetchone()['count']

    # =========================================================================
    # Activity Log
    # =========================================================================

    def log_activity(self, asset_id: int, action: str, details: str = "") -> int:
        """Log an activity."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO activity_log (asset_id, action, details, created_at)
                VALUES (?, ?, ?, ?)
            ''', (asset_id, action, details, datetime.now()))
            conn.commit()
            return cursor.lastrowid

    def get_activity_log(self, asset_id: int = None, limit: int = 50) -> List[dict]:
        """Get activity log entries, optionally filtered by asset."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if asset_id:
                cursor.execute('''
                    SELECT al.id, al.asset_id, al.action, al.details, al.created_at,
                           a.item_name
                    FROM activity_log al
                    LEFT JOIN assets a ON al.asset_id = a.id
                    WHERE al.asset_id = ?
                    ORDER BY al.created_at DESC LIMIT ?
                ''', (asset_id, limit))
            else:
                cursor.execute('''
                    SELECT al.id, al.asset_id, al.action, al.details, al.created_at,
                           a.item_name
                    FROM activity_log al
                    LEFT JOIN assets a ON al.asset_id = a.id
                    ORDER BY al.created_at DESC LIMIT ?
                ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_activity_count(self, days: int = 30) -> int:
        """Get count of activity in the last N days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM activity_log
                WHERE created_at >= datetime('now', ?)
            ''', (f'-{days} days',))
            return cursor.fetchone()['count']

    # =========================================================================
    # Backup & Import
    # =========================================================================

    def backup_database(self, backup_path: str = None) -> str:
        """Create a backup of the database using SQLite backup API."""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_dir = Path(self.db_path).parent
            backup_path = str(base_dir / f"inventory_backup_{timestamp}.db")

        with self._get_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()

        logger.info(f"Database backed up to: {backup_path}")
        return backup_path

    def import_from_csv(self, csv_path: str) -> Tuple[int, int]:
        """Import assets from a legacy CSV file."""
        import csv

        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        successful = 0
        failed = 0

        with open(csv_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    self.add_asset(
                        item_name=row.get('Item Name', ''),
                        category=row.get('Category', ''),
                        serial_number=row.get('Serial Number', ''),
                        estimated_value=float(row.get('Estimated Value', 0)),
                        location=row.get('Location', ''),
                        notes=row.get('Notes', '')
                    )
                    successful += 1
                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to import row: {e}")
                    failed += 1

        logger.info(f"CSV import complete: {successful} successful, {failed} failed")
        return successful, failed
