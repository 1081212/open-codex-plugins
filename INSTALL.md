# Agent Installation Protocol

This document is written for a Codex agent asked to install the Lark Codex integration from this repository.

## Outcome

Complete both routes:

```text
Lark or Feishu messages -> lark-channel-bridge -> local Codex
local Codex -> @larksuite/cli -> Lark or Feishu documents
```

The account owner must scan QR codes, approve OAuth scopes, and approve restricted system changes. Do not bypass, simulate, or transfer those approvals.

## Procedure

1. If only the GitHub URL was supplied, inspect or clone the public repository into a temporary working directory so these instructions and bundled scripts are available. Do not place it inside an unrelated user repository.
2. Confirm that `codex` is installed and signed in and that Node.js is at least 20.12. If Node.js is missing or too old, identify the user's existing version manager or operating-system package manager, explain the proposed change, obtain approval, install a supported Node.js version, and rerun the check. Do not silently replace an existing Node installation or version manager.
3. Add this marketplace and install the plugin if they are not already installed:

   ```bash
   codex plugin marketplace add 1081212/open-codex-plugins --ref main
   codex plugin add lark-docs@open-codex-plugins
   ```

4. Install the external dependencies. This is a global npm change and may trigger the host's normal approval flow. Never add `sudo` automatically.

   macOS or Linux:

   ```bash
   bash plugins/lark-docs/skills/lark-codex-setup/scripts/install-dependencies.sh
   ```

   Windows PowerShell:

   ```powershell
   powershell -ExecutionPolicy Bypass -File plugins/lark-docs/skills/lark-codex-setup/scripts/install-dependencies.ps1
   ```

5. Run the platform-appropriate doctor script.

   macOS or Linux:

   ```bash
   bash plugins/lark-docs/skills/lark-docs/scripts/doctor.sh
   ```

   Windows PowerShell:

   ```powershell
   powershell -ExecutionPolicy Bypass -File plugins/lark-docs/skills/lark-docs/scripts/doctor.ps1
   ```
6. Bootstrap and register the background service:

   ```bash
   lark-channel-bridge start --profile codex --agent codex
   ```

   Keep the interactive process visible. Pause while the user scans the QR code and selects or creates their own PersonalAgent application. Never request an App Secret in chat or put one on a command line.

7. Verify the daemon:

   ```bash
   lark-channel-bridge status --profile codex
   ```

8. Authorize the profile-local user identity with the bundled `lark-cli-profile` wrapper and `auth login`. Pause for the user's device-flow or OAuth consent. Verify with `whoami` and `auth status --json --verify`; personal document access requires a user identity. Use `lark-cli-profile` on macOS or Linux and `lark-cli-profile.ps1` on Windows.
9. Ask the user to send `/config` to the bot and select the user identity policy when they want bridge-triggered Codex sessions to access personal resources. Confirm `/status` reports `lark-cli: user-ready`.
10. Keep chat access private to the PersonalAgent owner unless the user explicitly asks to invite another user or group. Do not run `/invite` commands as part of default setup. Ask the user to review the bridge's filesystem permission mode in `/config`; do not broaden it silently.
11. Run acceptance checks:
   - ask the user to send the bot a private message and confirm Codex replies;
   - fetch a document URL supplied by the user;
   - perform a write check only if the user explicitly authorizes a small reversible edit, then fetch the changed passage.
12. Report each direction separately as verified or still pending. Do not call the setup complete merely because package installation succeeded.

After plugin installation, a new Codex thread can invoke `$lark-codex-setup` directly.
