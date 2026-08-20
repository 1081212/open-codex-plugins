# Lark Docs for Codex

This plugin gives Codex a safe workflow for reading, searching, creating, and editing Lark or Feishu documents through the current user's local authorization.

## What it installs

The plugin installs instructions and portable helper scripts. It does not install system packages, create a Lark application, or store credentials automatically.

## Prerequisites

- Node.js 20.12 or newer
- Codex CLI, already signed in
- [`lark-channel-bridge`](https://github.com/zarazhangrui/feishu-claude-code-bridge)
- [`@larksuite/cli`](https://github.com/larksuite/cli)

Install the external CLIs:

```bash
npm install --global lark-channel-bridge @larksuite/cli
```

Initialize a local profile:

```bash
lark-channel-bridge run --profile codex --agent codex
```

Scan the QR code with your own Lark or Feishu account and select or create your own PersonalAgent application. Personal document access is authorized separately by the user when requested.

## Privacy and security

- Credentials remain in the user's local `~/.lark-channel` profile.
- Never copy profiles between users or commit them to a repository.
- The plugin fetches content before edits and verifies writes afterward.
- Destructive document operations require explicit confirmation.

## Attribution

This plugin integrates with the independently maintained MIT-licensed `lark-channel-bridge` and `@larksuite/cli` projects. They are dependencies, not bundled source code, and their authors do not endorse this plugin.
