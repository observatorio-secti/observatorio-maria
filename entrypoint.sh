#!/bin/sh
set -eu

# Aplica migrações pendentes, carrega seeds novos e sincroniza as fontes.
alembic upgrade head
python -m observatorio_maria.catalog.seed catalog/fomento.yaml catalog/simcc.yaml catalog/concepts.yaml
python -m observatorio_maria.catalog.sync

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec uvicorn observatorio_maria.app:app --host 0.0.0.0 --port 8000 --proxy-headers
