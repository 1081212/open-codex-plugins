---
name: codex-usage-dashboard
description: Install, update, open, diagnose, or configure the local Codex token usage dashboard. Use when the user asks for a Codex usage or token dashboard, wants automatic dashboard updates, or needs dashboard service troubleshooting.
---

# Codex Usage Dashboard

Operate the bundled local-only usage dashboard. The runtime extracts structured
`token_count` metadata from the current user's Codex sessions and does not
collect, store, or expose conversation content.

## Requirements

- Python 3.9 or newer
- Codex CLI available on `PATH`
- macOS, Linux with a systemd user session, or Windows PowerShell

## Install

1. Explain that the dashboard binds only to `127.0.0.1`, reads local structured
   token metadata, and installs a per-user background service.
2. Automatic updates execute future code from the configured public Git
   Marketplace. Enable them only when the user explicitly requests or approves
   automatic updates.
3. On macOS or Linux, run:

   ```bash
   bash scripts/install.sh --enable-auto-update
   ```

   Omit `--enable-auto-update` when it was not approved. To explicitly disable
   an existing updater, use `--disable-auto-update`.

4. On Windows PowerShell, run:

   ```powershell
   ./scripts/install.ps1 -EnableAutoUpdate
   ```

   Omit `-EnableAutoUpdate` when it was not approved. Use
   `-DisableAutoUpdate` to remove an existing update task.
5. Verify `http://127.0.0.1:47831/healthz`, then give the user the dashboard URL.

The installer uses only per-user directories and must not be run with `sudo` or
as Administrator. It preserves the previous runtime and rolls back when the new
service fails its health check.

## Update

For a manual update, run the platform update script:

```bash
bash scripts/update.sh
```

```powershell
./scripts/update.ps1
```

The updater refreshes the `open-codex-plugins` Marketplace, reinstalls this
plugin, resolves the new plugin source from `codex plugin list --json`, and
deploys the runtime only if its version changed. Use `--force` or `-Force` only
when repairing the same version.

After a plugin update, tell the user to start a new Codex thread before relying
on newly added Skill instructions. The dashboard runtime itself is restarted by
the installer and does not require a new thread.

## Diagnose

- Health: `curl -fsS http://127.0.0.1:47831/healthz`
- macOS service: `launchctl print gui/$(id -u)/dev.opencodex.usage-dashboard`
- Linux service: `systemctl --user status codex-usage-dashboard.service`
- Windows service task: `Get-ScheduledTask -TaskName CodexUsageDashboard`
- Logs are under the install root's `logs` directory.

If port `47831` is occupied, rerun the installer with `--port <port>` or
`-Port <port>`. Do not expose the dashboard on a LAN address.

## Data and safety

- Never upload or copy a user's session logs.
- Never display prompt, response, tool-input, credential, or message content.
- Do not enable automatic updates without explicit user approval.
- Do not modify the user's Codex sessions.
- Treat API-equivalent costs as estimates, not billing records.
