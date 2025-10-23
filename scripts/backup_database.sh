#!/bin/bash

###############################################################################
# Database Backup Script for Telegram Training Bot
#
# This script creates automated backups of the database and uploads them
# to cloud storage or remote server.
#
# Usage:
#   ./scripts/backup_database.sh [OPTIONS]
#
# Options:
#   -t, --type       Database type (sqlite|postgres) [default: auto-detect]
#   -d, --dest       Backup destination directory [default: ./backups]
#   -r, --retention  Days to keep backups [default: 30]
#   -c, --compress   Compress backups (gzip) [default: yes]
#   -u, --upload     Upload to cloud (s3|gdrive|none) [default: none]
#   -h, --help       Show this help message
#
# Environment Variables (from .env):
#   DATABASE_URL     - Database connection string
#   BACKUP_S3_BUCKET - AWS S3 bucket for backups (optional)
#   BACKUP_S3_REGION - AWS S3 region (optional)
#   GDRIVE_FOLDER_ID - Google Drive folder ID (optional)
#
# Cron Setup Example:
#   # Daily backup at 2:00 AM
#   0 2 * * * /path/to/telegram-training-bot/scripts/backup_database.sh -u s3
#
#   # Weekly backup on Sunday at 3:00 AM
#   0 3 * * 0 /path/to/telegram-training-bot/scripts/backup_database.sh -u s3
#
###############################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
DB_TYPE="auto"
RETENTION_DAYS=30
COMPRESS=true
UPLOAD_TYPE="none"

# Load .env file if exists
if [ -f "${PROJECT_DIR}/.env" ]; then
    export $(cat "${PROJECT_DIR}/.env" | grep -v '^#' | xargs)
fi

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            DB_TYPE="$2"
            shift 2
            ;;
        -d|--dest)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -r|--retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -c|--compress)
            COMPRESS="$2"
            shift 2
            ;;
        -u|--upload)
            UPLOAD_TYPE="$2"
            shift 2
            ;;
        -h|--help)
            grep "^#" "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Auto-detect database type from DATABASE_URL
if [ "$DB_TYPE" = "auto" ]; then
    if [[ "$DATABASE_URL" == *"sqlite"* ]]; then
        DB_TYPE="sqlite"
    elif [[ "$DATABASE_URL" == *"postgres"* ]]; then
        DB_TYPE="postgres"
    else
        echo -e "${RED}Error: Cannot auto-detect database type from DATABASE_URL${NC}"
        exit 1
    fi
fi

# Generate timestamp for backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="telegram_bot_backup_${TIMESTAMP}"

echo -e "${GREEN}Starting database backup...${NC}"
echo "Database Type: $DB_TYPE"
echo "Backup Directory: $BACKUP_DIR"
echo "Timestamp: $TIMESTAMP"

# Perform backup based on database type
case $DB_TYPE in
    sqlite)
        # Extract SQLite database file path from DATABASE_URL
        DB_FILE=$(echo "$DATABASE_URL" | sed 's/.*:\/\///' | sed 's/\?.*//')

        if [ ! -f "$DB_FILE" ]; then
            echo -e "${RED}Error: SQLite database file not found: $DB_FILE${NC}"
            exit 1
        fi

        echo "Backing up SQLite database: $DB_FILE"

        # Create backup
        BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.db"
        cp "$DB_FILE" "$BACKUP_FILE"

        echo -e "${GREEN}✓ SQLite backup created: $BACKUP_FILE${NC}"
        ;;

    postgres)
        # Extract PostgreSQL connection details
        # Format: postgresql://user:password@host:port/database
        PG_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
        PG_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
        PG_DB=$(echo "$DATABASE_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')
        PG_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')
        PG_PASS=$(echo "$DATABASE_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')

        echo "Backing up PostgreSQL database: $PG_DB on $PG_HOST:$PG_PORT"

        # Set password for pg_dump
        export PGPASSWORD="$PG_PASS"

        # Create backup
        BACKUP_FILE="${BACKUP_DIR}/${BACKUP_NAME}.sql"
        pg_dump -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
                -F p -f "$BACKUP_FILE"

        # Unset password
        unset PGPASSWORD

        echo -e "${GREEN}✓ PostgreSQL backup created: $BACKUP_FILE${NC}"
        ;;

    *)
        echo -e "${RED}Error: Unsupported database type: $DB_TYPE${NC}"
        exit 1
        ;;
esac

# Compress backup if enabled
if [ "$COMPRESS" = true ] || [ "$COMPRESS" = "yes" ]; then
    echo "Compressing backup..."
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    echo -e "${GREEN}✓ Backup compressed: $BACKUP_FILE${NC}"
fi

# Upload to cloud storage if specified
case $UPLOAD_TYPE in
    s3)
        if [ -z "${BACKUP_S3_BUCKET:-}" ]; then
            echo -e "${YELLOW}Warning: BACKUP_S3_BUCKET not set, skipping upload${NC}"
        else
            echo "Uploading to AWS S3: s3://$BACKUP_S3_BUCKET/"
            aws s3 cp "$BACKUP_FILE" "s3://$BACKUP_S3_BUCKET/backups/" \
                --region "${BACKUP_S3_REGION:-us-east-1}"
            echo -e "${GREEN}✓ Backup uploaded to S3${NC}"
        fi
        ;;

    gdrive)
        if [ -z "${GDRIVE_FOLDER_ID:-}" ]; then
            echo -e "${YELLOW}Warning: GDRIVE_FOLDER_ID not set, skipping upload${NC}"
        else
            echo "Uploading to Google Drive..."
            gdrive upload --parent "$GDRIVE_FOLDER_ID" "$BACKUP_FILE"
            echo -e "${GREEN}✓ Backup uploaded to Google Drive${NC}"
        fi
        ;;

    none)
        echo "Skipping cloud upload (local backup only)"
        ;;

    *)
        echo -e "${YELLOW}Warning: Unknown upload type: $UPLOAD_TYPE${NC}"
        ;;
esac

# Clean up old backups
echo "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "telegram_bot_backup_*" -type f -mtime +$RETENTION_DAYS -delete
echo -e "${GREEN}✓ Old backups cleaned up${NC}"

# Get backup file size
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Backup completed successfully!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo "Backup file: $BACKUP_FILE"
echo "Size: $BACKUP_SIZE"
echo "Upload: $UPLOAD_TYPE"
echo ""

exit 0
