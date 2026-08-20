#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PLUGIN_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../../.." && pwd)"
RUNTIME_SOURCE="$PLUGIN_ROOT/runtime"
INSTALL_ROOT="${CODEX_USAGE_DASHBOARD_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/codex-usage-dashboard}"
PORT=""
TIMEZONE_NAME=""
MARKETPLACE=""
AUTO_UPDATE="preserve"
NO_SERVICE=0

usage() {
  printf '%s\n' "Usage: install.sh [--enable-auto-update|--disable-auto-update] [--port PORT] [--timezone ZONE] [--marketplace NAME] [--install-root PATH] [--no-service]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --enable-auto-update) AUTO_UPDATE="enabled" ;;
    --disable-auto-update) AUTO_UPDATE="disabled" ;;
    --port) shift; PORT="${1:-}" ;;
    --timezone) shift; TIMEZONE_NAME="${1:-}" ;;
    --marketplace) shift; MARKETPLACE="${1:-}" ;;
    --install-root) shift; INSTALL_ROOT="${1:-}" ;;
    --no-service) NO_SERVICE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

command -v python3 >/dev/null 2>&1 || { printf 'Python 3.9 or newer is required.\n' >&2; exit 1; }
PYTHON="$(command -v python3)"
"$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))' || {
  printf 'Python 3.9 or newer is required.\n' >&2
  exit 1
}
[ -f "$RUNTIME_SOURCE/codex_usage_dashboard.py" ] || { printf 'Plugin runtime is incomplete.\n' >&2; exit 1; }

find_codex() {
  if [ -n "${CODEX_CLI_PATH:-}" ] && [ -x "$CODEX_CLI_PATH" ]; then printf '%s\n' "$CODEX_CLI_PATH"; return; fi
  if command -v codex >/dev/null 2>&1; then command -v codex; return; fi
  "$PYTHON" - <<'PY'
from pathlib import Path
candidates = list((Path.home() / ".nvm/versions/node").glob("*/bin/codex"))
candidates += [Path.home() / ".local/bin/codex", Path("/opt/homebrew/bin/codex"), Path("/usr/local/bin/codex")]
existing = [path for path in candidates if path.is_file()]
if existing:
    print(max(existing, key=lambda path: path.stat().st_mtime))
PY
}
CODEX_CLI="$(find_codex)"
[ -n "$CODEX_CLI" ] || { printf 'Codex CLI is required.\n' >&2; exit 1; }

INSTALL_ROOT="$($PYTHON -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$INSTALL_ROOT")"
if [ "$INSTALL_ROOT" = "/" ] || [ "$INSTALL_ROOT" = "$HOME" ] || [ -z "$INSTALL_ROOT" ]; then
  printf 'Refusing unsafe install root: %s\n' "$INSTALL_ROOT" >&2
  exit 1
fi

SETTINGS="$INSTALL_ROOT/settings.json"
read_setting() {
  "$PYTHON" - "$SETTINGS" "$1" "$2" <<'PY'
import json, pathlib, sys
path, key, fallback = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
try:
    value = json.loads(path.read_text()).get(key, fallback)
except (OSError, ValueError, TypeError):
    value = fallback
print(value)
PY
}

if [ -z "$PORT" ]; then PORT="$(read_setting port 47831)"; fi
case "$PORT" in ''|*[!0-9]*) printf 'Port must be numeric.\n' >&2; exit 2 ;; esac
if [ "$PORT" -lt 1024 ] || [ "$PORT" -gt 65535 ]; then printf 'Port must be between 1024 and 65535.\n' >&2; exit 2; fi

if [ -z "$TIMEZONE_NAME" ]; then
  TIMEZONE_NAME="$(read_setting timezone '')"
fi
if [ -z "$TIMEZONE_NAME" ] && [ -n "${TZ:-}" ]; then TIMEZONE_NAME="$TZ"; fi
if [ -z "$TIMEZONE_NAME" ] && [ -L /etc/localtime ]; then
  TIMEZONE_NAME="$(readlink /etc/localtime | sed 's#^.*zoneinfo/##')"
fi
if [ -z "$TIMEZONE_NAME" ]; then TIMEZONE_NAME="UTC"; fi
"$PYTHON" -c 'from zoneinfo import ZoneInfo; import sys; ZoneInfo(sys.argv[1])' "$TIMEZONE_NAME" || {
  printf 'Unknown timezone: %s\n' "$TIMEZONE_NAME" >&2
  exit 2
}

if [ -z "$MARKETPLACE" ]; then MARKETPLACE="$(read_setting marketplace open-codex-plugins)"; fi
case "$MARKETPLACE" in ''|*[!A-Za-z0-9._-]*) printf 'Invalid marketplace name.\n' >&2; exit 2 ;; esac

mkdir -p "$INSTALL_ROOT" "$INSTALL_ROOT/logs"
LOCK_DIR="$INSTALL_ROOT/.install-lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  LOCK_PID="$(sed -n '1p' "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    printf 'Another dashboard install or update is already running.\n' >&2
    exit 1
  fi
  rm -rf -- "$LOCK_DIR"
  mkdir "$LOCK_DIR"
fi
printf '%s\n' "$$" > "$LOCK_DIR/pid"
STAGE=""
cleanup() {
  [ -z "$STAGE" ] || rm -rf -- "$STAGE"
  rm -f -- "$LOCK_DIR/pid"
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

VERSION="$($PYTHON - "$PLUGIN_ROOT/.codex-plugin/plugin.json" <<'PY'
import json, pathlib, sys
print(json.loads(pathlib.Path(sys.argv[1]).read_text())["version"])
PY
)"
STAGE="$(mktemp -d "$INSTALL_ROOT/.stage.XXXXXX")"
cp "$RUNTIME_SOURCE/codex_usage_dashboard.py" "$STAGE/codex_usage_dashboard.py"
cp "$RUNTIME_SOURCE/index.html" "$STAGE/index.html"
printf '%s\n' "$VERSION" > "$STAGE/VERSION"
"$PYTHON" -m py_compile "$STAGE/codex_usage_dashboard.py"

rm -rf -- "$INSTALL_ROOT/previous"
if [ -d "$INSTALL_ROOT/app" ]; then mv "$INSTALL_ROOT/app" "$INSTALL_ROOT/previous"; fi
mv "$STAGE" "$INSTALL_ROOT/app"
STAGE=""
cp "$SCRIPT_DIR/update.sh" "$INSTALL_ROOT/update.sh"
chmod 700 "$INSTALL_ROOT/update.sh"

CODEX_HOME_PATH="${CODEX_HOME:-$HOME/.codex}"
"$PYTHON" - "$SETTINGS" "$PORT" "$TIMEZONE_NAME" "$MARKETPLACE" "$CODEX_HOME_PATH" "$CODEX_CLI" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({
    "port": int(sys.argv[2]),
    "timezone": sys.argv[3],
    "marketplace": sys.argv[4],
    "codex_home": sys.argv[5],
    "codex_cli": sys.argv[6],
    "python": sys.executable,
}, indent=2) + "\n")
PY

MARKER="$INSTALL_ROOT/auto-update-enabled"
if [ "$AUTO_UPDATE" = "enabled" ]; then
  : > "$MARKER"
elif [ "$AUTO_UPDATE" = "disabled" ]; then
  rm -f -- "$MARKER"
fi

restart_service() {
  OS_NAME="$(uname -s)"
  if [ "$OS_NAME" = "Darwin" ]; then
    AGENTS_DIR="$HOME/Library/LaunchAgents"
    DASHBOARD_PLIST="$AGENTS_DIR/dev.opencodex.usage-dashboard.plist"
    UPDATE_PLIST="$AGENTS_DIR/dev.opencodex.usage-dashboard.update.plist"
    mkdir -p "$AGENTS_DIR"
    "$PYTHON" - "$DASHBOARD_PLIST" "$UPDATE_PLIST" "$PYTHON" "$CODEX_CLI" "$INSTALL_ROOT" "$PORT" "$TIMEZONE_NAME" "$CODEX_HOME_PATH" <<'PY'
import pathlib, plistlib, sys
dashboard, updater, python, codex_cli, root, port, timezone, codex_home = sys.argv[1:]
logs = pathlib.Path(root) / "logs"
dashboard_data = {
    "Label": "dev.opencodex.usage-dashboard",
    "ProgramArguments": [python, str(pathlib.Path(root) / "app/codex_usage_dashboard.py"), "--host", "127.0.0.1", "--port", port, "--timezone", timezone, "--refresh-seconds", "300"],
    "EnvironmentVariables": {"CODEX_HOME": codex_home, "CODEX_CLI_PATH": codex_cli},
    "RunAtLoad": True,
    "KeepAlive": True,
    "ProcessType": "Background",
    "ThrottleInterval": 10,
    "StandardOutPath": str(logs / "dashboard.log"),
    "StandardErrorPath": str(logs / "dashboard.error.log"),
}
update_data = {
    "Label": "dev.opencodex.usage-dashboard.update",
    "ProgramArguments": [str(pathlib.Path(root) / "update.sh"), "--automatic"],
    "StartInterval": 86400,
    "ProcessType": "Background",
    "EnvironmentVariables": {
        "CODEX_CLI_PATH": codex_cli,
        "CODEX_USAGE_PYTHON": python,
        "PATH": ":".join(dict.fromkeys([str(pathlib.Path(python).parent), str(pathlib.Path(codex_cli).parent), "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"])),
    },
    "StandardOutPath": str(logs / "update.log"),
    "StandardErrorPath": str(logs / "update.error.log"),
}
for path, data in ((dashboard, dashboard_data), (updater, update_data)):
    with open(path, "wb") as stream:
        plistlib.dump(data, stream)
PY
    DOMAIN="gui/$(id -u)"
    launchctl bootout "$DOMAIN/dev.opencodex.usage-dashboard" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$DASHBOARD_PLIST"
    if [ -f "$MARKER" ]; then
      launchctl bootout "$DOMAIN/dev.opencodex.usage-dashboard.update" 2>/dev/null || true
      launchctl bootstrap "$DOMAIN" "$UPDATE_PLIST"
    else
      launchctl bootout "$DOMAIN/dev.opencodex.usage-dashboard.update" 2>/dev/null || true
      rm -f -- "$UPDATE_PLIST"
    fi
  elif [ "$OS_NAME" = "Linux" ]; then
    command -v systemctl >/dev/null 2>&1 || { printf 'systemctl is required for the Linux user service.\n' >&2; return 1; }
    UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
    mkdir -p "$UNIT_DIR"
    "$PYTHON" - "$UNIT_DIR" "$PYTHON" "$CODEX_CLI" "$INSTALL_ROOT" "$PORT" "$TIMEZONE_NAME" "$CODEX_HOME_PATH" <<'PY'
import pathlib, sys
unit_dir, python, codex_cli, root, port, timezone, codex_home = sys.argv[1:]
unit_dir = pathlib.Path(unit_dir)
def q(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
(unit_dir / "codex-usage-dashboard.service").write_text(f"""[Unit]
Description=Codex Usage Dashboard
After=default.target

[Service]
Type=simple
Environment={q('CODEX_HOME=' + codex_home)}
Environment={q('CODEX_CLI_PATH=' + codex_cli)}
ExecStart={q(python)} {q(str(pathlib.Path(root) / 'app/codex_usage_dashboard.py'))} --host 127.0.0.1 --port {port} --timezone {q(timezone)} --refresh-seconds 300
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
""")
(unit_dir / "codex-usage-dashboard-update.service").write_text(f"""[Unit]
Description=Update Codex Usage Dashboard

[Service]
Type=oneshot
Environment={q('CODEX_CLI_PATH=' + codex_cli)}
Environment={q('CODEX_USAGE_PYTHON=' + python)}
ExecStart={q(str(pathlib.Path(root) / 'update.sh'))} --automatic
""")
(unit_dir / "codex-usage-dashboard-update.timer").write_text("""[Unit]
Description=Daily Codex Usage Dashboard update

[Timer]
OnBootSec=10min
OnUnitActiveSec=24h
Persistent=true

[Install]
WantedBy=timers.target
""")
PY
    systemctl --user daemon-reload
    systemctl --user enable --now codex-usage-dashboard.service
    systemctl --user restart codex-usage-dashboard.service
    if [ -f "$MARKER" ]; then
      systemctl --user enable --now codex-usage-dashboard-update.timer
    else
      systemctl --user disable --now codex-usage-dashboard-update.timer 2>/dev/null || true
    fi
  else
    printf 'Unsupported service platform: %s\n' "$OS_NAME" >&2
    return 1
  fi
}

health_check() {
  "$PYTHON" - "$PORT" <<'PY'
import json, sys, time, urllib.request
url = f"http://127.0.0.1:{sys.argv[1]}/healthz"
for _ in range(20):
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status == 200:
                json.load(response)
                raise SystemExit(0)
    except Exception:
        time.sleep(0.5)
raise SystemExit(1)
PY
}

if [ "$NO_SERVICE" -eq 0 ]; then
  if ! restart_service || ! health_check; then
    printf 'New dashboard failed its health check; restoring the previous runtime.\n' >&2
    if [ -d "$INSTALL_ROOT/previous" ]; then
      rm -rf -- "$INSTALL_ROOT/app"
      mv "$INSTALL_ROOT/previous" "$INSTALL_ROOT/app"
      restart_service || true
    fi
    exit 1
  fi
fi

printf 'Codex Usage Dashboard %s installed.\n' "$VERSION"
printf 'Dashboard: http://127.0.0.1:%s/\n' "$PORT"
if [ -f "$MARKER" ]; then
  printf 'Automatic updates: enabled (daily)\n'
else
  printf 'Automatic updates: disabled\n'
fi
