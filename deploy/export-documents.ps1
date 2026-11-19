# Windows counterpart of deploy/export-documents.sh. Copies the encrypted report files out
# of the running Docker deployment, together with an index.csv that maps each stored file
# to its database row. Nothing is decrypted.
param([string]$OutDir)
$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location $projectDir

function Invoke-Compose {
    docker compose --env-file .env.docker @args
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($args[0]) failed (exit code $LASTEXITCODE)."
    }
}

# No 2>$null here: Windows PowerShell 5.1 turns redirected stderr into a terminating error.
$appId = docker compose --env-file .env.docker ps -q app
$dbId = docker compose --env-file .env.docker ps -q db
if (-not $appId -or -not $dbId) {
    throw "STMA is not running. Start it with deploy\start.bat first."
}

if (-not $OutDir) {
    $OutDir = Join-Path (Join-Path $projectDir "encrypted-export") (Get-Date -Format "yyyy-MM-dd_HHmmss")
}
$filesDir = Join-Path $OutDir "files"
New-Item -ItemType Directory -Force -Path $filesDir | Out-Null

Invoke-Compose cp "app:/app/storage/." "$filesDir" | Out-Null

# psql writes the CSV inside the container and it is copied out as-is: piping it through
# PowerShell would re-encode it and mangle non-ASCII file names (for example Turkish letters).
$query = @"
SELECT d.storage_name AS stored_file,
       d.filename AS original_name,
       s.username AS sender,
       CASE WHEN r.student_id = d.sender_id THEN e.username ELSE st.username END AS recipient,
       d.ciphertext_size AS encrypted_bytes,
       rk.version AS recipient_key_version,
       sk.version AS signing_key_version,
       encode(d.iv, 'hex') AS iv_hex,
       length(d.wrapped_des_key) AS wrapped_des_key_bytes,
       to_char(d.created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS') || ' UTC' AS uploaded
FROM documents d
JOIN users s ON s.id = d.sender_id
JOIN relationships r ON r.id = d.relationship_id
JOIN users st ON st.id = r.student_id
JOIN users e ON e.id = r.evaluator_id
JOIN public_keys rk ON rk.id = d.recipient_key_id
JOIN public_keys sk ON sk.id = d.signing_key_id
ORDER BY d.created_at;
"@
$tempCsv = "/tmp/stma-document-index.csv"
Invoke-Compose exec -T db psql -U stma -d stma --csv -v ON_ERROR_STOP=1 -o $tempCsv -c $query
Invoke-Compose cp "db:$tempCsv" (Join-Path $OutDir "index.csv") | Out-Null
Invoke-Compose exec -T db rm -f $tempCsv

$files = @(Get-ChildItem -File -Path $filesDir)
Write-Host ""
Write-Host "First 32 bytes of each stored file (DES ciphertext):"
foreach ($file in $files) {
    $stream = [System.IO.File]::OpenRead($file.FullName)
    try {
        $buffer = New-Object byte[] 32
        $read = $stream.Read($buffer, 0, 32)
    } finally {
        $stream.Dispose()
    }
    $hex = ($buffer[0..($read - 1)] | ForEach-Object { $_.ToString("x2") }) -join " "
    Write-Host "  $($file.Name)  $hex"
}

Write-Host ""
Write-Host "Exported $($files.Count) encrypted file(s) to $filesDir"
Write-Host "Index of original names, sender, recipient and key versions: $(Join-Path $OutDir 'index.csv')"
