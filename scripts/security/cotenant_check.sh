#!/usr/bin/env bash
# Co-tenant isolation verifier — RUN ON THE DROPLET (needs local sudo, e.g. bob).
#
# The GitHub-runner probe (probe.py) can only reach prod over HTTP, so it can NOT
# assert on-box, filesystem/loopback isolation of the `shos` co-tenant. This is
# the manual/periodic on-box counterpart (docs/security.md §6.2 exception, boot
# 5.8 Step 6). Asserts the DESIRED secure end-state, so it is RED until the
# pre-existing blockers (S-18/S-19/S-20) are fixed and GREEN afterwards.
#
#   ssh tetapi 'sudo bash -s' < scripts/security/cotenant_check.sh
#
# Exit 1 if any assertion fails. Read-only / non-destructive (redis: PING only).
set -u
U=shos
fail=0
ok(){ echo "  PASS: $1"; }
bad(){ echo "  FAIL: $1"; fail=1; }

echo "== shos identity =="
id "$U" || { echo "no such user $U"; exit 2; }

echo "== must be DENIED =="
# S-18: cannot read TETA+PI secrets
if sudo -u "$U" -H test -r /opt/tetapi/api/.env; then
  bad "shos can READ /opt/tetapi/api/.env (S-18 — must be chmod 600 root:root)"
else
  ok "shos cannot read /opt/tetapi/api/.env"
fi
# docker socket (must not be in docker group)
if sudo -u "$U" -H docker ps >/dev/null 2>&1; then
  bad "shos can use the host docker socket (must NOT be in docker group)"
else
  ok "shos cannot use host docker socket"
fi
# sudo
if sudo -u "$U" -H sudo -n true >/dev/null 2>&1; then
  bad "shos has passwordless sudo (must have none)"
else
  ok "shos has no sudo"
fi
# control a tetapi unit
if sudo -u "$U" -H systemctl restart tetapi-api >/dev/null 2>&1; then
  bad "shos can restart tetapi-api (must be denied)"
else
  ok "shos cannot control tetapi units"
fi
# write TETA+PI web root
if sudo -u "$U" -H bash -c 'touch /var/www/teta-pi/.shos_probe' >/dev/null 2>&1; then
  sudo rm -f /var/www/teta-pi/.shos_probe
  bad "shos can WRITE the TETA+PI web root"
else
  ok "shos cannot write TETA+PI web root"
fi
# S-20: redis must not answer unauthenticated
resp=$(sudo -u "$U" -H python3 - <<'PY' 2>/dev/null
import socket
try:
    s=socket.create_connection(("127.0.0.1",6379),2); s.sendall(b"PING\r\n")
    print(s.recv(64))
except Exception as e:
    print(b"")
PY
)
if [[ "$resp" == *PONG* ]]; then
  bad "redis 6379 answers PING with NO auth (S-20 — set requirepass or drop the loopback publish)"
else
  ok "redis rejects unauthenticated access"
fi

echo "== ownership (S-19) =="
own=$(stat -c '%U:%G' /opt/tetapi/api)
if [[ "$own" == "root:root" ]]; then
  ok "/opt/tetapi/api owned by root:root"
else
  bad "/opt/tetapi/api owned by $own (S-19 — a co-tenant must not own TETA+PI's tree; chown -R root:root)"
fi

echo "== port range (informational) =="
echo "  shos must listen only on 127.0.0.1:8200–8299. Current shos-owned listeners:"
sudo ss -tlnp 2>/dev/null | grep -F 'uid:1002' || echo "  (none yet)"

echo "== NOTE: OOM/cgroup limit is NOT tested here =="
echo "  A 'sudo -u shos' process runs under the caller's slice, not user-1002.slice."
echo "  Run the memory stress test from a REAL shos session (SSH with the shos key):"
echo "    python3 -c 'bytearray(650*1024*1024)'   # expect: Killed (MemoryMax=512M), tetapi-api stays up"

[[ $fail -eq 0 ]] && { echo "ALL ISOLATION ASSERTS PASS"; exit 0; } || { echo "ISOLATION ASSERTS FAILED"; exit 1; }
