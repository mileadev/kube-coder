#!/bin/sh
set -eu
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT HUP INT TERM
cat > "$root/kubectl" <<'MOCK'
#!/bin/sh
for arg in "$@"; do
  case "$arg" in --from-file=auth=*) cp "${arg#--from-file=auth=}" "$MOCK_HTPASSWD" ;; esac
done
case " $* " in *' create namespace '*) printf '%s\n' 'apiVersion: v1' 'kind: Namespace' ;; *' create secret generic '*) printf '%s\n' 'apiVersion: v1' 'kind: Secret' ;; esac
MOCK
chmod 755 "$root/kubectl"
export PATH="$root:$PATH" HOME="$root" KC_LOCAL_AUTH_FILE="$root/config/local-auth" MOCK_HTPASSWD="$root/captured"
output=$(sh "$(dirname "$0")/local-auth.sh")
test -f "$KC_LOCAL_AUTH_FILE"
test "$(stat -c '%a' "$KC_LOCAL_AUTH_FILE")" = 600
test "$(wc -c < "$KC_LOCAL_AUTH_FILE")" -ge 48
sed -n '1p' "$MOCK_HTPASSWD" | grep '^admin:\$apr1\$' >/dev/null
first=$(cat "$KC_LOCAL_AUTH_FILE")
output2=$(sh "$(dirname "$0")/local-auth.sh")
test "$(cat "$KC_LOCAL_AUTH_FILE")" = "$first"
case "$output$output2" in *"$first"*) echo 'Password leaked to output' >&2; exit 1 ;; esac
export LOCAL_AUTH_PASS='test-injected-pass'
sh "$(dirname "$0")/local-auth.sh" >/dev/null
test "$(cat "$KC_LOCAL_AUTH_FILE")" = test-injected-pass
if LOCAL_AUTH_PASS='weak' sh "$(dirname "$0")/local-auth.sh" >/dev/null 2>&1; then
  echo 'accepted weak operator-supplied password' >&2
  exit 1
fi
test "$(cat "$KC_LOCAL_AUTH_FILE")" = test-injected-pass
ln -s "$root/captured" "$root/symlink"
KC_LOCAL_AUTH_FILE="$root/symlink" sh "$(dirname "$0")/local-auth.sh" >/dev/null 2>&1 && exit 1
printf '%s\n' 'PASS local-auth lifecycle, file mode, no stdout secret, symlink rejection'
