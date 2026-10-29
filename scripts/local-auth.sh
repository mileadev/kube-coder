#!/bin/sh
# Generate and persist a high-entropy password for loopback-only local ingress.
set -eu
umask 077
: "${HOME:?HOME is required}"
context=${KC_LOCAL_CONTEXT:-kube-coder}
namespace=${KC_LOCAL_NAMESPACE:-ws-local}
secret=${KC_LOCAL_AUTH_SECRET:-kube-coder-basic-auth}
user=${KC_LOCAL_AUTH_USER:-admin}
auth_file=${KC_LOCAL_AUTH_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/kube-coder/local-auth}
for value in "$context" "$namespace" "$secret" "$user"; do
  case "$value" in ''|*[!a-zA-Z0-9_.-]*) echo 'Invalid Kubernetes selector or auth user' >&2; exit 64 ;; esac
done
case "$auth_file" in /*) ;; *) echo 'KC_LOCAL_AUTH_FILE must be absolute' >&2; exit 64 ;; esac
auth_dir=$(dirname "$auth_file")
mkdir -p "$auth_dir"
chmod 700 "$auth_dir"
if [ -L "$auth_file" ]; then
  echo 'Refusing symlinked local auth file' >&2
  exit 1
fi
if [ -n "${LOCAL_AUTH_PASS:-}" ] && [ "${#LOCAL_AUTH_PASS}" -lt 16 ]; then
  echo "LOCAL_AUTH_PASS must contain at least 16 characters" >&2
  exit 64
fi
if [ -n "${LOCAL_AUTH_PASS:-}" ] || [ ! -f "$auth_file" ]; then
  candidate=$(mktemp "$auth_dir/.local-auth.XXXXXXXX")
  trap 'rm -f "$candidate"' 0 1 2 3 15
  if [ -n "${LOCAL_AUTH_PASS:-}" ]; then
    printf '%s' "$LOCAL_AUTH_PASS" > "$candidate"
  else
    openssl rand -hex 24 > "$candidate"
  fi
  mv -f "$candidate" "$auth_file"
  trap - 0 1 2 3 15
fi
chmod 600 "$auth_file"
password=$(cat "$auth_file")
[ "${#password}" -ge 16 ] || { echo 'Local auth password must have at least 16 characters' >&2; exit 1; }
htpasswd=$(mktemp)
trap 'rm -f "$htpasswd"' 0 1 2 3 15
hash=$(printf '%s' "$password" | openssl passwd -apr1 -stdin)
printf '%s:%s\n' "$user" "$hash" > "$htpasswd"
kubectl --context "$context" create namespace "$namespace" --dry-run=client -o yaml | \
  kubectl --context "$context" apply -f -
kubectl --context "$context" -n "$namespace" create secret generic "$secret" \
  --from-file="auth=$htpasswd" --dry-run=client -o yaml | \
  kubectl --context "$context" apply -f -
echo "Local basic-auth Secret updated; username=$user; password file=$auth_file (0600)"
