[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Automatic,
    [switch]$NoService,
    [string]$InstallRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $InstallRoot) {
    $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME ".local/share" }
    $InstallRoot = Join-Path $base "CodexUsageDashboard"
}
$settingsPath = Join-Path $InstallRoot "settings.json"
if (-not (Test-Path $settingsPath)) { throw "Dashboard is not installed. Run install.ps1 first." }
$settings = Get-Content -Raw $settingsPath | ConvertFrom-Json
$marketplace = if ($settings.marketplace) { $settings.marketplace } else { "open-codex-plugins" }
$fallbackCodex = Get-Command codex -ErrorAction SilentlyContinue
$codexCli = if ($settings.codex_cli -and (Test-Path $settings.codex_cli)) {
    $settings.codex_cli
} elseif ($fallbackCodex) {
    $fallbackCodex.Source
} else {
    ""
}
if (-not $codexCli) { throw "Codex CLI is required." }
$pythonCli = if ($settings.python -and (Test-Path $settings.python)) { $settings.python } else { "" }

$mutex = New-Object Threading.Mutex($false, "Local\CodexUsageDashboardUpdate")
if (-not $mutex.WaitOne(0)) {
    if ($Automatic) { exit 0 }
    throw "Another dashboard update is already running."
}
try {
    & $codexCli plugin marketplace upgrade $marketplace
    if ($LASTEXITCODE -ne 0) { throw "Marketplace refresh failed." }
    & $codexCli plugin add "codex-usage-dashboard@$marketplace"
    if ($LASTEXITCODE -ne 0) { throw "Plugin reinstall failed." }
    $plugins = (& $codexCli plugin list --json | ConvertFrom-Json)
    $pluginId = "codex-usage-dashboard@$marketplace"
    $plugin = $plugins.installed | Where-Object { $_.pluginId -eq $pluginId } | Select-Object -First 1
    if (-not $plugin -or -not (Test-Path $plugin.source.path)) { throw "Could not resolve the refreshed plugin source." }
    $pluginRoot = $plugin.source.path
    $manifest = Get-Content -Raw (Join-Path $pluginRoot ".codex-plugin/plugin.json") | ConvertFrom-Json
    $currentVersionPath = Join-Path $InstallRoot "app/VERSION"
    $currentVersion = if (Test-Path $currentVersionPath) { (Get-Content $currentVersionPath -First 1) } else { "" }
    if (-not $Force -and $manifest.version -eq $currentVersion) {
        Write-Host "Codex Usage Dashboard is already up to date ($currentVersion)."
        exit 0
    }
    $installer = Join-Path $pluginRoot "skills/codex-usage-dashboard/scripts/install.ps1"
    if (-not (Test-Path $installer)) { throw "Refreshed plugin does not contain install.ps1." }
    $installArgs = @{ InstallRoot = $InstallRoot; Marketplace = $marketplace }
    $env:CODEX_CLI_PATH = $codexCli
    if ($pythonCli) { $env:CODEX_USAGE_PYTHON = $pythonCli }
    if ($NoService) { $installArgs.NoService = $true }
    if (Test-Path (Join-Path $InstallRoot "auto-update-enabled")) {
        $installArgs.EnableAutoUpdate = $true
    } else {
        $installArgs.DisableAutoUpdate = $true
    }
    & $installer @installArgs
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
