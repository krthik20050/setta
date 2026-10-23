param([string]$Expression)
$ErrorActionPreference = 'Stop'
if ($Expression -notmatch '^\d+(\.\d+)?\s*[+*/-]\s*\d+(\.\d+)?$') { throw 'Unsupported expression' }
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Start-Process calc.exe -WindowStyle Normal | Out-Null
$taskRoot = [System.Windows.Automation.AutomationElement]::RootElement
$taskWindow = $null
$taskDeadline = [DateTime]::UtcNow.AddSeconds(8)
while (-not $taskWindow -and [DateTime]::UtcNow -lt $taskDeadline) {
    $taskCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty,'Calculator')
    $taskWindow = $taskRoot.FindFirst([System.Windows.Automation.TreeScope]::Children,$taskCondition)
    if (-not $taskWindow) { Start-Sleep -Milliseconds 100 }
}
if (-not $taskWindow) { throw 'Calculator window unavailable' }
$taskProcess = Get-Process -Id $taskWindow.Current.ProcessId
if ($taskProcess.ProcessName -notin @('CalculatorApp','Calculator','ApplicationFrameHost')) { throw 'Unexpected Calculator process' }
function Invoke-CalculatorButton([string]$ButtonId) {
    $taskCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$ButtonId)
    $taskButton = $taskWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$taskCondition)
    if (-not $taskButton) { throw 'Calculator control unavailable' }
    $taskPattern = $taskButton.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $taskPattern.Invoke()
}
Invoke-CalculatorButton 'clearButton'
foreach ($taskCharacter in ($Expression -replace '\s','').ToCharArray()) {
    $taskButtonId = switch ([string]$taskCharacter) {
        '+' {'plusButton'} '-' {'minusButton'} '*' {'multiplyButton'} '/' {'divideButton'} '.' {'decimalSeparatorButton'}
        default {'num' + $taskCharacter + 'Button'}
    }
    Invoke-CalculatorButton $taskButtonId
}
Invoke-CalculatorButton 'equalButton'
Start-Sleep -Milliseconds 150
$taskCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'CalculatorResults')
$taskResult = $taskWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$taskCondition)
if (-not $taskResult) { throw 'Calculator result unavailable' }
@{display=$taskResult.Current.Name} | ConvertTo-Json -Compress
