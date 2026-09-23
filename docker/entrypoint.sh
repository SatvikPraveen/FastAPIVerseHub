#!/usr/bin/env sh
# Container entrypoint.
#   serve    - run migrations (unless SKIP_MIGRATIONS=1) then start uvicorn
#   migrate  - run migrations and exit
#   <other>  - exec the given command (e.g. `pytest`, `alembic history`)
set -eu

WORKERS="${WEB_CONCURRENCY:-2}"

case "${1:-serve}" in
  serve)
    if [ "${SKIP_MIGRATIONS:-0}" != "1" ]; then
      echo "Applying database migrations..."
      alembic upgrade head
    fi
    exec uvicorn app.main:app \
      --host "${HOST:-0.0.0.0}" \
      --port "${PORT:-8000}" \
      --workers "${WORKERS}" \
      --proxy-headers \
      --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}" \
      --timeout-graceful-shutdown 30 \
      --no-access-log
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  *)
    exec "$@"
    ;;
esac
