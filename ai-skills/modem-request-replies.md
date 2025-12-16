# Modem Request Issue Replies

Standard response templates for new modem support requests on cable_modem_monitor.

## Workflow Overview

1. **Triage** - Is the data actionable?
2. **Assess** - Auth complexity? Similar to existing parser?
3. **Respond** - Use appropriate template
4. **Iterate** - Development usually takes multiple rounds

---

## Part 1: Initial Acknowledgment + Triage

Use this immediately when a new request comes in:

```markdown
Thanks for submitting this request! 🎉

Let me check what we have to work with:

**Data Review:**
- [ ] Attachment present and accessible
- [ ] Contains status/channel pages (not just login)
- [ ] Auth type identified

I'll review what you've sent and follow up shortly.
```

---

## Part 2: Response Templates

### 2a: Data looks good - proceeding

```markdown
**Assessment:**
- Modem: [MODEL] ([MANUFACTURER])
- Auth: [Basic/None/Form] → [straightforward / moderate complexity]
- Similar to: [existing parser if applicable]
- Status pages: Found [list pages]

**What happens next:**
1. I'll develop a parser (timing varies based on complexity)
2. Tag you for testing once there's a working draft

These requests often take a few iterations - first pass gets basic data working, then we refine based on your testing. The more responsive you can be with feedback, the faster we can get your modem supported.

I'll follow up here with progress.
```

### 2b: Need more data - missing HTML capture

```markdown
**What's missing:** The diagnostics don't include `raw_html_capture` data.

This usually means the "Capture HTML" button wasn't clicked before downloading diagnostics. Could you try again?

1. Go to your modem device in Home Assistant
2. Click the **"Capture HTML"** button and wait for confirmation
3. Then click the three-dot menu → **Download Diagnostics**
4. Attach the new JSON file here

This captures the actual HTML pages I need to build the parser.
```

### 2c: Need more data - HAR quality concerns

```markdown
**About the HAR capture:**

I noticed you used [Chrome's built-in HAR export / manual capture]. This can work, but our [capture script](https://github.com/solentlabs/cable_modem_monitor/blob/main/docs/MODEM_REQUEST.md#-method-2-har-capture-for-authentication-issues) has advantages:
- Automatic PII sanitization (passwords, MACs, serials)
- Disables browser caching (captures all async requests)
- Compresses output

I'll review what you sent and see if it has what I need. If the status pages are missing or incomplete, I may ask for a re-capture with the script.
```

### 2d: Auth complexity detected (HNAP/SOAP)

```markdown
**Assessment:**
- Modem: [MODEL] ([MANUFACTURER])
- Auth: Appears to use **HNAP/SOAP** authentication

This is more complex than standard HTML parsing. HNAP modems (like Motorola MB8611, Arris S33) require understanding the authentication handshake, which typically means:

1. **HAR capture** to trace the auth flow
2. **Multiple rounds** of testing and fixes

Could you run the HAR capture script? This records the full browser session:

```bash
git clone https://github.com/solentlabs/cable_modem_monitor.git
cd cable_modem_monitor
pip install playwright && playwright install chromium
python scripts/capture_modem.py --ip [YOUR_MODEM_IP]
```

Log in normally, navigate to the status/connection pages, then close the browser. Attach the resulting `.sanitized.har.gz` file here.

Fair warning: HNAP parsers typically take longer and require more back-and-forth than simple HTML parsers. But we've done several successfully (MB8611, S33), so it's definitely doable.
```

### 2e: Blocked on sanitization / PII concerns

```markdown
**Thanks for flagging the PII concern!**

You're right to be cautious. Before re-uploading, please:

1. Update to the latest version (v[X.X.X])
2. Re-capture using the "Capture HTML" button
3. **Before attaching**, search the JSON file for:
   - Your WiFi network name (SSID)
   - Your WiFi password
   - Any other personal info

If you find anything that should have been sanitized, let me know what pattern it was in and I'll improve the sanitizer.
```

---

## Closing Responses

### Parser released - request testing

```markdown
**Good news!** I've added initial support for the [MODEL] in v[X.X.X].

Could you test it?
1. Update the integration to v[X.X.X]
2. Remove your current modem device
3. Re-add it (should auto-detect as [MODEL])

Let me know:
- [ ] Does it connect and show channel data?
- [ ] Are the values reasonable (power, SNR, frequencies)?
- [ ] Does restart work? (if applicable)

If anything's broken, share the error logs and I'll fix it in the next release.
```

### Issue resolved

```markdown
Glad it's working! 🎉

I've marked the [MODEL] parser as verified. Thanks for your patience through the testing process - your feedback helped catch [specific issues fixed].

Feel free to close this issue, or leave it open if you notice any other problems.
```

---

## Notes

- **Engaged users are gold** - prioritize requests where users respond quickly
- **Auth is the hard part** - set expectations early for HNAP/SOAP modems
- **Multiple iterations are normal** - S33 took 13+ comments, CM2000 took several rounds
- **Similar modems help** - if it's Netgear, check CM600/CM2000 patterns first
