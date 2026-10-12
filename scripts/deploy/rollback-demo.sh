#!/usr/bin/env bash
# Roll back the demo image only. Never auto-restore an old DB over newer orders.
set -Eeuo pipefail
umask 077
root=$(cd "${1:?demo directory required}" && pwd -P)
backup=$(cd "${2:?backup release directory required}" && pwd -P)
[[ -f "$root/.qiu-pay-demo" && "$backup" == "$root"/releases/* ]] || exit 2
exec 9>"$root/.deploy.lock"
flock -n 9 || exit 2
[[ -f "$backup/previous-image-id" && -f "$backup/compose.yaml" ]] || { echo 'No previous release image recorded'; exit 2; }
image=$(cat "$backup/previous-image-id")
[[ "$image" =~ ^sha256:[a-f0-9]{64}$ ]] || exit 2
docker image inspect "$image" >/dev/null
cp "$backup/compose.yaml" "$root/compose.yaml"
printf 'DEMO_IMAGE=%s\n' "$image" > "$root/.image.env"
cd "$root"
docker compose --env-file .image.env -f compose.yaml up -d --wait --wait-timeout 90
printf 'DEMO_ROLLBACK_OK image=%s database_retained=True\n' "$image"
