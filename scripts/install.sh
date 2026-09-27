#!/usr/bin/env bash
# Первичная установка MediaWiki в ПУСТУЮ базу: создаёт таблицы и первого администратора.
#
# LocalSettings.php, который генерирует установщик, выбрасывается (пишется в /tmp контейнера):
# рабочая конфигурация — ./LocalSettings.php из репозитория, секреты берутся из .env.
#
# Запуск из корня репозитория:  bash scripts/install.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# Git Bash на Windows иначе переписывает пути вида /tmp в C:/...
export MSYS_NO_PATHCONV=1

set -a; . ./.env; set +a

docker compose up -d --wait db

if docker compose exec -T db mariadb -u"$MW_DB_USER" -p"$MW_DB_PASSWORD" "$MW_DB_NAME" -N \
     -e "SHOW TABLES LIKE 'page'" | grep -q page; then
  echo "В базе $MW_DB_NAME уже есть таблицы MediaWiki, установка не требуется." >&2
  echo "Обновить схему: docker compose exec mediawiki php maintenance/run.php update --quick" >&2
  exit 1
fi

# Название вики здесь ни на что не влияет: оно задаётся в LocalSettings.php.
# Сервис installer — тот же образ, но без смонтированного LocalSettings.php.
docker compose run --rm -T --no-deps installer \
  php maintenance/run.php install \
    --dbtype mysql --dbserver db \
    --dbname "$MW_DB_NAME" --dbuser "$MW_DB_USER" --dbpass "$MW_DB_PASSWORD" \
    --server "$MW_SERVER" --scriptpath "" \
    --lang ru \
    --pass "$MW_ADMIN_PASSWORD" \
    --confpath /tmp \
    "Wiki" "$MW_ADMIN_USER"

# Таблицы для расширений, подключённых в LocalSettings.php
docker compose run --rm -T --no-deps mediawiki php maintenance/run.php update --quick

docker compose up -d
echo "Готово: $MW_SERVER"
