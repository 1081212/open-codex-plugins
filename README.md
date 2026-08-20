# Open Codex Plugins

An open marketplace for reusable Codex plugins developed or integrated by community contributors.

The repository is vendor-neutral and project-neutral. Plugins must not contain organization-specific configuration, private endpoints, credentials, user data, or machine-specific paths.

## Give this repository to Codex

Send this repository URL to Codex:

```text
https://github.com/1081212/open-codex-plugins
```

Then ask:

```text
Install and configure the Lark Codex integration from this repository. Complete
the setup and verification, pausing only when I must scan a QR code, approve
OAuth, or grant a system permission.
```

Codex should follow [INSTALL.md](INSTALL.md). The QR code and OAuth consent must be completed by the account owner; they cannot safely be automated or shared.

## Manual marketplace installation

```bash
codex plugin marketplace add 1081212/open-codex-plugins --ref main
```

Then open Codex and enter `/plugins`, or install a plugin directly:

```bash
codex plugin add lark-docs@open-codex-plugins
```

## Plugins

### Lark Codex

Provides both directions through two independent local components:

```text
Lark or Feishu messages -> lark-channel-bridge -> local Codex
local Codex -> @larksuite/cli -> Lark or Feishu documents
```

The plugin contains no credentials. Each user completes their own QR-code and OAuth authorization. See [the plugin documentation](plugins/lark-docs/README.md).

## Repository layout

```text
.agents/plugins/marketplace.json   Marketplace catalog
plugins/<name>/.codex-plugin/      Plugin manifest
plugins/<name>/skills/             Reusable Codex workflows
```

## Development

Each plugin must:

- use a unique kebab-case name;
- include `.codex-plugin/plugin.json`;
- use only relative, portable paths;
- keep credentials and personal configuration out of Git;
- document external dependencies and their licenses;
- pass the official plugin and skill validators before release.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow.

## License

Repository-authored content is licensed under the [MIT License](LICENSE). Integrated dependencies retain their own licenses and are not redistributed unless explicitly stated.
