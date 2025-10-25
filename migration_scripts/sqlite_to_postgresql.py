"""
SQLite to PostgreSQL Migration Script for telegram-training-bot.

This script safely migrates data from SQLite to PostgreSQL production database.

Usage:
    python migration_scripts/sqlite_to_postgresql.py \
        --sqlite-path training_bot.db \
        --postgres-url postgresql://botuser:password@localhost/training_bot \
        --dry-run  # Optional: test without making changes

Requirements:
    - Source SQLite database file
    - Target PostgreSQL database (must be initialized with schema)
    - asyncpg and aiosqlite packages installed
"""

import asyncio
import sqlite3
import asyncpg
import argparse
import sys
from datetime import datetime
from typing import List, Tuple, Dict, Any
import logging


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseMigration:
    """Handle database migration from SQLite to PostgreSQL"""

    def __init__(self, sqlite_path: str, postgres_url: str, dry_run: bool = False):
        """
        Initialize migration.

        Args:
            sqlite_path: Path to SQLite database file
            postgres_url: PostgreSQL connection URL
            dry_run: If True, don't commit changes
        """
        self.sqlite_path = sqlite_path
        self.postgres_url = postgres_url
        self.dry_run = dry_run
        self.stats = {
            'users': {'migrated': 0, 'skipped': 0, 'errors': 0},
            'user_activity': {'migrated': 0, 'skipped': 0, 'errors': 0}
        }

    async def migrate(self):
        """Execute full migration"""
        logger.info("=" * 60)
        logger.info("Starting database migration: SQLite → PostgreSQL")
        logger.info("=" * 60)

        if self.dry_run:
            logger.warning("🔍 DRY RUN MODE - No changes will be committed")

        try:
            # Connect to databases
            logger.info(f"📁 Connecting to SQLite: {self.sqlite_path}")
            sqlite_conn = self.connect_sqlite()

            logger.info(f"🐘 Connecting to PostgreSQL...")
            pg_conn = await self.connect_postgresql()

            # Verify schema
            logger.info("🔍 Verifying PostgreSQL schema...")
            await self.verify_schema(pg_conn)

            # Migrate tables
            logger.info("\n📊 Migrating users table...")
            await self.migrate_users(sqlite_conn, pg_conn)

            logger.info("\n📊 Migrating user_activity table...")
            await self.migrate_user_activity(sqlite_conn, pg_conn)

            # Print summary
            self.print_summary()

            # Verify data integrity
            if not self.dry_run:
                logger.info("\n🔍 Verifying data integrity...")
                await self.verify_integrity(sqlite_conn, pg_conn)

            # Cleanup
            sqlite_conn.close()
            await pg_conn.close()

            logger.info("\n✅ Migration completed successfully!")

            return True

        except Exception as e:
            logger.error(f"\n❌ Migration failed: {e}")
            raise

    def connect_sqlite(self) -> sqlite3.Connection:
        """Connect to SQLite database"""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to SQLite: {e}")
            raise

    async def connect_postgresql(self) -> asyncpg.Connection:
        """Connect to PostgreSQL database"""
        try:
            conn = await asyncpg.connect(self.postgres_url)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    async def verify_schema(self, pg_conn: asyncpg.Connection):
        """Verify PostgreSQL schema exists"""
        # Check if users table exists
        users_exists = await pg_conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            )
        """)

        if not users_exists:
            logger.error("PostgreSQL schema not initialized. Run Alembic migrations first!")
            raise RuntimeError("Schema missing")

        logger.info("✓ PostgreSQL schema verified")

    async def migrate_users(
        self,
        sqlite_conn: sqlite3.Connection,
        pg_conn: asyncpg.Connection
    ):
        """Migrate users table"""
        # Fetch all users from SQLite
        cursor = sqlite_conn.execute("SELECT * FROM users")
        users = cursor.fetchall()

        logger.info(f"Found {len(users)} users in SQLite")

        for user in users:
            try:
                # Check if user already exists in PostgreSQL
                exists = await pg_conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM users WHERE telegram_id = $1)",
                    user['telegram_id']
                )

                if exists:
                    logger.debug(f"User {user['telegram_id']} already exists, skipping")
                    self.stats['users']['skipped'] += 1
                    continue

                # Insert user
                if not self.dry_run:
                    await pg_conn.execute("""
                        INSERT INTO users (
                            telegram_id, full_name, username,
                            department, position, park_location,
                            created_at, updated_at, is_blocked
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                        user['telegram_id'],
                        user['full_name'],
                        user.get('username'),
                        user.get('department'),
                        user.get('position'),
                        user.get('park_location'),
                        user.get('created_at', datetime.utcnow()),
                        user.get('updated_at', datetime.utcnow()),
                        user.get('is_blocked', False)
                    )

                self.stats['users']['migrated'] += 1
                if self.stats['users']['migrated'] % 10 == 0:
                    logger.info(f"  Migrated {self.stats['users']['migrated']} users...")

            except Exception as e:
                logger.error(f"Error migrating user {user['telegram_id']}: {e}")
                self.stats['users']['errors'] += 1

        logger.info(f"✓ Users migration complete: {self.stats['users']['migrated']} migrated, "
                   f"{self.stats['users']['skipped']} skipped, {self.stats['users']['errors']} errors")

    async def migrate_user_activity(
        self,
        sqlite_conn: sqlite3.Connection,
        pg_conn: asyncpg.Connection
    ):
        """Migrate user_activity table"""
        # Check if table exists
        cursor = sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity'"
        )
        if not cursor.fetchone():
            logger.warning("⚠️  user_activity table not found in SQLite, skipping")
            return

        # Fetch all activities from SQLite
        cursor = sqlite_conn.execute("SELECT * FROM user_activity ORDER BY timestamp")
        activities = cursor.fetchall()

        logger.info(f"Found {len(activities)} activity records in SQLite")

        # Use batch insert for better performance
        batch_size = 100
        for i in range(0, len(activities), batch_size):
            batch = activities[i:i + batch_size]

            try:
                if not self.dry_run:
                    # Prepare batch insert
                    values = []
                    for activity in batch:
                        values.append((
                            activity['user_id'],
                            activity['action'],
                            activity.get('section'),
                            activity.get('details'),
                            activity.get('timestamp', datetime.utcnow())
                        ))

                    # Insert batch
                    await pg_conn.executemany("""
                        INSERT INTO user_activity (
                            user_id, action, section, details, timestamp
                        )
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT DO NOTHING
                    """, values)

                self.stats['user_activity']['migrated'] += len(batch)
                logger.info(f"  Migrated {self.stats['user_activity']['migrated']} activity records...")

            except Exception as e:
                logger.error(f"Error migrating activity batch: {e}")
                self.stats['user_activity']['errors'] += len(batch)

        logger.info(f"✓ Activity migration complete: {self.stats['user_activity']['migrated']} migrated, "
                   f"{self.stats['user_activity']['errors']} errors")

    async def verify_integrity(
        self,
        sqlite_conn: sqlite3.Connection,
        pg_conn: asyncpg.Connection
    ):
        """Verify data integrity after migration"""
        # Count users
        sqlite_count = sqlite_conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        pg_count = await pg_conn.fetchval("SELECT COUNT(*) FROM users")

        logger.info(f"  Users: SQLite={sqlite_count}, PostgreSQL={pg_count}")

        if sqlite_count != pg_count:
            logger.warning(f"⚠️  User count mismatch! Difference: {sqlite_count - pg_count}")
        else:
            logger.info("  ✓ User counts match")

        # Sample verification
        sample_user = sqlite_conn.execute(
            "SELECT telegram_id, full_name FROM users LIMIT 1"
        ).fetchone()

        if sample_user:
            pg_user = await pg_conn.fetchrow(
                "SELECT telegram_id, full_name FROM users WHERE telegram_id = $1",
                sample_user['telegram_id']
            )

            if pg_user:
                logger.info(f"  ✓ Sample user verification passed (ID: {sample_user['telegram_id']})")
            else:
                logger.error(f"  ❌ Sample user not found in PostgreSQL!")

    def print_summary(self):
        """Print migration summary"""
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)

        for table, stats in self.stats.items():
            logger.info(f"\n{table.upper()}:")
            logger.info(f"  ✅ Migrated: {stats['migrated']}")
            logger.info(f"  ⏭️  Skipped:  {stats['skipped']}")
            logger.info(f"  ❌ Errors:   {stats['errors']}")

        total_migrated = sum(s['migrated'] for s in self.stats.values())
        total_errors = sum(s['errors'] for s in self.stats.values())

        logger.info(f"\nTOTAL: {total_migrated} records migrated, {total_errors} errors")

        if self.dry_run:
            logger.info("\n⚠️  DRY RUN - No changes were committed to database")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Migrate telegram-training-bot database from SQLite to PostgreSQL"
    )
    parser.add_argument(
        '--sqlite-path',
        default='training_bot.db',
        help='Path to SQLite database file (default: training_bot.db)'
    )
    parser.add_argument(
        '--postgres-url',
        required=True,
        help='PostgreSQL connection URL (e.g., postgresql://user:pass@host/dbname)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test migration without committing changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Confirm if not dry run
    if not args.dry_run:
        logger.warning("\n⚠️  WARNING: This will modify the PostgreSQL database!")
        response = input("Continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Migration cancelled")
            return

    # Execute migration
    migration = DatabaseMigration(
        sqlite_path=args.sqlite_path,
        postgres_url=args.postgres_url,
        dry_run=args.dry_run
    )

    try:
        await migration.migrate()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
