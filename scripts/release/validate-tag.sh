#!/usr/bin/env bash
set -Eeuo pipefail
tag=${1:?version tag required}
[[ "$tag" =~ ^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || { echo 'Expected stable vMAJOR.MINOR.PATCH tag'; exit 2; }
sha=$(git rev-parse "refs/tags/$tag^{commit}")
git merge-base --is-ancestor "$sha" origin/main || { echo 'Release commit must belong to main'; exit 2; }
printf '%s\n' "$sha"
