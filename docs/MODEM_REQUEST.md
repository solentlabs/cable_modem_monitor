# Requesting Support for Your Modem

This guide explains how to submit data from your modem to help us add support for your model.

## What We're Building Together

Cable Modem Monitor extracts signal quality data from your modem's web interface - the same information you'd see if you logged into your modem manually. To add support for a new modem model, we need a HAR capture from your modem's web pages.

**What we extract:**

- Downstream/upstream channel data (frequency, power levels, SNR)
- Error counts (corrected/uncorrectable codewords)
- Connection status and DOCSIS lock state
- System information (firmware version, uptime)

**What we DON'T need:**

- WiFi settings or passwords
- Router configuration
- Device lists or client names
- Account information

### Why HAR Captures Matter

Your captured data becomes a **test fixture** - a frozen snapshot we use to:

1. **Develop the parser** - Understand your modem's HTML/API structure
2. **Detect auth strategy** - Identify how your modem authenticates
3. **Write tests** - Verify the parser extracts data correctly
4. **Prevent regressions** - Ensure future changes don't break your modem

You can see supported modems in the [catalog](../packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/).

---

## Important: About PII and Sanitization

> **Automated sanitization is best-effort, not foolproof.**

We automatically attempt to remove personally identifiable information (PII) from captured data:

- MAC addresses
- Serial numbers
- Public/private IP addresses
- Passwords and credentials
- Session tokens

**However, modem manufacturers store data in unpredictable ways.** Some embed WiFi credentials in JavaScript variables without labels. Others use proprietary formats we haven't encountered before.

### Your Responsibility

Before sharing any captured data:

1. **Search the file for your WiFi network name (SSID)**
2. **Search for your WiFi password**
3. **Search for your router admin password**
4. **Review any sections flagged as warnings**

If you find credentials that weren't automatically redacted:

- Manually replace them with `***REDACTED***`
- Let us know in your issue so we can improve the sanitizer

**We're building a pattern library together.** Each time someone reports a missed credential format, we add it to our sanitization filters. Your feedback makes this safer for everyone.

---

## How to Capture Data

Use [har-capture](https://github.com/solentlabs/har-capture) to record the complete HTTP conversation between your browser and your modem. HAR files capture authentication flows, API calls, and page content — everything needed to build a parser.

```bash
# Install har-capture (one-time)
pip install "har-capture[full]"

# Capture from your modem (default cable modem IP)
har-capture get 192.168.100.1

# Or specify a different IP
har-capture get 192.168.0.1

# If your modem uses HTTP Basic Auth
har-capture get 192.168.100.1 -u admin -p yourpassword
```

See the [har-capture documentation](https://github.com/solentlabs/har-capture) for more options.

**During capture:**

1. Browser opens to your modem
2. Log in normally (if form-based auth)
3. Navigate to status/DOCSIS pages
4. **Wait 3-5 seconds per page** (let async data load)
5. Close browser when done

**Important:** Use an incognito/private browsing window or clear cookies first. If your browser has a cached session, the capture will miss the login flow.

The tool automatically sanitizes and compresses the output. **Review before sharing.**

---

## Before You Submit: Review Checklist

Open your captured file and verify:

- [ ] **Search for your WiFi SSID** - should return no results (or only `***REDACTED***`)
- [ ] **Search for your WiFi password** - should return no results
- [ ] **Search for your router admin password** - should return no results
- [ ] **Check for your public IP address** - should be `***PUBLIC_IP***`
- [ ] **Look for serial numbers** - should be `***SERIAL***` or similar

### What to Look For

Check for:

- Cookie values
- Authorization headers
- POST body content
- Literal password values
- Network names you recognize
- Patterns like `password`, `passphrase`, `psk`, `wpa`

If anything sensitive remains, either:

1. Manually redact it (replace with `***REDACTED***`)
2. Note it in your issue so we can improve the sanitizer

---

## Submitting Your Request

1. **Open a new issue** using the [Modem Request template](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)
2. Fill in modem details (model, manufacturer, IP address)
3. Attach your HAR capture
4. Note any manual redactions you made

### What Happens Next

1. **We analyze your capture** - Understanding the HTML/API structure and auth mechanism
2. **We may request additional captures** - Different pages or scenarios
3. **We develop a parser** - Using your data as test fixtures
4. **You verify it works** - Test on your actual modem
5. **Parser ships in next release** - Your modem is now supported!

**Setting expectations:**

- This is a solo-maintained project - requests are handled as capacity allows
- Complete submissions with clean captures get prioritized
- Parser complexity varies widely - some modems take significantly longer
- There's no guaranteed timeline, but quality submissions help move things faster
- Expect 2-3 rounds of interaction; quick responses to follow-ups speed things along

---

## Privacy Summary

| Data Type | What Happens |
| ----------- | -------------- |
| WiFi credentials | Should be auto-redacted, **verify before sharing** |
| MAC addresses | Auto-redacted (format-preserving hash, e.g., `02:xx:xx:xx:xx:xx`) |
| Serial numbers | Auto-redacted (hash with `SERIAL_` prefix) |
| Public IPs | Auto-redacted (reserved range, e.g., `240.x.x.x`) |
| Channel data (power, SNR) | Preserved - needed for parser |
| Firmware version | Preserved - useful for compatibility |
| Uptime | Preserved - useful for testing |

**Modem IPs like `192.168.100.1` are preserved** - these are standard defaults, not personal information.

---

## Questions?

- Check existing [modem request issues](https://github.com/solentlabs/cable_modem_monitor/issues?q=label%3A%22new+modem%22) for examples
- Open a [GitHub Discussion](https://github.com/solentlabs/cable_modem_monitor/discussions) for questions
- See the [modem catalog](../packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/) for currently supported modems
