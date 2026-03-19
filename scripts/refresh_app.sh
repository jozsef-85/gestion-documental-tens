#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANAGE_SCRIPT="$ROOT_DIR/scripts/manage.sh"
APP_URL="${APP_URL:-http://127.0.0.1:8000/}"
GUNICORN_PATTERN="${GUNICORN_PATTERN:-/opt/gestion_documental/venv/bin/python3 /opt/gestion_documental/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 config.wsgi:application}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-0}"
VERIFY_HTTP="${VERIFY_HTTP:-1}"

if [ ! -x "$MANAGE_SCRIPT" ]; then
    echo "No se encontro el helper de Django: $MANAGE_SCRIPT" >&2
    exit 1
fi

cd "$ROOT_DIR"

echo "[1/4] Ejecutando system check de Django"
"$MANAGE_SCRIPT" check

if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "[2/4] Aplicando migraciones"
    "$MANAGE_SCRIPT" migrate --noinput
else
    echo "[2/4] Saltando migraciones (usa RUN_MIGRATIONS=1 para aplicarlas)"
fi

echo "[3/4] Recargando Gunicorn con HUP"
if ! pkill -HUP -f "$GUNICORN_PATTERN"; then
    echo "No fue posible recargar Gunicorn con el patron configurado." >&2
    echo "Revisa GUNICORN_PATTERN o recarga manualmente el proceso." >&2
    exit 1
fi

if [ "$VERIFY_HTTP" = "1" ]; then
    echo "[4/4] Verificando respuesta HTTP en $APP_URL"
    curl -fsSI "$APP_URL"
else
    echo "[4/4] Verificacion HTTP omitida (VERIFY_HTTP=0)"
fi

echo "Recarga completada."
