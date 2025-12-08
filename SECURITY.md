***REMOVED*** Security Policy

***REMOVED******REMOVED*** Supported Versions

We release security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 2.x.x   | :white_check_mark: |
| < 2.0   | :x:                |

***REMOVED******REMOVED*** Reporting a Vulnerability

We take the security of Cable Modem Monitor seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

***REMOVED******REMOVED******REMOVED*** How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **Preferred**: Open a [Security Advisory](https://github.com/solentlabs/cable_modem_monitor/security/advisories/new) on GitHub
2. **Alternative**: Email the maintainer directly at the email address listed in the [GitHub profile](https://github.com/kwschulz)

***REMOVED******REMOVED******REMOVED*** What to Include

Please include as much of the following information as possible:

- Type of vulnerability (e.g., authentication bypass, credential exposure, code injection)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability and how an attacker might exploit it
- Any potential fixes you've identified

***REMOVED******REMOVED******REMOVED*** Response Timeline

- **Initial Response**: Within 48 hours of receipt
- **Status Update**: Within 7 days with an expected timeline for a fix
- **Resolution**: We aim to release security patches within 30 days for critical vulnerabilities

***REMOVED******REMOVED******REMOVED*** Disclosure Policy

- We will acknowledge your report within 48 hours
- We will provide regular updates on our progress
- Once a fix is released, we will publicly disclose the vulnerability (with credit to you, if desired)
- We ask that you do not publicly disclose the vulnerability until we've had a chance to address it

***REMOVED******REMOVED******REMOVED*** Security Best Practices for Users

When using Cable Modem Monitor:

1. **Credentials**: All modem credentials are stored in Home Assistant's encrypted storage
2. **HTTPS**: Use HTTPS when accessing modems that support SSL/TLS
3. **Network Access**: Ensure your Home Assistant instance is properly secured if exposed to the internet
4. **Updates**: Keep the integration updated to receive the latest security patches
5. **Local Access**: This integration is designed for local network access only - modems should not be exposed to the public internet

***REMOVED******REMOVED******REMOVED*** Known Security Considerations

- **Read-Only Access**: This integration only reads data from your modem and does not modify its configuration (except for the optional restart button feature)
- **Local Network**: The integration communicates only with devices on your local network
- **No Cloud Services**: All data stays local - no information is sent to external services
- **Authentication**: Supports Basic Auth and Form-based authentication with encrypted credential storage

***REMOVED******REMOVED******REMOVED*** Security-Related Configuration

- SSL certificate verification is currently not configurable - the integration will attempt to verify SSL certificates when connecting via HTTPS
- Failed authentication attempts are logged but do not trigger account lockouts
- Network timeouts are set to 30 seconds to prevent hanging connections

***REMOVED******REMOVED*** Acknowledgments

We appreciate the security research community's efforts to improve the security of open source projects. Contributors who responsibly disclose security vulnerabilities will be acknowledged in our release notes (unless they prefer to remain anonymous).

---

Thank you for helping keep Cable Modem Monitor and its users safe!
