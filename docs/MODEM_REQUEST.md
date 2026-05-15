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

Follow [har-capture's quickstart](https://github.com/solentlabs/har-capture#quick-start)
to record the HTTP conversation between your browser and your modem.
Use your modem's IP as the capture target (the default cable modem IP
is `192.168.100.1`). If your modem requires HTTP Basic Auth, see the
auth flags in har-capture's CLI reference.

A few cable-modem-specific tips on top of the upstream guide:

- **During capture**, log in if needed, visit all status pages, and
  wait 3–5 seconds per page for async data to load before closing the
  browser. har-capture launches its own controlled chromium instance,
  so there's no need to use your regular browser's incognito mode —
  each capture starts from a clean session.

har-capture produces a sanitized, gzipped `.sanitized.har.gz` file —
that's the artifact to attach in Step 3.

## Step 2 — Review for PII

`har-capture` automatically redacts MAC addresses, serial numbers,
public IPs, and known credential patterns — but it's best-effort. Some
modems embed WiFi credentials in unlabeled JavaScript or proprietary
blobs the sanitizer hasn't seen. Pick one of these to verify before
sharing:

- **AI-assisted self-screen (faster)** — paste a prepared prompt into
  ChatGPT, Claude, or any AI assistant that takes file attachments.
  Full prompt and instructions:
  [docs/examples/har-pii-screen-prompt.md](examples/har-pii-screen-prompt.md).
- **Manual checklist (5 minutes)** — open the file in a text editor and
  search for a short list of patterns:
  [docs/examples/har-pii-manual-checklist.md](examples/har-pii-manual-checklist.md).

If anything sensitive remains, replace it with `***REDACTED***`, save,
re-gzip, and note what you redacted in your issue so the sanitizer
can be improved for future contributors.

## Step 3 — Submit

Open the [Modem Request issue template](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)
and:

- Fill in modem details (model, manufacturer)
- Attach your `.sanitized.har.gz`
- If you ran the AI screen, include the output block in your issue
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

## Resources

- Browse [existing modem request issues](https://github.com/solentlabs/cable_modem_monitor/issues?q=label%3A%22new+modem%22)
  for examples
- See the [modem catalog](../packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/)
  for currently supported modems
