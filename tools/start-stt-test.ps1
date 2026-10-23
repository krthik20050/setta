$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python).Source }
$runtime = Join-Path $root 'runtime'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
$ready = $false
try { $page = Invoke-WebRequest 'http://127.0.0.1:8771/record-stt.html' -UseBasicParsing -TimeoutSec 2; $ready = $page.Content -match 'Record once, compare transcription' } catch { }
if (-not $ready) {
    $server = Start-Process $python -ArgumentList @('-m','http.server','8771','--bind','127.0.0.1') -WorkingDirectory (Join-Path $root 'tools\voice') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'stt-test.stdout.log') -RedirectStandardError (Join-Path $runtime 'stt-test.stderr.log')
    $server.Id | Set-Content (Join-Path $runtime '.stt-test.pid')
    Start-Sleep -Seconds 2
}
Start-Process 'http://127.0.0.1:8771/record-stt.html'
