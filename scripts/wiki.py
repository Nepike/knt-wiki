"""Публикация черновиков из articles/ в вики через MediaWiki API (mwclient + бот-пароль).

Черновик -> страница:
    articles/С чего начать.wiki           -> «С чего начать»
    articles/Шаблон/Статус страницы.wiki  -> «Шаблон:Статус страницы» (первая папка = пространство имён)

Правило «не перезаписывать вслепую»: для каждой страницы в articles/.sync.json запоминается ревизия,
с которой взят черновик (после pull или publish). publish отказывается сохранять, если в вики уже есть
более новая ревизия (кто-то поправил через браузер) или если страницу никогда не скачивали.
Порядок правки существующей страницы: pull -> правка черновика -> diff -> publish.

Команды (из корня репозитория):
    python scripts/wiki.py check                         проверить вход по бот-паролю, ничего не меняет
    python scripts/wiki.py status                        состояние всех черновиков относительно вики
    python scripts/wiki.py pull "Заглавная страница"     скачать текущую версию страницы в articles/
                                                         (можно указать и путь к черновику: "articles/X.wiki")
    python scripts/wiki.py diff "articles/X.wiki"        разница: вики -> черновик
    python scripts/wiki.py publish "articles/X.wiki" -m "что изменено"
                                                         показать diff, спросить подтверждение, сохранить
    python scripts/wiki.py upload "articles/Файл/X.png" -m "что на картинке"
                                                         загрузить картинку как «Файл:X.png»; уже загруженный
                                                         другой файл с тем же именем заменяется только с --replace

Настройки берутся из .env (переменные окружения имеют приоритет):
    WIKI_URL=https://wiki.inbicst.ru
    WIKI_BOT_USER=Участник@publisher
    WIKI_BOT_PASSWORD=...
"""
import argparse
import difflib
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import mwclient

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "articles"
STATE_FILE = ARTICLES / ".sync.json"
USER_AGENT = "knt-wiki-publisher/1.0 (https://github.com/Nepike/knt-wiki)"


def load_env():
    env = {}
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("WIKI_")})
    missing = [k for k in ("WIKI_URL", "WIKI_BOT_USER", "WIKI_BOT_PASSWORD") if not env.get(k)]
    if missing:
        sys.exit(f"Не заданы {', '.join(missing)} — добавьте в .env (см. .env.example)")
    return env


def connect(env):
    url = urlsplit(env["WIKI_URL"])
    site = mwclient.Site(url.netloc, path=(url.path.rstrip("/") + "/"), scheme=url.scheme,
                         clients_useragent=USER_AGENT)
    site.login(env["WIKI_BOT_USER"], env["WIKI_BOT_PASSWORD"])
    return site


def sha1(text):
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()


def normalize(text):
    # MediaWiki хранит текст без хвостовых пробелов и переводов строк
    return text.replace("\r\n", "\n").rstrip()


def path_to_title(path):
    rel = Path(path).resolve().relative_to(ARTICLES)
    if rel.suffix != ".wiki":
        sys.exit(f"{path}: черновик должен иметь расширение .wiki")
    parts = rel.with_suffix("").parts
    if len(parts) == 1:
        return parts[0].replace("_", " ")
    if len(parts) == 2:
        return f"{parts[0]}:{parts[1]}".replace("_", " ")
    sys.exit(f"{path}: ожидается articles/<Название>.wiki или articles/<Пространство>/<Название>.wiki")


def title_to_path(title):
    if ":" in title:
        ns, name = title.split(":", 1)
        return ARTICLES / ns / f"{name}.wiki"
    return ARTICLES / f"{title}.wiki"


class State:
    """articles/.sync.json: {адрес вики: {название: {"revid": ..., "sha1": ...}}}"""

    def __init__(self, wiki_url):
        self.wiki_url = wiki_url.rstrip("/")
        self.data = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}

    def get(self, title):
        return self.data.get(self.wiki_url, {}).get(title)

    def set(self, title, revid, text):
        self.data.setdefault(self.wiki_url, {})[title] = {"revid": revid, "sha1": sha1(text)}
        STATE_FILE.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                              encoding="utf-8", newline="\n")


def fetch(site, title):
    """(page, текст, revid последней ревизии или None, если страницы нет)"""
    page = site.pages[title]
    if not page.exists:
        return page, None, None
    return page, page.text(cache=False), page.revision


def show_diff(old, new, title):
    lines = list(difflib.unified_diff(normalize(old or "").splitlines(), normalize(new).splitlines(),
                                      f"вики: {title}", f"черновик: {title}", lineterm=""))
    for line in lines:
        print(line)
    return bool(lines)


def read_draft(path):
    path = Path(path)
    if not path.exists():
        sys.exit(f"Нет файла {path}")
    return path.read_text(encoding="utf-8")


def cmd_check(site, env, args):
    info = site.api("query", meta="userinfo", uiprop="rights|groups")["query"]["userinfo"]
    needed = ["edit", "createpage", "editinterface", "upload", "reupload"]
    print(f"Вики: {env['WIKI_URL']}, вход как: {info['name']} (группы: {', '.join(info['groups'])})")
    for right in needed:
        print(f"  {right:14} {'есть' if right in info['rights'] else 'НЕТ'}")


def cmd_status(site, env, args):
    state = State(env["WIKI_URL"])
    for path in sorted(ARTICLES.rglob("*.wiki")):
        title = path_to_title(path)
        _, text, revid = fetch(site, title)
        known = state.get(title)
        draft = read_draft(path)
        if revid is None:
            status = "новая (в вики нет)"
        elif known is None:
            status = "КОНФЛИКТ: страница есть в вики, но не скачивалась — сделайте pull"
        elif known["revid"] != revid:
            status = f"КОНФЛИКТ: в вики изменена после pull (r{known['revid']} -> r{revid}) — сделайте pull"
        elif sha1(draft) == sha1(text):
            status = "совпадает с вики"
        else:
            status = "есть неопубликованные правки"
        print(f"{status:40}  {title}")


def cmd_pull(site, env, args):
    state = State(env["WIKI_URL"])
    for title in args.titles:
        if title.endswith(".wiki"):
            title = path_to_title(title)
        page, text, revid = fetch(site, title)
        title = page.name
        if revid is None:
            print(f"{title}: в вики нет такой страницы")
            continue
        path = title_to_path(title)
        known = state.get(title)
        if path.exists():
            draft = read_draft(path)
            # Черновик, который отличается от вики и не совпадает с последней синхронизацией
            # (или вообще ни разу не синхронизировался), содержит чью-то работу — не затираем.
            unsynced = sha1(draft) != sha1(text) and (known is None or sha1(draft) != known["sha1"])
            if unsynced and not args.force:
                print(f"{title}: в черновике {path.relative_to(ROOT)} есть неопубликованные правки — не перезаписываю.\n"
                      f"  Посмотрите разницу (diff), сохраните нужное, затем повторите с --force.")
                continue
            if unsynced:
                backup = path.with_name(path.name + ".bak")
                backup.write_text(draft, encoding="utf-8", newline="\n")
                print(f"  старый черновик сохранён в {backup.relative_to(ROOT)}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(normalize(text) + "\n", encoding="utf-8", newline="\n")
        state.set(title, revid, text)
        print(f"{title}: r{revid} -> {path.relative_to(ROOT)}")


def cmd_diff(site, env, args):
    title = path_to_title(args.path)
    _, text, revid = fetch(site, title)
    if not show_diff(text, read_draft(args.path), title):
        print("Черновик совпадает с вики.")


def cmd_publish(site, env, args):
    state = State(env["WIKI_URL"])
    title = path_to_title(args.path)
    draft = read_draft(args.path)
    page, text, revid = fetch(site, title)
    known = state.get(title)

    if revid is not None:
        if known is None:
            sys.exit(f"«{title}» уже есть в вики, а черновик не из неё. Сначала: python scripts/wiki.py pull \"{title}\","
                     f" потом перенесите правки в скачанную версию.")
        if known["revid"] != revid:
            last = next(page.revisions(max_items=1, prop="user|comment|timestamp"))
            sys.exit(f"«{title}» изменили в вики после pull: r{known['revid']} -> r{revid} "
                     f"({last.get('user')}: «{last.get('comment', '')}»). Не перезаписываю.\n"
                     f"Сохраните свои правки, сделайте pull и перенесите их в новую версию.")
        if sha1(draft) == sha1(text):
            print("Черновик совпадает с вики, публиковать нечего.")
            return

    print(f"{'Создание' if revid is None else 'Правка'} страницы «{title}» на {env['WIKI_URL']}\n")
    show_diff(text, draft, title)
    if not args.yes and input("\nОпубликовать? [y/N] ").strip().lower() not in ("y", "yes", "д", "да"):
        print("Отменено.")
        return

    extra = {"createonly": 1} if revid is None else {"nocreate": 1, "baserevid": revid}
    result = page.edit(normalize(draft), summary=args.message, minor=False, bot=False, **extra)
    if result.get("result") != "Success":
        sys.exit(f"Ошибка сохранения: {result}")
    new_revid = result.get("newrevid", revid)
    state.set(title, new_revid, draft)
    print(f"Опубликовано: r{new_revid} {site.scheme}://{site.host}/wiki/{title.replace(' ', '_')}")


def cmd_upload(site, env, args):
    path = Path(args.path)
    if not path.is_file():
        sys.exit(f"Нет файла {path}")
    name = args.name or path.name
    data = path.read_bytes()
    image = site.images[name]
    if image.exists:
        if image.imageinfo.get("sha1") == hashlib.sha1(data).hexdigest():
            print(f"«Файл:{name}» уже загружен, точно такой же.")
            return
        if not args.replace:
            sys.exit(f"«Файл:{name}» уже есть в вики, и он другой. Не перезаписываю; "
                     f"чтобы заменить, повторите с --replace.")

    print(f"{'Замена' if image.exists else 'Загрузка'} «Файл:{name}» ({max(1, round(len(data) / 1024))} КБ) на {env['WIKI_URL']}")
    if not args.yes and input("Загрузить? [y/N] ").strip().lower() not in ("y", "yes", "д", "да"):
        print("Отменено.")
        return
    result = site.upload(io.BytesIO(data), filename=name, description=args.message,
                         comment=args.message, ignore=args.replace)
    if result.get("result") != "Success":
        sys.exit(f"Файл не загружен: {result.get('warnings') or result}")
    print(f"Загружено: {site.scheme}://{site.host}/wiki/Файл:{name.replace(' ', '_')}")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    p = sub.add_parser("pull")
    p.add_argument("titles", nargs="+", help="название страницы или путь к черновику articles/....wiki")
    p.add_argument("--force", action="store_true", help="перезаписать черновик с неопубликованными правками")
    p = sub.add_parser("diff")
    p.add_argument("path")
    p = sub.add_parser("publish")
    p.add_argument("path")
    p.add_argument("-m", "--message", required=True, help="описание правки")
    p.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")
    p = sub.add_parser("upload")
    p.add_argument("path")
    p.add_argument("--name", help="имя файла в вики (по умолчанию — имя файла на диске)")
    p.add_argument("-m", "--message", required=True, help="описание файла")
    p.add_argument("--replace", action="store_true", help="заменить уже загруженный файл с тем же именем")
    p.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")
    args = parser.parse_args()

    env = load_env()
    site = connect(env)
    {"check": cmd_check, "status": cmd_status, "pull": cmd_pull,
     "diff": cmd_diff, "publish": cmd_publish, "upload": cmd_upload}[args.command](site, env, args)


if __name__ == "__main__":
    main()
