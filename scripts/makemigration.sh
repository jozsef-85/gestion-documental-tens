#!/usr/bin/env bash

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Uso: ./scripts/makemigration.sh nombre_corto [app]"
    echo "Ejemplo: ./scripts/makemigration.sh estado_manual_labels core"
    exit 1
fi

NAME="$1"
APP_LABEL="${2:-core}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$NAME" in
    *[!a-z0-9_]*)
        echo "El nombre debe usar solo minusculas, numeros y guion bajo."
        exit 1
        ;;
esac

"$ROOT_DIR/scripts/manage.sh" makemigrations "$APP_LABEL" --name "$NAME"
