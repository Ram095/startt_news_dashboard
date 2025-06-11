# scripts/backup.sh
#!/bin/bash

# Database backup script
set -e

# Configuration
DB_NAME="${DB_NAME:-news_dashboard}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/news_dashboard_${TIMESTAMP}.sql"

echo "🗄️ Starting database backup..."

# Create backup
if command -v pg_dump &> /dev/null; then
    pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        --verbose --clean --no-owner --no-privileges \
        --format=custom > "${BACKUP_FILE}.custom"
    
    # Also create plain SQL backup
    pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        --verbose --clean --no-owner --no-privileges \
        --format=plain > "$BACKUP_FILE"
    
    echo "✅ Backup created: $BACKUP_FILE"
    
    # Compress backups
    gzip "$BACKUP_FILE"
    gzip "${BACKUP_FILE}.custom"
    
    echo "✅ Backups compressed"
else
    echo "❌ pg_dump not found. Cannot create backup."
    exit 1
fi

# Clean up old backups
echo "🧹 Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "news_dashboard_*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "news_dashboard_*.sql.custom.gz" -mtime +$RETENTION_DAYS -delete

echo "✅ Backup process completed"