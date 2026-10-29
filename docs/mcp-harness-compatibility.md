# External MCP harness compatibility

**Protocol transport:** \`scripts/kc-mcp-stdio.sh\` (stdio via authenticated
Kubernetes \`exec\`) or \`scripts/kc-mcp-http.py\` (authenticated loopback
Streamable HTTP). The servers expose dashboard, memory and orchestration
independently. Protocol-level compatibility is not a claim that each
client's current release has passed integration testing.

## Shared configuration

Replace \`/absolute/path/to/kube-coder\` with the checkout path.
The \`KC_MCP_CONTEXT\` is **mandatory** to avoid accidentally targeting a
production/current kubeconfig context.

\`\`\`json
{
  "command": "/absolute/path/to/kube-coder/scripts/kc-mcp-stdio.sh",
  "args": ["dashboard"],
  "env": {
    "KC_MCP_CONTEXT": "kube-coder",
    "KC_MCP_NAMESPACE": "ws-local",
    "KC_MCP_DEPLOYMENT": "ws-local"
  }
}
\`\`\`

\`memory\` and \`agent-orchestrator\` use the same command and env, with only
the first argument changed. Do not register the mutating dashboard tools to
an untrusted agent.

## Configuration examples

### Claude Code, Claude Desktop, Cursor, Cline, Gemini CLI

Use the common object inside the client's \`mcpServers\` configuration. These
products use different **file locations** and may have different UI/tool
permission policies. For example, Cursor normally uses
\`~/.cursor/mcp.json\`; Gemini CLI uses \`~/.gemini/settings.json\`.
Claude Code can also use its CLI:

\`\`\`sh
claude mcp add --transport stdio --scope user kube-coder \
  -- /absolute/path/to/kube-coder/scripts/kc-mcp-stdio.sh dashboard
\`\`\`

Set \`KC_MCP_CONTEXT\`, \`KC_MCP_NAMESPACE\`, and \`KC_MCP_DEPLOYMENT\` in the
environment inherited by the CLI, or use its explicit MCP environment
configuration. Never store a kubeconfig token in these config snippets.

### Codex CLI / IDE (\`~/.codex/config.toml\`)

\`\`\`toml
[mcp_servers.kube_coder]
command = "/absolute/path/to/kube-coder/scripts/kc-mcp-stdio.sh"
args = ["dashboard"]
[mcp_servers.kube_coder.env]
KC_MCP_CONTEXT = "kube-coder"
KC_MCP_NAMESPACE = "ws-local"
KC_MCP_DEPLOYMENT = "ws-local"
\`\`\`

### OpenCode v1 (\`opencode.json\`)

\`\`\`json
{
  "mcp": {
    "kube-coder": {
      "type": "local",
      "command": ["/absolute/path/to/kube-coder/scripts/kc-mcp-stdio.sh", "dashboard"],
      "environment": {
        "KC_MCP_CONTEXT": "kube-coder",
        "KC_MCP_NAMESPACE": "ws-local",
        "KC_MCP_DEPLOYMENT": "ws-local"
      }
    }
  }
}
\`\`\`

OpenCode **v2** instead nests entries under \`mcp.servers\`; consult the
installed CLI's schema before copying a v1 configuration.

### VS Code Copilot Agent (\`.vscode/mcp.json\`)

\`\`\`json
{
  "servers": {
    "kube-coder": {
      "type": "stdio",
      "command": "/absolute/path/to/kube-coder/scripts/kc-mcp-stdio.sh",
      "args": ["dashboard"],
      "env": {
        "KC_MCP_CONTEXT": "kube-coder",
        "KC_MCP_NAMESPACE": "ws-local",
        "KC_MCP_DEPLOYMENT": "ws-local"
      }
    }
  }
}
\`\`\`

### HTTP-only clients

Run the optional loopback gateway as documented in
[model-providers-mcp.md](model-providers-mcp.md). Use
\`http://127.0.0.1:8765/mcp/dashboard\` and read the bearer credential
from the local mode-\`0600\` token file. \`GET\`/SSE is deliberately rejected.
Only local clients can reach this endpoint. A remotely hosted harness or
ChatGPT connector cannot reach \`127.0.0.1\` on your machine; this is
**not a publicly deployed MCP server**. A remote integration requires a
separately reviewed HTTPS, authentication, authorization and tenancy layer.

## Protocol smoke test

A client must successfully perform these **in order**:

1. \`initialize\` with a supported legacy version (or
   \`server/discover\` in modern MCP).
2. \`tools/list\`, checking the declared schema and limited scope.
3. A read-only \`tools/call\`, checking JSON-RPC id correlation and error handling.
4. Only after deliberate authorization, test a mutating tool on a disposable
   workspace, then restore or delete the disposable resources.

For stdout-safe stdio transports, do not write banners to stdout; stderr
is available for diagnostics. The Kubernetes launcher does not translate
protocol versions or tool permissions.

## Support matrix

| Harness / client family | Transport path | Status |
| --- | --- | --- |
| Claude Code / Claude Desktop | stdio | configuration supplied; live test needed |
| Codex CLI / IDE | stdio | configuration supplied; live test needed |
| Gemini CLI | stdio | configuration supplied; live test needed |
| Cursor / Cline / VS Code | stdio | configuration supplied; live test needed |
| OpenCode v1 / v2 | stdio | version-specific config; live test needed |
| Continue, Goose, Aider adapters | stdio if supported by installed client | integration unverified |
| Generic local MCP HTTP clients | HTTP POST | synthetic transport tests passed |
| Remotely hosted MCP clients | HTTP | not supported without a separately secured edge |

Protocol implementation and client versions evolve independently. Consult
[the MCP specification](https://modelcontextprotocol.io/specification)
and each client's installed-version documentation.

## Security boundary

\`pods/exec\` gives effective remote code execution in the workspace and can
read workspace secrets or files. Never treat an MCP tool's prose approval
as an authorization boundary. Use disposable, namespaced workspaces,
restrict the kubeconfig, and do not use a cluster-admin kubeconfig with
untrusted or externally hosted harnesses.
