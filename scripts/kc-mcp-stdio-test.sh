#!/bin/sh
# Unit tests for kube-context guards and stdio pass-through; no cluster needed.
set -eu
root=$(mktemp -d)
trap 'rm -rf "$root"' 0 1 2 3 15
script="$(dirname "$0")/kc-mcp-stdio.sh"
cat > "$root/kubectl" <<'MOCK'
#!/bin/sh
printf '%s\n' "$*" > "$MOCK_ARGS"
cat
MOCK
chmod 755 "$root/kubectl"
export PATH="$root:$PATH" MOCK_ARGS="$root/args"
unset KC_MCP_CONTEXT KC_MCP_NAMESPACE KC_MCP_DEPLOYMENT || true
if "$script" dashboard >/dev/null 2>&1; then echo 'expected missing selector failure' >&2; exit 1; fi
export KC_MCP_CONTEXT=kube-coder KC_MCP_NAMESPACE=ws-local KC_MCP_DEPLOYMENT=ws-local
if "$script" '../escape' >/dev/null 2>&1; then echo 'accepted unknown server' >&2; exit 1; fi
if KC_MCP_CONTEXT='wrong;context' "$script" dashboard >/dev/null 2>&1; then echo 'accepted context injection' >&2; exit 1; fi
actual=$(printf '%s\n' '{"jsonrpc":"2.0","id":1}' | "$script" dashboard)
test "$actual" = '{"jsonrpc":"2.0","id":1}'
test "$(cat "$MOCK_ARGS")" = '--context kube-coder -n ws-local exec -i deployment/ws-local -c ide -- python3 /tmp/browser/mcp_dashboard.py'
printf '%s\n' 'PASS MCP stdio selectors, server allowlist and pass-through'
