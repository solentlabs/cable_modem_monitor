***REMOVED*** Capture Guide for Modem Diagnostics

This guide explains how to capture data from your modem to help developers add support for your model.

***REMOVED******REMOVED*** Which Method Should I Use?

| Situation | Use This Method |
|-----------|-----------------|
| Integration already installed | [Integration Capture Button](***REMOVED***method-1-integration-capture-button) |
| Adding a new modem / need auth flow | [HAR Capture Script](***REMOVED***method-2-har-capture-script) |

---

***REMOVED******REMOVED*** Method 1: Integration Capture Button

**Best for:** Users with the integration installed (even with limited functionality).

1. Go to **Settings → Devices & Services → Cable Modem**
2. Press the **"Capture HTML"** button
3. Wait for notification (~5-10 seconds)
4. **Download diagnostics** within 5 minutes:
   - Settings → Devices → Find "Cable Modem"
   - Click menu (⋮) → **Download diagnostics**
5. Attach the JSON file to your GitHub issue

**What gets captured:** All modem pages, automatically sanitized (MACs, serials, IPs removed).

---

***REMOVED******REMOVED*** Method 2: HAR Capture Script

**Best for:** Authentication issues, capturing full HTTP conversation including login flow.

HAR (HTTP Archive) files capture the complete HTTP conversation - headers, cookies, auth flow, and content.

***REMOVED******REMOVED******REMOVED*** VS Code (One-Click)

1. Press **Ctrl+Shift+P** → **Tasks: Run Task**
2. Select **"📹 Capture Modem Traffic"**
3. Enter your modem's IP when prompted

***REMOVED******REMOVED******REMOVED*** Command Line

```bash
***REMOVED*** One-time setup
pip install playwright
playwright install chromium

***REMOVED*** Capture
python scripts/capture_modem.py

***REMOVED*** Options
python scripts/capture_modem.py --ip 192.168.0.1
python scripts/capture_modem.py --browser firefox
```

**What happens:**
1. Browser opens to your modem
2. Log in normally - script just records
3. Navigate to DOCSIS status pages
4. Close browser - script sanitizes and compresses output

The `.sanitized.har.gz` file is safe to share.

---

***REMOVED******REMOVED*** What Gets Sanitized?

| Removed | Replaced With |
|---------|---------------|
| Passwords | `[REDACTED]` |
| Cookie values | `[REDACTED]` |
| MAC addresses | `XX:XX:XX:XX:XX:XX` |
| Serial numbers | `***REDACTED***` |
| Private IPs | `***PRIVATE_IP***` |
| Public IPs | `***PUBLIC_IP***` |

**Preserved** (needed for parser development):
- Channel tables and structure
- Signal levels (frequency, power, SNR)
- Form field names (not values)
- HTML structure and CSS classes
- Software version and uptime

---

***REMOVED******REMOVED*** Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection error | Check modem IP, verify same network |
| No pages captured | Try accessing modem in browser first |
| HAR missing content | Use Firefox instead of Chrome |
| Auth required | Re-run with username/password |

---

***REMOVED******REMOVED*** What Happens Next?

1. You share the capture in a GitHub issue
2. Developer analyzes the structure and auth flow
3. Developer may request additional captures (common!)
4. Parser built and tested against your samples
5. You verify it works on your actual modem

***REMOVED******REMOVED******REMOVED*** Pages to Capture

For a complete parser, we typically need:

| Page Type | What It Contains |
|-----------|------------------|
| **Status/DOCSIS page** | Channel data (power, SNR, frequency) |
| **System info page** | Uptime, firmware version, model |
| **Login flow** | Authentication mechanism |

**Tip:** Navigate through your modem's menu during capture - more pages = fewer follow-ups.

***REMOVED******REMOVED******REMOVED*** Expect Iteration

Most new modem support requires 2-3 rounds of captures as we discover:
- Additional pages with useful data
- Edge cases in the HTML structure
- Authentication quirks

This is normal! Quick responses to follow-up requests speed up the process.
