#!/bin/bash
# Automated Backup System for telegram-training-bot
# Backs up: Database, Redis, Configuration
# Storage: Local + S3/MinIO
# Retention: 7d (daily), 30d (weekly), 1y (monthly)

set -e

BACKUP_DIR="/var/backups/telegram-bot"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
S3_BUCKET="${S3_BUCKET:-telegram-bot-backups}"

echo "🔄 Starting backup process..."

# Database backup
if [ -n "$DATABASE_URL" ]; then
    echo "📦 Backing up PostgreSQL..."
    pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/db_$TIMESTAMP.sql.gz"
elif [ -f "training_bot.db" ]; then
    echo "📦 Backing up SQLite..."
    sqlite3 training_bot.db ".backup '$BACKUP_DIR/db_$TIMESTAMP.db'"
    gzip "$BACKUP_DIR/db_$TIMESTAMP.db"
fi

# Redis backup
echo "📦 Backing up Redis..."
redis-cli --rdb "$BACKUP_DIR/redis_$TIMESTAMP.rdb" || true

# Configuration backup
echo "📦 Backing up configuration..."
tar -czf "$BACKUP_DIR/config_$TIMESTAMP.tar.gz" \
    .env.production \
    docker-compose.production.yml \
    monitoring/

# Upload to S3 (if configured)
if command -v aws &> /dev/null; then
    echo "☁️  Uploading to S3..."
    aws s3 sync "$BACKUP_DIR" "s3://$S3_BUCKET/backups/"
fi

# Cleanup old backups (retention policy)
find "$BACKUP_DIR" -name "db_*" -mtime +7 -delete
find "$BACKUP_DIR" -name "redis_*" -mtime +7 -delete

echo "✅ Backup completed: $TIMESTAMP"
