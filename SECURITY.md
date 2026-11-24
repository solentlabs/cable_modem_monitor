# Security Policy

## Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 3.14.x  | :white_check_mark: |
| < 3.14  | :x:                |

## Reporting a Vulnerability

We take the security of Cable Modem Monitor seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report them privately:

- Open a private [Security Advisory](https://github.com/solentlabs/cable_modem_monitor/security/advisories/new) on GitHub

### What to Include

Please include as much of the following information as possible:

- Type of vulnerability (e.g., authentication bypass, credential exposure, code injection)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability and how an attacker might exploit it
- Any potential fixes you've identified

### Response Timeline

- **Initial Response**: Within 48 hours of receipt
- **Status Update**: Within 7 days with an expected timeline for a fix
- **Resolution**: We aim to release security patches within 30 days for critical vulnerabilities

### Disclosure Policy

- We will acknowledge your report within 48 hours
- We will provide regular updates on our progress
- Once a fix is released, we will publicly disclose the vulnerability (with credit to you, if desired)
- We ask that you do not publicly disclose the vulnerability until we've had a chance to address it

### Security Best Practices for Users

When using Cable Modem Monitor:

1. **Credentials**: Modem credentials are stored in the Home Assistant config entry (Home Assistant's `.storage` directory), which Home Assistant does not encrypt. Protect access to your Home Assistant configuration
2. **HTTPS**: Use HTTPS when accessing modems that support SSL/TLS
3. **Network Access**: Ensure your Home Assistant instance is properly secured if exposed to the internet
4. **Updates**: Keep the integration updated to receive the latest security patches
5. **Local Access**: This integration is designed for local network access only - modems should not be exposed to the public internet

### Known Security Considerations

- **Read-Only Access**: This integration only reads data from your modem and does not modify its configuration (except for the optional restart button feature)
- **Local Network**: The integration communicates only with devices on your local network
- **No Cloud Services**: All data stays local - no information is sent to external services
- **Authentication**: Supports the login methods listed in the [README](.github/README.md); credentials are sent only to the modem

### Security-Related Configuration

- SSL certificates are not verified: cable modems serve self-signed certificates, so HTTPS encrypts the connection but does not authenticate the modem
- Rejected credentials trip a circuit breaker that stops further login attempts until you re-enter credentials or reload the integration; some modems lock out or restart after repeated bad logins
- Requests time out after 10 seconds by default; some modems' catalog entries set up to 20

## Acknowledgments

We appreciate the security research community's efforts to improve the security of open source projects. Contributors who responsibly disclose security vulnerabilities will be acknowledged in our release notes (unless they prefer to remain anonymous).

---

Thank you for helping keep Cable Modem Monitor and its users safe!
