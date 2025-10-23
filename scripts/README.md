# Scripts Directory

This directory contains utility scripts for database management and maintenance.

## 📦 Available Scripts

### `backup_database.sh`

Automated database backup script with cloud upload support.

**Features:**
- ✅ Supports SQLite and PostgreSQL
- ✅ Automatic compression (gzip)
- ✅ Cloud upload (AWS S3, Google Drive)
- ✅ Automatic cleanup of old backups
- ✅ Configurable retention period
- ✅ Cron-ready

**Usage:**

```bash
# Basic backup (local only)
./scripts/backup_database.sh

# Backup with S3 upload
./scripts/backup_database.sh --upload s3

# Backup with custom retention
./scripts/backup_database.sh --retention 60

# See all options
./scripts/backup_database.sh --help
```

**Environment Variables:**

Add these to your `.env` file:

```bash
# Required
DATABASE_URL=your_database_url

# Optional - for S3 uploads
BACKUP_S3_BUCKET=your-s3-bucket-name
BACKUP_S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Optional - for Google Drive uploads
GDRIVE_FOLDER_ID=your-folder-id
```

**Cron Setup:**

Edit crontab:
```bash
crontab -e
```

Add one of these lines:

```bash
# Daily backup at 2:00 AM
0 2 * * * /path/to/telegram-training-bot/scripts/backup_database.sh -u s3 >> /var/log/bot-backup.log 2>&1

# Weekly backup on Sunday at 3:00 AM
0 3 * * 0 /path/to/telegram-training-bot/scripts/backup_database.sh -u s3 >> /var/log/bot-backup.log 2>&1

# Hourly backup (for critical data)
0 * * * * /path/to/telegram-training-bot/scripts/backup_database.sh >> /var/log/bot-backup.log 2>&1
```

**Restore from Backup:**

SQLite:
```bash
# Decompress if needed
gunzip backups/telegram_bot_backup_20250123_020000.db.gz

# Restore
cp backups/telegram_bot_backup_20250123_020000.db bot.db
```

PostgreSQL:
```bash
# Decompress if needed
gunzip backups/telegram_bot_backup_20250123_020000.sql.gz

# Restore
psql -h localhost -U postgres -d training_bot < backups/telegram_bot_backup_20250123_020000.sql
```

---

## 🔧 System Requirements

**For SQLite backups:**
- `cp` (standard on all systems)
- `gzip` (for compression)

**For PostgreSQL backups:**
- `pg_dump` (PostgreSQL client tools)
- `gzip` (for compression)

**For S3 uploads:**
- AWS CLI (`aws`)
- Configured AWS credentials

**For Google Drive uploads:**
- `gdrive` CLI tool
- Authenticated Google Drive account

---

## 🚨 Troubleshooting

### "Cannot auto-detect database type"
- Ensure `DATABASE_URL` is set in `.env`
- Or specify type manually: `--type sqlite` or `--type postgres`

### "pg_dump: command not found"
```bash
# Install PostgreSQL client tools
sudo apt-get install postgresql-client  # Debian/Ubuntu
brew install postgresql                 # macOS
```

### "aws: command not found"
```bash
# Install AWS CLI
pip install awscli
# Configure credentials
aws configure
```

### Backup failed with "Permission denied"
```bash
# Make script executable
chmod +x scripts/backup_database.sh

# Check directory permissions
chmod 755 backups/
```

---

## 📝 Best Practices

1. **Test restores regularly** - Backups are useless if they can't be restored
2. **Store backups off-site** - Use cloud storage for disaster recovery
3. **Encrypt sensitive backups** - Add GPG encryption for production data
4. **Monitor backup jobs** - Set up alerts for failed backups
5. **Document recovery procedures** - Write step-by-step restoration guide

---

## 🔐 Security Notes

- Backup files may contain sensitive user data
- Use encryption for production backups
- Restrict access to backup storage
- Regularly audit backup access logs
- Use separate AWS credentials for backups
- Rotate credentials periodically

---

For questions or issues, see the main [README.md](../README.md)
