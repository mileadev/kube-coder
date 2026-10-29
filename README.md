# kube-coder

Self-hosted, Kubernetes-backed development workspaces with persistent home directories, browser IDE, terminal, AI agent orchestration, memory, and MCP tools.

[Documentation](docs/) · [Security](SECURITY.md) · [Local development](docs/local-development.md) · [Model providers and MCP](docs/model-providers-mcp.md) · [Contributing](CONTRIBUTING.md)

## Architecture

Each workspace runs as an isolated Kubernetes deployment with a persistent volume. The Python backend serves a web dashboard; optional agents use existing CLI runtimes, including the built-in narrow-tool `kc-harness`. Built-in stdio MCP servers expose dashboard, memory, and agent-orchestration operations. Kubernetes isolation is not a substitute for tool-level authorization.

## Local quick start

Requires Docker, minikube, Helm, kubectl, and Make.

```sh
make local
# In a separate terminal:
make local-forward
# Add 127.0.0.1 kube-coder.local to /etc/hosts.
# Open http://kube-coder.local:8080/
```

**Security:** local startup creates a random password in `~/.config/kube-coder/local-auth` (mode `0600`). Keep HTTP forwarding bound to loopback; never expose the demo ingress to an untrusted network. For multi-user installations follow the production authentication, RBAC, and NetworkPolicy guidance.

## Model providers

The existing `kc-harness` supports an OpenAI-compatible fallback. Optional, independent assistants are `kc-ollama-local`, `kc-ollama-cloud`, and `kc-bedrock`. Configure `assistant.*` in a private Helm values overlay; store credentials in named Kubernetes Secrets, not in Git. See [provider and MCP guide](docs/model-providers-mcp.md). Cloud inference can incur usage charges.

## MCP

Three existing stdio servers: `dashboard`, `memory`, and `agent-orchestrator`. External clients may connect through the guarded Kubernetes stdio launcher or the optional **loopback-only, bearer-authenticated Streamable HTTP bridge**. See [model-providers-mcp.md](docs/model-providers-mcp.md) and [MCP harness configurations](docs/mcp-harness-compatibility.md).

## Development and checks

```sh
python3 -m unittest discover -s charts/workspace/tests -p '*_test.py'
python3 charts/workspace/harness_provider_test.py
sh scripts/local-auth-test.sh
python3 scripts/test-kc-mcp-http.py
helm lint charts/workspace
helm template local charts/workspace -f deployments/local/values.yaml >/dev/null
```

The repository additionally contains web/mobile clients, Helm tests, and GitHub Actions checks; follow their respective package scripts and CI workflow. Do not assume one test command covers all components.

## License

MIT. See [LICENSE](LICENSE).
