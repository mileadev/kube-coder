# kube-coder security and deployment audit — 2026-10-29

**Repository:** `mileadev/kube-coder`  
**Base:** `main` at `02e196af54a212c2c61c9c34e809f9356f8f2ecb`  
**Changes:** `feat/local-model-providers-mcp-audit-20261029` / [PR #1](https://github.com/mileadev/kube-coder/pull/1)

## Scope and evidence standard

The GitHub tree reports **1,356 tracked files** (not all executable source), including 797 under `charts/`, 261 under `docs/`, 149 under `mobile/`, 24 under `keeper/`, and 20 under `scripts/`. The audit inspected project/CI structure, runtime dispatch, provider configuration, Helm deployment/RBAC and NetworkPolicy templates, MCP servers, gateway, memory, high-risk HTTP handling, representative handlers, and selected tests. The backend `charts/workspace/server.py` is ~16,400 lines. **This is a targeted static architecture/security audit, NOT line-by-line verification of all 1,356 files.** No assertion of absence of malicious code is justified by this scope.

Risk severity describes the consequence **if the stated precondition holds**, not evidence of an active exploit.

## Findings and dispositions

| ID | Severity | Verified observation | Disposition / remaining action |
| --- | --- | --- | --- |
| KC-01 | High | Local `Makefile` originally provisioned public `admin/admin` HTTP basic credentials; `local-forward` lacked an explicit bind address. | **Fixed in PR:** random persistent 0600 password, no plaintext output, explicit 127.0.0.1 forwarding. Synthetic CLI tests pass. Existing local installs should rotate credentials using `make local-secret`. |
| KC-02 | High | Each in-pod `kc-harness` model may invoke arbitrary `bash` and file tools. Remote model responses are therefore untrusted instructions that can execute as the pod user. | **Architectural / remains:** isolate pod per trust boundary, no cluster-admin or host mounts, non-root, seccomp, restricted network egress, container runtime sandbox where available. Prompts are not authorization enforcement. |
| KC-03 | High | MCP dashboard can mutate tasks; memory and agent-orchestrator previously exposed mutation tools even when the workspace is read-only. | **Fixed in PR:** readonly filtering and runtime refusal for memory mutators and agent spawn/kill; focused unit tests added. Needs full repository regression suite. |
| KC-04 | High | MCP stdio launcher requires Kubernetes `pods/exec`, which conveys general shell/code execution authority within the targeted container, not tool-level RBAC. | **Constrained by design:** mandatory named Kubernetes context, namespace, deployment and fixed server allowlist. Use only trusted/local clients; ideally dedicated narrow RBAC for a disposable workspace. Remote multi-tenant MCP gateway requires different architecture. |
| KC-05 | High | `build.mode=buildkit` adds a privileged UID-0 Docker daemon sidecar. | **Existing opt-in hazard:** default remains `kaniko`. Do not allow buildkit mode in a shared threat domain without workload isolation. |
| KC-06 | High | Model-provider API keys are injected through Kubernetes Secret references as environment variables into the same workspace processes that run model-issued tools. | **Partially mitigated:** separate provider Secrets, no tracked credential values; not protected from agent-controlled process reads. For hostile repositories or external agents, use a tightly scoped egress proxy / broker instead. |
| KC-07 | Moderate | Default NetworkPolicy CIDRs are DOKS-specific; a local minikube Calico profile could block DNS/apiserver incorrectly, while default minikube CNI does not enforce policy. | **Fixed local overlay for standard minikube service CIDRs** (`10.96.0.0/12` with DNS `10.96.0.10`, API `10.96.0.1`). Verify cluster's real pod/service CIDRs and CNI enforcement before deployment; do not treat a rendered policy as proof of enforcement. |
| KC-08 | Moderate | Existing MCP servers negotiated only a 2024 revision and a 2026 revision, omitting common 2025 protocol versions. | **Fixed in PR:** 2025-03-26, 2025-06-18 and 2025-11-25 negotiation included; fixture tests updated. Live per-client interoperability remains untested. |
| KC-09 | Moderate | Original OpenAI-compatible `kc-harness` sent `tool_choice=auto` even though Ollama's documented compatibility surface does not support that field. | **Fixed:** omit optional field; add request-shape test. Bedrock and Ollama live model calls remain untested. |
| KC-10 | Moderate | The new HTTP MCP bridge is an externalized tool-execution interface. Exposing it on an unrestricted listener would enable high-consequence access through a bearer credential. | **Preventive controls in PR:** loopback-only, bearer auth, 0600 secret file, Origin check, small request cap, concurrency cap, no-store headers, no redirects, no network ingress. Synthetic integration tests pass. Not a multi-user/public MCP service. |
| KC-11 | Moderate | `server.py` remains >16k lines; auth, task, and provider logic live in a large module. This increases review and regression risk. | **Not refactored:** isolate auth policy, provider adapter, task manager and HTTP routing behind characterized interfaces in separate PRs. A bulk untested rewrite would increase risk. |
| KC-12 | Moderate | `.trivyignore` suppresses multiple CVEs and GHSAs based on historical reachability/non-applicability assessments. | **Review required at each dependency update** against current SBOM, reachable code and upstream fixes. Do not assume these suppressions remain valid indefinitely. |
| KC-13 | Moderate | Fork GitHub Actions returned no workflow runs/checks for the feature branch at audit time. | **Unverified execution:** updated CI test jobs, but GitHub-hosted compilation, Helm, Node/mobile, Go, image scanning and SBOM generation did not execute. Enable/run Actions and require green checks before merge. |
| KC-14 | Low / functional | Existing `kc-harness --once` returned a zero process status after HTTP/model errors, making model smoke tests misleading. | **Fixed in PR:** failed upstream/malformed/exhausted-loop one-shot exits nonzero. Mocked failure/success tests added. |

## Provider behavior / isolation

- `kc-ollama-local`: isolated configuration (URL, model and optional bearer credential). The chosen URL must be reachable **from within the pod**, not just the Mac host; don't expose Ollama to the public Internet.
- `kc-ollama-cloud`: pinned HTTPS OpenAI-compatible endpoint; separate API key and model. Usage may be billable.
- `kc-bedrock`: regional HTTPS OpenAI-compatible endpoint, **Bedrock API key** authentication (not AWS SigV4/IRSA). Validate region, model ID, account entitlement, chat completions and tool-call compatibility. Using IAM identities requires an SDK adapter or separately authenticated proxy.
- Old `kc-harness` fallback remains unchanged for existing deployments. New backends are opt-in.
- A configured provider is not a capability guarantee: model tool-use quality differs by model and provider and must be measured.

## Tests executed versus still required

**Executed locally (synthetic, not production):**
- `sh scripts/local-auth-test.sh`: passed lifecycle, file mode, non-logging, override and symlink cases.
- `sh scripts/kc-mcp-stdio-test.sh`: passed required selectors, invalid name, injection string and stdin/stdout pass-through.
- `python3 scripts/test-kc-mcp-http.py`: 5 tests passed for request forwarding, authentication, Origin, notifications, invalid HTTP/path/JSON and oversized requests.
- `python3 -m py_compile scripts/kc-mcp-http.py`: passed.

**Not executed:** full Python suite, Helm lint/render/chart unittest, Preact/React Native tests, Go test/race, Docker builds, Trivy and TruffleHog, live Kubernetes rollout, native MCP clients and real Ollama/Bedrock inference. GitHub app access can edit/push code, but does not provide a live Kubernetes cluster or API credentials. Inactive GitHub Actions on this fork are an external blocker.

**Acceptance gate for live deployment:**
1. Enable fork Actions, require `helm-lint`, `helm-test`, `python-tests`, `shell-tests`, `web-tests`, `controller-web-tests`, `mobile-tests`, `keeper-tests`, `docker-build`, `security-scan` to pass.
2. In a dedicated minikube/k3s sandbox, verify CNI policy enforcement, storage persistence, ingress authentication, non-root context and pod egress including both DNS and API endpoint.
3. Configure each provider with a scoped test key / local model, run one completion and one tool-call prompt; assert a nonzero exit for simulated 401, invalid model, and unreachable provider.
4. For each chosen MCP client/harness, run `initialize`, `tools/list`, read-only `tools/call`, rejected write in readonly mode, and a disposable authorized write. No blanket claim of all-client support.
5. Validate teardown, rollback, secret rotation, PVC retention and recovery. Document billing guardrails for external providers.

## Deployment, rollback and controls

Use `make local-up local-build local-secret`, provision Kubernetes Secrets from files, then `make local-deploy LOCAL_PROVIDER_VALUES=/secure/path/providers.yaml` and `make local-forward`. Access through `http://kube-coder.local:8080` only on loopback and retrieve the random password from your local credential file. The local Helm release is **`local-workspace`** in **`ws-local`**.

Rollback with `helm --kube-context kube-coder rollback local-workspace <revision> -n ws-local`. Never delete persistent volume claims during rollback. Disable specific model providers via `assistant.<provider>.enabled=false`; delete their Secrets only after every deployment referencing them is stopped.

## Prioritized residual backlog

- P0: Enable/execute CI and run live integration with actual cluster, providers, and targeted MCP clients before merge.
- P0: Confirm namespace and pod escape boundaries with Calico/Cilium enforcement, including kaniko Jobs and any privileged sidecar.
- P1: Separate model credentials from arbitrary agent tools via broker/role-limited service; replace `pods/exec` MCP for untrusted/remote clients with authenticated, scope-limited API surface.
- P1: Validate/resolve every currently suppressed CVE against current SBOM; run comprehensive SAST and secrets scanning.
- P2: Extract monolithic backend into test-characterized modules without broad behavior changes; measure function-level coverage and race/serialization behavior.

**Conclusion:** significant targeted changes are pushed, but this repository cannot be accurately certified as fully audited, secure, or production-ready without the unexecuted acceptance gate above.
