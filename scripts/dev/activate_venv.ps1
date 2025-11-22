# VS Code terminal auto-activation script for PowerShell
# This runs automatically when you open a terminal in VS Code

$venvPath = ".venv"
$activateScript = "$venvPath\Scripts\Activate.ps1"

if (Test-Path $activateScript) {
    # .venv exists and is set up - activate it
    & $activateScript
} else {
    # .venv doesn't exist - show helpful instructions
    Write-Host ""
    Write-Host "Welcome to Cable Modem Monitor!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Choose your development environment:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Option 1: Local Python (Fastest)" -ForegroundColor Green
    Write-Host "  A. Use VS Code Menu: Ctrl+Shift+P -> Tasks -> 'Setup Local Python Environment'" -ForegroundColor White
    Write-Host "  B. Or run from terminal: bash scripts/setup.sh" -ForegroundColor White
    Write-Host "  - Takes ~2 minutes" -ForegroundColor Gray
    Write-Host "  - Fastest test execution" -ForegroundColor Gray
    Write-Host "  - After setup, close and reopen this terminal" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Option 2: Dev Container (Zero Setup)" -ForegroundColor Green
    Write-Host "  A. Use VS Code Menu: Ctrl+Shift+P -> 'Dev Containers: Reopen in Container'" -ForegroundColor White
    Write-Host "  B. VS Code may also show a pop-up notification suggesting this." -ForegroundColor Gray
    Write-Host "  - Takes ~5 minutes first time" -ForegroundColor Gray
    Write-Host "  - All dependencies pre-installed" -ForegroundColor Gray
    Write-Host "  - Guaranteed consistency with CI" -ForegroundColor Gray
    Write-Host ""
    Write-Host "See docs/GETTING_STARTED.md for detailed comparison" -ForegroundColor Gray
    Write-Host ""
}
