#!/usr/bin/env bash
# Dedicated DEMO only. Never point this at a production deployment directory.
set -Eeuo pipefail
umask 077
root=${1:?usage: demo.sh DEMO_DIR IMAGE_DIGEST}
image=${2:?immutable image digest required}
[[ "$image" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]] || { echo 'Immutable GHCR digest required'; exit 2; }
root=$(cd "$root" && pwd -P)
[[ "$root" != / && -f "$root/.qiu-pay-demo" && -f "$root/.env.demo" ]] || { echo 'Dedicated demo marker and .env.demo required'; exit 2; }
exec 9>"$root/.deploy.lock"
flock -n 9 || { echo 'Another deployment is active'; exit 2; }
here=$(cd "$(dirname "$0")/../.." && pwd -P)
cd "$root"
[[ ! -e data || ( -d data && ! -L data ) ]] || exit 2
[[ ! -e uploads || ( -d uploads && ! -L uploads ) ]] || exit 2
mkdir -p data uploads releases
stamp=$(date -u +%Y%m%dT%H%M%SZ)-$$
backup="$root/releases/$stamp"
mkdir "$backup"
cp .env.demo "$backup/.env.demo"
[[ ! -f compose.yaml ]] || cp compose.yaml "$backup/compose.yaml"
[[ ! -f .image.env ]] || cp .image.env "$backup/.image.env"
compose() { docker compose --env-file .image.env -f compose.yaml "$@"; }
old_id=''
if [[ -f compose.yaml && -f .image.env ]]; then
  old_id=$(compose ps -q demo)
  [[ -z "$old_id" ]] || docker inspect --format '{{.Image}}' "$old_id" > "$backup/previous-image-id"
fi
docker pull "$image"
# Candidate verification mounts neither live data nor live configuration.
docker run --rm --network none -v "$here/scripts/smoke_issue14.py:/smoke.py:ro" \
  -e PYTHONPATH=/app "$image" python /smoke.py | tee "$backup/candidate-verification.txt"
# SQLite online backup is WAL-consistent; only this separate backup container reads demo DB.
if [[ -f data/qiupay.db ]]; then
  docker run --rm --network none -v "$root/data:/source:ro" -v "$backup:/backup" "$image" \
    python -c "import sqlite3; a=sqlite3.connect('file:/source/qiupay.db?mode=ro',uri=True); b=sqlite3.connect('/backup/qiupay.db'); a.backup(b); assert b.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; b.close(); a.close()"
fi
tar -czf "$backup/uploads.tar.gz" -C "$root" uploads
rollback() {
  # Source-only patch, no schema migration: retain current DB so newer orders survive.
  if [[ -f "$backup/previous-image-id" ]]; then
    cp "$backup/compose.yaml" compose.yaml
    previous=$(cat "$backup/previous-image-id")
    printf 'DEMO_IMAGE=%s\n' "$previous" > .image.env
    compose up -d --wait --wait-timeout 90
  else
    compose down || true
    [[ ! -f "$backup/compose.yaml" ]] || cp "$backup/compose.yaml" compose.yaml
    [[ ! -f "$backup/.image.env" ]] || cp "$backup/.image.env" .image.env
  fi
}
trap 'echo "Deployment failed; rolling back demo image"; rollback; exit 1' ERR
cp "$here/deploy/demo/compose.yaml" compose.yaml
printf 'DEMO_IMAGE=%s\n' "$image" > .image.env
compose up -d --wait --wait-timeout 90
running=$(compose ps -q demo)
[[ -n "$running" ]]
[[ "$(docker inspect --format '{{.Image}}' "$running")" == "$(docker image inspect --format '{{.Id}}' "$image")" ]]
# Verification runs in a separate container using the deployed image, not the demo DB.
docker run --rm --network none -v "$here/scripts/smoke_issue14.py:/smoke.py:ro" \
  -e PYTHONPATH=/app "$image" python /smoke.py | tee "$backup/deployed-image-verification.txt"
trap - ERR
printf '%s\n' "$backup" > .last-release
printf 'DEMO_DEPLOYED image=%s backup=%s\n' "$image" "$backup"
