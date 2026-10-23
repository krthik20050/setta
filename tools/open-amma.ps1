$ErrorActionPreference = 'Stop'
try {
    & (Join-Path $PSScriptRoot 'start.ps1')
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Amma could not start') | Out-Null
    exit 1
}
