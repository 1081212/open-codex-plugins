[CmdletBinding()]
param(
    [switch]$EnableAutoUpdate,
    [switch]$DisableAutoUpdate,
    [ValidateRange(1024, 65535)][int]$Port = 0,
    [string]$Timezone = "",
    [string]$Marketplace = "",
    [string]$InstallRoot = "",
    [switch]$NoService
)

$ErrorActionPreference = "Stop"
if ($EnableAutoUpdate -and $DisableAutoUpdate) {
    throw "Choose either -EnableAutoUpdate or -DisableAutoUpdate."
}
if (-not $InstallRoot) {
    $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME ".local/share" }
    $InstallRoot = Join-Path $base "CodexUsageDashboard"
}
$InstallRoot = [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($InstallRoot))
if ($InstallRoot -eq [IO.Path]::GetPathRoot($InstallRoot) -or $InstallRoot -eq $HOME) {
    throw "Refusing unsafe install root: $InstallRoot"
}

$pluginRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$runtimeSource = Join-Path $pluginRoot "runtime"
$manifestPath = Join-Path $pluginRoot ".codex-plugin/plugin.json"
$pythonCommand = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $pythonCommand) { $pythonCommand = Get-Command python -ErrorAction SilentlyContinue }
$python = if ($env:CODEX_USAGE_PYTHON -and (Test-Path $env:CODEX_USAGE_PYTHON)) {
    $env:CODEX_USAGE_PYTHON
} elseif ($pythonCommand) {
    $pythonCommand.Source
} else {
    ""
}
if (-not $python) { throw "Python 3.9 or newer is required." }
& $python -c "import sys; raise SystemExit(sys.version_info < (3, 9))"
if ($LASTEXITCODE -ne 0) { throw "Python 3.9 or newer is required." }

New-Item -ItemType Directory -Force -Path $InstallRoot, (Join-Path $InstallRoot "logs") | Out-Null
$settingsPath = Join-Path $InstallRoot "settings.json"
$settings = @{}
if (Test-Path $settingsPath) {
    $existing = Get-Content -Raw $settingsPath | ConvertFrom-Json
    $existing.psobject.Properties | ForEach-Object { $settings[$_.Name] = $_.Value }
}
if (-not $Port) { $Port = if ($settings.port) { [int]$settings.port } else { 47831 } }
if (-not $Timezone) { $Timezone = if ($settings.timezone) { $settings.timezone } else { "UTC" } }
if (-not $Marketplace) { $Marketplace = if ($settings.marketplace) { $settings.marketplace } else { "open-codex-plugins" } }
if ($Marketplace -notmatch '^[A-Za-z0-9._-]+$') { throw "Invalid marketplace name." }
if ($Timezone.ToUpperInvariant() -ne "UTC") {
    & $python -c "from zoneinfo import ZoneInfo; import sys; ZoneInfo(sys.argv[1])" $Timezone
    if ($LASTEXITCODE -ne 0) { throw "Unknown timezone: $Timezone" }
}

$codexCommand = Get-Command codex -ErrorAction SilentlyContinue
$codexCli = if ($env:CODEX_CLI_PATH -and (Test-Path $env:CODEX_CLI_PATH)) {
    $env:CODEX_CLI_PATH
} elseif ($codexCommand) {
    $codexCommand.Source
} else {
    ""
}
if (-not $codexCli) { throw "Codex CLI is required." }

$version = (Get-Content -Raw $manifestPath | ConvertFrom-Json).version
$stage = Join-Path $InstallRoot (".stage." + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    Copy-Item (Join-Path $runtimeSource "codex_usage_dashboard.py") $stage
    Copy-Item (Join-Path $runtimeSource "index.html") $stage
    Set-Content -Encoding ascii -Path (Join-Path $stage "VERSION") -Value $version
    & $python -m py_compile (Join-Path $stage "codex_usage_dashboard.py")
    if ($LASTEXITCODE -ne 0) { throw "Dashboard runtime failed Python compilation." }

    $previous = Join-Path $InstallRoot "previous"
    $app = Join-Path $InstallRoot "app"
    if (Test-Path $previous) { Remove-Item -Recurse -Force $previous }
    if (Test-Path $app) { Move-Item $app $previous }
    Move-Item $stage $app
    $stage = $null
    Copy-Item (Join-Path $PSScriptRoot "update.ps1") (Join-Path $InstallRoot "update.ps1") -Force

    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
    [ordered]@{
        port = $Port
        timezone = $Timezone
        marketplace = $Marketplace
        codex_home = $codexHome
        codex_cli = $codexCli
        python = $python
    } | ConvertTo-Json | Set-Content -Encoding utf8 $settingsPath

    $marker = Join-Path $InstallRoot "auto-update-enabled"
    if ($EnableAutoUpdate) { New-Item -ItemType File -Force $marker | Out-Null }
    if ($DisableAutoUpdate -and (Test-Path $marker)) { Remove-Item -Force $marker }

    if (-not $NoService) {
        $dashboardScript = Join-Path $InstallRoot "app/codex_usage_dashboard.py"
        $powerShellCommand = Get-Command pwsh -ErrorAction SilentlyContinue
        if (-not $powerShellCommand) { $powerShellCommand = Get-Command powershell.exe -ErrorAction Stop }
        $powerShell = $powerShellCommand.Source
        function Quote-PowerShellLiteral([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
        $runner = Join-Path $InstallRoot "run-dashboard.ps1"
        @(
            '$ErrorActionPreference = "Stop"'
            '$env:CODEX_HOME = ' + (Quote-PowerShellLiteral $codexHome)
            '$env:CODEX_CLI_PATH = ' + (Quote-PowerShellLiteral $codexCli)
            '& ' + (Quote-PowerShellLiteral $python) + ' -u ' + (Quote-PowerShellLiteral $dashboardScript) + ' --host 127.0.0.1 --port ' + $Port + ' --timezone ' + (Quote-PowerShellLiteral $Timezone) + ' --refresh-seconds 300'
        ) | Set-Content -Encoding utf8 $runner
        $dashboardArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
        $dashboardAction = New-ScheduledTaskAction -Execute $powerShell -Argument $dashboardArgs
        $dashboardTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $dashboardSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        Stop-ScheduledTask -TaskName "CodexUsageDashboard" -ErrorAction SilentlyContinue
        Register-ScheduledTask -TaskName "CodexUsageDashboard" -Action $dashboardAction -Trigger $dashboardTrigger -Settings $dashboardSettings -Description "Local Codex usage dashboard" -Force | Out-Null
        Start-ScheduledTask -TaskName "CodexUsageDashboard"

        if (Test-Path $marker) {
            $updateScript = Join-Path $InstallRoot "update.ps1"
            $updateArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$updateScript`" -Automatic"
            $updateAction = New-ScheduledTaskAction -Execute $powerShell -Argument $updateArgs
            $updateTrigger = New-ScheduledTaskTrigger -Daily -At "03:00"
            Register-ScheduledTask -TaskName "CodexUsageDashboardUpdate" -Action $updateAction -Trigger $updateTrigger -Description "Daily Codex usage dashboard update" -Force | Out-Null
        } else {
            Unregister-ScheduledTask -TaskName "CodexUsageDashboardUpdate" -Confirm:$false -ErrorAction SilentlyContinue
        }

        $healthy = $false
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 1 "http://127.0.0.1:$Port/healthz"
                if ($response.StatusCode -eq 200) { $healthy = $true; break }
            } catch { Start-Sleep -Milliseconds 500 }
        }
        if (-not $healthy) {
            if (Test-Path $previous) {
                Stop-ScheduledTask -TaskName "CodexUsageDashboard" -ErrorAction SilentlyContinue
                Remove-Item -Recurse -Force $app
                Move-Item $previous $app
                Start-ScheduledTask -TaskName "CodexUsageDashboard"
            }
            throw "New dashboard failed its health check; the previous runtime was restored."
        }
    }

    Write-Host "Codex Usage Dashboard $version installed."
    Write-Host "Dashboard: http://127.0.0.1:$Port/"
    Write-Host ("Automatic updates: " + $(if (Test-Path $marker) { "enabled (daily)" } else { "disabled" }))
} finally {
    if ($stage -and (Test-Path $stage)) { Remove-Item -Recurse -Force $stage }
}
