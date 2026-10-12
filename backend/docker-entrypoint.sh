#!/bin/sh
set -e

# Wait for Postgres.
python - <<'PY'
import os, time, psycopg
url = os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1)
for i in range(60):
    try:
        psycopg.connect(url).close()
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("database not reachable")
PY

# Only the API container migrates and seeds; the others wait for it.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
  python manage.py seed_demo
fi

exec "$@"
