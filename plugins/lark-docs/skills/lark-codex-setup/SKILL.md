---
name: lark-codex-setup
description: Install, configure, diagnose, and verify a bidirectional Lark or Feishu connection with local Codex. Use when a user asks to install this plugin, connect Lark or Feishu to Codex, configure the bot or document access, or repair an incomplete setup.
---

# Lark Codex Setup

Complete both routes and report their status separately:

```text
Lark or Feishu messages -> lark-channel-bridge -> local Codex
local Codex -> lark-cli user identity -> Lark or Feishu documents
```

Resolve `<setup-dir>` to this Skill directory and `<docs-dir>` to the sibling `../lark-docs` Skill directory.

## Install

1. Run the platform-appropriate dependency installer from `<setup-dir>/scripts` when the user has asked to install or repair the integration. It checks Node.js and Codex before changing global npm packages. Do not add `sudo`, replace Node.js, or alter shell startup files automatically.
2. Run the platform-appropriate doctor script from `<docs-dir>/scripts`.
3. If the profile is absent or its service is not installed, run:

   ```bash
   lark-channel-bridge start --profile codex --agent codex
   ```

   Use a PTY and keep the QR code visible. Pause for the user to scan it and select or create their own PersonalAgent application. Never ask them to paste an App Secret, OAuth token, or profile archive into chat.
4. Run `lark-channel-bridge status --profile codex` and require a running service before marking the inbound route ready.

## Authorize document access

Use the platform-appropriate `lark-cli-profile` wrapper from `<docs-dir>/scripts`.

1. Run `auth status --json --verify`.
2. If user authorization is missing, run `auth login` and pause for the account owner to approve the device flow.
3. Run `whoami`; personal documents require the effective identity to be `user`.
4. Ask the user to send `/config` to the bot and select the user identity policy if bridge-triggered Codex sessions should access personal resources. Verify `/status` reports `lark-cli: user-ready`.
5. Preserve the default owner-only chat access. Do not invite users or groups, add administrators, or broaden the bridge's filesystem permission mode unless the user explicitly requests and understands that change.

## Verify both directions

- Inbound: ask the user to send the bot a private message and confirm the local Codex replies.
- Outbound read: fetch a document URL supplied by the user with `--as user`.
- Outbound write: only with explicit authorization, make a small reversible edit and fetch the changed passage afterward.

Report `verified`, `pending user action`, or `failed` for each direction. Package installation, profile creation, or OAuth alone is not end-to-end verification.

## Safety

- Credentials remain in the user's profile-local configuration.
- Do not export profiles with secrets, log out an existing identity, change access lists, or broaden filesystem permissions unless explicitly requested.
- Stop after a repeated authentication or bootstrap failure and report the exact failing step without exposing secrets.
