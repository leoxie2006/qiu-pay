#!/usr/bin/env bash
# Promote only the current, checked main image; retrying old CI must not roll latest back.
set -Eeuo pipefail
image=${1:?immutable SHA tag required}
ref=${2:?verified digest required}
: "${GITHUB_SHA:?}"
[[ "$image" == ghcr.io/*:sha-"$GITHUB_SHA" ]] || exit 1
repository=${image%:sha-*}
[[ "$ref" == "$repository"@sha256:* ]] || exit 1
[[ "${ref##*@}" =~ ^sha256:[a-f0-9]{64}$ ]] || exit 1
main_sha=$(git ls-remote origin refs/heads/main | awk '{print $1}')
if [[ "$main_sha" != "$GITHUB_SHA" ]]; then
  echo "Skip latest: this revision is no longer the current main"
  exit 0
fi
latest="$repository:latest"
docker tag "$ref" "$latest"
docker push "$latest"
remote_digest=$(docker buildx imagetools inspect "$latest" | awk '/^Digest:/ {print $2}')
[[ "$remote_digest" == "${ref##*@}" ]] || { echo "Latest digest mismatch" >&2; exit 1; }
echo "LATEST_VERIFIED $latest@$remote_digest"
