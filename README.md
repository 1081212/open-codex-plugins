# Open Codex Plugins

An open marketplace for reusable Codex plugins developed or integrated by community contributors.

The repository is vendor-neutral and project-neutral. Plugins must not contain organization-specific configuration, private endpoints, credentials, user data, or machine-specific paths.

## Install the marketplace

```bash
codex plugin marketplace add 1081212/open-codex-plugins --ref main
```

Then open Codex and enter `/plugins`, or install a plugin directly:

```bash
codex plugin add lark-docs@open-codex-plugins
```

## Plugins

### Lark Docs

Connects Codex to documents owned or accessible by the current user's Lark or Feishu account.

The plugin contains no credentials. Each user installs the required local CLIs and completes their own QR-code and OAuth authorization. See [the plugin documentation](plugins/lark-docs/README.md).

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
