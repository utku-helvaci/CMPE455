#!/usr/bin/env bash
# Relays the Docker PostgreSQL to 127.0.0.1:5433 on this computer only, so HeidiSQL can
# connect. Stop it with Ctrl+C.
set -euo pipefail

cd "$(dirname "$0")/.."

db="$(docker compose --env-file .env.docker ps -q db)"
if [[ -z "$db" ]]; then
  printf 'The STMA database is not running. Start STMA with ./deploy/start.sh first.\n' >&2
  exit 1
fi
network="$(docker inspect "$db" --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}')"

printf 'PostgreSQL relay: 127.0.0.1 port 5433, user stma, database stma.\n'
printf 'The password is STMA_POSTGRES_PASSWORD in .env.docker. Press Ctrl+C to stop.\n'
exec docker run --rm --name stma-db-viewer --network "$network" -p 127.0.0.1:5433:5433 \
  alpine/socat TCP-LISTEN:5433,fork,reuseaddr TCP:db:5432
