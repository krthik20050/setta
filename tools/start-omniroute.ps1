$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$gateway = Join-Path $root '.tools\omniroute\node_modules\omniroute\bin\omniroute.mjs'
$node = Join-Path $root '.tools\omniroute\node_modules\node\bin\node.exe'
if (-not (Test-Path -LiteralPath $node)) { $node = Join-Path $root '.tools\omniroute\node_modules\node\node.exe' }
if (-not (Test-Path -LiteralPath $gateway)) { throw 'OmniRoute installation is incomplete.' }
if (-not (Test-Path -LiteralPath $node)) { throw 'The project-local Node runtime is missing.' }
$env:DATA_DIR = Join-Path $root 'data\omniroute'
$env:OMNIROUTE_CLI_SKIP_DEFAULT_DATA_ENV = '1'
$env:OMNIROUTE_CLI_SKIP_REPO_ENV = '1'
$env:HOSTNAME = '127.0.0.1'
New-Item -ItemType Directory -Force -Path $env:DATA_DIR | Out-Null
Push-Location $env:DATA_DIR
try { & $node $gateway @args }
finally { Pop-Location }
