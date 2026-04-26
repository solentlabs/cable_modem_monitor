# Requesting Support for Your Modem

Don't see your modem listed? Adding support starts with a HAR capture
from your modem's web interface. This guide walks you through capturing
and submitting it. From there, a maintainer or contributor builds a
parser, and you verify it works on your hardware before it ships.

This guide is for **Home Assistant users** who want to request support.
If you're comfortable with AI tools and want to help move things faster
(analyze the capture yourself, propose a catalog entry, help triage
issues), see the
[AI-assisted catalog contribution guide](../CONTRIBUTING.md#ai-assisted-catalog-contribution)
in CONTRIBUTING.md instead.

## What's collected

- Downstream/upstream channel data (frequency, power, SNR)
- Error counts (corrected/uncorrectable codewords)
- Connection status and DOCSIS lock state
- System information (firmware, uptime)

## What's not collected

WiFi settings, router configuration, device lists, account information.

---

## Step 1 — Capture

Use [har-capture](https://github.com/solentlabs/har-capture) to record
the HTTP conversation between your browser and your modem:

```bash
pip install "har-capture[full]"

# Default cable modem IP
har-capture 192.168.100.1

# If your modem uses HTTP Basic Auth
har-capture 192.168.100.1 -u admin -p yourpassword
```

**Use an incognito/private browsing window** — if your browser has a
cached session, the capture will miss the login flow and won't be
usable for building a parser.

During capture: log in if needed, visit all status pages, wait 3–5
seconds per page for async data to load, then close the browser. The
tool produces a sanitized, gzipped `.sanitized.har.gz` file.

## Step 2 — Review for PII

`har-capture` automatically redacts MAC addresses, serial numbers,
public IPs, and known credential patterns — but it's best-effort. Some
modems embed WiFi credentials in unlabeled JavaScript or proprietary
blobs the sanitizer hasn't seen. Before sharing:

**Option A — AI-assisted self-screen (faster).** Decompress the
`.sanitized.har.gz` and attach it to ChatGPT, Claude, or any AI
assistant that accepts file attachments. ChatGPT in an incognito window
without an account works for a few prompts; the free tiers of ChatGPT
and Claude both work. Paste this prompt:

````text
I need a defensive privacy review on a sanitized HAR file before I
share it publicly on GitHub. The file has been through an automated
sanitizer; I'm asking you to look for anything it might have missed,
so I can redact before sharing. This is a leak-prevention check, not
credential extraction.

Search the attached HAR for:

1. WiFi network names — short alphanumeric tokens near "ssid",
   "network_name", "wifi_name", or JSON keys ending in "Ssid" or
   "NetworkName". Report any value that doesn't look like a placeholder.
2. Passwords — any value near "password", "passphrase", "psk",
   "wpa_key", "admin_password" that is NOT "***REDACTED***" or empty.
3. MAC addresses NOT in the format "02:xx:xx:xx:xx:xx" (sanitizer
   hash format starts with 02). Real MACs in any other format are a leak.
4. IPv4 addresses that aren't RFC1918 private (10.x, 172.16-31.x,
   192.168.x), 0.0.0.0, 127.0.0.1, or 240.x.x.x (sanitizer's
   placeholder for redacted public IPs).
5. Session tokens, bearer tokens, or API keys — long opaque strings
   in cookies, Authorization headers, or response bodies that aren't
   already "***REDACTED***".

Output a fenced markdown block:

```
## PII review

- WiFi names found: <list or "none">
- Passwords found: <list or "none">
- Non-hashed MACs: <list or "none">
- Non-redacted public IPs: <list or "none">
- Suspicious tokens: <list or "none">
- Verdict: <CLEAN | NEEDS MANUAL REDACTION>
```

For each item include the entry index plus a 10-20 character snippet
around the value (e.g. "entry 47, response body, near
`var wifiSsid = `"). Don't paste the actual sensitive value back to me.
````

If the verdict is **CLEAN**, you're ready to submit. If it's **NEEDS
MANUAL REDACTION**, open the file in a text editor, replace each flagged
value with `***REDACTED***`, save, re-gzip, and submit. Note in your
issue what you redacted so the sanitizer can be improved for future
contributors.

False positives are common (an AI may flag a placeholder as suspicious).
Err on the side of redacting if unsure — the cost of an unnecessary
redaction is zero, the cost of a leaked credential is real.

**Option B — Manual checklist.** Open `.sanitized.har` in a text editor
and search for each:

- Your WiFi network name (SSID) — should return no results
- Your WiFi password — should return no results
- Your router admin password — should return no results
- Your public IP — should be `***PUBLIC_IP***`
- Serial numbers — should be `***SERIAL***` or hashed

If anything sensitive remains, replace it with `***REDACTED***` and
note it in your issue.

## Step 3 — Submit

Open the [Modem Request issue template](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)
and:

- Fill in modem details (model, manufacturer)
- Attach your `.sanitized.har.gz`
- If you ran the AI screen, paste the output block in **Additional
  Information**
- Note any manual redactions you made

---

## Privacy summary

| Data type | What happens |
|-----------|--------------|
| WiFi credentials | Auto-redacted; **verify before sharing** |
| MAC addresses | Auto-redacted (hashed, format `02:xx:xx:xx:xx:xx`) |
| Serial numbers | Auto-redacted (hashed, `SERIAL_*` prefix) |
| Public IPs | Auto-redacted (`240.x.x.x` reserved range) |
| Channel data (power, SNR) | Preserved — needed for parser |
| Firmware version | Preserved — useful for compatibility |
| Uptime | Preserved — useful for testing |

Modem IPs like `192.168.100.1` are preserved — they're standard
defaults, not personal information.

---

## Want to help more?

If you have AI access and want to do more than file a request — analyze
your own capture, propose a catalog entry, help triage other users'
submissions — see the
[AI-assisted catalog contribution guide](../CONTRIBUTING.md#ai-assisted-catalog-contribution).
The intake pipeline is designed for outside contributors with hardware
the maintainer doesn't have.

## Questions

- Browse [existing modem request issues](https://github.com/solentlabs/cable_modem_monitor/issues?q=label%3A%22new+modem%22)
  for examples
- [Open a Discussion](https://github.com/solentlabs/cable_modem_monitor/discussions)
  for questions
- See the [modem catalog](../packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/)
  for currently supported modems
