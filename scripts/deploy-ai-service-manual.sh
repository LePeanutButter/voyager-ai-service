#!/usr/bin/env bash
set -euo pipefail

# Manual deploy for AWS Academy / Learner Lab
# Requires local AWS CLI auth already active (temporary credentials).
#
# Usage:
#   ./scripts/deploy-ai-service-manual.sh /path/to/ai-service-api.tar.gz /path/to/smarttrip-key.pem

PACKAGE_PATH="${1:-}"
KEY_PATH="${2:-}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AI_ASG_NAME="${AI_ASG_NAME:-smarttrip-ai-service-asg}"
SSH_USER="${SSH_USER:-ec2-user}"
AI_APP_DIR="${AI_APP_DIR:-/opt/smarttrip/ai-service}"

if [[ -z "${PACKAGE_PATH}" || -z "${KEY_PATH}" ]]; then
  echo "Usage: $0 <ai-service-api.tar.gz-path> <ssh-key-path>"
  exit 1
fi

if [[ ! -f "${PACKAGE_PATH}" ]]; then
  echo "Package not found: ${PACKAGE_PATH}"
  exit 1
fi

if [[ ! -f "${KEY_PATH}" ]]; then
  echo "SSH key not found: ${KEY_PATH}"
  exit 1
fi

echo "Resolving AI instances from ASG: ${AI_ASG_NAME}"
INSTANCE_IDS=$(aws autoscaling describe-auto-scaling-groups \
  --region "${AWS_REGION}" \
  --auto-scaling-group-names "${AI_ASG_NAME}" \
  --query "AutoScalingGroups[0].Instances[?LifecycleState=='InService'].InstanceId" \
  --output text)

if [[ -z "${INSTANCE_IDS}" ]]; then
  echo "No InService instances found in ASG ${AI_ASG_NAME}"
  exit 1
fi

IPS=$(aws ec2 describe-instances \
  --region "${AWS_REGION}" \
  --instance-ids ${INSTANCE_IDS} \
  --query "Reservations[].Instances[?State.Name=='running'].PublicIpAddress" \
  --output text | tr '\t' '\n' | sed '/^$/d')

if [[ -z "${IPS}" ]]; then
  echo "No public IPs found for AI instances"
  exit 1
fi

chmod 600 "${KEY_PATH}"
ssh-keyscan -H ${IPS} >> ~/.ssh/known_hosts 2>/dev/null || true

for IP in ${IPS}; do
  echo "Deploying AI service artifact to ${IP}"
  scp -i "${KEY_PATH}" -o StrictHostKeyChecking=yes "${PACKAGE_PATH}" "${SSH_USER}@${IP}:/tmp/ai-service-api.tar.gz"

  ssh -i "${KEY_PATH}" -o StrictHostKeyChecking=yes "${SSH_USER}@${IP}" << EOF
set -e
mkdir -p "${AI_APP_DIR}"
cd "${AI_APP_DIR}"
tar -xzf /tmp/ai-service-api.tar.gz

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

pkill -f "uvicorn app.main:app" || true
nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 > ai-service.log 2>&1 &
EOF
done

echo "AI service deployment completed."
