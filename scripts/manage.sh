#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_VENV_PYTHON="/opt/gestion_documental/venv/bin/python"
VENV_PYTHON="${VENV_PYTHON:-$DEFAULT_VENV_PYTHON}"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "No se encontro el interprete de Django en: $VENV_PYTHON" >&2
    echo "Define VENV_PYTHON o activa el virtualenv correcto antes de continuar." >&2
    exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_PYTHON" manage.py "$@"
