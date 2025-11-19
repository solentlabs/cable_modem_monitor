# HTML Capture for Diagnostics

## Overview

Add optional HTML capture to diagnostics to help developers add support for new modems and debug parsing issues.

## Status

**Planned for Phase 4**
**Priority:** High (enables community parser development)

## Problem Statement

Currently, when a modem is unsupported or parsing fails:
1. Users cannot install the integration (blocked)
2. Developers cannot get HTML samples to build parsers
3. Requires manual HTML capture and sharing
4. Slows down community contributions

## Proposed Solution

### **Phase 1: Button Entity (Existing Installations)**

Add a button entity to capture HTML on demand:

**Entity:** `button.cable_modem_monitor_capture_html`

**Behavior:**
- Fetches HTML from modem pages
- Applies heavy sanitization (removes MAC, serial, private IPs)
- Triggers browser download as ZIP file
- Works even if parsing is failing
- No disk storage required

**User Flow:**
1. User presses button in UI
2. Integration captures ~7 core pages
3. Browser downloads `modem_html_capture_20251108.zip`
4. User attaches to GitHub issue

### **Phase 2: Failed Setup Flow (New Installations)**

When auto-detection fails during setup, offer to help:

**New config flow step:** `async_step_unsupported_modem`

**User Experience:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Modem Not Supported
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Your modem could not be detected. We'd love to
add support for it!

☐ Help add support for my modem
  (Captures sanitized HTML - removes MAC addresses,
   serial numbers, and private information)

[Submit]  [Cancel]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**If user opts in:**
1. HTML is captured and sanitized
2. Browser downloads file
3. Shows instructions to open GitHub issue
4. Setup is aborted (modem not supported yet)

**If user declines:**
- Setup is aborted
- No download

## Pages to Capture

### **Phase 1 - Core Pages (7 pages, ~50-150KB)**

```python
pages_to_capture = [
    # Universal attempts (no auth)
    "/",
    "/cmSignalData.htm",           # ARRIS

    # Motorola (most common)
    "/MotoConnection.asp",         # Signal data - CRITICAL
    "/MotoHome.asp",               # System info
    "/MotoSwInfo.asp",             # Software version

    # Technicolor TC4400
    "/cmconnectionstatus.html",

    # Technicolor XB7
    "/network_setup.jst",
]
```

### **Phase 2 - Extended Pages (if needed)**

```python
extended_pages = [
    "/Login.html",                 # Shows auth method
    "/cmswinfo.html",              # TC4400 software
    "/at_a_glance.jst",           # XB7 dashboard
    "/HNAP1/",                    # MB8611 HNAP
]
```

## HTML Sanitization

### **Information Removed**

**Identifiers:**
- MAC addresses: `AA:BB:CC:DD:EE:FF` → `**:**:**:**:**:MAC`
- Serial numbers: `SB6141-123456` → `SB6141-***SERIAL***`
- DOCSIS MAC, CM MAC, eMTA MAC
- Service/account IDs

**Network Info:**
- Private IP addresses (except 192.168.100.1 for context)
- IPv6 addresses
- Gateway IPs
- DNS servers

**ISP-Specific:**
- Account numbers
- Service IDs
- Provisioning codes

### **Information Preserved (for debugging)**

**Keep:**
- Channel tables and structure
- Signal levels, frequencies, SNR
- Error counts
- Modulation types
- HTML structure and tags
- Status messages
- Software version patterns
- Table headers and formatting

### **Sanitization Function**

```python
def _sanitize_html(html: str) -> str:
    """Sanitize HTML by removing personal/network identifiers."""

    # MAC addresses (multiple formats)
    html = re.sub(
        r'\b([0-9A-F]{2}[:-]){5}([0-9A-F]{2})\b',
        '**:**:**:**:**:MAC',
        html,
        flags=re.IGNORECASE
    )

    # Serial numbers (common patterns)
    html = re.sub(
        r'\b(SN|Serial|S/N)[:\s]*[\w-]+',
        r'\1: ***SERIAL***',
        html,
        flags=re.IGNORECASE
    )

    # Private IPs (keep 192.168.100.1 for context)
    html = re.sub(
        r'\b(?!192\.168\.100\.1\b)(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)\d{1,3}\.\d{1,3}\b',
        '***PRIVATE_IP***',
        html
    )

    # IPv6 addresses
    html = re.sub(
        r'\b([0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b',
        '***IPv6***',
        html,
        flags=re.IGNORECASE
    )

    # Account/service IDs
    html = re.sub(
        r'\b(Account|Service|Customer)\s*(ID|Number)[:\s]*[\w-]+',
        r'\1 \2: ***REDACTED***',
        html,
        flags=re.IGNORECASE
    )

    return html
```

## Output Structure

### **ZIP File Contents**

```
modem_html_capture_20251108_223045.zip
├── capture_info.json          # Metadata
├── MotoConnection.asp.html    # Sanitized HTML
├── MotoHome.asp.html          # Sanitized HTML
├── MotoSwInfo.asp.html        # Sanitized HTML
└── README.txt                 # Instructions
```

### **capture_info.json**

```json
{
  "modem_html_capture": {
    "host": "192.168.100.1",
    "captured_at": "2025-11-08T22:45:12",
    "integration_version": "3.0.0",
    "pages_captured": [
      {
        "path": "/MotoConnection.asp",
        "url": "http://192.168.100.1/MotoConnection.asp",
        "size_bytes": 42922,
        "auth_method": "form",
        "status_code": 200
      },
      {
        "path": "/MotoHome.asp",
        "url": "http://192.168.100.1/MotoHome.asp",
        "size_bytes": 8341,
        "auth_method": "form",
        "status_code": 200
      }
    ],
    "failed_pages": [
      {
        "path": "/cmSignalData.htm",
        "reason": "404 Not Found"
      }
    ],
    "total_pages": 2,
    "total_size_kb": 50.1,
    "sanitization_applied": true,
    "note": "All MAC addresses, serial numbers, and private IPs have been removed"
  }
}
```

## Implementation Components

### **1. Button Entity**

```python
# custom_components/cable_modem_monitor/button.py

class CaptureModemHTMLButton(CoordinatorEntity, ButtonEntity):
    """Button to capture modem HTML for support."""

    _attr_name = "Capture Modem HTML for Support"
    _attr_icon = "mdi:file-download"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Capture and download HTML."""
        try:
            # Capture HTML from modem
            html_data = await self._capture_html_pages()

            # Create ZIP file in memory
            zip_buffer = self._create_zip_file(html_data)

            # Trigger browser download
            await self._trigger_download(zip_buffer)

            # Show notification
            self.hass.components.persistent_notification.create(
                title="Modem HTML Captured",
                message=f"File downloaded successfully!\n\n"
                        f"Pages captured: {len(html_data['pages'])}\n"
                        f"Total size: {html_data['total_size_kb']:.1f} KB\n\n"
                        f"Attach this file to GitHub issues to help add modem support.",
                notification_id="cable_modem_html_capture"
            )

        except Exception as err:
            _LOGGER.error("Failed to capture modem HTML: %s", err)
            self.hass.components.persistent_notification.create(
                title="HTML Capture Failed",
                message=f"Error: {err}\n\nCheck logs for details.",
                notification_id="cable_modem_html_capture_error"
            )
```

### **2. Config Flow Enhancement**

```python
# custom_components/cable_modem_monitor/config_flow.py

async def async_step_unsupported_modem(
    self, user_input: dict[str, Any] | None = None
) -> FlowResult:
    """Handle unsupported modem - offer to help."""

    if user_input is not None:
        if user_input.get("capture_html"):
            # User wants to help - capture HTML
            try:
                html_data = await self._capture_html_pages()
                zip_buffer = self._create_zip_file(html_data)

                # Store in context for download
                self.context["html_capture"] = zip_buffer

                # Show instructions
                return await self.async_step_upload_instructions()

            except Exception as err:
                _LOGGER.error("Failed to capture HTML: %s", err)
                return self.async_abort(reason="capture_failed")
        else:
            # User doesn't want to help
            return self.async_abort(reason="unsupported_modem")

    # Show opt-in form
    return self.async_show_form(
        step_id="unsupported_modem",
        data_schema=vol.Schema({
            vol.Optional("capture_html", default=False): bool
        }),
        description_placeholders={
            "host": self._host
        }
    )
```

### **3. HTML Capture Utility**

```python
# custom_components/cable_modem_monitor/core/html_capture.py

async def capture_modem_html_pages(
    hass: HomeAssistant,
    host: str,
    username: str | None = None,
    password: str | None = None
) -> dict[str, Any]:
    """Capture HTML pages from modem.

    Args:
        hass: Home Assistant instance
        host: Modem IP address
        username: Optional authentication username
        password: Optional authentication password

    Returns:
        Dict containing captured pages and metadata
    """
    pages_to_capture = [
        "/",
        "/cmSignalData.htm",
        "/MotoConnection.asp",
        "/MotoHome.asp",
        "/MotoSwInfo.asp",
        "/cmconnectionstatus.html",
        "/network_setup.jst",
    ]

    results = {
        "host": host,
        "captured_at": datetime.now().isoformat(),
        "integration_version": VERSION,
        "pages": [],
        "failed_pages": [],
        "total_size_kb": 0,
        "sanitization_applied": True,
    }

    for page_path in pages_to_capture:
        try:
            page_data = await _capture_single_page(
                hass, host, page_path, username, password
            )
            if page_data:
                results["pages"].append(page_data)
                results["total_size_kb"] += page_data["size_bytes"] / 1024
        except Exception as err:
            results["failed_pages"].append({
                "path": page_path,
                "reason": str(err)
            })

    return results
```

## Size Limits and Performance

**Per-Page Limits:**
- Max 100KB per HTML page
- Skip if larger (add note in metadata)

**Total Limits:**
- Max 7 pages in Phase 1
- Target: 50-150KB total ZIP size
- Timeout: 30 seconds total capture time

**Performance:**
- HTML fetching: Already done during detection
- Sanitization: ~50ms per 50KB HTML
- ZIP creation: ~10ms
- No disk I/O (all in memory)

## User Documentation Updates

### **TROUBLESHOOTING.md**

Add section:
```markdown
### Capturing Modem HTML for Unsupported Modems

If your modem is not supported, you can help us add support:

**Method 1: Button Entity (if integration installed)**
1. Go to your Cable Modem device page
2. Press "Capture Modem HTML for Support" button
3. Browser downloads file automatically
4. Attach file to GitHub issue

**Method 2: During Setup (if setup failed)**
1. During setup, if modem is unsupported, you'll see an option
2. Check "Help add support for my modem"
3. Click Submit
4. Browser downloads file
5. Open GitHub issue and attach file

**What's included:**
- 7 core HTML pages from your modem
- All personal info removed (MAC, serial, IPs)
- Metadata about capture
- ~50-150KB ZIP file
```

### **Bug Report Template**

Update to mention HTML capture:
```markdown
**For unsupported modems:**
If you have an unsupported modem, please use the "Capture Modem HTML"
button to generate a file, then attach it to this issue. This helps
developers add support for your modem much faster.
```

## Testing Requirements

**Test Cases:**
1. ✅ Button press triggers capture and download
2. ✅ MAC addresses are sanitized in all formats
3. ✅ Serial numbers are sanitized
4. ✅ Private IPs removed (192.168.100.1 kept)
5. ✅ Pages without auth work
6. ✅ Pages with auth work (credentials provided)
7. ✅ Large pages are skipped with note
8. ✅ Failed pages don't crash capture
9. ✅ ZIP file structure is correct
10. ✅ Metadata is accurate
11. ✅ Unsupported modem flow works
12. ✅ User can decline and setup aborts

## Benefits

✅ **Enables Community Growth** - Easy to add new modem support
✅ **User Control** - Opt-in, not forced
✅ **Privacy Protected** - Heavy sanitization
✅ **Developer-Friendly** - Get exact HTML structure
✅ **No Storage** - Direct download, no disk usage
✅ **Fast Debugging** - Issue reports include HTML
✅ **Better UX** - Clear instructions and notifications

## Related Issues

- Issue #3: Netgear CM600 support (needs HTML)
- Issue #4: All entities unavailable (MB8611 - needs HTML to debug)
- Issue #6: MB8611 connection failed (needs HTML)

## Implementation Timeline

**Estimated Effort:** 4-6 hours

**Breakdown:**
- HTML capture utility: 1-2 hours
- Button entity: 1 hour
- Config flow enhancement: 1-2 hours
- Sanitization function: 1 hour
- Testing: 1 hour
- Documentation: 30 minutes

**Target:** Phase 4 implementation (after v3.0.0 release)

## Success Metrics

- Number of HTML captures submitted in issues
- New parsers added from community HTML
- Reduction in "can't test, don't have modem" blockers
- Issue resolution time for unsupported modems

## Open Questions

1. ~~Should files be saved to disk or downloaded directly?~~ **Decision: Download directly**
2. ~~Include auth/login pages or skip them?~~ **Decision: Include if needed for debugging**
3. Should we limit captures per day to prevent abuse? **Decision: No, trust users**
4. Add telemetry for capture usage? **Decision: No, privacy first**

## References

- [Python zipfile documentation](https://docs.python.org/3/library/zipfile.html)
- [Home Assistant Download Response](https://developers.home-assistant.io/docs/api/rest/)
- [Button Entity Documentation](https://developers.home-assistant.io/docs/core/entity/button/)
