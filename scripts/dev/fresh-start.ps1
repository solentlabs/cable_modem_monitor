# Fresh Start Script - Reset VS Code state to test new developer experience
# PowerShell version for Windows
# This is ONLY needed to test what a brand new developer sees
# Normal development doesn't require this script

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🔄 Fresh Start - Reset VS Code State" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "This script resets VS Code's memory of this project."
Write-Host "Use this to test the new developer onboarding experience."
Write-Host ""
Write-Host "⚠️  Note: This is ONLY for testing. Normal development doesn't need this." -ForegroundColor Yellow
Write-Host ""

# Step 1: Check if VS Code is running
$codeProcess = Get-Process -Name "Code" -ErrorAction SilentlyContinue
if ($codeProcess) {
    Write-Host "⚠️  VS Code appears to be running" -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "Close all VS Code windows and press Enter to continue (or Ctrl+C to cancel)"
}

# Step 2: Set cache path for Windows
$CACHE_PATH = "$env:APPDATA\Code\User\workspaceStorage"

Write-Host "🖥️  Detected: Windows" -ForegroundColor Green
Write-Host ""

# Step 3: Clear workspace cache for this project
Write-Host "🧹 Clearing VS Code workspace cache for this project..." -ForegroundColor Cyan

if (Test-Path $CACHE_PATH) {
    $found = 0

    Get-ChildItem -Path $CACHE_PATH -Directory | ForEach-Object {
        $workspaceJsonPath = Join-Path $_.FullName "workspace.json"

        if (Test-Path $workspaceJsonPath) {
            $content = Get-Content $workspaceJsonPath -Raw -ErrorAction SilentlyContinue

            if ($content -match "cable_modem_monitor") {
                Write-Host "   → Removing: $($_.Name)" -ForegroundColor Gray
                Remove-Item -Path $_.FullName -Recurse -Force
                $found++
            }
        }
    }

    if ($found -gt 0) {
        Write-Host "   ✅ Cleared $found workspace cache folder(s)" -ForegroundColor Green
    } else {
        Write-Host "   → No cached workspace found (already clean)" -ForegroundColor Gray
    }
} else {
    Write-Host "   → Workspace cache directory not found" -ForegroundColor Gray
    Write-Host "   → This is normal on first install" -ForegroundColor Gray
}

# Step 4: Optional - Remove .venv
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Optional: Test Setup From Scratch" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Remove .venv to test the complete setup process?"
Write-Host "(This simulates a brand new clone)"
Write-Host ""
$removeVenv = Read-Host "Remove .venv? (y/N)"

if ($removeVenv -eq "y" -or $removeVenv -eq "Y") {
    if (Test-Path ".venv") {
        Write-Host "   → Removing .venv..." -ForegroundColor Gray
        Remove-Item -Path ".venv" -Recurse -Force
        Write-Host "   ✅ Removed .venv" -ForegroundColor Green
    } else {
        Write-Host "   → No .venv found" -ForegroundColor Gray
    }
} else {
    Write-Host "   → Keeping .venv (faster testing)" -ForegroundColor Gray
}

# Step 5: Summary
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ Fresh start ready!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Now open VS Code to see the new developer experience:"
Write-Host ""
Write-Host "   code ." -ForegroundColor Yellow
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "What You Should See:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Notifications (in order):"
Write-Host "  1. 'Dev Container configuration available...'"
Write-Host "     → Your choice: Use it OR dismiss"
Write-Host ""
Write-Host "  2. 'Install recommended extensions?'"
Write-Host "     → Click 'Install' (6 essential extensions)"
Write-Host ""
Write-Host "What You Should NOT See:"
Write-Host "  ❌ GitLens notification (removed - optional)" -ForegroundColor Red
Write-Host "  ❌ CodeQL error notifications (removed - optional)" -ForegroundColor Red
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "If you dismissed Dev Container:"
Write-Host "   .\scripts\setup.sh (in Git Bash)" -ForegroundColor Yellow
Write-Host "   OR" -ForegroundColor Yellow
Write-Host "   bash scripts/setup.sh (if bash is in PATH)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Then validate everything works:"
Write-Host "   make validate" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or use VS Code task:"
Write-Host "   Ctrl+Shift+P → Tasks: Run Task → Quick Validation" -ForegroundColor Yellow
Write-Host ""
