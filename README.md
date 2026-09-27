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
| `scripts/gen_env.py` | Генерирует `.env` со случайными паролями и ключами |
| `scripts/install.sh` | Первичная установка в пустую БД (таблицы + первый администратор) |
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
