$ErrorActionPreference = "Stop"

$ProfileName = if ($env:LARK_CHANNEL_PROFILE) { $env:LARK_CHANNEL_PROFILE } else { "codex" }
$BridgeRoot = if ($env:LARK_CHANNEL_HOME) { $env:LARK_CHANNEL_HOME } else { Join-Path $HOME ".lark-channel" }
$SourceConfig = Join-Path $BridgeRoot "profiles/$ProfileName/lark-cli-source/config.json"
$CliConfigDir = Join-Path $BridgeRoot "profiles/$ProfileName/lark-cli"

if (-not (Test-Path -LiteralPath $SourceConfig -PathType Leaf)) {
    throw "Lark profile is not configured: $ProfileName. Initialize it with: lark-channel-bridge start --profile $ProfileName --agent codex"
}

$LarkCli = Get-Command lark-cli -ErrorAction SilentlyContinue
if (-not $LarkCli) {
    throw "lark-cli is not installed or not on PATH. Package: @larksuite/cli"
}

$env:LARK_CHANNEL = "1"
$env:LARK_CHANNEL_HOME = $BridgeRoot
$env:LARK_CHANNEL_PROFILE = $ProfileName
$env:LARK_CHANNEL_CONFIG = $SourceConfig
$env:LARKSUITE_CLI_CONFIG_DIR = $CliConfigDir
$env:LARKSUITE_CLI_NO_UPDATE_NOTIFIER = "1"
$env:LARKSUITE_CLI_NO_SKILLS_NOTIFIER = "1"

& $LarkCli.Source @args
exit $LASTEXITCODE
