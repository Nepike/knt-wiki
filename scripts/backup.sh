#!/usr/bin/env bash
# Бэкап вики в папку backups/itwiki-ГГГГММДД-ЧЧММСС/:
#   db.sql.gz        — дамп MariaDB (главное: всё содержимое вики, пользователи, история)
#   images.tar.gz    — загруженные файлы (без миниатюр — они пересоздаются)
#   pages.xml.gz     — XML-выгрузка всех страниц с историей (переносима между версиями MediaWiki)
#   VERSIONS.txt     — версии образов и коммит репозитория
#   SHA256SUMS
# .env в бэкап не входит: храните его отдельно (без него восстановится всё, кроме активных сессий).
#
# Запуск из корня репозитория:  bash scripts/backup.sh [папка-назначения]
set -euo pipefail
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

DEST="${1:-backups}/itwiki-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"

echo "БД..."
docker compose exec -T db sh -c 'exec mariadb-dump --single-transaction --quick --hex-blob \
  --default-character-set=binary -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"' \
  | gzip > "$DEST/db.sql.gz"

echo "Файлы..."
docker compose exec -T mediawiki tar -C /var/www/html -czf - \
  --exclude=images/thumb --exclude=images/tmp --exclude=images/lockdir images \
  > "$DEST/images.tar.gz"

echo "XML-выгрузка страниц..."
docker compose exec -T mediawiki php maintenance/run.php dumpBackup --full --quiet \
  | gzip > "$DEST/pages.xml.gz"

{
  docker compose config --images
  echo "git: $(git rev-parse --short HEAD 2>/dev/null || echo '-')"
} > "$DEST/VERSIONS.txt"

# Пустой дамп — признак ошибки (например, БД не запущена)
[ "$(gzip -dc "$DEST/db.sql.gz" | head -c 100 | wc -c)" -gt 0 ] || { echo "Пустой дамп БД!" >&2; exit 1; }

(cd "$DEST" && sha256sum db.sql.gz images.tar.gz pages.xml.gz VERSIONS.txt > SHA256SUMS)
du -sh "$DEST"
echo "Готово: $DEST"
