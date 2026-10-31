# Requesting Support for Your Modem

Modem not listed? Send a capture of its web interface. A maintainer or
contributor builds support from it, and you test it on your hardware.

Comfortable with AI tools and want to do more of the work yourself? See
the [AI-assisted catalog contribution guide](../CONTRIBUTING.md#ai-assisted-catalog-contribution).

The integration reads channel data, error counts, connection status,
firmware and uptime; never WiFi settings, device lists or account
details.

## If an AI agent is helping

- Say which tool and model helped, in the issue.
- Capture with `har-capture` (section 1). A browser DevTools export has
  no cookies and loses login values the catalog needs.
- Do not send a failed login to the device outside step 6 of the
  capture.
- File through the [issue form](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml)
  in a browser, not the API. The form carries the capture instructions
  and the file upload.
- Report what you observed on the device or in the logs, and mark
  anything inferred.

## 1. Capture

```bash
pip install "har-capture[full]"
har-capture 192.168.100.1 --patterns network-device
```

Use your modem's IP if it differs. For HTTP Basic Auth, add
`--username` and `--password`
([CLI reference](https://github.com/solentlabs/har-capture#quick-start)).

A browser opens. Work through these steps in it, in order.

1. **Open a status page directly.**

   - Type its address into the address bar, for example
     `192.168.100.1/DocsisStatus.htm`.
   - Seeing the login page is expected.
   - *Why: it shows how the modem answers when a session has expired.*

2. **Log in with the real password.**

   - Wait for the next page to finish loading.
   - *Why: that page is how the integration confirms a login worked.*

3. **Visit every status page.**

   - Wait 3 to 5 seconds on each.
   - *Why: some data loads after the page appears.*

4. **Click any button that loads more data.**

   - Examples: Refresh, More, Show channels.
   - Click each one once.
   - *Why: on some modems that button fetches data the page load does
     not.*

5. **Log out.**

   - *Why: modems that allow one login at a time need this to release
     the session.*

6. **Log in with a wrong password, once.**

   - Do this last.
   - The wrong guess is redacted.
   - *Why: some modems lock the account after a failed login. On some,
     a rejected login looks just like a success, and this can't be
     recorded later.*

Then close the browser. The result is a `.sanitized.har.gz` file.

### Capture a restart

- Do this if your modem has a Reboot or Restart control.
- The integration's Restart button needs it.
- Your internet drops for a few minutes.

1. **Run the `har-capture` command again.**

   - This is a second capture.

2. **Log in, then click Reboot or Restart.**

   - Close the browser once the click is sent.

3. **Attach this file to the same issue as the first.**

## 2. Check for personal data

har-capture redacts MAC addresses, serial numbers, public IPs and known
password fields, but can miss WiFi credentials in unusual places. Local
addresses like `192.168.100.1` are kept on purpose. Check the file
with either:

- an [AI prompt](examples/har-pii-screen-prompt.md) (faster), or
- a [manual checklist](examples/har-pii-manual-checklist.md) (5 minutes).

If you find anything:

1. Replace it with `***REDACTED***` and save.
2. Re-gzip: `gzip -kf -9 your-file.sanitized.har`
3. Check that the edited file still matches the `.gz`, and scan for
   known personal-data patterns (MACs, serials, IPs, emails, passwords,
   tokens). A clean scan can't prove nothing slipped through:
   `har-capture validate your-file.sanitized.har --patterns network-device`
4. Say what you redacted in your issue, so the redaction rules can be
   improved.

## 3. Submit

Open a [Modem Request issue](https://github.com/solentlabs/cable_modem_monitor/issues/new?template=modem_request.yml),
fill in the model and manufacturer, and attach the `.sanitized.har.gz`.
Include the AI screen output if you ran it.

Optional: the [HAR audit prompt](../CONTRIBUTING.md#auditing-a-har-for-completeness)
checks a capture for missing login steps before you submit.

## 4. Test the beta

The maintainer comments when a beta with your modem is out.

1. In HACS, open Cable Modem Monitor, choose **Redownload**, click
   **Need a different version?** and pick the version named in the
   comment from the **Release** dropdown.
2. Restart Home Assistant.
3. Add the integration and select your modem from the list.
4. Download diagnostics (Settings, Devices & services, Cable Modem
   Monitor, the three-dot menu) and attach the file to the issue.

For examples, see [past modem requests](https://github.com/solentlabs/cable_modem_monitor/issues?q=label%3A%22new+modem%22)
and the [modem catalog](../packages/cable_modem_monitor_catalog/solentlabs/cable_modem_monitor_catalog/modems/).
