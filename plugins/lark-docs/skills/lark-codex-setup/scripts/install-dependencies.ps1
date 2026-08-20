$ErrorActionPreference = "Stop"

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI is not installed or not on PATH."
}
if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js and npm are required. Install Node.js 20.12 or newer first."
}

node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>20||(a===20&&b>=12)?0:1)'
if ($LASTEXITCODE -ne 0) {
    throw "Node.js 20.12 or newer is required; found $(node --version)."
}

Write-Host "Installing lark-channel-bridge and @larksuite/cli globally with npm..."
npm install --global lark-channel-bridge @larksuite/cli
if ($LASTEXITCODE -ne 0) {
    throw "npm failed to install the required packages."
}

if (-not (Get-Command lark-channel-bridge -ErrorAction SilentlyContinue) -or -not (Get-Command lark-cli -ErrorAction SilentlyContinue)) {
    throw "Installation completed but the required commands are not on PATH."
}
Write-Host "Dependencies installed successfully."
