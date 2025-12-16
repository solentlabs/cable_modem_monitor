# Cross-Platform Support

**Cable Modem Monitor is fully cross-platform** and works identically on Windows, macOS, Linux, and Chrome OS.

## Verified Operating Systems

✅ **Windows 10/11** - PowerShell, Git Bash, WSL2
✅ **macOS** - Bash, Zsh
✅ **Linux** - Bash (Ubuntu, Debian, Fedora, etc.)
✅ **Chrome OS Flex** - Linux (Beta) container with Bash

---

## VS Code Settings Compatibility

All settings in `.vscode/settings.json` are **cross-platform**:

### ✅ Python Configuration
```json
"python.defaultInterpreterPath": "${workspaceFolder}/.venv"
```
- **Windows:** Resolves to `.venv\Scripts\python.exe`
- **Unix:** Resolves to `.venv/bin/python`
- VS Code automatically handles the path translation

### ✅ Terminal Auto-Activation
Platform-specific profiles configured for each OS:

**Windows:**
```json
"terminal.integrated.profiles.windows": {
  "PowerShell": {
    "args": ["-NoExit", "-File", "${workspaceFolder}/scripts/dev/activate_venv.ps1"]
  }
}
```

**Linux:**
```json
"terminal.integrated.profiles.linux": {
  "bash": {
    "args": ["--init-file", "${workspaceFolder}/scripts/dev/activate_venv.sh"]
  }
}
```

**macOS:**
```json
"terminal.integrated.profiles.osx": {
  "zsh": {
    "args": ["-c", "source ${workspaceFolder}/scripts/dev/activate_venv.sh && exec zsh"]
  }
}
```

### ✅ File Paths
All paths use `${workspaceFolder}` variable:
- Cross-platform path resolution
- Works in both workspace and folder mode
- Compatible with remote containers

### ✅ Line Endings
```json
"files.eol": "\n"
```
Enforced Unix-style line endings on all platforms (backed by `.gitattributes`)

---

## Scripts Compatibility

### Platform-Specific Scripts

**Windows:**
- `scripts/dev/activate_venv.ps1` - PowerShell terminal activation
- Git Bash can run `.sh` scripts via `bash scriptname.sh`

**Linux/macOS:**
- `scripts/dev/activate_venv.sh` - Bash/Zsh terminal activation
- Native shell script execution

**Cross-Platform:**
- `scripts/dev/fresh_start.py` - Python script works everywhere
- `scripts/setup.sh` - Works on all platforms (use `bash setup.sh` on Windows)

### Makefile Commands
All `make` commands work on all platforms:
```bash
make test       # Works on Windows (Git Bash), macOS, Linux
make validate   # Cross-platform
make format     # Cross-platform
```

**Windows Note:** Requires Git Bash or WSL2 for `make` commands

---

## Dev Container Support

✅ **100% Cross-Platform**

The Dev Container provides **identical environment** on all platforms:
- Same Python version (3.12)
- Same dependencies
- Same tools and CLI
- Eliminates "works on my machine" issues

**Platform Requirements:**
- Windows: Docker Desktop with WSL2 backend
- macOS: Docker Desktop
- Linux: Docker Engine
- Chrome OS: Docker in Linux (Beta) container

---

## Testing on All Platforms

### Automated CI Testing
GitHub Actions tests on:
- ✅ Ubuntu Latest (Linux)
- ✅ Windows Latest
- ✅ macOS Latest

### Manual Testing
Verified on:
- ✅ Windows 11 (PowerShell, Git Bash)
- ✅ Chrome OS Flex (Linux Beta)
- ✅ macOS Ventura (Zsh)
- ✅ Ubuntu 22.04 (Bash)

---

## Common Cross-Platform Issues (Solved)

### ❌ Line Endings (CRLF vs LF)
**Solution:** `.gitattributes` enforces LF on all platforms
```gitattributes
* text=auto eol=lf
*.sh text eol=lf
```

### ❌ Path Separators (\ vs /)
**Solution:** Use VS Code variables like `${workspaceFolder}` and Python's `pathlib`
```python
from pathlib import Path
venv_path = Path(".venv")  # Works everywhere
```

### ❌ Shell Differences (PowerShell vs Bash)
**Solution:** Platform-specific activation scripts
- `activate_venv.ps1` for Windows
- `activate_venv.sh` for Unix

### ❌ File Permissions
**Solution:** Git tracks executable bit, scripts auto-executable on Unix
```bash
chmod +x scripts/setup.sh  # Preserved in git
```

---

## Platform-Specific Features

### Windows
- **PowerShell:** Native colored output with `Write-Host -ForegroundColor`
- **Git Bash:** Can run `.sh` scripts with `bash scriptname.sh`
- **WSL2:** Full Linux compatibility

### macOS
- **Zsh:** Default shell since macOS Catalina
- **Bash:** Still available and supported
- **Homebrew:** Easy dependency installation

### Linux
- **Bash:** Default on most distributions
- **Package Managers:** apt, yum, dnf all work with setup script

### Chrome OS Flex
- **Linux (Beta):** Debian container with full development support
- **Docker:** Available in Linux container
- **VS Code:** Web or Linux app version

---

## Recommendations

### For New Contributors

**Best cross-platform experience:**
1. Use **Dev Container** - eliminates all platform differences
2. Or use **Local Python** + follow platform-specific setup

### For Regular Contributors

**Platform-specific workflows:**
- **Windows:** PowerShell + Git for commits
- **macOS/Linux:** Native terminal + shell scripts
- **Any OS:** Dev Container for consistency

### For CI/CD

**GitHub Actions matrix:**
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    python-version: ['3.11', '3.12']
```
Ensures compatibility across all platforms and Python versions

---

## Troubleshooting

### Windows: "bash: command not found"
**Solution:** Install Git for Windows (includes Git Bash)

### macOS: "permission denied" for scripts
**Solution:** `chmod +x scripts/setup.sh`

### Linux: "docker: command not found"
**Solution:** `sudo apt install docker.io` (Ubuntu/Debian)

### All Platforms: "make: command not found"
**Solution:**
- Windows: Use Git Bash or WSL2
- macOS: `xcode-select --install`
- Linux: `sudo apt install build-essential`

---

## Summary

✅ **All VS Code settings are cross-platform compatible**
✅ **Platform-specific terminal profiles work on their respective OS**
✅ **Scripts have platform-specific versions where needed**
✅ **Dev Container provides 100% identical environment everywhere**
✅ **CI tests on Windows, macOS, and Linux**
✅ **Tested and verified on all major platforms**

**Bottom Line:** Whether you use Windows, macOS, Linux, or Chrome OS, the development experience is smooth and well-supported.
