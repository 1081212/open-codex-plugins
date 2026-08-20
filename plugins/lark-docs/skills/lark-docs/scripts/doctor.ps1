$ErrorActionPreference = "Stop"

$ProfileName = if ($env:LARK_CHANNEL_PROFILE) { $env:LARK_CHANNEL_PROFILE } else { "codex" }
$BridgeRoot = if ($env:LARK_CHANNEL_HOME) { $env:LARK_CHANNEL_HOME } else { Join-Path $HOME ".lark-channel" }
$SourceConfig = Join-Path $BridgeRoot "profiles/$ProfileName/lark-cli-source/config.json"
$Failed = $false

foreach ($CommandName in @("codex", "node", "npm", "lark-channel-bridge", "lark-cli")) {
    $Command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($Command) {
        Write-Host ("ok      {0,-21} {1}" -f $CommandName, $Command.Source)
    } else {
        Write-Host ("missing {0,-21}" -f $CommandName)
        $Failed = $true
    }
}

if (Get-Command node -ErrorAction SilentlyContinue) {
    node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=12)?0:1)'
    if ($LASTEXITCODE -eq 0) {
        Write-Host ("ok      {0,-21} {1}" -f "node-version", (node --version))
    } else {
        Write-Host ("invalid {0,-21} {1}; require 20.12 or newer" -f "node-version", (node --version))
        $Failed = $true
    }
}

if (Test-Path -LiteralPath $SourceConfig -PathType Leaf) {
    Write-Host ("ok      {0,-21} {1}" -f "profile", $ProfileName)
} else {
    Write-Host ("missing {0,-21} {1}" -f "profile", $ProfileName)
    Write-Host "        initialize with: lark-channel-bridge start --profile $ProfileName --agent codex"
    $Failed = $true
}

if ($Failed) { exit 1 }
exit 0
