$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$pidFile = Join-Path $runtimeRoot '.setta.pid'
if (Test-Path -LiteralPath $pidFile) {
    $recordedPid = Get-Content -LiteralPath $pidFile -TotalCount 1
    if ($recordedPid -match '^\d+$' -and (Get-Process -Id ([int]$recordedPid) -ErrorAction SilentlyContinue)) {
        $existing = Get-CimInstance Win32_Process -Filter "ProcessId = $recordedPid" -ErrorAction SilentlyContinue
        $expectedEntry = Join-Path $projectRoot 'setta.py'
        if ($existing -and $existing.CommandLine -and $existing.CommandLine.Contains($expectedEntry)) {
            Set-Content -LiteralPath (Join-Path $runtimeRoot '.open-hub') -Value 'open'
            Write-Output "Opening the existing Setta app (PID $recordedPid)."
            return
        }
        if ($existing) { throw 'The saved PID belongs to another process. Refusing to launch a duplicate; check the existing Setta process.' }
    }
}
# Old model copies can remain locked until the previous camera process exits.
foreach ($modelName in @('face_landmarker.task', 'hand_landmarker.task')) {
    $legacyPath = [IO.Path]::GetFullPath((Join-Path $projectRoot ('assets\' + $modelName)))
    $currentPath = Join-Path $projectRoot ('assets\models\' + $modelName)
    if (-not $legacyPath.StartsWith($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Cleanup outside project' }
    if ((Test-Path -LiteralPath $legacyPath) -and (Test-Path -LiteralPath $currentPath)) {
        if ((Get-FileHash -LiteralPath $legacyPath).Hash -eq (Get-FileHash -LiteralPath $currentPath).Hash) {
            try { Remove-Item -LiteralPath $legacyPath -ErrorAction Stop }
            catch { Write-Warning "Legacy model still in use: $legacyPath" }
        }
    }
}
$virtualPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$pythonPath = if (Test-Path -LiteralPath $virtualPython) { $virtualPython } else { (Get-Command python).Source }
$entryPoint = Join-Path $projectRoot 'setta.py'
$process = Start-Process -FilePath $pythonPath -ArgumentList @('-u', ('"' + $entryPoint + '"')) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'setta.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'setta.stderr.log')
$process.Id | Set-Content -LiteralPath $pidFile
Write-Output "SETTA started (PID $($process.Id)). Logs: $runtimeRoot"
