# Lark Codex

This plugin configures a bidirectional connection between Lark or Feishu and a local Codex installation.

```text
Lark or Feishu messages -> lark-channel-bridge -> local Codex
local Codex -> @larksuite/cli -> Lark or Feishu documents
```

## What it installs

The plugin installs setup and document-operation skills with portable helper scripts. When explicitly asked to install the integration, Codex can install the external CLI packages, start the profile bootstrap, register the background service, and run local checks.

The user must personally scan the Lark or Feishu QR code and approve OAuth scopes. The plugin never automates consent, copies another profile, or stores credentials in the repository.

## Prerequisites

- Node.js 20.12 or newer
- Codex CLI, already signed in
- [`lark-channel-bridge`](https://github.com/zarazhangrui/feishu-claude-code-bridge)
- [`@larksuite/cli`](https://github.com/larksuite/cli)

For an agent-guided installation, invoke the `lark-codex-setup` skill or give Codex this repository URL and ask it to follow the root `INSTALL.md`.

After the plugin is installed, start a new Codex thread and ask:

```text
$lark-codex-setup install and verify both directions
```

Manual dependency installation:

```bash
npm install --global lark-channel-bridge @larksuite/cli
```

Initialize and register a background profile:

```bash
lark-channel-bridge start --profile codex --agent codex
```

Scan the QR code with your own Lark or Feishu account and select or create your own PersonalAgent application. Then authorize the profile-local user identity when Codex requests it.

Check the service:

```bash
lark-channel-bridge status --profile codex
```

Inside Lark or Feishu, send `/status`. For document access from bridge-triggered Codex sessions, complete user authorization and select the user identity policy in `/config`; `/status` should report `lark-cli: user-ready`.

## Acceptance checks

1. Send a private message to the bot and confirm the local Codex replies.
2. Ask Codex to fetch a document URL that your user account can access.
3. For a write test, explicitly authorize a small reversible change and confirm Codex fetches the changed passage afterward.

## Privacy and security

- Credentials remain in the user's local `~/.lark-channel` profile.
- Chat access is private to the PersonalAgent owner by default; do not invite users or groups unless intentionally sharing access to the local Codex.
- Never copy profiles between users or commit them to a repository.
- Review the bridge's filesystem permission mode before using it with sensitive local workspaces.
- The plugin fetches content before edits and verifies writes afterward.
- Destructive document operations require explicit confirmation.

## Attribution

This plugin integrates with the independently maintained MIT-licensed `lark-channel-bridge` and `@larksuite/cli` projects. They are dependencies, not bundled source code, and their authors do not endorse this plugin.
