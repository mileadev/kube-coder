#!/bin/sh
# Stdio transport to an existing authenticated Kubernetes workspace.
set -eu
server=${1:-}
case "$server" in
  dashboard) path=/tmp/browser/mcp_dashboard.py ;;
  memory) path=/home/dev/.claude-memory/mcp_memory.py ;;
  agent-orchestrator) path=/tmp/browser/mcp_agent_orchestrator.py ;;
  *) printf '%s\n' 'usage: kc-mcp-stdio.sh dashboard|memory|agent-orchestrator' >&2; exit 64 ;;
esac
: "${KC_MCP_CONTEXT:?set an explicit KC_MCP_CONTEXT}"
: "${KC_MCP_NAMESPACE:?set KC_MCP_NAMESPACE}"
: "${KC_MCP_DEPLOYMENT:?set KC_MCP_DEPLOYMENT}"
for value in "$KC_MCP_CONTEXT" "$KC_MCP_NAMESPACE" "$KC_MCP_DEPLOYMENT"; do
  case "$value" in *[!a-zA-Z0-9_.-]*|'') printf '%s\n' 'invalid kube selector' >&2; exit 64 ;; esac
done
exec kubectl --context "$KC_MCP_CONTEXT" -n "$KC_MCP_NAMESPACE" exec -i \
  "deployment/$KC_MCP_DEPLOYMENT" -c ide -- python3 "$path"
