# Windows counterpart of deploy/start.sh. Requires Docker Desktop only: OpenSSL is
# run inside a container, so nothing else has to be installed.
$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location $projectDir
$certDir = Join-Path (Join-Path $projectDir "deploy") "certs"
New-Item -ItemType Directory -Force -Path $certDir | Out-Null

$envFile = Join-Path $projectDir ".env.docker"
$opensslImage = "python:3.12-slim-bookworm"

function Assert-Success([string]$what) {
    if ($LASTEXITCODE -ne 0) {
        throw "$what failed (exit code $LASTEXITCODE)."
    }
}

function Invoke-OpenSsl {
    docker run --rm -v "${certDir}:/certs" -w /certs $opensslImage openssl @args
    Assert-Success "openssl $($args[0])"
}

# Docker and OpenSSL need LF line endings and no byte-order mark.
function Write-UnixFile([string]$path, [string[]]$lines) {
    $text = ($lines -join "`n") + "`n"
    [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false)))
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running. Start Docker Desktop, wait until it is ready, and run this script again."
}

if (-not (Test-Path $envFile)) {
    $lanIp = $env:STMA_LAN_IP
    if (-not $lanIp) {
        try {
            $lanIp = (Find-NetRoute -RemoteIPAddress "1.1.1.1" |
                Where-Object { $_.IPAddress } |
                Select-Object -First 1).IPAddress
        } catch {
            $lanIp = $null
        }
    }
    if (-not $lanIp) {
        throw 'Could not determine this computer''s LAN IP. Run:  $env:STMA_LAN_IP = "<address>"; .\deploy\start.ps1'
    }
    $bytes = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $generator.GetBytes($bytes)
    $generator.Dispose()
    $password = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    Write-UnixFile $envFile @("STMA_POSTGRES_PASSWORD=$password", "STMA_LAN_IP=$lanIp")
}

$lanIp = $null
foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*STMA_LAN_IP=(.+?)\s*$') { $lanIp = $Matches[1] }
}
if (-not $lanIp) {
    throw "STMA_LAN_IP is missing from .env.docker."
}

function Test-Cert([string]$name) {
    Test-Path (Join-Path $certDir $name)
}

if (-not ((Test-Cert "ca.crt") -and (Test-Cert "ca.key"))) {
    Invoke-OpenSsl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes `
        -keyout ca.key `
        -out ca.crt `
        -subj "/CN=STMA Local Network CA" `
        -addext "basicConstraints=critical,CA:TRUE" `
        -addext "keyUsage=critical,keyCertSign,cRLSign"
}

$needServerCert = -not ((Test-Cert "server.crt") -and (Test-Cert "server.key"))
if (-not $needServerCert) {
    $san = (Invoke-OpenSsl x509 -in server.crt -noout -ext subjectAltName) -join "`n"
    $needServerCert = $san -notmatch ("IP Address:" + [regex]::Escape($lanIp) + "(\D|$)")
}
if ($needServerCert) {
    Invoke-OpenSsl req -new -newkey rsa:3072 -nodes `
        -keyout server.key `
        -out server.csr `
        -subj "/CN=$lanIp"
    Write-UnixFile (Join-Path $certDir "server.ext") @(
        "basicConstraints=critical,CA:FALSE",
        "keyUsage=critical,digitalSignature,keyEncipherment",
        "extendedKeyUsage=serverAuth",
        "subjectAltName=IP:$lanIp,IP:127.0.0.1,DNS:localhost"
    )
    Invoke-OpenSsl x509 -req -in server.csr `
        -CA ca.crt `
        -CAkey ca.key `
        -CAcreateserial `
        -out server.crt `
        -days 825 `
        -sha256 `
        -extfile server.ext
    foreach ($leftover in "server.csr", "server.ext", "ca.srl") {
        Remove-Item (Join-Path $certDir $leftover) -ErrorAction SilentlyContinue
    }
}

docker compose --env-file .env.docker up --build -d
Assert-Success "docker compose up"

Write-Host ""
Write-Host "STMA is starting at https://${lanIp}:8000/"
Write-Host "HTTPS certificate authority: $(Join-Path $certDir 'ca.crt')"
Invoke-OpenSsl x509 -in ca.crt -noout -fingerprint -sha256
Write-Host "Install that CA certificate as trusted on client computers for browser Web Crypto."
Write-Host "To create the initial Sysadmin account, run:"
Write-Host "  docker compose --env-file .env.docker run --rm app python -m stma.cli create-admin sysadmin"
