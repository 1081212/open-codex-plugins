#!/usr/bin/env bash
set -euo pipefail

if ! command -v codex >/dev/null 2>&1; then
  printf 'Codex CLI is not installed or not on PATH.\n' >&2
  exit 2
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  printf 'Node.js and npm are required. Install Node.js 20.12 or newer first.\n' >&2
  exit 2
fi

if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=12)?0:1)'; then
  printf 'Node.js 20.12 or newer is required; found %s.\n' "$(node --version)" >&2
  exit 2
fi

printf 'Installing lark-channel-bridge and @larksuite/cli globally with npm...\n'
npm install --global lark-channel-bridge @larksuite/cli

command -v lark-channel-bridge >/dev/null
command -v lark-cli >/dev/null
printf 'Dependencies installed successfully.\n'
