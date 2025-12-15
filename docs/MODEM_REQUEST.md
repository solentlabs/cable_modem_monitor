# Requesting Support for Your Modem

This guide explains how to submit data from your modem to help us add support for your model.

## What We're Building Together

Cable Modem Monitor extracts signal quality data from your modem's web interface - the same information you'd see if you logged into your modem manually. To add support for a new modem model, we need sample data from that modem's web pages.

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

### Why Test Fixtures Matter

Your captured data becomes a **test fixture** - a frozen snapshot we use to:
1. **Develop the parser** - Understand your modem's HTML/API structure
2. **Write tests** - Verify the parser extracts data correctly
3. **Prevent regressions** - Ensure future changes don't break your modem

You can see existing fixtures at [`tests/parsers/FIXTURES.md`](../tests/parsers/FIXTURES.md).

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

### Option 1: Integration Capture (Easiest)

**Best for:** Users who already have the integration installed (even if your modem isn't fully supported).

1. Configure the integration with your modem (use "Fallback Mode" if your model isn't listed)
2. Go to **Settings > Devices & Services > Cable Modem Monitor**
3. Press the **"Capture HTML"** button
4. **Download diagnostics** within 5 minutes:
   - Same page > Click menu (three dots) > **Download diagnostics**
5. **Review the JSON file** - search for your credentials before sharing
6. Attach to your GitHub issue

### Option 2: HAR Capture Script

**Best for:** Modems with login requirements, HNAP/API-based modems, or when Option 1 doesn't capture what's needed.

[HAR (HTTP Archive)](http://www.softwareishard.com/blog/har-12-spec/) files capture the complete HTTP conversation including authentication and API calls.

```bash
# One-time setup
pip install playwright && playwright install chromium

# Capture
python scripts/capture_modem.py
```

**During capture:**
1. Browser opens to your modem
2. Log in normally
3. Navigate to status/DOCSIS pages
4. **Wait 3-5 seconds per page** (let async data load)
5. Close browser when done

The script generates a `.sanitized.har.gz` file. **Review before sharing.**

### Which Method Do I Need?

| Modem Type | Recommended Method |
|------------|-------------------|
| HTML-based (SB6141, SB8200, CM600) | Either works |
| HNAP/API modems (MB8611, S33) | HAR Capture required |
| Login issues or errors | HAR Capture |

> **Why HNAP modems need HAR:** These modems load data via JavaScript API calls after the page renders. The Integration Capture only sees the HTML shell, not the actual data.

---

## Before You Submit: Review Checklist

Open your captured file and verify:

- [ ] **Search for your WiFi SSID** - should return no results (or only `***REDACTED***`)
- [ ] **Search for your WiFi password** - should return no results
- [ ] **Search for your router admin password** - should return no results
- [ ] **Check for your public IP address** - should be `***PUBLIC_IP***`
- [ ] **Look for serial numbers** - should be `***SERIAL***` or similar

### What to Look For

**In JSON files**, search for:
- Literal password values
- Network names you recognize
- Patterns like `password`, `passphrase`, `psk`, `wpa`

**In HAR files**, also check:
- Cookie values
- Authorization headers
- POST body content

If anything sensitive remains, either:
1. Manually redact it (replace with `***REDACTED***`)
2. Note it in your issue so we can improve the sanitizer

---

## Submitting Your Request

1. **Open a new issue** using the [Modem Request template](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)
2. Fill in modem details (model, manufacturer, IP address)
3. Attach your captured file (JSON or HAR)
4. Note any manual redactions you made

### What Happens Next

1. **We analyze your capture** - Understanding the HTML/API structure
2. **We may request additional captures** - Different pages or scenarios
3. **We develop a parser** - Using your data as test fixtures
4. **You verify it works** - Test on your actual modem
5. **Parser ships in next release** - Your modem is now supported!

**Expect 2-3 rounds of interaction.** Most modems have quirks we discover during development. Quick responses to follow-up requests speed up the process.

---

## Privacy Summary

| Data Type | What Happens |
|-----------|--------------|
| WiFi credentials | Should be auto-redacted, **verify before sharing** |
| MAC addresses | Auto-redacted to `XX:XX:XX:XX:XX:XX` |
| Serial numbers | Auto-redacted to `***SERIAL***` |
| Public IPs | Auto-redacted to `***PUBLIC_IP***` |
| Channel data (power, SNR) | Preserved - needed for parser |
| Firmware version | Preserved - useful for compatibility |
| Uptime | Preserved - useful for testing |

**Modem IPs like `192.168.100.1` are preserved** - these are standard defaults, not personal information.

---

## Questions?

- Check existing [modem request issues](https://github.com/solentlabs/cable_modem_monitor/issues?q=label%3A%22new+modem%22) for examples
- Open a [GitHub Discussion](https://github.com/solentlabs/cable_modem_monitor/discussions) for questions
- See [FIXTURES.md](../tests/parsers/FIXTURES.md) for the current modem library
