#!/usr/bin/env bash
# Bootstrap SSH + Git for a fresh container.
# Safe to run repeatedly (idempotent).

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PERSIST_DIR="${PROJECT_DIR}/.ssh-persist"
KEY_NAME="id_ed25519_github"

if [ ! -f "${PERSIST_DIR}/${KEY_NAME}" ]; then
  echo "ERROR: ${PERSIST_DIR}/${KEY_NAME} not found." >&2
  echo "Generate one with:" >&2
  echo "  mkdir -p ${PERSIST_DIR} && chmod 700 ${PERSIST_DIR}" >&2
  echo "  ssh-keygen -t ed25519 -f ${PERSIST_DIR}/${KEY_NAME} -C persistent -N ''" >&2
  exit 1
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

cp -f "${PERSIST_DIR}/${KEY_NAME}"     "${HOME}/.ssh/${KEY_NAME}"
cp -f "${PERSIST_DIR}/${KEY_NAME}.pub" "${HOME}/.ssh/${KEY_NAME}.pub"
chmod 600 "${HOME}/.ssh/${KEY_NAME}"
chmod 644 "${HOME}/.ssh/${KEY_NAME}.pub"

SSH_CONFIG="${HOME}/.ssh/config"
if [ ! -f "${SSH_CONFIG}" ] || ! grep -q "Host github.com" "${SSH_CONFIG}" 2>/dev/null; then
  cat >> "${SSH_CONFIG}" <<EOF
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/${KEY_NAME}
  IdentitiesOnly yes
EOF
fi
chmod 600 "${SSH_CONFIG}"

touch "${HOME}/.ssh/known_hosts"
if ! grep -q "github.com" "${HOME}/.ssh/known_hosts" 2>/dev/null; then
  ssh-keyscan -t ed25519,rsa github.com >> "${HOME}/.ssh/known_hosts" 2>/dev/null || true
fi
chmod 644 "${HOME}/.ssh/known_hosts"

git config --global --add safe.directory "${PROJECT_DIR}" 2>/dev/null || true
git config --global init.defaultBranch master 2>/dev/null || true

echo "[bootstrap] SSH + git ready."
echo "[bootstrap] Testing GitHub authentication..."
SSH_TEST_OUTPUT="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 || true)"
if echo "${SSH_TEST_OUTPUT}" | grep -q "successfully authenticated"; then
  echo "[bootstrap] GitHub SSH OK -> ${SSH_TEST_OUTPUT}"
else
  echo "[bootstrap] GitHub SSH NOT working yet."
  echo "[bootstrap] ssh output: ${SSH_TEST_OUTPUT}"
  echo "[bootstrap] Add this public key to https://github.com/settings/keys :"
  echo ""
  cat "${HOME}/.ssh/${KEY_NAME}.pub"
  echo ""
fi
