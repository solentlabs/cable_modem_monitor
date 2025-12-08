***REMOVED*** Testing on Home Assistant

This guide explains how to deploy a development branch of Cable Modem Monitor to a real Home Assistant instance for testing.

> **For local development** (running tests, working on code): See [DEVELOPER_QUICKSTART.md](./DEVELOPER_QUICKSTART.md)
>
> **For stable installation** (released versions): See [README.md Installation](../README.md***REMOVED***installation)

---

***REMOVED******REMOVED*** Quick Start

***REMOVED******REMOVED******REMOVED*** Using the Deploy Script (Recommended)

```bash
***REMOVED*** Clone the repo (or switch to the branch you want to test)
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
git checkout feature/your-branch-name

***REMOVED*** Run the deployment script
./scripts/deploy_updates.sh
```

The script supports multiple deployment methods:
- **Local path**: Direct copy to a local HA config directory
- **SSH**: Remote deployment via SSH
- **Docker**: Copy into a running Docker container

---

***REMOVED******REMOVED*** Manual Deployment

If the script doesn't work for your setup, follow these manual steps.

***REMOVED******REMOVED******REMOVED*** Step 1: Get the Code

```bash
***REMOVED*** Clone the repository
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor

***REMOVED*** Switch to the branch you want to test
git checkout feature/branch-name
```

***REMOVED******REMOVED******REMOVED*** Step 2: Copy ONLY the Integration Folder

**Important**: Copy only the `custom_components/cable_modem_monitor/` folder, NOT the entire repository.

```bash
***REMOVED*** Example: Copy to local HA config
cp -r custom_components/cable_modem_monitor /path/to/ha/config/custom_components/

***REMOVED*** Example: Copy via SSH
scp -r custom_components/cable_modem_monitor user@ha-host:/config/custom_components/

***REMOVED*** Example: Copy to Docker container
docker cp custom_components/cable_modem_monitor homeassistant:/config/custom_components/
```

***REMOVED******REMOVED******REMOVED*** Step 3: Verify the Structure

Your HA config should look like this:

```
/config/
└── custom_components/
    └── cable_modem_monitor/
        ├── __init__.py
        ├── manifest.json
        ├── config_flow.py
        ├── sensor.py
        ├── button.py
        ├── coordinator.py
        ├── core/
        ├── parsers/
        └── ...
```

**NOT** like this (common mistake):

```
/config/
└── custom_components/
    └── cable_modem_monitor/          <-- Wrong! This is the repo root
        ├── custom_components/        <-- Integration buried here
        │   └── cable_modem_monitor/
        ├── tests/
        ├── docs/
        ├── README.md
        └── ...
```

***REMOVED******REMOVED******REMOVED*** Step 4: Restart Home Assistant

```bash
***REMOVED*** HA OS / Supervised
ha core restart

***REMOVED*** Docker
docker restart homeassistant

***REMOVED*** Core installation
systemctl restart home-assistant
```

---

***REMOVED******REMOVED*** Common Issues

***REMOVED******REMOVED******REMOVED*** "Integration not found"

This usually means you cloned the entire repo into custom_components instead of just the integration folder.

**Fix**: Remove the incorrectly installed folder and copy only `custom_components/cable_modem_monitor/`:

```bash
***REMOVED*** Remove incorrect installation
rm -rf /config/custom_components/cable_modem_monitor

***REMOVED*** Copy correctly (from repo root)
cp -r custom_components/cable_modem_monitor /config/custom_components/
```

***REMOVED******REMOVED******REMOVED*** "No module named 'custom_components.cable_modem_monitor'"

Same issue as above - the folder structure is wrong.

***REMOVED******REMOVED******REMOVED*** Permissions Issues

On some systems, you may need to fix ownership:

```bash
***REMOVED*** Docker
docker exec homeassistant chown -R root:root /config/custom_components/cable_modem_monitor

***REMOVED*** Linux
sudo chown -R homeassistant:homeassistant /config/custom_components/cable_modem_monitor
```

---

***REMOVED******REMOVED*** Testing a PR

To test a specific pull request:

```bash
***REMOVED*** Fetch the PR branch
git fetch origin pull/44/head:pr-44
git checkout pr-44

***REMOVED*** Deploy
./scripts/deploy_updates.sh
```

Or use GitHub CLI:

```bash
gh pr checkout 44
./scripts/deploy_updates.sh
```

---

***REMOVED******REMOVED*** Providing Feedback

After testing, please report back on the GitHub issue or PR:

1. **If it works**: Comment that testing was successful
2. **If it fails**: Provide debug logs and any error messages

To get debug logs:

```yaml
***REMOVED*** In configuration.yaml
logger:
  default: warning
  logs:
    custom_components.cable_modem_monitor: debug
```

Then check Settings → System → Logs after restarting.

---

***REMOVED******REMOVED*** See Also

- [DEVELOPER_QUICKSTART.md](./DEVELOPER_QUICKSTART.md) - Local development setup
- [CONTRIBUTING.md](../CONTRIBUTING.md) - How to contribute
- [CAPTURE_GUIDE.md](./CAPTURE_GUIDE.md) - Capturing modem data for debugging
