# Platform Support

Cable Modem Monitor supports development on **Linux** and **macOS**. Windows users must use **WSL2** (Windows Subsystem for Linux).

## Supported Platforms

| Platform | Support | Notes |
|----------|---------|-------|
| **Linux** | Native | Ubuntu, Debian, Fedora, etc. |
| **macOS** | Native | Intel and Apple Silicon |
| **Windows** | Via WSL2 | See [WSL2_SETUP.md](WSL2_SETUP.md) |
| **Chrome OS** | Via Linux (Beta) | Debian container |

---

## Why Not Native Windows?

Native Windows development (PowerShell, cmd.exe, Git Bash) is **not supported**. The toolchain requires a Unix environment:

1. **Shell scripts** - Pre-commit hooks and dev scripts use bash
2. **Path separators** - Scripts assume Unix `/` paths
3. **File permissions** - Git hooks need Unix executable bits
4. **Encoding** - Windows cp1252 vs Unix UTF-8 causes failures
5. **CI mismatch** - CI runs on Ubuntu; Windows testing doesn't catch real issues

**Solution:** Windows users develop inside WSL2, which provides a real Linux environment. VS Code's Remote-WSL extension makes this seamless.

---

## Development Environment Options

### Option 1: Native (Linux/macOS)

Clone the repo and run setup:

```bash
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
./scripts/setup.sh
code .
```

### Option 2: WSL2 (Windows)

See [WSL2_SETUP.md](WSL2_SETUP.md) for complete instructions.

### Option 3: Dev Container (Any Platform)

For guaranteed consistency with CI:

1. Install Docker and VS Code Dev Containers extension
2. Clone the repo and open in VS Code
3. Click "Reopen in Container"

See [DEVCONTAINER.md](DEVCONTAINER.md) for details.

---

## CI/CD Testing

GitHub Actions tests on:
- Ubuntu Latest (primary)
- macOS Latest (validates Unix compatibility)

---

## Troubleshooting

### macOS: "permission denied" for scripts
```bash
chmod +x scripts/setup.sh scripts/dev/*.sh
```

### Linux: "docker: command not found"
```bash
sudo apt install docker.io
sudo usermod -aG docker $USER
# Log out and back in
```

### macOS: "make: command not found"
```bash
xcode-select --install
```

### Linux: "make: command not found"
```bash
sudo apt install build-essential
```

---

## Summary

- **Linux/macOS:** Full native support
- **Windows:** Use WSL2 (see [WSL2_SETUP.md](WSL2_SETUP.md))
- **Dev Container:** Available as alternative on all platforms
