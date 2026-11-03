#!/usr/bin/env bash
set -euo pipefail
# Explicit publication only; requires user-supplied Docker Hub namespace and login.
if [[ $# -ne 2 ]]; then
  echo "Usage: bash scripts/publish_images.sh DOCKERHUB_USERNAME TAG"
  exit 2
fi
cd "$(dirname "$0")/.."
image="$1/distributed-banking:$2"
docker build -t "$image" .
docker push "$image"
echo "Published application image: $image"
echo "PostgreSQL uses the official postgres:16-alpine image (not republished)."

