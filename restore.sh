# scripts/restore.sh
#!/bin/bash

# Database restore script
set -e

# Check arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 ./backups/news_dashboard_20241201_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
DB_NAME="${DB_NAME:-news_dashboard}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "🗄️ Starting database restore from: $BACKUP_FILE"

# Determine if file is compressed
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "📦 Decompressing backup file..."
    TEMP_FILE="/tmp/restore_$(basename "$BACKUP_FILE" .gz)"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    RESTORE_FILE="$TEMP_FILE"
else
    RESTORE_FILE="$BACKUP_FILE"
fi

# Determine restore method based on file type
if [[ "$RESTORE_FILE" == *.custom* ]]; then
    echo "🔄 Restoring from custom format..."
    pg_restore -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        --verbose --clean --if-exists \
        "$RESTORE_FILE"
else
    echo "🔄 Restoring from plain SQL..."
    psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
        -f "$RESTORE_FILE"
fi

# Clean up temporary file
if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
    rm "$TEMP_FILE"
fi

echo "✅ Database restore completed"