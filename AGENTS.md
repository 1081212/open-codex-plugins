# Repository Guidance

This repository is a public, vendor-neutral Codex plugin marketplace.

- Keep every plugin usable outside any single company, employer, tenant, or private project.
- Never commit credentials, OAuth responses, profile archives, private URLs, user documents, logs, internal identifiers, or absolute home-directory paths.
- Keep authentication local to each user. Never automate consent or move `~/.lark-channel` state between machines or users.
- Preserve upstream attribution and license terms. Do not imply endorsement by integrated projects.
- Add plugins under `plugins/<kebab-case-name>` with `.codex-plugin/plugin.json`, and keep the marketplace entry in `.agents/plugins/marketplace.json` consistent.
- Put reusable runtime behavior in focused skills. Use `AGENTS.md` only for repository development rules.
- Explain external dependencies, network access, global installs, permissions, and remote writes in user-facing documentation.
- Require explicit confirmation immediately before destructive remote actions.
- Validate every changed plugin and Skill, syntax-check helper scripts, and scan staged content for secrets and machine-specific paths before committing.
- Keep public installation instructions usable from a clean machine and distinguish automated steps from QR, OAuth, and operating-system approvals that require the user.
