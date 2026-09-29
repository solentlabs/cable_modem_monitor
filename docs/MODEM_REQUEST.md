# Requesting Support for Your Modem

Modem not listed? Send a capture of its web interface. A maintainer or
contributor builds support from it, and you test it on your hardware.

Comfortable with AI tools and want to do more of the work yourself? See
the [AI-assisted catalog contribution guide](../CONTRIBUTING.md#ai-assisted-catalog-contribution).

The integration reads channel data, error counts, connection status,
firmware and uptime; never WiFi settings, device lists or account
details.

## 1. Capture

```bash
pip install "har-capture[full]"
har-capture 192.168.100.1 --patterns network-device
```

Use your modem's IP if it differs. For HTTP Basic Auth, add
`--username` and `--password`
([CLI reference](https://github.com/solentlabs/har-capture#quick-start)).

A browser opens. Work through these steps in it, in order.

### Before logging in

**Step 1. Open a status page directly.** Type its address into the
address bar, for example `192.168.100.1/DocsisStatus.htm`.
*Seeing the login page is expected: it shows how the modem answers
when a session has expired.*

### Logging in

**Step 2. Log in with a wrong password.**
*On some modems a rejected login looks just like a success, and this
can't be recorded later. The wrong guess is redacted.*

**Step 3. Log in with the real password, and wait for the next page
to finish loading.**
*That page is how the integration confirms a login worked.*

### Collecting data

**Step 4. Visit every status page, waiting 3–5 seconds on each.**
*Some data loads after the page appears.*

**Step 5. If a page has a Refresh button, click it once.**
*On some modems it fetches data differently from the page load.*

### Finishing

**Step 6. Log out.**
*Modems that allow one login at a time need this to release the
session.*

**Step 7 (optional). Capture a restart.** Log back in, click Reboot or
Restart, and close the browser once the click is sent.
*Needed for the integration's Restart button. Your internet drops for
a few minutes.*

The result is a `.sanitized.har.gz` file.

## 2. Check for personal data

har-capture redacts MAC addresses, serial numbers, public IPs and known
password fields, but can miss WiFi credentials in unusual places. Local
addresses like `192.168.100.1` are kept on purpose. Check the file
with either:

- an [AI prompt](examples/har-pii-screen-prompt.md) (faster), or
- a [manual checklist](examples/har-pii-manual-checklist.md) (5 minutes).

If you find anything:

1. Replace it with `***REDACTED***` and save.
2. Re-gzip: `gzip -kf -9 yourfile.sanitized.har`
3. Confirm the files are clean and match:
   `har-capture validate yourfile.sanitized.har --patterns network-device`
4. Say what you redacted in your issue, so the redaction rules can be
   improved.

## 3. Submit

Open a [Modem Request issue](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml),
fill in the model and manufacturer, and attach the `.sanitized.har.gz`.
Include the AI screen output if you ran it.

For examples, see [past modem requests](https://github.com/solentlabs/cable_modem_monitor/issues?q=label%3A%22new+modem%22)
and the [modem catalog](../packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/).
