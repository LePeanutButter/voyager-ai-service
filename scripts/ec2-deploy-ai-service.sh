#!/usr/bin/env bash
#
# EC2 manual deploy for AWS Academy Learner Lab (sin registry Docker).
# Instala Docker si falta, carga la imagen desde el .tar de CI, garantiza la base
# PostgreSQL (RDS) con SSL y arranca el stack (Ollama + FastAPI) bajo systemd via
# docker compose.
#
# Layout esperado del artefacto de CI (mismo que voyager-backend-core):
#   ./environment
#   ./scripts/ec2-deploy-ai-service.sh
#   ./release/voyager-ai-service-image.tar
#
# Uso (como root, desde el directorio del artefacto):
#   sudo ./scripts/ec2-deploy-ai-service.sh [/ruta/voyager-ai-service-image.tar]
#
# Requeridas en ./environment (o VOYAGER_AI_ENV_FILE):
#   DB_HOST, DB_USERNAME, DB_PASSWORD — para psql bootstrap (CREATE DATABASE)
#   DB_PORT, DB_NAME, DB_SSLMODE
#
# Si DB_SSLMODE=verify-full|verify-ca, el script descarga el bundle RDS a
# $INSTALL_ROOT/global-bundle.pem, lo monta en el contenedor en
# /etc/ssl/certs/global-bundle.pem y exporta PGSSLROOTCERT en el env file para
# que psycopg2 (libpq) lo encuentre.
#
# Opcional:
#   VOYAGER_AI_IMAGE         default voyager-ai-service:latest
#   VOYAGER_AI_INSTALL_ROOT  default $(pwd) (mismo enfoque que voyager-backend-core)
#   VOYAGER_AI_ENV_FILE      default $INSTALL_ROOT/environment
#   VOYAGER_AI_SERVICE_NAME  systemd, default voyager-ai-service
#   AI_HOST_PORT             puerto del host expuesto por FastAPI, default 8000

set -euo pipefail

readonly INSTALL_ROOT="${VOYAGER_AI_INSTALL_ROOT:-$(pwd)}"
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

# Instala el plugin Compose v2 de Docker. En Amazon Linux 2 el paquete `docker`
# del repo oficial NO incluye el plugin (solo buildx), por lo que `docker compose`
# falla con "unknown shorthand flag: 'f'". En AL2023 / Ubuntu hay paquetes nativos
# (docker-compose-plugin) pero como fallback descargamos el binario oficial del
# repo de GitHub y lo dejamos en /usr/libexec/docker/cli-plugins (system-wide).
install_docker_compose_plugin() {
  if docker compose version >/dev/null 2>&1; then
    log "Plugin docker compose ya disponible: $(docker compose version --short 2>/dev/null || echo present)"
    return 0
  fi

  log "Plugin 'docker compose' no encontrado. Instalando..."
  local os
  os="$(detect_os)"
  # Intento 1: paquete nativo donde exista.
  case "$os" in
    amzn\ 2023*|fedora*|rocky*|almalinux*)
      dnf install -y docker-compose-plugin >/dev/null 2>&1 || true
      ;;
    ubuntu*|debian*)
      apt-get install -y docker-compose-plugin >/dev/null 2>&1 || true
      ;;
  esac

  if docker compose version >/dev/null 2>&1; then
    log "Plugin docker compose instalado vía gestor de paquetes."
    return 0
  fi

  # Intento 2: binario oficial de github.com/docker/compose como CLI plugin.
  local plugin_dir="/usr/libexec/docker/cli-plugins"
  local arch
  arch="$(uname -m)"
  install -d -m 0755 "$plugin_dir"
  log "Descargando docker-compose-linux-${arch} desde github.com/docker/compose..."
  curl -fSL \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${arch}" \
    -o "$plugin_dir/docker-compose" \
    || die "No se pudo descargar el plugin docker compose."
  chmod 0755 "$plugin_dir/docker-compose"

  docker compose version >/dev/null 2>&1 \
    || die "Plugin docker compose instalado pero 'docker compose version' sigue fallando."
  log "Plugin docker compose listo: $(docker compose version --short 2>/dev/null || echo present)"
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

  # Si el env file no está en INSTALL_ROOT, lo copiamos desde el directorio del
  # script. Esto cubre el flujo "extraer artefacto y ejecutar desde otro path".
  if [[ ! -f "$ENV_FILE" && -f "$SCRIPT_DIR/environment" ]]; then
    log "Copiando archivo de entorno desde $SCRIPT_DIR/environment a $ENV_FILE"
    cp "$SCRIPT_DIR/environment" "$ENV_FILE"
    chmod 0600 "$ENV_FILE"
  fi

  if [[ -f "$ENV_FILE" ]]; then
    log "Cargando $ENV_FILE"
    set +u
    # shellcheck source=/dev/null
    set -a && source "$ENV_FILE" && set +a
    set -u
  fi
}

# Descarga el bundle de certificados RDS si no está presente. Devuelve la ruta absoluta.
# Necesario cuando DB_SSLMODE=verify-full|verify-ca (psycopg2/libpq y psql lo requieren).
download_rds_cert() {
  local cert_file="$INSTALL_ROOT/global-bundle.pem"
  if [[ ! -f "$cert_file" ]]; then
    log "Descargando certificado SSL de AWS RDS..."
    curl -fsSL -o "$cert_file" https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem \
      || die "No se pudo descargar el certificado RDS."
    chmod 644 "$cert_file"
  fi
  printf "%s" "$cert_file"
}

# Cuando DB_SSLMODE (o el sslmode dentro de DATABASE_URL) exige validación de CA,
# psycopg2/libpq buscan el cert raíz en ~/.postgresql/root.crt, que no existe en
# el contenedor (`/home/appuser/.postgresql/root.crt`). Para evitar el error
# `Could not open SSL root certificate file ...`, exportamos PGSSLROOTCERT
# apuntando a la ruta donde el unit systemd monta el bundle dentro del contenedor.
ensure_db_ssl_compatibility() {
  [[ -f "$ENV_FILE" ]] || return 0
  local container_cert="/etc/ssl/certs/global-bundle.pem"
  local needs_ca=0
  if [[ "${DB_SSLMODE:-}" =~ ^verify-(full|ca)$ ]]; then
    needs_ca=1
  fi
  if [[ -n "${DATABASE_URL:-}" && "$DATABASE_URL" =~ sslmode=verify-(full|ca) ]]; then
    needs_ca=1
  fi
  [[ "$needs_ca" -eq 1 ]] || return 0

  if [[ "${PGSSLROOTCERT:-}" == "$container_cert" ]] && grep -q "^PGSSLROOTCERT=$container_cert$" "$ENV_FILE"; then
    return 0
  fi

  log "DB_SSLMODE/DATABASE_URL exige verify-* sin sslrootcert; inyectando PGSSLROOTCERT=$container_cert en $ENV_FILE"
  local tmp
  tmp="$(mktemp)"
  awk -v new="PGSSLROOTCERT=${container_cert}" '
    BEGIN { replaced = 0 }
    /^PGSSLROOTCERT=/ { print new; replaced = 1; next }
    { print }
    END { if (!replaced) print new }
  ' "$ENV_FILE" >"$tmp"
  install -m 0600 "$tmp" "$ENV_FILE"
  rm -f "$tmp"
  export PGSSLROOTCERT="$container_cert"
}

resolve_image_tar() {
  local tar_path="$IMAGE_TAR_CLI"
  if [[ -n "$tar_path" ]]; then
    echo "$tar_path"
    return
  fi
  # Acepta .tar y .tar.gz para soportar el artefacto comprimido del CI nuevo
  # y los .tar antiguos que sigan en disco.
  local candidates=(
    "$INSTALL_ROOT/voyager-ai-service-image.tar.gz"
    "$INSTALL_ROOT/voyager-ai-service-image.tar"
    "$SCRIPT_DIR/voyager-ai-service-image.tar.gz"
    "$SCRIPT_DIR/voyager-ai-service-image.tar"
    "$INSTALL_ROOT/release/voyager-ai-service-image.tar.gz"
    "$INSTALL_ROOT/release/voyager-ai-service-image.tar"
    "$SCRIPT_DIR/release/voyager-ai-service-image.tar.gz"
    "$SCRIPT_DIR/release/voyager-ai-service-image.tar"
  )
  local c
  for c in "${candidates[@]}"; do
    if [[ -f "$c" ]]; then
      echo "$c"
      return
    fi
  done
  # Última opción: busca en cualquiera de los release/ disponibles.
  local found=""
  if [[ -d "$INSTALL_ROOT/release" ]]; then
    found=$(find "$INSTALL_ROOT/release" -maxdepth 2 \
      \( -name 'voyager-ai-service-image.tar' -o -name 'voyager-ai-service-image.tar.gz' \) \
      -type f 2>/dev/null | head -1)
  fi
  if [[ -z "$found" && -d "$SCRIPT_DIR/release" ]]; then
    found=$(find "$SCRIPT_DIR/release" -maxdepth 2 \
      \( -name 'voyager-ai-service-image.tar' -o -name 'voyager-ai-service-image.tar.gz' \) \
      -type f 2>/dev/null | head -1)
  fi
  echo "${found:-}"
}

load_image_if_needed() {
  local tar_path
  tar_path="$(resolve_image_tar)"
  if [[ -n "$tar_path" ]]; then
    [[ -f "$tar_path" ]] || die "No se encontró el tar de imagen: $tar_path"
    if [[ "$tar_path" == *.gz || "$tar_path" == *.tgz ]]; then
      log "Cargando imagen Docker desde (gzip): $tar_path"
      gunzip -c "$tar_path" | docker load
    else
      log "Cargando imagen Docker desde: $tar_path"
      docker load -i "$tar_path"
    fi
    install -d -m 0755 "$INSTALL_ROOT"
    install -m 0644 "$tar_path" "$INSTALL_ROOT/$(basename "$tar_path")" 2>/dev/null || true
  fi
}

ensure_database_exists() {
  [[ -n "${DB_HOST:-}" ]] || die "DB_HOST no está definido."
  [[ -n "${DB_USERNAME:-}" ]] || die "DB_USERNAME no está definido."
  [[ -n "${DB_PASSWORD:-}" ]] || die "DB_PASSWORD no está definido."
  local port="${DB_PORT:-5432}"
  local dbname="${DB_NAME:-tourism_ai}"
  local admin_db="${DB_ADMIN_DATABASE:-postgres}"

  # Determina el modo SSL para psql en el bootstrap. Prioridad:
  #   PGSSLMODE explícito > DB_SSLMODE del env file > "require" por defecto.
  local sslmode="${PGSSLMODE:-${DB_SSLMODE:-require}}"
  local cert_file=""
  local conn_str

  export PGPASSWORD="$DB_PASSWORD"
  if [[ "$sslmode" =~ ^verify-(full|ca)$ ]]; then
    cert_file="$(download_rds_cert)"
    export PGSSLMODE="$sslmode"
    export PGSSLROOTCERT="$cert_file"
    conn_str="host=$DB_HOST port=$port user=$DB_USERNAME dbname=$admin_db sslmode=$sslmode sslrootcert=$cert_file"
    log "Comprobando base '$dbname' en $DB_HOST:$port con SSL ($sslmode + sslrootcert)..."
  else
    export PGSSLMODE="$sslmode"
    conn_str="host=$DB_HOST port=$port user=$DB_USERNAME dbname=$admin_db sslmode=$sslmode"
    log "Comprobando base '$dbname' en $DB_HOST:$port (sslmode=$sslmode)..."
  fi

  local exists
  exists="$(psql "$conn_str" -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$dbname'" || true)"
  if [[ "$(echo "$exists" | tr -d '[:space:]')" == "1" ]]; then
    log "La base '$dbname' ya existe."
  else
    log "Creando base '$dbname' (la app crea sus tablas en el primer arranque)."
    psql "$conn_str" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$dbname\";"
  fi
  unset PGPASSWORD PGSSLMODE PGSSLROOTCERT
}

write_systemd_unit() {
  local compose_file="$INSTALL_ROOT/docker-compose.yml"
  local cert_file="$INSTALL_ROOT/global-bundle.pem"

  log "Regenerando docker-compose.yml para producción..."
  # Regeneramos siempre el compose para reflejar mejoras del script (p. ej. monte del cert RDS).
  cat >"$compose_file" <<EOF
# Stack listo para EC2: Ollama en un contenedor y el microservicio FastAPI en otro.
# El cert RDS se monta en /etc/ssl/certs/global-bundle.pem para que psycopg2 lo
# encuentre cuando DB_SSLMODE=verify-full|verify-ca (lo apunta PGSSLROOTCERT en el env_file).
services:
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - ai_net
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 20s

  ai:
    image: \${VOYAGER_AI_IMAGE:-voyager-ai-service:latest}
    restart: unless-stopped
    depends_on:
      ollama:
        condition: service_healthy
    ports:
      - "\${AI_HOST_PORT:-8000}:8000"
    env_file:
      - $ENV_FILE
    volumes:
      - ai_service_data:/app/data
      - ai_ml_models:/app/app/ml/models
      - $cert_file:/etc/ssl/certs/global-bundle.pem:ro
    networks:
      - ai_net

volumes:
  ollama_data:
  ai_service_data:
  ai_ml_models:

networks:
  ai_net:
    driver: bridge
EOF

  local unit="/etc/systemd/system/${SERVICE_NAME}.service"
  log "Creando servicio systemd para docker-compose..."
  cat >"$unit" <<EOF
[Unit]
Description=Voyager AI Stack (Ollama + FastAPI)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
TimeoutStartSec=0
Restart=always
RestartSec=15
WorkingDirectory=$INSTALL_ROOT
EnvironmentFile=$ENV_FILE
ExecStartPre=-/usr/bin/docker compose -f $compose_file down
ExecStart=/usr/bin/docker compose -f $compose_file up
ExecStop=/usr/bin/docker compose -f $compose_file down

[Install]
WantedBy=multi-user.target
EOF
}

create_template_environment() {
  log "Creando plantilla en $ENV_FILE — edita valores reales y vuelve a ejecutar."
  install -d -m 0755 "$INSTALL_ROOT"
  cat >"$ENV_FILE" <<'EOF'
# Database configuration (RDS PostgreSQL)
# DATABASE_URL es opcional: si lo dejas vacío, la app construye la URL desde DB_*.
DATABASE_URL=
DB_HOST=your-ai-rds.region.rds.amazonaws.com
DB_PORT=5432
DB_NAME=smarttrip-ai
DB_USERNAME=smarttrip_user
DB_PASSWORD=your_password
# Opciones: require | verify-ca | verify-full (recomendado para RDS).
# Si usas verify-*, el script descarga el bundle RDS y exporta PGSSLROOTCERT.
DB_SSLMODE=verify-full
PGSSLMODE=verify-full
# Ruta DENTRO del contenedor donde el compose monta el bundle. No editar a menos
# que cambies también el volume del compose.
PGSSLROOTCERT=/etc/ssl/certs/global-bundle.pem

# AI/ML Configuration (Ollama en la misma EC2 vía Docker network)
# phi3:3.8b ~ 2.3 GB, ~2x más rápido que mistral:7b en CPU. Cambia a
# mistral:7b-instruct si necesitas mejor calidad y aceptas el tradeoff.
OLLAMA_URL=http://ollama:11434
LOCAL_MODEL_NAME=phi3:3.8b
OLLAMA_HTTP_TIMEOUT_SECONDS=300
OLLAMA_PULL_ON_START=1
LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# Service Configuration
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Fixed values (no secrets)
AI_HOST_PORT=8000
CORS_ALLOW_EC2_COMPUTE_DNS=false
LOG_LEVEL=INFO
VOYAGER_AI_IMAGE=voyager-ai-service:latest
VOYAGER_AI_ENV_FILE=$INSTALL_ROOT/environment
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
  install_docker_compose_plugin
  install_psql_client

  # Si DB_SSLMODE/DATABASE_URL pide verify-*, baja el bundle y deja PGSSLROOTCERT
  # en el env file para que psycopg2 dentro del contenedor lo use al conectar.
  download_rds_cert >/dev/null
  ensure_db_ssl_compatibility

  ensure_database_exists

  load_image_if_needed
  assert_image_present

  write_systemd_unit
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
  log "Stack $SERVICE_NAME iniciado (Ollama + IA). Revisa: systemctl status $SERVICE_NAME | docker compose -f $INSTALL_ROOT/docker-compose.yml logs -f"
}

main "$@"
