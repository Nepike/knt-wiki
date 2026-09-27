#!/usr/bin/env bash
# Восстановление из бэкапа, сделанного scripts/backup.sh.
# ВНИМАНИЕ: текущая БД вики и загруженные файлы ЗАМЕНЯЮТСЯ данными из бэкапа.
#
# Запуск из корня репозитория (нужен .env; стек может быть как запущен, так и новым):
#   bash scripts/restore.sh backups/itwiki-ГГГГММДД-ЧЧММСС [--yes]
set -euo pipefail
SRC="${1:?Укажите папку бэкапа}"
SRC="$(cd "$SRC" && pwd)"
cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) || { echo "Контрольные суммы не совпали" >&2; exit 1; }

if [ "${2:-}" != "--yes" ]; then
  read -r -p "БД и файлы вики будут заменены данными из $SRC. Продолжить? [yes/N] " answer
  [ "$answer" = "yes" ] || { echo "Отменено."; exit 1; }
fi

docker compose up -d --wait db
docker compose stop mediawiki

echo "БД..."
docker compose exec -T db sh -c 'exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e \
  "DROP DATABASE IF EXISTS \`$MARIADB_DATABASE\`; CREATE DATABASE \`$MARIADB_DATABASE\`;
   GRANT ALL PRIVILEGES ON \`$MARIADB_DATABASE\`.* TO \`$MARIADB_USER\`@\`%\`;"'
gzip -dc "$SRC/db.sql.gz" \
  | docker compose exec -T db sh -c 'exec mariadb --default-character-set=binary -uroot -p"$MARIADB_ROOT_PASSWORD" "$MARIADB_DATABASE"'

echo "Файлы..."
docker compose run --rm -T --no-deps --entrypoint sh mediawiki -c \
  'find /var/www/html/images -mindepth 1 -delete && tar -C /var/www/html -xzf - && chown -R www-data:www-data /var/www/html/images' \
  < "$SRC/images.tar.gz"

docker compose up -d
# Если бэкап сделан на более старой версии MediaWiki — обновить схему
docker compose exec -T mediawiki php maintenance/run.php update --quick > /dev/null
echo "Готово. Проверьте вики в браузере."
