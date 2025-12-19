# Attribution and Credits

This project builds on the work of the open source community. We acknowledge and thank the following projects and contributors.

---

## Research and Inspiration

### Modem Compatibility Research

<!-- AUTO-GENERATED FROM fixtures - DO NOT EDIT BELOW -->

### Data Contributors (Auto-Generated)

Users who provided modem captures for parser development:

| Contributor | Modem | Contribution | Issue |
|-------------|-------|--------------|-------|
| @captain-coredump | ARRIS SB6141 | HTML samples and compatibility testing (Community Forum) | — |
| @dlindnegm | Motorola MB8611 | Original HTML page captures | [#4](https://github.com/solentlabs/cable_modem_monitor/issues/4) |
| @cvonk | Motorola MB8611 | HAR captures, debug logs, iterative testing | [#6](https://github.com/solentlabs/cable_modem_monitor/issues/6) |
| @Mar1usW3 | Technicolor TC4400 | HTML samples and compatibility testing | [#1](https://github.com/solentlabs/cable_modem_monitor/issues/1) |

### External References (Auto-Generated)

Open source projects that informed our parser implementations:

| Project | Used For | Contribution |
|---------|----------|--------------|
| [BowlesCR/MB8600_Login](https://github.com/BowlesCR/MB8600_Login) | Motorola MB8611 | HNAP HMAC-MD5 challenge-response authentication |
| [Tatsh/mb8611](https://github.com/Tatsh/mb8611) | Motorola MB8611 | HNAP action names and response field definitions (StatusSoftwareSfVer, etc.) |
| [xNinjaKittyx/mb8600](https://github.com/xNinjaKittyx/mb8600) | Motorola MB8611 | Protocol reference and prior art for understanding HNAP flow |
| [philfry/check_tc4400](https://github.com/philfry/check_tc4400) | Technicolor TC4400 | Related prior art for TC4400 web interface monitoring |

<!-- END AUTO-GENERATED ATTRIBUTION -->

### Polling Interval Research

**SNMP Polling Best Practices**
- **Source:** Obkio Network Monitoring Blog
- **URL:** https://obkio.com/blog/snmp-polling/
- **Contribution:** Industry standards for network device polling intervals (5-10 minutes standard)
- **Applied:** Default scan interval configuration (300 seconds)

**API Polling Best Practices**
- **Source:** Merge.dev Engineering Blog
- **URL:** https://www.merge.dev/blog/api-polling-best-practices
- **Contribution:** Guidance on preventing server overload (> 1 second polling can overload)
- **Applied:** Minimum scan interval validation (60 seconds)

**Network Device Polling Guidelines**
- **Source:** Broadcom DX NetOps Community
- **URL:** https://community.broadcom.com/communities/community-home/digestviewer/viewthread?MID=824934
- **Contribution:** Recommendations for client device polling (not lower than 5 minutes)
- **Applied:** Health recommendations in UI and documentation

---

## Dependencies

This integration relies on the following open source libraries:

### Python Libraries
- **BeautifulSoup4** (https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- **Home Assistant Core** (https://github.com/home-assistant/core) - Integration framework

### Development & Testing
- **pytest** (https://pytest.org/) - Testing framework
- **pytest-homeassistant-custom-component** - HA testing utilities
- **ruff** (https://github.com/astral-sh/ruff) - Code linting

---

## Community Contributions

### Hardware Testing & Samples
- **@captain-coredump** - Confirmed ARRIS SB6141 compatibility, provided HTML samples and testing feedback ([Community Forum](https://community.home-assistant.io/t/cable-modem-monitor-track-your-internet-signal-quality-in-home-assistant))
- **@esand** - Provided Technicolor XB7 HTML samples and detailed modem information (Issue #2)

### User Contributions
- Users who report modem compatibility issues
- Contributors who provide HTML samples for new modem support
- Community members who test pre-release versions
- Documentation improvements and bug reports

**Thank you to all community members who help improve this integration!**

---

## Tools and Platforms

- **GitHub** - Code hosting and collaboration
- **GitHub Actions** - CI/CD automation
- **HACS** (Home Assistant Community Store) - Distribution platform
- **Home Assistant** - Smart home platform

---

## Attribution Policy

### For This Project

When using or referencing this project:
- **Attribution:** Cable Modem Monitor by kwschulz
- **Repository:** https://github.com/solentlabs/cable_modem_monitor
- **License:** MIT License (see LICENSE file)

### Our Commitment

We commit to:
- ✅ Properly attribute external research and code
- ✅ Credit community contributors
- ✅ Acknowledge dependencies
- ✅ Respect open source licenses
- ✅ Give back to the community

### If We Missed Something

If we've used your work without proper attribution:
1. We sincerely apologize - it was unintentional
2. Please open an issue or contact us
3. We'll add proper attribution immediately

Open source thrives on mutual respect and acknowledgment. We're committed to doing our part.

---

## How to Get Credit

### Contributing Code
- Pull requests with merged code are automatically credited in release notes
- Your GitHub profile is linked in commit history
- Significant contributions acknowledged in this file

### Contributing Research/Ideas
- Open an issue describing your contribution
- We'll add you to the acknowledgments section
- Credit will be included in relevant documentation

### Providing Modem Support
- Users who provide HTML samples for new modem support are credited in:
  - Release notes when support is added
  - Comments in the code for that modem
  - Compatibility guide

---

## Contact

Questions about attribution or credits?
- **GitHub Issues:** https://github.com/solentlabs/cable_modem_monitor/issues
- **GitHub Discussions:** https://github.com/solentlabs/cable_modem_monitor/discussions

---

**Last Updated:** 2025-10-28
**Document Version:** 1.1
