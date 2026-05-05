#!/usr/bin/env bash
#
# EC2 manual deploy for AWS Academy Learner Lab (sin registry Docker).
# Instala Docker si falta, carga la imagen desde el .tar de CI, asegura la base
# PostgreSQL (RDS o local) y arranca el contenedor FastAPI con systemd.
#
# Uso (como root):
#   sudo ./ec2-deploy-ai-service.sh [/ruta/voyager-ai-service-image.tar]
#
# Variables en /opt/voyager-ai-service/environment (o VOYAGER_AI_ENV_FILE):
#   DB_HOST, DB_USERNAME, DB_PASSWORD — para psql bootstrap (CREATE DATABASE)
#   DB_PORT, DB_NAME, DB_ADMIN_DATABASE, PGSSLMODE
#
# Modelos en la misma instancia:
#   Artefactos en $INSTALL_ROOT/ml-models/ (p. ej. vía deploy-ai-service-manual.sh).
#   Se montan en el contenedor como /app/app/ml/models (solo lectura) si hay al menos un fichero.
#
# Opcional:
#   VOYAGER_AI_IMAGE     default voyager-ai-service:latest
#   VOYAGER_AI_INSTALL_ROOT default /opt/voyager-ai-service
#   VOYAGER_AI_MODELS_HOST_DIR default $INSTALL_ROOT/ml-models (directorio a montar)
#   VOYAGER_AI_ENV_FILE  default $INSTALL_ROOT/environment
#   VOYAGER_AI_SERVICE_NAME systemd, default voyager-ai-service

set -euo pipefail

readonly INSTALL_ROOT="${VOYAGER_AI_INSTALL_ROOT:-/opt/voyager-ai-service}"
readonly SERVICE_NAME="${VOYAGER_AI_SERVICE_NAME:-voyager-ai-service}"
readonly CONTAINER_NAME="${VOYAGER_AI_CONTAINER_NAME:-voyager-ai-service}"
readonly ENV_FILE="${VOYAGER_AI_ENV_FILE:-$INSTALL_ROOT/environment}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_TAR_CLI="${1:-}"

log() { echo "[$(date -Iseconds)] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    die "Ejecutar como root (sudo)."
  fi
}

detect_os() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    echo "${ID:-unknown} ${VERSION_ID:-}"
  else
    echo "unknown"
  fi
}

ensure_docker_daemon() {
  if systemctl is-system-running &>/dev/null; then
    systemctl enable docker &>/dev/null || true
    systemctl start docker || service docker start || die "No se pudo iniciar Docker."
  else
    service docker start 2>/dev/null || true
  fi
  docker info >/dev/null 2>&1 || die "El daemon de Docker no está en ejecución."
}

install_docker() {
  if command -v docker >/dev/null 2>&1; then
    ensure_docker_daemon
    log "Docker ya instalado: $(docker --version)"
    return 0
  fi
  log "Instalando Docker..."
  local os
  os="$(detect_os)"
  case "$os" in
    amzn\ 2*)
      yum install -y docker
      ;;
    amzn\ 2023*|fedora*|rocky*|almalinux*)
      dnf install -y docker
      ;;
    ubuntu*|debian*)
      apt-get update -y
      apt-get install -y docker.io
      ;;
    *)
      die "SO no soportado para instalar Docker automáticamente: $os"
      ;;
  esac
  ensure_docker_daemon
  command -v docker >/dev/null 2>&1 || die "CLI de Docker no disponible tras la instalación."
}

install_psql_client() {
  if command -v psql >/dev/null 2>&1; then
    return 0
  fi
  log "Instalando cliente PostgreSQL (psql)..."
  local os
  os="$(detect_os)"
  case "$os" in
    amzn\ 2*)
      amazon-linux-extras install -y postgresql14 >/dev/null 2>&1 || true
      yum install -y postgresql
      ;;
    amzn\ 2023*|fedora*)
      dnf install -y postgresql15
      ;;
    ubuntu*|debian*)
      apt-get update -y
      apt-get install -y postgresql-client
      ;;
    *)
      die "SO no soportado para instalar psql: $os"
      ;;
  esac
  command -v psql >/dev/null 2>&1 || die "psql no disponible."
}

load_environment() {
  mkdir -p "$INSTALL_ROOT"
  if [[ -f "$ENV_FILE" ]]; then
    log "Cargando $ENV_FILE"
    set +u
    # shellcheck source=/dev/null
    set -a && source "$ENV_FILE" && set +a
    set -u
  fi
}

resolve_image_tar() {
  local tar_path="$IMAGE_TAR_CLI"
  if [[ -z "$tar_path" ]]; then
    if [[ -f "$INSTALL_ROOT/voyager-ai-service-image.tar" ]]; then
      tar_path="$INSTALL_ROOT/voyager-ai-service-image.tar"
    elif [[ -f "$SCRIPT_DIR/voyager-ai-service-image.tar" ]]; then
      tar_path="$SCRIPT_DIR/voyager-ai-service-image.tar"
    fi
  fi
  echo "${tar_path:-}"
}

load_image_if_needed() {
  local tar_path
  tar_path="$(resolve_image_tar)"
  if [[ -n "$tar_path" ]]; then
    [[ -f "$tar_path" ]] || die "No se encontró el tar de imagen: $tar_path"
    log "docker load -i $tar_path"
    docker load -i "$tar_path"
    install -d -m 0755 "$INSTALL_ROOT"
    install -m 0644 "$tar_path" "$INSTALL_ROOT/voyager-ai-service-image.tar" 2>/dev/null || true
  fi
}

ensure_database_exists() {
  [[ -n "${DB_HOST:-}" ]] || die "DB_HOST no está definido."
  [[ -n "${DB_USERNAME:-}" ]] || die "DB_USERNAME no está definido."
  [[ -n "${DB_PASSWORD:-}" ]] || die "DB_PASSWORD no está definido."
  local port="${DB_PORT:-5432}"
  local dbname="${DB_NAME:-tourism_ai}"
  local admin_db="${DB_ADMIN_DATABASE:-postgres}"
  export PGPASSWORD="$DB_PASSWORD"
  export PGSSLMODE="${PGSSLMODE:-require}"

  log "Comprobando base de datos '$dbname' en $DB_HOST:$port ..."
  local exists
  exists="$(psql -h "$DB_HOST" -p "$port" -U "$DB_USERNAME" -d "$admin_db" -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$dbname'" || true)"
  if [[ "$(echo "$exists" | tr -d '[:space:]')" == "1" ]]; then
    log "La base '$dbname' ya existe."
    return 0
  fi
  log "Creando base '$dbname' (Alembic/migraciones se aplican aparte si aplica)."
  psql -h "$DB_HOST" -p "$port" -U "$DB_USERNAME" -d "$admin_db" -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE \"$dbname\";"
  unset PGPASSWORD
}

write_systemd_unit() {
  local image_ref="${VOYAGER_AI_IMAGE:-voyager-ai-service:latest}"
  local models_host="${VOYAGER_AI_MODELS_HOST_DIR:-$INSTALL_ROOT/ml-models}"
  local has_models=0
  if [[ -d "$models_host" ]] && find "$models_host" -type f -print -quit | grep -q .; then
    has_models=1
  fi

  local unit="/etc/systemd/system/${SERVICE_NAME}.service"
  if [[ "$has_models" -eq 1 ]]; then
    log "Montando modelos locales: $models_host -> /app/app/ml/models (ro)"
    cat >"$unit" <<EOF
[Unit]
Description=Voyager AI service (FastAPI / Docker)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
TimeoutStartSec=0
Restart=always
RestartSec=15
WorkingDirectory=$INSTALL_ROOT
ExecStartPre=-/usr/bin/docker stop $CONTAINER_NAME
ExecStartPre=-/usr/bin/docker rm $CONTAINER_NAME
ExecStart=/usr/bin/docker run --name $CONTAINER_NAME \\
  --env-file $ENV_FILE \\
  -v $models_host:/app/app/ml/models:ro \\
  -p 0.0.0.0:8000:8000 \\
  $image_ref
ExecStop=/usr/bin/docker stop $CONTAINER_NAME
ExecStopPost=-/usr/bin/docker rm $CONTAINER_NAME

[Install]
WantedBy=multi-user.target
EOF
  else
    log "Sin ficheros en $models_host: el contenedor usará lo que venga en la imagen Docker (directorio models del build)."
    cat >"$unit" <<EOF
[Unit]
Description=Voyager AI service (FastAPI / Docker)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
TimeoutStartSec=0
Restart=always
RestartSec=15
WorkingDirectory=$INSTALL_ROOT
ExecStartPre=-/usr/bin/docker stop $CONTAINER_NAME
ExecStartPre=-/usr/bin/docker rm $CONTAINER_NAME
ExecStart=/usr/bin/docker run --name $CONTAINER_NAME \\
  --env-file $ENV_FILE \\
  -p 0.0.0.0:8000:8000 \\
  $image_ref
ExecStop=/usr/bin/docker stop $CONTAINER_NAME
ExecStopPost=-/usr/bin/docker rm $CONTAINER_NAME

[Install]
WantedBy=multi-user.target
EOF
  fi
}

create_template_environment() {
  log "Creando plantilla en $ENV_FILE — edita valores reales y vuelve a ejecutar."
  install -d -m 0755 "$INSTALL_ROOT"
  cat >"$ENV_FILE" <<'EOF'
VOYAGER_AI_IMAGE=voyager-ai-service:latest
DB_HOST=your-ai-rds.region.rds.amazonaws.com
DB_PORT=5432
DB_NAME=tourism_ai
DB_USERNAME=smarttrip_user
DB_PASSWORD=your_password
PGSSLMODE=require
DB_SSLMODE=require
EOF
  chmod 0600 "$ENV_FILE"
}

assert_environment_ready() {
  if grep -qF 'your-ai-rds.region.rds.amazonaws.com' "$ENV_FILE" 2>/dev/null; then
    die "Edita $ENV_FILE y sustituye el host RDS y credenciales."
  fi
}

assert_image_present() {
  local image="${VOYAGER_AI_IMAGE:-voyager-ai-service:latest}"
  docker image inspect "$image" >/dev/null 2>&1 || die "Imagen Docker '$image' no encontrada. Pasa el .tar de CI o construye en la instancia."
}

main() {
  require_root
  install -d -m 0755 "$INSTALL_ROOT"

  if [[ ! -f "$ENV_FILE" ]]; then
    create_template_environment
    die "Plantilla creada en $ENV_FILE. Edítala y ejecuta de nuevo."
  fi

  load_environment
  assert_environment_ready

  install_docker
  install_psql_client

  ensure_database_exists
  install -d -m 0755 "${VOYAGER_AI_MODELS_HOST_DIR:-$INSTALL_ROOT/ml-models}"

  load_image_if_needed
  assert_image_present

  write_systemd_unit
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
  log "Servicio $SERVICE_NAME iniciado. Revisa: systemctl status $SERVICE_NAME | docker logs -f $CONTAINER_NAME"
}

main "$@"
