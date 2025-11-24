***REMOVED*** VS Code terminal auto-activation script for PowerShell
***REMOVED*** This runs automatically when you open a terminal in VS Code

$venvPath = ".venv"
$activateScript = "$venvPath\Scripts\Activate.ps1"

if (Test-Path $activateScript) {
    ***REMOVED*** .venv exists, activate it and show "next steps" message
    & $activateScript
    Clear-Host
    Write-Host ""
    Get-Content -Path (Join-Path $PSScriptRoot "next_steps.txt") | Write-Host
    Write-Host ""
} else {
    ***REMOVED*** .venv doesn't exist - show helpful instructions
    Get-Content -Path (Join-Path $PSScriptRoot "welcome_message.txt") | Write-Host
    Write-Host ""
}
