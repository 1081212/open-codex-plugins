#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${CODEX_USAGE_DASHBOARD_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/codex-usage-dashboard}"
FORCE=0
AUTOMATIC=0
NO_SERVICE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --force) FORCE=1 ;;
    --automatic) AUTOMATIC=1 ;;
    --no-service) NO_SERVICE=1 ;;
    --install-root) shift; INSTALL_ROOT="${1:-}" ;;
    -h|--help) printf '%s\n' 'Usage: update.sh [--force] [--automatic] [--install-root PATH] [--no-service]'; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [ -n "${CODEX_USAGE_PYTHON:-}" ] && [ -x "$CODEX_USAGE_PYTHON" ]; then
  PYTHON="$CODEX_USAGE_PYTHON"
else
  command -v python3 >/dev/null 2>&1 || { printf 'Python 3 is required.\n' >&2; exit 1; }
  PYTHON="$(command -v python3)"
fi
INSTALL_ROOT="$($PYTHON -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$INSTALL_ROOT")"
SETTINGS="$INSTALL_ROOT/settings.json"
[ -f "$SETTINGS" ] || { printf 'Dashboard is not installed. Run install.sh first.\n' >&2; exit 1; }
MARKETPLACE="$($PYTHON - "$SETTINGS" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text()).get("marketplace", "open-codex-plugins"))
PY
)"
CODEX_CLI="$($PYTHON - "$SETTINGS" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text()).get("codex_cli", ""))
PY
)"
if [ ! -x "$CODEX_CLI" ]; then CODEX_CLI="$(command -v codex 2>/dev/null || true)"; fi
if [ -z "$CODEX_CLI" ]; then
  CODEX_CLI="$($PYTHON - <<'PY'
from pathlib import Path
candidates = list((Path.home() / ".nvm/versions/node").glob("*/bin/codex"))
candidates += [Path.home() / ".local/bin/codex", Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")]
existing = [path for path in candidates if path.is_file()]
if existing:
    print(max(existing, key=lambda path: path.stat().st_mtime))
PY
)"
fi
[ -n "$CODEX_CLI" ] || { printf 'Codex CLI is required.\n' >&2; exit 1; }

LOCK_DIR="$INSTALL_ROOT/.update-lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  LOCK_PID="$(sed -n '1p' "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    if [ "$AUTOMATIC" -eq 1 ]; then exit 0; fi
    printf 'Another dashboard update is already running.\n' >&2
    exit 1
  fi
  rm -rf -- "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi
printf '%s\n' "$$" > "$LOCK_DIR/pid"
TMP_JSON="$(mktemp "${TMPDIR:-/tmp}/codex-usage-dashboard.XXXXXX")"
cleanup() { rm -f -- "$TMP_JSON" "$LOCK_DIR/pid"; rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

"$CODEX_CLI" plugin marketplace upgrade "$MARKETPLACE"
"$CODEX_CLI" plugin add "codex-usage-dashboard@$MARKETPLACE"
"$CODEX_CLI" plugin list --json > "$TMP_JSON"
PLUGIN_ROOT="$($PYTHON - "$TMP_JSON" "$MARKETPLACE" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
plugin_id = "codex-usage-dashboard@" + sys.argv[2]
for item in data.get("installed", []):
    if item.get("pluginId") == plugin_id:
        print(item.get("source", {}).get("path", ""))
        break
PY
)"
[ -n "$PLUGIN_ROOT" ] && [ -d "$PLUGIN_ROOT" ] || { printf 'Could not resolve the refreshed plugin source.\n' >&2; exit 1; }
INSTALLER="$PLUGIN_ROOT/skills/codex-usage-dashboard/scripts/install.sh"
[ -f "$INSTALLER" ] || { printf 'Refreshed plugin does not contain install.sh.\n' >&2; exit 1; }
NEW_VERSION="$($PYTHON - "$PLUGIN_ROOT/.codex-plugin/plugin.json" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())["version"])
PY
)"
CURRENT_VERSION=""
[ ! -f "$INSTALL_ROOT/app/VERSION" ] || CURRENT_VERSION="$(sed -n '1p' "$INSTALL_ROOT/app/VERSION")"
if [ "$FORCE" -eq 0 ] && [ "$NEW_VERSION" = "$CURRENT_VERSION" ]; then
  printf 'Codex Usage Dashboard is already up to date (%s).\n' "$CURRENT_VERSION"
  exit 0
fi

AUTO_FLAG="--disable-auto-update"
[ ! -f "$INSTALL_ROOT/auto-update-enabled" ] || AUTO_FLAG="--enable-auto-update"
INSTALL_ARGS=("$AUTO_FLAG" --install-root "$INSTALL_ROOT" --marketplace "$MARKETPLACE")
if [ "$NO_SERVICE" -eq 1 ]; then INSTALL_ARGS+=(--no-service); fi
bash "$INSTALLER" "${INSTALL_ARGS[@]}"
