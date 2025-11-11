# Comprehensive linting script for local development (PowerShell)
# Run this before committing to catch code quality issues early

$ErrorActionPreference = "Stop"

Write-Host "🔍 Running Code Quality Checks..." -ForegroundColor Cyan
Write-Host ""

# Exit code tracking
$ExitCode = 0

# Check if linting tools are installed
function Test-Tool {
    param([string]$ToolName)

    try {
        $null = Get-Command $ToolName -ErrorAction Stop
        Write-Host "✓ $ToolName found" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "✗ $ToolName not found. Install with: pip install -r requirements-dev.txt" -ForegroundColor Red
        return $false
    }
}

Write-Host "Checking for linting tools..."
$ToolsOK = $true
if (-not (Test-Tool "ruff")) { $ToolsOK = $false }
if (-not (Test-Tool "black")) { $ToolsOK = $false }
if (-not (Test-Tool "mypy")) { $ToolsOK = $false }
Write-Host ""

if (-not $ToolsOK) {
    Write-Host "✗ Some tools are missing. Please install them first." -ForegroundColor Red
    exit 1
}

# Target directory
$TargetDir = "."

# Run Ruff
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "1. Running Ruff linter..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
try {
    ruff check $TargetDir
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Ruff: No linting issues found" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Ruff: Linting issues detected" -ForegroundColor Red
        Write-Host "  Tip: Run 'ruff check --fix $TargetDir' to auto-fix some issues" -ForegroundColor Yellow
        $ExitCode = 1
    }
}
catch {
    Write-Host "✗ Ruff: Error running linter" -ForegroundColor Red
    $ExitCode = 1
}
Write-Host ""

# Run Black format check
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "2. Checking code formatting with Black..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
try {
    black --check $TargetDir
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Black: Code is properly formatted" -ForegroundColor Green
    }
    else {
        Write-Host "✗ Black: Code formatting issues detected" -ForegroundColor Red
        Write-Host "  Tip: Run 'black $TargetDir' to auto-format code" -ForegroundColor Yellow
        $ExitCode = 1
    }
}
catch {
    Write-Host "✗ Black: Error checking formatting" -ForegroundColor Red
    $ExitCode = 1
}
Write-Host ""

# Run mypy type checker
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
Write-Host "3. Running mypy type checker..." -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
try {
    mypy $TargetDir --config-file=mypy.ini
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ mypy: No type errors found" -ForegroundColor Green
    }
    else {
        Write-Host "✗ mypy: Type errors detected" -ForegroundColor Red
        $ExitCode = 1
    }
}
catch {
    Write-Host "✗ mypy: Error running type checker" -ForegroundColor Red
    $ExitCode = 1
}
Write-Host ""

# Summary
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Blue
if ($ExitCode -eq 0) {
    Write-Host "✅ All code quality checks passed!" -ForegroundColor Green
    Write-Host ""
    exit 0
}
else {
    Write-Host "❌ Code quality issues found. Please fix before committing." -ForegroundColor Red
    Write-Host ""
    Write-Host "Quick fixes:" -ForegroundColor Yellow
    Write-Host "  • Format code:     black $TargetDir" -ForegroundColor Cyan
    Write-Host "  • Fix lint issues: ruff check --fix $TargetDir" -ForegroundColor Cyan
    Write-Host "  • Or use Make:     make lint-fix && make format" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}
