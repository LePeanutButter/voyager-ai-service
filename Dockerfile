# syntax=docker/dockerfile:1.7
# BuildKit: caché de wheels pip entre builds (--mount=type=cache). Habilitado por
# defecto en Docker Desktop y en GitHub Actions con docker/setup-buildx-action.
#
# Multi-stage:
#   builder    → instala el venv (con build-essential)
#   production → solo runtime mínimo, copia /opt/venv del builder
#
# Optimizaciones de tamaño/velocidad:
#   1. requirements.txt slim (runtime puro). Dev tools van en requirements-dev.txt
#      y nunca entran a la imagen.
#   2. torch CPU-only desde el índice oficial de PyTorch (~200 MB en vez de ~800 MB).
#   3. Pre-entrena artefactos sklearn durante el build → cold-start ~5 s en vez
#      de ~60-180 s entrenando al primer arranque.
#   4. Limpieza agresiva del venv (pycache, tests, dist-info redundante).

ARG PYTHON_VERSION=3.11
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu

# ---------------------------------------------------------------------------
# Stage 1: builder
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_WARN_SCRIPT_LOCATION=0

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

ARG TORCH_INDEX_URL
COPY requirements.txt ./

# Instalación en dos pasos para forzar la wheel CPU de torch sin tirar de CUDA:
#   1) Instala torch desde el índice CPU primero. Sin esto, pip resuelve la
#      versión con CUDA del índice principal y se traga ~600 MB extra.
#   2) Instala el resto de runtime con el índice CPU como secundario; pip ve
#      torch ya satisfecho con la wheel `+cpu` y no lo reemplaza.
# Capturamos la línea `torch...` en una variable para evitar que `<3` (rango
# semver) se interprete como redirección de stdin en el shell del RUN.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
 && TORCH_REQ="$(grep -E '^torch' requirements.txt | head -n1)" \
 && pip install --extra-index-url "${TORCH_INDEX_URL}" "${TORCH_REQ}" \
 && pip install -r requirements.txt --extra-index-url "${TORCH_INDEX_URL}"

# Limpieza del venv (no necesitamos tests, dist-info docs, ni .pyc fuente).
# Ahorra 80–150 MB adicionales sin tocar funcionalidad.
RUN find /opt/venv -depth -type d \( -name __pycache__ -o -name tests -o -name test \) -exec rm -rf {} + \
 && find /opt/venv -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete \
 && find /opt/venv -type f -name "*.so" -exec strip --strip-unneeded {} + 2>/dev/null || true

# ---------------------------------------------------------------------------
# Stage 2: production
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app"

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean \
 && groupadd -r appuser \
 && useradd -r -g appuser appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

COPY app/ ./app/
COPY README.md ./
COPY docker/entrypoint-ai.sh /docker/entrypoint-ai.sh

# Pre-entrena artefactos ML baseline DURANTE el build, así no se entrenan en el
# primer arranque del contenedor. Si por algún motivo falla (p. ej. dependencia
# rota en CI), el entrypoint se encarga de reintentarlo en runtime.
RUN sed -i 's/\r$//' /docker/entrypoint-ai.sh \
 && chmod +x /docker/entrypoint-ai.sh \
 && mkdir -p /app/logs /app/data /app/models /app/app/ml/models \
 && (python -m app.ml.training.train_baseline_artifacts || \
     echo "[build] aviso: pre-entrenamiento baseline fallo; entrypoint lo reintentará en runtime.") \
 && chown -R appuser:appuser /app /docker/entrypoint-ai.sh

USER appuser

EXPOSE 8000

# start-period más bajo porque ya no entrenamos en arranque (artefactos baked-in).
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/docker/entrypoint-ai.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
