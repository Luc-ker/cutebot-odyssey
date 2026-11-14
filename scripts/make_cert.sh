#!/usr/bin/env bash
# T100 — make an HTTPS certificate for the laptop so the phone's camera page works.
#
#   bash scripts/make_cert.sh                 # auto-detect the laptop's LAN IP
#   bash scripts/make_cert.sh 192.168.137.1   # or name the IP(s)/hostnames yourself
#   bash scripts/make_cert.sh --serve         # also serve rootCA.pem on :8000 so the phone can download it
#
# Uses mkcert (https://github.com/FiloSottile/mkcert). It creates a local certificate authority (CA), trusts
# it on this laptop, and issues a certificate for the laptop's IP plus localhost/127.0.0.1. The files go to
# ~/.genrator/certs (outside the repo, so the private key can never be committed). The phone must trust the
# CA once: see docs/network.md, "Trust the certificate on the phone".
set -euo pipefail

OUT="${GENRATOR_CERT_DIR:-$HOME/.genrator/certs}"
SERVE=0
NAMES=()
for arg in "$@"; do
  case "$arg" in
    --serve) SERVE=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) NAMES+=("$arg") ;;
  esac
done

if ! command -v mkcert >/dev/null 2>&1; then
  cat >&2 <<'EOF'
mkcert is not installed. Install it, then run this script again:
  Windows:  winget install FiloSottile.mkcert      (or: choco install mkcert / scoop install mkcert)
  macOS:    brew install mkcert
  Linux:    sudo apt install mkcert libnss3-tools
EOF
  exit 1
fi

PY="$(command -v python3 || command -v python || true)"
detect_ip() {
  if [ -n "$PY" ]; then
    "$PY" - <<'EOF'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("10.255.255.255", 1)); print(s.getsockname()[0])
except OSError:
    print("")
finally:
    s.close()
EOF
  fi
}

if [ ${#NAMES[@]} -eq 0 ]; then
  IP="$(detect_ip)"
  if [ -z "$IP" ] || [ "$IP" = "127.0.0.1" ]; then
    echo "Could not detect the LAN IP. Connect to the demo network first, or pass the IP: bash scripts/make_cert.sh 192.168.137.1" >&2
    exit 1
  fi
  NAMES=("$IP")
  # The Windows mobile hotspot always gives the laptop this address; include it so the cert survives a switch.
  [ "$IP" != "192.168.137.1" ] && NAMES+=("192.168.137.1")
fi
HOST="$(hostname 2>/dev/null || true)"
[ -n "$HOST" ] && NAMES+=("$HOST" "$HOST.local")
NAMES+=("localhost" "127.0.0.1")

mkdir -p "$OUT"
echo "Installing the local CA on this laptop (may ask for your password / a confirmation dialog)..."
mkcert -install
mkcert -cert-file "$OUT/genrator.pem" -key-file "$OUT/genrator-key.pem" "${NAMES[@]}"
CAROOT="$(mkcert -CAROOT)"
cp "$CAROOT/rootCA.pem" "$OUT/rootCA.pem"
# Android wants a .crt extension to offer "CA certificate"; iOS is happy with either.
cp "$CAROOT/rootCA.pem" "$OUT/genrator-rootCA.crt"

cat <<EOF

Certificate for: ${NAMES[*]}
  cert: $OUT/genrator.pem
  key:  $OUT/genrator-key.pem
  CA:   $OUT/genrator-rootCA.crt   (install this on the phone; it is public, never share rootCA-key.pem)

Tell Genrator to use it (in the same terminal you start the launcher from):
  bash / Git Bash:  export GENRATOR_TLS_CERT="$OUT/genrator.pem" GENRATOR_TLS_KEY="$OUT/genrator-key.pem"
  PowerShell:       \$env:GENRATOR_TLS_CERT="$OUT/genrator.pem"; \$env:GENRATOR_TLS_KEY="$OUT/genrator-key.pem"

Then: python scripts/launch.py   (pages are now https://, the hub wss://)
EOF

if [ "$SERVE" -eq 1 ]; then
  [ -z "$PY" ] && { echo "python not found; cannot serve" >&2; exit 1; }
  SERVE_DIR="$(mktemp -d)"
  cp "$OUT/genrator-rootCA.crt" "$SERVE_DIR/"
  echo
  echo "On the phone, open:  http://${NAMES[0]}:8000/genrator-rootCA.crt   (Ctrl-C here when done)"
  "$PY" -m http.server 8000 --directory "$SERVE_DIR"
fi
