#!/usr/bin/env bash
# Polls a docker-compose service's healthcheck until it reports
# "healthy", or fails loudly with the service's logs. Shared between
# .github/workflows/ci.yml and scripts/integration-test.sh so the two
# never drift apart on how "ready" is defined.
set -euo pipefail

service="${1:?usage: wait-healthy.sh <compose-service>}"
cd "$(dirname "$0")/.."

for _ in $(seq 1 30); do
  container_id="$(docker compose ps -q "$service")"
  if [[ -n "$container_id" ]]; then
    status="$(docker inspect -f '{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "")"
    if [[ "$status" == "healthy" ]]; then
      exit 0
    fi
  fi
  sleep 1
done

echo "'$service' did not become healthy in time" >&2
docker compose logs "$service" >&2
exit 1
