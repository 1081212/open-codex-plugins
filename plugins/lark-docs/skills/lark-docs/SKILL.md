---
name: lark-docs
description: Read, search, create, and edit Lark or Feishu cloud documents through the current user's locally authorized profile. Use for Lark, Feishu, larksuite.com, or feishu.cn document and wiki requests. Do not use for general chat-bot operation that does not involve cloud documents.
---

# Lark Documents

Use the bundled wrapper so every command uses a profile-local configuration and never a maintainer's credentials. In the commands below, resolve `<skill-dir>` to the installed directory that contains this `SKILL.md` file.

## Setup and identity

1. Run `bash <skill-dir>/scripts/doctor.sh` before the first document operation on a machine.
2. If a dependency is missing, explain what is missing and ask before installing global packages or changing local configuration.
3. Initialize a local profile only with the user's approval. The supported bootstrap is `lark-channel-bridge run --profile codex --agent codex`; the user must scan the QR code and select or create their own PersonalAgent application.
4. Never copy, print, commit, or transfer app secrets, OAuth tokens, encrypted profiles, or another user's `~/.lark-channel` directory.
5. Verify the effective identity with `scripts/lark-cli-profile whoami`. Personal documents require a user identity. If authorization is incomplete, let the CLI present its normal authorization flow to the current user.

## Document workflow

Before choosing document flags, read the version-matched guide:

```bash
bash <skill-dir>/scripts/lark-cli-profile skills read lark-doc
```

Follow every additional reference that guide marks as required for the intended operation.

- Use `--as user` for the user's personal documents.
- Fetch relevant content before an edit and preserve unrelated blocks and embedded resources.
- Make the smallest targeted change.
- Ask immediately before deleting documents, blocks, comments, permissions, or other remote data, and before commands classified as high-risk writes.
- Verify successful writes by fetching the changed passage afterward.
- Return the document URL and a concise summary of verified changes.

Example fetch:

```bash
bash <skill-dir>/scripts/lark-cli-profile docs +fetch --as user --doc '<document URL or token>'
```

## Failure handling

- On authentication errors, run `bash <skill-dir>/scripts/lark-cli-profile auth status --json --verify` and report the missing identity or scope without exposing secrets.
- If the profile is absent, stop the document operation and offer the bootstrap command from the setup section.
- Do not fall back to browser automation or web scraping for private documents.
- Do not claim a remote write succeeded until the changed content has been fetched and verified.
