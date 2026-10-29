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

Apply with an explicit Helm release and a private file:

```sh
helm upgrade --install local charts/workspace \
  -n ws-local -f deployments/local/values.yaml -f /secure/path/providers.yaml
```

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

## Security and rollback

Keep kubeconfig and provider keys outside repositories. Prefer a dedicated workspace service account, namespaced RBAC, restricted egress, secret rotation, and network isolation. `kubectl exec` may enable arbitrary in-container operations; avoid sharing the kubeconfig with untrusted users. Disable a backend by setting `assistant.<provider>.enabled=false` and redeploying. Roll back a Helm release with `helm rollback local <revision> -n ws-local`. Do not remove PVCs during rollback.
