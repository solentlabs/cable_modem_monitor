# VS Code terminal auto-activation script for PowerShell
# This runs automatically when you open a terminal in VS Code

$venvPath = ".venv"

if (Test-Path $venvPath) {
    # .venv exists - activate it
    & "$venvPath\Scripts\Activate.ps1"
} else {
    # .venv doesn't exist - show helpful instructions
    Write-Host ""
    Write-Host "Welcome to Cable Modem Monitor!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Setup required - .venv not found" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Run this command to set up your development environment:" -ForegroundColor Green
    Write-Host "    bash scripts/setup.sh" -ForegroundColor White
    Write-Host ""
    Write-Host "This will:" -ForegroundColor Gray
    Write-Host "  - Create Python virtual environment (.venv)" -ForegroundColor Gray
    Write-Host "  - Install all dependencies" -ForegroundColor Gray
    Write-Host "  - Set up pre-commit hooks" -ForegroundColor Gray
    Write-Host "  - Takes ~2 minutes" -ForegroundColor Gray
    Write-Host ""
    Write-Host "After setup, close and reopen this terminal." -ForegroundColor Gray
    Write-Host ""
}
