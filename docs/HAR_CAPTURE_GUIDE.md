# HAR Capture Guide for Modem Diagnostics

This guide explains how to capture HTTP Archive (HAR) files from your modem to help developers add support for your model or fix authentication issues.

## Why HAR?

HAR files capture the **complete HTTP conversation** with your modem:
- Full request/response headers
- Authentication flow (login sequence)
- Cookies and session data
- All page content

This is much more useful than just HTML because we can see **how** your browser successfully authenticated.

---

## Method 1: Capture Script (Recommended)

The easiest and most reliable method. Works on any OS with Python.

### VS Code (One-Click)

If you're using VS Code with this project:

1. Press **Ctrl+Shift+P** → **Tasks: Run Task**
2. Select **"📹 Capture Modem Traffic"**
3. Enter your modem's IP when prompted (default: `192.168.100.1`)

### Command Line

**One-time setup:**
```bash
pip install playwright
playwright install chromium
```

**Capture:**
```bash
python scripts/capture_modem.py
```

**What happens:**
1. A browser window opens to your modem (default: `http://192.168.100.1`)
2. **Log in normally** - you handle authentication, the script just records
3. Navigate to the DOCSIS status / signal pages
4. Close the browser window
5. Script automatically:
   - Removes bloat (fonts, images, duplicates)
   - Sanitizes PII (passwords, MACs, etc.)
   - Compresses the output (~99% smaller)

**Options:**
```bash
# Different modem IP
python scripts/capture_modem.py --ip 192.168.0.1

# Specify output filename
python scripts/capture_modem.py --output my_modem.har

# Use Firefox instead of Chromium
python scripts/capture_modem.py --browser firefox
```

The compressed file (`.sanitized.har.gz`) is safe to share in a GitHub issue.

---

## Method 2: Browser DevTools

If you can't install Python/Playwright, you can capture manually using browser DevTools.

### Firefox (Recommended for Manual Capture)

Firefox provides the most reliable HAR export with full response content.

1. Open your modem's web interface: `http://192.168.100.1`
2. Press **F12** to open DevTools (or **Ctrl+Shift+I** on ChromeOS)
3. Click the **Network** tab
4. Click the gear icon → Check **Persist Logs**
5. **Log into your modem** normally
6. Navigate to the **DOCSIS Status** or signal page
7. Right-click in the Network panel → **Save All As HAR**
8. **Sanitize the HAR file** (removes passwords and personal info):
   ```bash
   python scripts/sanitize_har.py your_capture.har
   ```
9. Attach `your_capture.sanitized.har` to your GitHub issue

### Chrome / Edge (Limited Support)

> ⚠️ **Known Limitation**: Chrome only retains response bodies for the most recently loaded page. Earlier pages in your session will be missing their HTML content. **Use Firefox for reliable HAR capture.**

Chrome can still be useful for capturing **authentication flow** (login requests, redirects, cookies) even without full page content.

**One-time setup:**
1. Open DevTools (**Ctrl+Shift+I** on ChromeOS, **F12** on Windows/Mac)
2. Click the **gear icon** (Settings) in DevTools
3. Go to **Preferences** → **Network**
4. Enable **"Allow to generate HAR with sensitive data"**

**Capture steps:**
1. Open your modem's web interface: `http://192.168.100.1`
2. Open DevTools (**Ctrl+Shift+I** or **F12**)
3. Click the **Network** tab
4. Check **Preserve log** and **Disable cache**
5. **Log into your modem** normally
6. Navigate to the **DOCSIS Status** or signal page
7. Click the **download icon** (tooltip: "Export HAR...")
8. Select **"Export HAR (with sensitive data)"**
9. **Sanitize the HAR file** (removes passwords and personal info):
   ```bash
   python scripts/sanitize_har.py your_capture.har
   ```
10. Attach `your_capture.sanitized.har` to your GitHub issue

*Note: If you only have Chrome available, the auth flow data is still valuable for developers.*

---

## Alternative: Use the Integration's Capture Button

If you already have the integration installed:

1. Go to **Settings → Devices & Services → Cable Modem**
2. Press the **"Capture HTML"** button
3. Wait for notification (~5-10 seconds)
4. **Download diagnostics** within 5 minutes:
   - Settings → Devices → Find "Cable Modem"
   - Click the menu → **Download diagnostics**
5. Attach the JSON file to your GitHub issue

*Note: This captures HTML but not headers/auth flow. Use browser capture for authentication issues.*

---

## What Gets Sanitized?

For your privacy, the following is automatically removed:

| Removed | Replaced With |
|---------|---------------|
| Passwords in forms | `[REDACTED]` |
| Cookie values | `[REDACTED]` |
| Authorization headers | `[REDACTED]` |
| MAC addresses | `XX:XX:XX:XX:XX:XX` |
| Serial numbers | `***REDACTED***` |
| Private IPs (except modem) | `***PRIVATE_IP***` |
| Public IPs | `***PUBLIC_IP***` |
| Email addresses | `***EMAIL***` |

**Preserved** (needed for parser development):
- Form field **names** (not values)
- URL structure (including query params like `?id=XXX`)
- Response status codes
- Page content structure
- Channel data tables
- Signal levels

---

## What Happens Next?

1. **User shares** sanitized HAR in a GitHub issue
2. **Developer analyzes** the authentication flow
3. **Developer generates** fixtures and test stubs
4. **Developer builds** the parser
5. **New version released** with modem support
6. **User verifies** it works

---

## Privacy & Security

- All processing is **local** (no data sent anywhere)
- Passwords are **never** stored in sanitized files
- You control what you upload
- Open source - review the code anytime

---

## Troubleshooting

### HAR file is missing page content

If developers report that your HAR file is missing response content, common causes are:

1. **Used Chrome** - Chrome only retains response bodies for the last page loaded, not the full session. This is a known Chrome limitation.
2. **Used Chrome's "Export HAR (sanitized)"** - This strips all response bodies.
3. **Didn't navigate to status page** - Make sure to visit the DOCSIS/signal status page before exporting.

**Solution**: Use **Method 1 (capture script)** or **Firefox** for reliable HAR capture.

### DevTools won't open with F12

On ChromeOS, use **Ctrl+Shift+I** instead of F12.

### Right-click doesn't work

On ChromeOS and some touchpad configurations, use a **two-finger tap** instead of right-click.

---

## Questions?

- Open a GitHub issue with your sanitized HAR file
- Include your modem model and ISP
- Describe any errors you encountered

Thank you for helping expand modem support!
