# Вики IT-отдела студсовета

Конфигурация вики отдела на MediaWiki: база знаний для новичков.

- MediaWiki **1.43.9** (текущая LTS-ветка, поддержка до декабря 2027) — образ `mediawiki:1.43.9`
- MariaDB **11.8.9** (LTS-ветка) — образ `mariadb:11.8.9`
- Docker Compose, конфигурация в `LocalSettings.php`, секреты в `.env`

## Структура

| Путь | Что это |
|---|---|
| `docker-compose.yml` | Сервисы `db` (MariaDB) и `mediawiki`; `installer` — только для первичной установки |
| `LocalSettings.php` | Конфигурация MediaWiki. Секретов нет: они читаются из переменных окружения |
| `.env.example` | Образец `.env`. Сам `.env` в git не попадает |
| `php/uploads.ini` | Лимит размера загружаемых файлов (20 МБ) |
| `mariadb/low-memory.cnf`, `apache/mpm-limits.conf` | Урезанное потребление памяти (на сервере всего 1.8 ГБ RAM) |
| `assets/` | Логотип и favicon (исходник — `logo-source.png`) |
| `deploy/nginx/wiki.inbicst.ru.conf` | Конфиг nginx на сервере (reverse proxy + HTTPS) |
| `scripts/gen_env.py` | Генерирует `.env` со случайными паролями и ключами |
| `scripts/install.sh` | Первичная установка в пустую БД (таблицы + первый администратор) |
| `scripts/backup.sh`, `scripts/restore.sh` | Бэкап и восстановление |
| `articles/` | Черновики статей (`.wiki`) |

## Локальный запуск

Нужны Docker с Compose, Git Bash (на Windows) и Python 3.

```bash
python scripts/gen_env.py > .env      # случайные секреты; адрес по умолчанию http://localhost:8080
bash scripts/install.sh               # создаёт БД, таблицы, администратора и запускает вики
```

Откройте http://localhost:8080. Логин администратора — `MW_ADMIN_USER` из `.env`
(по умолчанию `Admin`), пароль — `MW_ADMIN_PASSWORD` оттуда же.

Повседневные команды:

```bash
docker compose up -d          # запустить
docker compose down           # остановить (данные сохраняются в томах)
docker compose logs -f mediawiki
```

После изменения `LocalSettings.php` перезапуск не нужен: файл читается на каждый запрос.
Если подключили расширение, которому нужны таблицы, выполните:

```bash
docker compose exec mediawiki php maintenance/run.php update --quick
```

## Права

- Читать могут все, вики публичная.
- Анонимы не могут редактировать.
- Самостоятельная регистрация закрыта. Аккаунты создают администраторы на странице
  `Служебная:Создать_учётную_запись` и сразу задают пароль (почта пока отключена).

## Расширения

Подключены только одобренные (все входят в поставку MediaWiki):
VisualEditor, SyntaxHighlight_GeSHi, ParserFunctions, TemplateData.

## Сервер

| | |
|---|---|
| Адрес | https://wiki.inbicst.ru |
| SSH | `ssh nepike@inbicst.ru` (Ubuntu 24.04) |
| Репозиторий на сервере | `/srv/knt-wiki` |
| Контейнеры | compose-проект `itwiki`, MediaWiki слушает только `127.0.0.1:8080` |
| HTTPS | nginx на хосте (`/etc/nginx/sites-available/wiki.inbicst.ru`), сертификат Let's Encrypt от certbot, продлевается `certbot.timer` |

На сервере работают и другие проекты (сайт `knt` в `/srv/knt`, сайт olgapostovalova.ru) —
их не трогаем. Команды с `sudo` требуют пароль пользователя `nepike`.

### Первый деплой

```bash
sudo install -d -o nepike -g nepike /srv/knt-wiki
git clone https://github.com/Nepike/knt-wiki.git /srv/knt-wiki
cd /srv/knt-wiki
python3 scripts/gen_env.py https://wiki.inbicst.ru > .env && chmod 600 .env
bash scripts/install.sh            # вики поднимется на 127.0.0.1:8080

# reverse proxy (сертификат для wiki.inbicst.ru уже выпущен certbot)
sudo cp deploy/nginx/wiki.inbicst.ru.conf /etc/nginx/sites-available/wiki.inbicst.ru
sudo ln -sf /etc/nginx/sites-available/wiki.inbicst.ru /etc/nginx/sites-enabled/wiki.inbicst.ru
sudo nginx -t && sudo systemctl reload nginx
sudo certbot renew --dry-run --cert-name wiki.inbicst.ru
```

На новом сервере, где сертификата ещё нет, перед копированием конфига nginx выпустите его:
`sudo certbot certonly --nginx -d wiki.inbicst.ru`.

Пароль администратора — в `/srv/knt-wiki/.env` (`MW_ADMIN_PASSWORD`).

### Выкатить изменения конфигурации

```bash
cd /srv/knt-wiki
git pull
docker compose up -d     # пересоздаст контейнеры, если менялся docker-compose.yml
```

Изменения `LocalSettings.php` применяются сразу, без перезапуска. Если менялся конфиг nginx —
скопируйте его снова и выполните `sudo nginx -t && sudo systemctl reload nginx`.

## Бэкап

```bash
cd /srv/knt-wiki
bash scripts/backup.sh     # → backups/itwiki-ГГГГММДД-ЧЧММСС/
```

В бэкапе: дамп БД (`db.sql.gz`), загруженные файлы (`images.tar.gz`), XML-выгрузка всех страниц
с историей (`pages.xml.gz`), версии образов и контрольные суммы. Бэкап делается на работающей вики,
останавливать ничего не нужно.

`.env` в бэкап не входит — храните его копию отдельно (например, в менеджере паролей).
Без него можно восстановиться с новым `.env`: пропадут только активные сессии.

Скачать бэкап к себе:

```bash
scp -r nepike@inbicst.ru:/srv/knt-wiki/backups/itwiki-ГГГГММДД-ЧЧММСС ./backups/
```

Папка `backups/` в `.gitignore`.

## Восстановление

**Текущие данные вики будут заменены** — скрипт проверит контрольные суммы и спросит подтверждение.

```bash
cd /srv/knt-wiki
bash scripts/restore.sh backups/itwiki-ГГГГММДД-ЧЧММСС
```

Восстановление на новый сервер: склонировать репозиторий, создать `.env`
(`python3 scripts/gen_env.py https://wiki.inbicst.ru > .env`), скопировать туда папку бэкапа и
запустить `restore.sh` — `install.sh` в этом случае **не нужен**. Затем настроить nginx (см. «Первый деплой»).

## Обновление MediaWiki

Версии образов закреплены в `docker-compose.yml`. Актуальные версии и сроки поддержки:
https://www.mediawiki.org/wiki/Version_lifecycle (используем LTS).

1. **Локально**: поменять тег `mediawiki:1.43.x` в `docker-compose.yml` и проверить:
   ```bash
   docker compose pull && docker compose up -d
   docker compose exec mediawiki php maintenance/run.php update --quick
   ```
   Открыть `Служебная:Версия`, попробовать отредактировать страницу визуальным редактором.
   Для перехода на новую ветку (например, 1.43 → 1.47) сначала прочитать release notes и
   проверить на локальной копии с восстановленным бэкапом с сервера. Закоммитить и запушить.
2. **На сервере**:
   ```bash
   cd /srv/knt-wiki
   bash scripts/backup.sh
   git pull
   docker compose pull && docker compose up -d
   docker compose exec mediawiki php maintenance/run.php update --quick
   ```
3. **Откат**: вернуть старый тег (`git revert` / `git checkout` нужного коммита), `docker compose up -d`
   и `bash scripts/restore.sh` с бэкапом из шага 2. Просто вернуть тег недостаточно: `update.php`
   мог изменить схему БД.

MariaDB обновляется так же (тег `mariadb:11.8.x`); при смене минорной версии `mariadb-upgrade`
запускается автоматически (`MARIADB_AUTO_UPGRADE`). Перед сменой мажорной версии — обязательно бэкап.
