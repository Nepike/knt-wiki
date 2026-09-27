#!/usr/bin/env bash
# Выкатить свежую конфигурацию из GitHub (запускать на сервере из /srv/knt-wiki).
#
# LocalSettings.php, php/*.ini, apache/*.conf, mariadb/*.cnf смонтированы в контейнеры по одному файлу.
# git pull заменяет их НОВЫМИ файлами, а контейнер продолжает видеть старые, пока его не перезапустить.
# Поэтому после pull перезапускаем контейнеры, чьи файлы изменились (простой — пара секунд).
set -euo pipefail
cd "$(dirname "$0")/.."

old=$(git rev-parse HEAD)
git pull --ff-only
new=$(git rev-parse HEAD)
changed=$(git diff --name-only "$old" "$new")

if [ -z "$changed" ]; then
  echo "Новых коммитов нет."
  exit 0
fi
echo "Изменённые файлы:"; echo "$changed" | sed 's/^/  /'

# Применяет изменения docker-compose.yml (пересоздаёт затронутые контейнеры)
docker compose up -d

if echo "$changed" | grep -q '^mariadb/'; then
  docker compose restart db
fi
if echo "$changed" | grep -qE '^(LocalSettings\.php|php/|apache/)'; then
  docker compose restart mediawiki
fi
if echo "$changed" | grep -q '^docker-compose\.yml$'; then
  echo "docker-compose.yml изменился. Если менялась версия MediaWiki, выполните:"
  echo "  docker compose exec mediawiki php maintenance/run.php update --quick"
fi

set -a; . ./.env; set +a
for i in $(seq 1 15); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${MW_HTTP_PORT:-8080}/api.php?action=query&meta=siteinfo&format=json"; then
    echo "Готово, вики отвечает."
    exit 0
  fi
  sleep 2
done
echo "Вики не отвечает! Смотрите: docker compose logs --tail 50 mediawiki" >&2
exit 1
