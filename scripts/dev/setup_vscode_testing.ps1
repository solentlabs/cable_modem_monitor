Write-Host "Setting up VS Code for Python testing..."

# Get the current directory (where the script is run from)
Set-Location $PSScriptRoot
$projectRoot = Get-Location

# Ensure .vscode directory exists
$vscodeDir = Join-Path $projectRoot ".vscode"
if (-not (Test-Path $vscodeDir)) {
    New-Item -ItemType Directory -Path $vscodeDir | Out-Null
    Write-Host "Created .vscode directory."
}

# Path to workspace settings.json
$settingsPath = Join-Path $vscodeDir "settings.json"

# Read existing settings or create an empty hash table
$settings = @{}
if (Test-Path $settingsPath) {
    $jsonContent = Get-Content $settingsPath | Out-String
    # Handle empty or invalid JSON gracefully
    if ($jsonContent -ne "" -and $jsonContent -match "^\s*{.*}\s*$") {
        $settings = $jsonContent | ConvertFrom-Json -AsHashtable
    } else {
        Write-Warning "settings.json is empty or invalid. Starting with empty settings."
    }
}

# Ensure 'python' and 'python.testing' hash tables exist
if (-not $settings.ContainsKey("python")) {
    $settings.python = @{}
    Write-Host "Initialized 'python' settings object."
}
if (-not $settings.python.ContainsKey("testing")) {
    $settings.python.testing = @{}
    Write-Host "Initialized 'python.testing' settings object."
}

# Enable pytest and configure arguments if not already set
if ($settings.python.testing.pytestEnabled -eq $null) {
    $settings.python.testing.pytestEnabled = $true
    Write-Host "Enabled Python pytest testing."
}

if ($settings.python.testing.cwd -eq $null) {
    # Set the current working directory for tests to the workspace folder
    # This is often important for finding modules correctly during test runs
    $settings.python.testing.cwd = "${workspaceFolder}"
    Write-Host "Set Python testing current working directory."
}

if ($settings.python.testing.pytestArgs -eq $null) {
    # Configure pytest to look for tests in the 'tests' folder within the workspace root
    $settings.python.testing.pytestArgs = @("tests")
    Write-Host "Configured pytest test arguments."
}

# Write updated settings back to settings.json
$settings | ConvertTo-Json -Depth 4 | Set-Content $settingsPath

Write-Host "VS Code workspace settings for Python testing updated in $settingsPath."
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Open this project in VS Code: code ."
Write-Host "2. In VS Code, open the Command Palette (Ctrl+Shift+P) and search for 'Python: Select Interpreter'."
Write-Host "3. Choose the Python interpreter located in your 'venv' folder (e.g., '.\venv\Scripts\python.exe').
   VS Code usually auto-detects it. If you don't see it, ensure your 'venv' is correctly activated in your terminal."
Write-Host "4. Go to the Testing tab (beaker icon in the Activity Bar) in VS Code to run your tests."
Write-Host ""
Write-Host "Script execution complete."

# Optional: Open VS Code after script runs
Start-Process code . -WorkingDirectory $projectRoot
