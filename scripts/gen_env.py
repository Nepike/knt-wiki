"""Печатает содержимое .env со случайными секретами.

Использование:  python scripts/gen_env.py [MW_SERVER] > .env
"""
import secrets
import sys

server = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"

print(f"""MW_SERVER={server}
MW_BIND_ADDR=127.0.0.1
MW_HTTP_PORT=8080

MW_DB_NAME=wiki
MW_DB_USER=wiki
MW_DB_PASSWORD={secrets.token_urlsafe(24)}
MARIADB_ROOT_PASSWORD={secrets.token_urlsafe(24)}

MW_SECRET_KEY={secrets.token_hex(32)}
MW_UPGRADE_KEY={secrets.token_hex(8)}

MW_ADMIN_USER=Admin
MW_ADMIN_PASSWORD={secrets.token_urlsafe(18)}""")
