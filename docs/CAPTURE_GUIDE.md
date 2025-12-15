# Capture Guide for Modem Diagnostics

> **Looking to submit a modem request?** See [MODEM_REQUEST.md](MODEM_REQUEST.md) for the complete guide including PII review checklist and submission process.

This guide provides technical details on capture methods and troubleshooting.

## Which Method Should I Use?

| Modem Type | Use This Method |
|------------|-----------------|
| HTML-based modems (SB6141, SB8200, etc.) | Either method works |
| [HNAP](https://en.wikipedia.org/wiki/Home_Network_Administration_Protocol)/API modems (MB8611, S33, etc.) | [HAR Capture Script](#method-2-har-capture-script) **required** |
| Authentication issues / new modem | [HAR Capture Script](#method-2-har-capture-script) |

> **Why HNAP modems need HAR:** These modems load data via JavaScript API calls after the page loads. The Integration Capture only sees the HTML shell, not the API responses. [HAR](http://www.softwareishard.com/blog/har-12-spec/) captures the full HTTP conversation including these async calls.

---

## Method 1: Integration Capture Button

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

## Method 2: HAR Capture Script

**Best for:** Authentication issues, capturing full HTTP conversation including login flow.

[HAR (HTTP Archive)](http://www.softwareishard.com/blog/har-12-spec/) files capture the complete HTTP conversation - headers, cookies, auth flow, and content.

### VS Code (One-Click)

1. Press **Ctrl+Shift+P** → **Tasks: Run Task**
2. Select **"📹 Capture Modem Traffic"**
3. Enter your modem's IP when prompted

### Command Line

```bash
# One-time setup
pip install playwright
playwright install chromium

# Capture
python scripts/capture_modem.py

# Options
python scripts/capture_modem.py --ip 192.168.0.1
python scripts/capture_modem.py --browser firefox
```

**What happens:**
1. Browser opens to your modem (cache disabled for fresh data)
2. Log in normally - script just records
3. Navigate to DOCSIS status pages
4. **Wait 3-5 seconds on each page** for async data to load
5. Close browser - script sanitizes and compresses output

The `.sanitized.har.gz` file is safe to share.

> **Important:** Many modems fetch data asynchronously via JavaScript after the page loads. If you navigate too quickly, these API calls won't be captured. Wait a few seconds on each page, especially the Connection Status page.

---

## What Gets Sanitized?

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

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Connection error | Check modem IP, verify same network |
| No pages captured | Try accessing modem in browser first |
| HAR missing content | Use Firefox instead of Chrome |
| Auth required | Re-run with username/password |

---

## What Happens Next?

1. You share the capture in a GitHub issue
2. Developer analyzes the structure and auth flow
3. Developer may request additional captures (common!)
4. Parser built and tested against your samples
5. You verify it works on your actual modem

### Pages to Capture

For a complete parser, we typically need:

| Page Type | What It Contains |
|-----------|------------------|
| **Status/DOCSIS page** | Channel data (power, SNR, frequency) |
| **System info page** | Uptime, firmware version, model |
| **Login flow** | Authentication mechanism |

**Tip:** Navigate through your modem's menu during capture - more pages = fewer follow-ups.

### Expect Iteration

Most new modem support requires 2-3 rounds of captures as we discover:
- Additional pages with useful data
- Edge cases in the HTML structure
- Authentication quirks

This is normal! Quick responses to follow-up requests speed up the process.
