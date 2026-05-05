#!/usr/bin/env bash
set -euo pipefail

# Despliegue manual (Learner Lab): misma EC2 — imagen Docker + modelos en disco.
# Copia ml-models.tar.gz por SSH, lo descomprime en /opt/voyager-ai-service/ml-models
# y ejecuta ec2-deploy-ai-service.sh (monta ese directorio en el contenedor).
#
# Requiere AWS CLI autenticado y SSH (puerto 22) al ASG de AI.
#
# Uso:
#   ./scripts/deploy-ai-service-manual.sh /ruta/ml-models.tar.gz /ruta/voyager-ai-service-image.tar /ruta/smarttrip-key.pem
#
# Variables opcionales:
#   AWS_REGION=us-east-1
#   AI_ASG_NAME=smarttrip-ai-service-asg
#   SSH_USER=ec2-user
#   AI_INSTALL_ROOT=/opt/voyager-ai-service
#   SKIP_EC2=1   — no desplegar en instancias (solo validar argumentos locales; raro)

ML_TAR="${1:-}"
IMAGE_TAR="${2:-}"
KEY_PATH="${3:-}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AI_ASG_NAME="${AI_ASG_NAME:-smarttrip-ai-service-asg}"
SSH_USER="${SSH_USER:-ec2-user}"
AI_INSTALL_ROOT="${AI_INSTALL_ROOT:-/opt/voyager-ai-service}"
SKIP_EC2="${SKIP_EC2:-0}"

if [[ -z "${ML_TAR}" || -z "${IMAGE_TAR}" || -z "${KEY_PATH}" ]]; then
  echo "Uso: $0 <ml-models.tar.gz> <voyager-ai-service-image.tar> <ssh-key.pem>"
  exit 1
fi

if [[ ! -f "${ML_TAR}" ]]; then
  echo "No existe el tarball de modelos: ${ML_TAR}"
  exit 1
fi

if [[ ! -f "${IMAGE_TAR}" ]]; then
  echo "No existe el tarball de imagen Docker: ${IMAGE_TAR}"
  exit 1
fi

if [[ ! -f "${KEY_PATH}" ]]; then
  echo "No existe la clave SSH: ${KEY_PATH}"
  exit 1
fi

if [[ "${SKIP_EC2}" == "1" ]]; then
  echo "SKIP_EC2=1: omitiendo copia a EC2."
  exit 0
fi

echo "Resolviendo instancias del ASG: ${AI_ASG_NAME}"
INSTANCE_IDS=$(aws autoscaling describe-auto-scaling-groups \
  --region "${AWS_REGION}" \
  --auto-scaling-group-names "${AI_ASG_NAME}" \
  --query "AutoScalingGroups[0].Instances[?LifecycleState=='InService'].InstanceId" \
  --output text)

if [[ -z "${INSTANCE_IDS}" ]]; then
  echo "No hay instancias InService en ${AI_ASG_NAME}"
  exit 1
fi

IPS=$(aws ec2 describe-instances \
  --region "${AWS_REGION}" \
  --instance-ids ${INSTANCE_IDS} \
  --query "Reservations[].Instances[?State.Name=='running'].PublicIpAddress" \
  --output text | tr '\t' '\n' | sed '/^$/d')

if [[ -z "${IPS}" ]]; then
  echo "No hay IPs públicas en ejecución para el ASG de AI"
  exit 1
fi

chmod 600 "${KEY_PATH}"
ssh-keyscan -H ${IPS} >> ~/.ssh/known_hosts 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_ON_INSTANCE="ec2-deploy-ai-service.sh"

for IP in ${IPS}; do
  echo "Copiando imagen Docker, modelos e instalador a ${IP}"
  scp -i "${KEY_PATH}" -o StrictHostKeyChecking=yes \
    "${IMAGE_TAR}" "${ML_TAR}" "${SCRIPT_DIR}/${DEPLOY_ON_INSTANCE}" \
    "${SSH_USER}@${IP}:/tmp/"

  ssh -i "${KEY_PATH}" -o StrictHostKeyChecking=yes "${SSH_USER}@${IP}" << EOF
set -e
sudo mkdir -p "${AI_INSTALL_ROOT}/ml-models"
sudo install -m 0644 /tmp/$(basename "${IMAGE_TAR}") "${AI_INSTALL_ROOT}/voyager-ai-service-image.tar"
sudo install -m 0755 /tmp/${DEPLOY_ON_INSTANCE} "${AI_INSTALL_ROOT}/"
sudo mv /tmp/$(basename "${ML_TAR}") /tmp/ml-models.tar.gz
sudo rm -rf "${AI_INSTALL_ROOT}/ml-models"
sudo mkdir -p "${AI_INSTALL_ROOT}/ml-models-stage"
sudo tar -xzf /tmp/ml-models.tar.gz -C "${AI_INSTALL_ROOT}/ml-models-stage"
if sudo test -d "${AI_INSTALL_ROOT}/ml-models-stage/models"; then
  sudo mv "${AI_INSTALL_ROOT}/ml-models-stage/models" "${AI_INSTALL_ROOT}/ml-models"
  sudo rm -rf "${AI_INSTALL_ROOT}/ml-models-stage"
else
  sudo mv "${AI_INSTALL_ROOT}/ml-models-stage" "${AI_INSTALL_ROOT}/ml-models"
fi
sudo rm -f /tmp/ml-models.tar.gz
sudo "${AI_INSTALL_ROOT}/${DEPLOY_ON_INSTANCE}" "${AI_INSTALL_ROOT}/voyager-ai-service-image.tar"
EOF
done

echo "Despliegue completado. Modelos en ${AI_INSTALL_ROOT}/ml-models; revisa ${AI_INSTALL_ROOT}/environment (DB_*)."
