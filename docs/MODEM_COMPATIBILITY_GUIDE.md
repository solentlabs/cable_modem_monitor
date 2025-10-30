***REMOVED*** Modem Compatibility Guide

Help us support your cable modem! This guide explains how to provide information that will help add support for your modem model.

***REMOVED******REMOVED*** Currently Supported Modems

This integration relies on community contributions for modem support. Compatibility can vary based on firmware versions and ISP customizations.

***REMOVED******REMOVED******REMOVED*** ✅ Confirmed Working
These models are actively tested or have been confirmed to work reliably by the community.

- **Motorola MB Series**: MB7420, MB7621, MB8600, MB8611
- **ARRIS SB6141**

***REMOVED******REMOVED******REMOVED*** ⚠️ Community Reported (Mixed Results)
These models have been reported to work by some users, but have also had reports of issues. They are not actively tested and may not work for everyone. Use the "auto" detection or select your model during configuration.

- **Arris SB6183**
- **Arris SB8200**

***REMOVED******REMOVED******REMOVED*** 🧪 Experimental / Untested
Parsers for these models exist in the code, but they have not been fully validated by the community. They may be incomplete or may not work at all.

- **Technicolor TC4400**
- **Technicolor XB7 (CGM4331COM)**

***REMOVED******REMOVED******REMOVED*** ❌ Known Incompatible
- None reported yet.

**Note:** Many other modems may work if they use similar web interface formats. If your modem doesn't work, please share an HTML sample!

---

***REMOVED******REMOVED*** Acknowledgments

Research for modem compatibility has been aided by:
- **philfry's check_tc4400** (https://github.com/philfry/check_tc4400) - TC4400 monitoring script that helped identify the modem's web interface structure and `/cmconnectionstatus.html` endpoint

---

***REMOVED******REMOVED*** Is Your Modem Compatible?

Your modem is likely compatible if it has:
1. ✅ A web interface (accessible via browser at http://192.168.100.1 or similar)
2. ✅ A status page showing channel information
3. ✅ Power levels, SNR, and frequency data displayed

---

***REMOVED******REMOVED*** How to Help Add Support for Your Modem

If the integration doesn't work with your modem, you can help us add support! Follow these steps:

***REMOVED******REMOVED******REMOVED*** Step 1: Check Your Modem's Web Interface

1. Open a web browser
2. Go to your modem's IP address (usually `http://192.168.100.1` or `http://192.168.0.1`)
3. Log in if required (check the label on your modem for credentials)
4. Look for a page showing:
   - Downstream channels
   - Upstream channels
   - Power levels (dBmV)
   - SNR (Signal-to-Noise Ratio)
   - Frequency

**Can you see this data?** → Great! Continue to Step 2.
**No web interface or no channel data?** → Unfortunately, your modem may not be compatible.

***REMOVED******REMOVED******REMOVED*** Step 2: Identify the Status Page URL

Look at your browser's address bar when viewing the channel data. Common URLs:
- `http://192.168.100.1/cmconnectionstatus.html` (Technicolor)
- `http://192.168.100.1/MotoConnection.asp` (Motorola)
- `http://192.168.100.1/cgi-bin/status` (Various)

**Write down the exact URL** - we'll need this!

***REMOVED******REMOVED******REMOVED*** Step 3: Capture the HTML Source

***REMOVED******REMOVED******REMOVED******REMOVED*** Option A: Using Browser (Easiest)

1. On the status page, right-click and select **"View Page Source"** (or press `Ctrl+U`)
2. You'll see HTML code
3. **Save this file:**
   - `Ctrl+S` or File → Save As
   - Name it: `[ModemBrand]_[Model]_status.html`
   - Example: `Technicolor_TC4400_status.html`

***REMOVED******REMOVED******REMOVED******REMOVED*** Option B: Using curl (More Technical)

```bash
***REMOVED*** Replace IP and URL with your modem's details
curl http://192.168.100.1/cmconnectionstatus.html -o modem_status.html

***REMOVED*** If authentication required:
curl -u admin:password http://192.168.100.1/cmconnectionstatus.html -o modem_status.html
```

***REMOVED******REMOVED******REMOVED*** Step 4: Sanitize the HTML (Important!)

Before sharing, **remove any personal information:**

1. Open the HTML file in a text editor
2. Look for and remove/replace:
   - ❌ Your modem's MAC address
   - ❌ Your public IP address
   - ❌ Any account numbers or identifiers
   - ❌ ISP-specific information you want private

**The signal data (power levels, SNR, frequencies) is fine to share** - that's what we need!

***REMOVED******REMOVED******REMOVED*** Step 5: Share the Information

Create a GitHub issue with this information:

**Go to:** https://github.com/kwschulz/cable_modem_monitor/issues/new

**Title:** `Add support for [Modem Brand] [Model]`

**Issue Template:**

```markdown
***REMOVED******REMOVED*** Modem Information

**Brand:** [e.g., Technicolor]
**Model:** [e.g., TC4400]
**ISP:** [Optional - e.g., Spectrum, Comcast]

***REMOVED******REMOVED*** Web Interface Details

**Modem IP Address:** [e.g., 192.168.100.1]
**Status Page URL:** [e.g., http://192.168.100.1/cmconnectionstatus.html]
**Authentication Required:** [Yes/No]
**Default Credentials:** [If known and not changed by ISP]

***REMOVED******REMOVED*** HTML Sample

I've attached the HTML source from my modem's status page.

[Attach the sanitized HTML file you saved]

***REMOVED******REMOVED*** Additional Notes

[Any other relevant information - e.g., "ISP changed default password", "Only accessible after reboot", etc.]
```

***REMOVED******REMOVED******REMOVED*** Step 6: Attach the HTML File

Drag and drop the sanitized HTML file into the GitHub issue to attach it.

---

***REMOVED******REMOVED*** Alternative: Enable Debug Logging

If you're comfortable with Home Assistant configuration:

***REMOVED******REMOVED******REMOVED*** Add Debug Logging

1. Edit your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.cable_modem_monitor: debug
```

2. Restart Home Assistant
3. Try to add the Cable Modem Monitor integration (it will fail)
4. Go to **Settings → System → Logs**
5. Look for entries with `cable_modem_monitor`
6. Copy the relevant log entries

***REMOVED******REMOVED******REMOVED*** Share the Logs

Create a GitHub issue and paste the debug logs. This shows us:
- What URL the integration tried to access
- What HTML structure it found
- Why parsing failed

**Important:** Logs may contain sensitive info - review before sharing!

---

***REMOVED******REMOVED*** What Happens Next?

1. **We review your submission** - Usually within a few days
2. **We analyze the HTML structure** - Different modems use different layouts
3. **We decide on feasibility:**
   - ✅ **Doable** - We'll add support in a future version
   - 🤔 **Needs more info** - We might ask follow-up questions
   - ❌ **Too different** - We'll explain why it's not feasible

4. **You get notified** - We'll comment on the issue with updates

---

***REMOVED******REMOVED*** Why Some Modems Might Not Be Supported

**Reasons we might not be able to add support:**

1. **No Web Interface** - Some modems don't have accessible web pages
2. **ISP Locked** - Some ISPs disable the web interface
3. **Non-Standard Format** - Data presented in ways that are very difficult to parse
4. **Requires JavaScript** - If the page uses heavy JavaScript to load data dynamically
5. **Limited Demand** - If only 1-2 people request a rare modem model

We'll always be honest about feasibility!

---

***REMOVED******REMOVED*** Quick Reference: Modem Information Checklist

Before creating an issue, gather:
- [ ] Modem brand and model number
- [ ] Status page URL (full web address)
- [ ] HTML source file (sanitized)
- [ ] Authentication details (if applicable)
- [ ] Screenshots of status page (optional but helpful)

---

***REMOVED******REMOVED*** Community Contributions Welcome!

**Are you a developer?** You can contribute modem support directly!

1. Fork the repository
2. Add parsing logic for your modem in `modem_scraper.py`
3. Add test fixtures in `tests/fixtures/`
4. Create a pull request

See `CONTRIBUTING.md` for developer guidelines.

---

***REMOVED******REMOVED*** FAQ

**Q: Will my personal information be exposed?**
A: No, as long as you sanitize the HTML file. Remove MAC addresses, IPs, and account numbers before sharing.

**Q: How long does it take to add support?**
A: Depends on complexity. Simple cases: 1-2 weeks. Complex cases: longer or may not be feasible.

**Q: Can I pay to prioritize my modem?**
A: This is a free open-source project. However, if you have development skills, we welcome pull requests!

**Q: My ISP changed the default password - should I share it?**
A: No! Never share your actual password. Just note that authentication is required.

**Q: The web interface requires JavaScript to load data. Will it work?**
A: Probably not easily. The integration parses static HTML. Dynamic JavaScript content is harder to support.

---

***REMOVED******REMOVED*** Success Stories

Once we add support for your modem, you'll be able to:
- ✅ Monitor signal quality in real-time
- ✅ Track historical trends
- ✅ Set up automations and alerts
- ✅ Have data when calling your ISP

**Your contribution helps everyone with the same modem model!** 🙌

---

***REMOVED******REMOVED*** Contact

- **GitHub Issues:** https://github.com/kwschulz/cable_modem_monitor/issues
- **GitHub Discussions:** https://github.com/kwschulz/cable_modem_monitor/discussions

Thank you for helping expand modem compatibility!
