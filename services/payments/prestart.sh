#!/usr/bin/env bash
set -euo pipefail

echo "[prestart] Waiting for DB ${DB_HOST}:${DB_PORT}..."
python - <<'PY'
import os, time, psycopg
h=os.environ["DB_HOST"]; p=int(os.environ.get("DB_PORT", "5432"))
d=os.environ["DB_NAME"]; u=os.environ["DB_USER"]; pw=os.environ["DB_PASSWORD"]
deadline = time.time() + 60
while True:
    try:
        with psycopg.connect(host=h, port=p, dbname=d, user=u, password=pw) as conn:
            with conn.cursor() as cur: cur.execute("select 1")
        break
    except Exception as e:
        if time.time() > deadline:
            raise
        time.sleep(1)
PY

echo "[prestart] Running alembic upgrade head..."
export DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
alembic upgrade head
echo "[prestart] Done."
