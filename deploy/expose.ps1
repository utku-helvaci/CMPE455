# Windows counterpart of deploy/expose.sh: relays the Docker PostgreSQL to 127.0.0.1:5433
# on this computer only, so HeidiSQL can connect. Stop it with Ctrl+C.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$db = docker compose --env-file .env.docker ps -q db
if (-not $db) {
    throw "The STMA database is not running. Start STMA with deploy\start.bat first."
}
$network = docker inspect $db --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}'

Write-Host "PostgreSQL relay: 127.0.0.1 port 5433, user stma, database stma."
Write-Host "The password is STMA_POSTGRES_PASSWORD in .env.docker. Press Ctrl+C to stop."
docker run --rm --name stma-db-viewer --network $network -p 127.0.0.1:5433:5433 `
    alpine/socat TCP-LISTEN:5433,fork,reuseaddr TCP:db:5432
