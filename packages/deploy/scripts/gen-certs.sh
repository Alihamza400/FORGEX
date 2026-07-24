#!/usr/bin/env bash
# forge-gen-certs — generate self-signed TLS certificates for development
set -euo pipefail

OUT_DIR="${1:-./certs}"
DAYS="${CERT_VALIDITY_DAYS:-365}"
KEY_SIZE="${CERT_KEY_SIZE:-4096}"
ORG="${CERT_ORG:-Forge}"

mkdir -p "${OUT_DIR}"

log() { echo "[$(date +%H:%M:%S)] $*"; }

log "Generating CA key and certificate"
openssl genrsa -out "${OUT_DIR}/ca.key" "${KEY_SIZE}"
openssl req -x509 -new -nodes -key "${OUT_DIR}/ca.key" \
    -sha256 -days "${DAYS}" \
    -subj "/C=XX/ST=State/L=City/O=${ORG}/CN=Forge Root CA" \
    -out "${OUT_DIR}/ca.crt"

log "Generating server key"
openssl genrsa -out "${OUT_DIR}/server.key" "${KEY_SIZE}"

log "Generating server CSR"
openssl req -new -key "${OUT_DIR}/server.key" \
    -subj "/C=XX/ST=State/L=City/O=${ORG}/CN=forge.local" \
    -addext "subjectAltName = DNS:forge.local,DNS:localhost,DNS:forge-api,DNS:*.forge.svc.cluster.local,IP:127.0.0.1" \
    -out "${OUT_DIR}/server.csr"

log "Signing server certificate with CA"
openssl x509 -req -in "${OUT_DIR}/server.csr" \
    -CA "${OUT_DIR}/ca.crt" -CAkey "${OUT_DIR}/ca.key" -CAcreateserial \
    -out "${OUT_DIR}/server.crt" -days "${DAYS}" -sha256 \
    -extfile <(cat <<EOF
subjectAltName = DNS:forge.local,DNS:localhost,DNS:forge-api,DNS:*.forge.svc.cluster.local,IP:127.0.0.1
EOF
)

log "Setting permissions"
chmod 600 "${OUT_DIR}/ca.key" "${OUT_DIR}/server.key"
chmod 644 "${OUT_DIR}/ca.crt" "${OUT_DIR}/server.crt"

log "Cleaning up CSR"
rm -f "${OUT_DIR}/server.csr" "${OUT_DIR}/ca.srl"

echo ""
echo "Generated certificates in ${OUT_DIR}:"
ls -la "${OUT_DIR}/"
echo ""
echo "CA certificate:      ${OUT_DIR}/ca.crt"
echo "Server certificate:  ${OUT_DIR}/server.crt"
echo "Server key:          ${OUT_DIR}/server.key"
echo ""
echo "To use with Docker:"
echo "  docker run -v \$(pwd)/certs:/certs ..."
echo ""
echo "To use with Kubernetes:"
echo "  kubectl create secret tls forge-tls --cert=${OUT_DIR}/server.crt --key=${OUT_DIR}/server.key -n forge"
echo "  kubectl create secret generic forge-ca --from-file=ca.crt=${OUT_DIR}/ca.crt -n forge"
