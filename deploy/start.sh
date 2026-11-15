#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
umask 077
mkdir -p deploy/certs

if [[ ! -f .env.docker ]]; then
  lan_ip="${STMA_LAN_IP:-$(ip -4 route get 1.1.1.1 | sed -n 's/.* src \([^ ]*\).*/\1/p' | head -n 1)}"
  if [[ -z "$lan_ip" ]]; then
    printf 'Could not determine this computer LAN IP. Run with STMA_LAN_IP=<address> ./deploy/start.sh\n' >&2
    exit 1
  fi
  password="$(openssl rand -hex 32)"
  printf 'STMA_POSTGRES_PASSWORD=%s\nSTMA_LAN_IP=%s\n' "$password" "$lan_ip" > .env.docker
fi

set -a
source .env.docker
set +a

if [[ ! -f deploy/certs/ca.crt || ! -f deploy/certs/ca.key ]]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
    -keyout deploy/certs/ca.key \
    -out deploy/certs/ca.crt \
    -subj "/CN=STMA Local Network CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

if [[ ! -f deploy/certs/server.crt || ! -f deploy/certs/server.key ]] \
  || ! openssl x509 -in deploy/certs/server.crt -noout -ext subjectAltName \
    | grep -q "IP Address:${STMA_LAN_IP}"; then
  openssl req -new -newkey rsa:3072 -nodes \
    -keyout deploy/certs/server.key \
    -out deploy/certs/server.csr \
    -subj "/CN=${STMA_LAN_IP}"
  cat > deploy/certs/server.ext <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:${STMA_LAN_IP},IP:127.0.0.1,DNS:localhost
EOF
  openssl x509 -req -in deploy/certs/server.csr \
    -CA deploy/certs/ca.crt \
    -CAkey deploy/certs/ca.key \
    -CAcreateserial \
    -out deploy/certs/server.crt \
    -days 825 \
    -sha256 \
    -extfile deploy/certs/server.ext
  rm deploy/certs/server.csr deploy/certs/server.ext deploy/certs/ca.srl
fi

docker compose --env-file .env.docker up --build -d

printf '\nSTMA is starting at https://%s:8000/\n' "$STMA_LAN_IP"
printf 'HTTPS certificate authority: %s/deploy/certs/ca.crt\n' "$PWD"
openssl x509 -in deploy/certs/ca.crt -noout -fingerprint -sha256
printf 'Install that CA certificate as trusted on client computers for browser Web Crypto.\n'
printf 'To create the initial Sysadmin account, run:\n'
printf '  docker compose --env-file .env.docker run --rm app python -m stma.cli create-admin sysadmin\n'
