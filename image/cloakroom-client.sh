#!/bin/sh
# The chat API client, run inside the container: docker exec cloakroom cloakroom <command>
export CLOAKROOM_DATA_DIR=/data
export CLOAKROOM_API_URL="http://127.0.0.1:${CLOAKROOM_API_LISTEN_PORT:-8423}"
exec python /opt/cloakroom/agent/client.py "$@"
