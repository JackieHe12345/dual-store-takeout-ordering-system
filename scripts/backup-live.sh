#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
test -f .env
backup_dir="backups/live-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
sudo -n docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup_dir/database.dump"
sudo -n docker compose exec -T postgres pg_restore --list < "$backup_dir/database.dump" > "$backup_dir/database-index.txt"
sudo -n docker compose exec -T backend tar -C /app/media -czf - uploads > "$backup_dir/uploads.tar.gz"
cp .env "$backup_dir/environment.private"
tar --exclude='./backups' --exclude='./node_modules' --exclude='./test-data' --exclude='./.env*' --exclude='./.git' --exclude='*/__pycache__' --exclude='*/._*' -czf "$backup_dir/source.tar.gz" backend frontend-customer frontend-staff frontend-admin frontend-shared nginx scripts compose.yaml package.json vite.config.js tsconfig.json
sha256sum "$backup_dir"/*.dump "$backup_dir"/*.gz > "$backup_dir/SHA256SUMS"
printf 'Backup complete: %s\n' "$backup_dir"
