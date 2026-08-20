# Contributing

Contributions are welcome for new plugins and improvements to existing ones.

## Requirements

- Keep plugins useful outside any single company or private project.
- Remove private hostnames, identifiers, examples, credentials, and absolute home-directory paths.
- Do not commit generated authorization state, tokens, secrets, logs, or user documents.
- Preserve upstream attribution and licenses when integrating external projects.
- Explain all network access, external writes, and authentication requirements in the plugin documentation.
- Require confirmation immediately before destructive or high-risk operations.

## Adding a plugin

1. Add the plugin under `plugins/<plugin-name>`.
2. Add its entry to `.agents/plugins/marketplace.json`.
3. Validate its manifest and every included skill.
4. Test helper scripts on a clean profile without using real secrets in fixtures or logs.
5. Open a pull request describing dependencies, permissions, and verification performed.

For versioned plugins, bump `.codex-plugin/plugin.json` whenever published
runtime behavior changes. Automatic updaters use that version to decide whether
the installed runtime must be redeployed.
