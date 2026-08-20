# Codex Usage Dashboard

A private, localhost-only dashboard for structured Codex token usage metadata.
It extracts `token_count` events under the current user's Codex session
directory; it does not collect, store, or expose prompts, responses, tool
inputs, or credentials.

## What it shows

- daily, weekly, and monthly token usage;
- cached input, uncached input, output, and reasoning output;
- model, project, and client-channel breakdowns;
- the current seven-day Codex quota window when the local CLI exposes it;
- estimated API-equivalent USD cost for model IDs with published prices.

The dashboard binds only to `127.0.0.1` and defaults to
<http://127.0.0.1:47831/>.

## Install through Codex

After adding this repository as a Marketplace, ask Codex:

```text
Install my Codex usage dashboard and enable daily automatic updates.
```

Codex follows the bundled Skill and runs the installer for the current
operating system. Python 3.9 or newer and the Codex CLI are required.

## Automatic updates

Automatic updates are opt-in. When enabled, a per-user background task runs
once per day and:

1. refreshes the `open-codex-plugins` Git Marketplace snapshot;
2. reinstalls `codex-usage-dashboard@open-codex-plugins`;
3. compares the installed runtime version;
4. atomically deploys and restarts the dashboard only when the version changed;
5. retains the previous runtime and rolls back if the new service fails its
   local health check.

The updater never needs administrator privileges. Configuration, logs, and the
runtime copy live outside Codex's plugin cache, so a plugin refresh does not
erase local state. Disable automatic updates at any time by asking Codex or by
rerunning the installer with `--disable-auto-update` (PowerShell:
`-DisableAutoUpdate`).

Automatic updates execute code from this public repository's `main` branch.
Enable them only if you trust the repository. Manual updates remain available.

## Manual commands

macOS and Linux:

```bash
./skills/codex-usage-dashboard/scripts/install.sh --enable-auto-update
./skills/codex-usage-dashboard/scripts/update.sh
```

Windows PowerShell:

```powershell
./skills/codex-usage-dashboard/scripts/install.ps1 -EnableAutoUpdate
./skills/codex-usage-dashboard/scripts/update.ps1
```

The POSIX installer supports macOS LaunchAgents and Linux systemd user units.
The Windows installer uses per-user Scheduled Tasks. No system-wide service or
administrator installation is required.

## Privacy and limitations

- The HTTP server refuses non-loopback bind addresses.
- The parser reads structured rollout metadata and token counters only.
- Project names come from session working-directory metadata.
- If the optional local Lark bridge exists, only its thread-to-session IDs are
  used to label matching sessions; message bodies are not collected or exposed.
- Codex's local JSONL schema and quota endpoint are implementation details and
  may change. Run the bundled tests after CLI upgrades.
- Cost figures are estimates based on published API prices, not subscription
  bills.

## Development

Run the tests from the plugin directory:

```bash
PYTHONPATH=runtime python3 -m unittest discover -s tests -v
```
