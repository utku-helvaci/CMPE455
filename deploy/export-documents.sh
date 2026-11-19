#!/usr/bin/env bash
# Copies the encrypted report files out of the running Docker deployment, together with
# an index.csv that maps each stored file to its database row. Nothing is decrypted.
set -euo pipefail

cd "$(dirname "$0")/.."
compose=(docker compose --env-file .env.docker)

if [[ -z "$("${compose[@]}" ps -q app 2>/dev/null)" || -z "$("${compose[@]}" ps -q db 2>/dev/null)" ]]; then
  printf 'STMA is not running. Start it with ./deploy/start.sh first.\n' >&2
  exit 1
fi

out="${1:-encrypted-export/$(date +%Y-%m-%d_%H%M%S)}"
mkdir -p "$out/files"

"${compose[@]}" cp app:/app/storage/. "$out/files/" >/dev/null

"${compose[@]}" exec -T db psql -U stma -d stma --csv -v ON_ERROR_STOP=1 -c "
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
ORDER BY d.created_at;" > "$out/index.csv"

count=0
printf '\nFirst 32 bytes of each stored file (DES ciphertext):\n'
for file in "$out"/files/*; do
  [[ -f "$file" ]] || continue
  count=$((count + 1))
  printf '  %s  %s\n' "$(basename "$file")" "$(od -An -tx1 -N32 "$file" | tr -s ' \n' ' ')"
done

printf '\nExported %d encrypted file(s) to %s/files\n' "$count" "$out"
printf 'Index of original names, sender, recipient and key versions: %s/index.csv\n' "$out"
