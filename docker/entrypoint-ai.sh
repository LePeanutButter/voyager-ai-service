#!/bin/sh
set -e

OLLAMA_URL="${OLLAMA_URL:-http://ollama:11434}"
OLLAMA_URL="${OLLAMA_URL%/}"

echo "[entrypoint] Esperando Ollama en ${OLLAMA_URL}..."
i=0
while ! curl -sf "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 120 ]; then
    echo "[entrypoint] Timeout: Ollama no respondió en ~4 minutos."
    exit 1
  fi
  sleep 2
done
echo "[entrypoint] Ollama disponible."

if [ "${OLLAMA_PULL_ON_START:-}" = "1" ] || [ "${OLLAMA_PULL_ON_START:-}" = "true" ]; then
  name="${LOCAL_MODEL_NAME:-mistral:7b-instruct}"
  echo "[entrypoint] Descargando modelo Ollama '${name}' (puede tardar mucho la primera vez)..."
  curl -sS -N -X POST "${OLLAMA_URL}/api/pull" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${name}\"}" \
    --max-time 7200 -o /dev/null || echo "[entrypoint] Aviso: pull no completó; puedes ejecutar en el host: docker compose exec ollama ollama pull ${name}"
fi

MODEL_DIR="/app/app/ml/models"
REC="${RECOMMENDATION_MODEL:-recommendation_model.pkl}"
if [ ! -f "${MODEL_DIR}/${REC}" ]; then
  echo "[entrypoint] No hay artefactos ML en ${MODEL_DIR}; entrenando baseline..."
  cd /app && python -m app.ml.training.train_baseline_artifacts
fi

exec "$@"
