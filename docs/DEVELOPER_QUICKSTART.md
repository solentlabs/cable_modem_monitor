***REMOVED*** Developer Quick Start Guide

Quick reference for getting started with Cable Modem Monitor development.

***REMOVED******REMOVED*** TL;DR - Get Started in 30 Seconds

```bash
***REMOVED*** Clone and start
git clone https://github.com/kwschulz/cable_modem_monitor.git
cd cable_modem_monitor
make docker-start

***REMOVED*** Open http://localhost:8123 in your browser
```

That's it! Home Assistant with the integration is now running locally.

---

***REMOVED******REMOVED*** Three Ways to Develop

***REMOVED******REMOVED******REMOVED*** 1. Docker (Easiest - Recommended for Beginners)

**Best for**: First-time contributors, testing in real Home Assistant

```bash
make docker-start       ***REMOVED*** Start Home Assistant
make docker-logs        ***REMOVED*** View logs
make docker-restart     ***REMOVED*** Restart after changes
```

**Pros**: No local setup, real Home Assistant environment, isolated
**Cons**: Slower restart times, requires Docker Desktop

***REMOVED******REMOVED******REMOVED*** 2. VS Code Dev Container (Best Experience)

**Best for**: Regular contributors, VS Code users

**Setup:**

1. **Install Dev Containers extension** (choose one method):

   - **From VS Code**: Press `Ctrl+Shift+X`, search "Dev Containers", click Install
   - **Quick command**: Press `Ctrl+P`, paste: `ext install ms-vscode-remote.remote-containers`
   - **Command line**: `code --install-extension ms-vscode-remote.remote-containers`
   - **From web**: Visit [marketplace link](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers), click Install

2. Open project in VS Code: `code .`
3. Press `F1` → "Dev Containers: Reopen in Container"
4. Wait for build (2-3 minutes first time)

**Pros**: Full IDE integration, debugging, IntelliSense inside container
**Cons**: Requires VS Code, initial setup time

See `.devcontainer/README.md` for detailed instructions.

***REMOVED******REMOVED******REMOVED*** 3. Local Python (Fastest)

**Best for**: Advanced developers, quick iteration

```bash
pip install -r tests/requirements.txt
make test               ***REMOVED*** Run tests
make lint               ***REMOVED*** Check code quality
```

**Pros**: Fastest iteration, no Docker overhead
**Cons**: No real Home Assistant testing, manual setup

---

***REMOVED******REMOVED*** Common Tasks

***REMOVED******REMOVED******REMOVED*** Running Tests

```bash
***REMOVED*** Full test suite
make test

***REMOVED*** Quick tests (development)
make test-quick

***REMOVED*** Specific test file
pytest tests/test_coordinator.py -v
```

***REMOVED******REMOVED******REMOVED*** Code Quality

```bash
***REMOVED*** Format code
make format

***REMOVED*** Check for issues
make lint

***REMOVED*** Auto-fix issues
make lint-fix

***REMOVED*** Run all checks
make check
```

***REMOVED******REMOVED******REMOVED*** Docker Management

```bash
make docker-start       ***REMOVED*** Start Home Assistant
make docker-stop        ***REMOVED*** Stop Home Assistant
make docker-restart     ***REMOVED*** Restart (load changes)
make docker-logs        ***REMOVED*** View logs (Ctrl+C to exit)
make docker-status      ***REMOVED*** Check if running
make docker-shell       ***REMOVED*** Open shell in container
make docker-clean       ***REMOVED*** Remove everything
```

***REMOVED******REMOVED******REMOVED*** Making Changes

```bash
***REMOVED*** 1. Create a branch
git checkout -b feature/my-feature

***REMOVED*** 2. Make your changes
***REMOVED*** ... edit files ...

***REMOVED*** 3. Test
make test

***REMOVED*** 4. Format and lint
make format
make lint-fix

***REMOVED*** 5. Commit
git add .
git commit -m "Add my feature"

***REMOVED*** 6. Push
git push origin feature/my-feature
```

---

***REMOVED******REMOVED*** Project Structure

```
cable_modem_monitor/
├── custom_components/cable_modem_monitor/  ***REMOVED*** Integration code
│   ├── __init__.py                        ***REMOVED*** Entry point
│   ├── config_flow.py                     ***REMOVED*** Configuration UI
│   ├── coordinator.py                     ***REMOVED*** Data fetching
│   ├── sensor.py                          ***REMOVED*** Sensor entities
│   ├── button.py                          ***REMOVED*** Button entities
│   └── parsers/                           ***REMOVED*** Modem parsers
│       ├── base_parser.py                 ***REMOVED*** Parser base class
│       ├── arris_sb6141.py               ***REMOVED*** Example parser
│       └── ...
├── tests/                                 ***REMOVED*** Unit tests
│   ├── fixtures/                          ***REMOVED*** HTML test data
│   └── test_*.py                          ***REMOVED*** Test files
├── scripts/                               ***REMOVED*** Development scripts
│   ├── dev/
│   │   ├── docker-dev.sh                 ***REMOVED*** Docker management
│   │   ├── run_tests_local.sh            ***REMOVED*** Test runner
│   │   └── ...
│   └── maintenance/
├── .devcontainer/                         ***REMOVED*** VS Code Dev Container config
├── Makefile                               ***REMOVED*** Quick commands
└── CONTRIBUTING.md                        ***REMOVED*** Full contributor guide
```

---

***REMOVED******REMOVED*** Quick Commands Reference

| Task | Command |
|------|---------|
| Start Docker dev | `make docker-start` |
| View logs | `make docker-logs` |
| Run tests | `make test` |
| Format code | `make format` |
| Lint code | `make lint` |
| Fix lint issues | `make lint-fix` |
| Run all checks | `make check` |
| See all commands | `make help` |

---

***REMOVED******REMOVED*** URLs

- **Home Assistant UI**: http://localhost:8123
- **GitHub Repo**: https://github.com/kwschulz/cable_modem_monitor
- **Issues**: https://github.com/kwschulz/cable_modem_monitor/issues

---

***REMOVED******REMOVED*** Adding a New Modem Parser

1. **Capture HTML** from your modem:
   ```bash
   curl http://192.168.100.1/status.html > tests/fixtures/my_modem.html
   ```

2. **Create parser** in `custom_components/cable_modem_monitor/parsers/my_modem.py`:
   ```python
   from .base_parser import ModemParser

   class MyModemParser(ModemParser):
       name = "My Modem Model"
       manufacturer = "Brand"
       models = ["Model123"]

       def can_parse(cls, soup, url, html):
           return "My Modem" in html

       def parse(self, soup, session=None, base_url=None):
           ***REMOVED*** Parse logic here
           return {"downstream": [], "upstream": [], "system_info": {}}
   ```

3. **Create tests** in `tests/test_parser_my_modem.py`

4. **Run tests**: `make test`

See `CONTRIBUTING.md` for detailed parser guide.

---

***REMOVED******REMOVED*** Troubleshooting

***REMOVED******REMOVED******REMOVED*** Docker won't start
```bash
***REMOVED*** Check Docker is running
docker ps

***REMOVED*** Clean and restart
make docker-clean
make docker-start
```

***REMOVED******REMOVED******REMOVED*** Tests failing
```bash
***REMOVED*** Run with verbose output
pytest tests/ -v --tb=short

***REMOVED*** Run specific test
pytest tests/test_coordinator.py::test_name -v
```

***REMOVED******REMOVED******REMOVED*** Linting errors
```bash
***REMOVED*** Auto-fix most issues
make lint-fix

***REMOVED*** Format code
make format
```

***REMOVED******REMOVED******REMOVED*** Port 8123 already in use
```bash
***REMOVED*** Stop existing Home Assistant
make docker-stop

***REMOVED*** Or find and kill the process
lsof -ti:8123 | xargs kill
```

---

***REMOVED******REMOVED*** Getting Help

1. Check [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guides
2. Read [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) for common issues
3. Open a [GitHub Issue](https://github.com/kwschulz/cable_modem_monitor/issues)
4. Ask in [GitHub Discussions](https://github.com/kwschulz/cable_modem_monitor/discussions)

---

***REMOVED******REMOVED*** Next Steps

- Read [CONTRIBUTING.md](../CONTRIBUTING.md) for full development workflow
- Check [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the codebase
- Review [MODEM_COMPATIBILITY_GUIDE.md](./MODEM_COMPATIBILITY_GUIDE.md) for parser details
- See [TEST_COVERAGE_SUMMARY.md](./TEST_COVERAGE_SUMMARY.md) for testing info

---

**Happy coding!** 🚀
