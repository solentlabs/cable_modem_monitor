***REMOVED*** Capture Guide for Modem Diagnostics

This guide explains how to capture data from your modem to help developers add support for your model.

***REMOVED******REMOVED*** Which Method Should I Use?

| Situation | Use This Method |
|-----------|-----------------|
| Integration already installed | [Integration Capture Button](***REMOVED***method-1-integration-capture-button) |
| Need to capture login/auth flow | [HAR Capture Script](***REMOVED***method-2-har-capture-script) |
| Can't install anything | [Browser DevTools](***REMOVED***method-3-browser-devtools) |
| Standalone (no integration) | [HTML Capture Script](***REMOVED***method-4-html-capture-script) |

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

HAR files capture the complete HTTP conversation - headers, cookies, auth flow, and content.

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

***REMOVED******REMOVED*** Method 3: Browser DevTools

**Best for:** When you can't install Python/Playwright.

***REMOVED******REMOVED******REMOVED*** Firefox (Recommended)

Firefox provides the most reliable HAR export.

1. Open modem: `http://192.168.100.1`
2. Press **F12** → **Network** tab
3. Click gear → Check **Persist Logs**
4. Log into modem, navigate to status page
5. Right-click in Network panel → **Save All As HAR**
6. Sanitize: `python scripts/sanitize_har.py your_capture.har`
7. Attach sanitized file to GitHub issue

***REMOVED******REMOVED******REMOVED*** Chrome/Edge (Limited)

> ⚠️ Chrome only retains response bodies for the last page. Use Firefox for complete captures.

Chrome is still useful for capturing authentication flow (login requests, cookies).

1. Open DevTools → Settings → Network
2. Enable **"Allow to generate HAR with sensitive data"**
3. Open modem, enable **Preserve log** and **Disable cache**
4. Log in and navigate to status page
5. Click download icon → **Export HAR (with sensitive data)**
6. Sanitize before sharing

---

***REMOVED******REMOVED*** Method 4: HTML Capture Script

**Best for:** Standalone capture when integration isn't installed.

```bash
python3 tools/capture_modem_html.py
```

Follow prompts for IP and credentials. Creates a sanitized ZIP file.

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
2. Developer analyzes the structure/auth flow
3. Developer builds parser with your samples as fixtures
4. New version released with your modem support
5. You verify it works

**Typical timeline:** 2-6 hours of development once capture is provided.
