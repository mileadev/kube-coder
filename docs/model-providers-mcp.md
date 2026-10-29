# Model providers and external MCP clients

## Provider configuration

Three explicit `kc-harness` profiles coexist with the original fallback. All are **off by default** and are selected per task.

| Profile | Helm block | Endpoint | Credential |
| --- | --- | --- | --- |
| `kc-ollama-local` | `assistant.ollamaLocal` | configured HTTP(S) OpenAI-compatible Ollama `/v1` | optional named Secret |
| `kc-ollama-cloud` | `assistant.ollamaCloud` | `https://ollama.com/v1` | named Secret containing `api-key` |
| `kc-bedrock` | `assistant.bedrock` | regional Bedrock OpenAI-compatible runtime `/openai/v1` | Bedrock API key in named Secret |

**Caution:** the Bedrock profile uses Bedrock's OpenAI-compatible API-key authentication, *not* AWS SigV4 or IAM role credentials. Obtain a supported Bedrock API key, choose a model available in your region/account, and check model support for Chat Completions and tool calling. For IAM/IRSA deployments use an authenticated SigV4 gateway or an SDK-native adapter instead. No silent fallback to a different provider occurs.

Create secrets without embedding keys in shell history:

```sh
kubectl -n ws-local create secret generic kc-ollama-cloud \
  --from-file=api-key=/secure/path/ollama-cloud-key
kubectl -n ws-local create secret generic kc-bedrock \
  --from-file=api-key=/secure/path/bedrock-key
```

Private values overlay (do not commit):

```yaml
assistant:
  default: kc-ollama-local
  ollamaLocal:
    enabled: true
    baseUrl: http://host.minikube.internal:11434/v1
    model: qwen3:8b
  ollamaCloud:
    enabled: true
    model: YOUR_CLOUD_MODEL
    existingSecretName: kc-ollama-cloud
  bedrock:
    enabled: true
    region: eu-west-1
    model: YOUR_BEDROCK_MODEL_ID
    existingSecretName: kc-bedrock
```

Apply using the **existing** local release name (`local-workspace`) and
private overlay. Create provider Secrets after `local-secret`, before deployment:

```sh
make local-up local-build local-secret
# Create the Secrets shown above, then:
make local-deploy LOCAL_PROVIDER_VALUES=/secure/path/providers.yaml
make local-forward
```

For updates to an existing local cluster, use the same `local-deploy` target.
For k3s/other clusters, adapt the namespace, StorageClass, ingress and Ollama
service address; do not assume `host.minikube.internal` resolves there.

Verify the pod is ready and select a configured agent in the dashboard. Use `kubectl exec -n ws-local deploy/ws-local -c ide -- python3 /tmp/browser/harness.py --provider ollama-local --once 'respond hello'` for an explicit harness smoke test. The `ollama-local` endpoint must be reachable from **inside the pod**; localhost refers to the pod, not the host. Do not expose Ollama on an unrestricted public interface. Cloud endpoints require outbound HTTPS; configure DNS and egress rules appropriately. Cloud model calls may incur charges.

## MCP connectivity

The image contains three stdio MCP servers:

| Server | In-pod path | Privilege |
| --- | --- | --- |
| dashboard | `/tmp/browser/mcp_dashboard.py` | full workspace API; includes mutating tools |
| memory | `/home/dev/.claude-memory/mcp_memory.py` | persistent memory read/write |
| agent-orchestrator | `/tmp/browser/mcp_agent_orchestrator.py` | can spawn autonomous agents |

External clients can use `scripts/kc-mcp-stdio.sh` as their stdio `command`, with args `dashboard`, `memory`, or `agent-orchestrator`. The launcher calls `kubectl exec -i` into a named workspace deployment using the operator's kubeconfig. This requires Kubernetes `pods/exec` privileges: treat the launcher as remote command execution and do not grant it to untrusted MCP clients. It never exposes a public listener.

Example client configuration, adaptable to any harness that supports MCP stdio:

```json
{
  "mcpServers": {
    "kube-coder": {
      "command": "/absolute/path/to/kube-coder/scripts/kc-mcp-stdio.sh",
      "args": ["dashboard"],
      "env": {
        "KC_MCP_NAMESPACE": "ws-local",
        "KC_MCP_DEPLOYMENT": "ws-local",
        "KC_MCP_CONTEXT": "your-explicit-local-kube-context"
      }
    }
  }
}
```

For clients whose MCP schema differs (Codex TOML, OpenCode local MCP, Gemini, Claude Desktop/Code, Cursor, Cline, VS Code), translate the same command/args/env to the client's own schema. Compatibility is subject to each client's current MCP transport and config support; this repository does **not** claim every known harness is tested. Test `initialize`, `tools/list`, and one non-mutating `tools/call` per client before granting write privileges. Tool output is untrusted input and can carry prompt injection.

## Optional MCP HTTP bridge (local process)

`scripts/kc-mcp-http.py` provides authenticated, **loopback-only**,
stateless Streamable HTTP. Each HTTP request is forwarded to a fresh stdio
process through `kc-mcp-stdio.sh`. No public ingress or cluster port is
created. A long-lived MCP session, SSE subscriptions, and unsolicited server
notifications are **not supported**; use stdio for clients requiring them.

```sh
umask 077
mkdir -p "$HOME/.config/kube-coder"
openssl rand -hex 32 > "$HOME/.config/kube-coder/mcp-http-token"
export KC_MCP_CONTEXT=kube-coder KC_MCP_NAMESPACE=ws-local KC_MCP_DEPLOYMENT=ws-local
export KC_MCP_HTTP_TOKEN_FILE="$HOME/.config/kube-coder/mcp-http-token"
python3 scripts/kc-mcp-http.py
```

HTTP endpoints (on the machine running the gateway):
`http://127.0.0.1:8765/mcp/dashboard`,
`/mcp/memory`, and `/mcp/agent-orchestrator`.
Clients must send `Authorization: Bearer <token>` and
`Content-Type: application/json`; browser origins are denied by default.
Keep the token in a secret store/file, never commit it or put it in client
configuration checked into a repository. Tool execution occurs with the
workspace's privileges. Do not expose the bridge by changing its loopback bind.

See [MCP client configurations](mcp-harness-compatibility.md) for stdio and
HTTP examples. These are protocol adapters, not universal compatibility
certification.

### Provider references

- [Ollama OpenAI-compatible API](https://github.com/ollama/ollama/blob/main/docs/api/openai-compatibility.mdx)
- [Amazon Bedrock Chat Completions](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-chat-completions.html)
- [MCP protocol versions](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)

## Security and rollback

Keep kubeconfig and provider keys outside repositories. Prefer a dedicated workspace service account, namespaced RBAC, restricted egress, secret rotation, and network isolation. `kubectl exec` may enable arbitrary in-container operations; avoid sharing the kubeconfig with untrusted users. Disable a backend by setting `assistant.<provider>.enabled=false` and redeploying. Roll back a Helm release with `helm rollback local-workspace <revision> -n ws-local`. Do not remove PVCs during rollback.
