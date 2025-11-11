# HTML Capture Guide for Unsupported Modems

This guide helps you capture HTML from your modem to help developers add support for your model.

## For Users WHO CAN Install the Integration

If you can install the integration (even with limited functionality):

### Steps:

1. **Install** the Cable Modem Monitor integration
2. **Go to** Settings → Devices & Services → Cable Modem
3. **Press** the "Capture HTML" button
4. **Wait** for notification (captures HTML in ~5-10 seconds)
5. **Download diagnostics** within 5 minutes:
   - Go to Settings → Devices
   - Find "Cable Modem" device
   - Click the three dots menu (⋮)
   - Select "Download diagnostics"
6. **Attach** the downloaded JSON file to your GitHub issue

### What Gets Captured:

- All relevant modem pages (status, connection, system info)
- Automatically sanitized (MACs, serials, IPs removed)
- 5-minute expiration (for privacy)
- Typically 50-150 KB total

---

## For Users WHO CANNOT Install the Integration

If your modem isn't supported yet and you can't install the integration, use the standalone capture script.

### Requirements:

- Python 3.9 or higher
- Access to your modem's web interface

### Steps:

1. **Download** the capture script from the repository:
   - File: `tools/capture_modem_html.py`
   - Or copy from the section below

2. **Run the script:**
   ```bash
   python3 tools/capture_modem_html.py
   ```

3. **Follow prompts:**
   - Enter modem IP (usually 192.168.100.1)
   - Enter username/password (if required, or press Enter to skip)

4. **Output:**
   - Creates `modem_capture_YYYYMMDD_HHMMSS.zip` file
   - Contains sanitized HTML from all modem pages
   - Safe to share (personal info removed)

5. **Attach** the ZIP file to your GitHub issue

---

## What Information is Removed?

For your privacy and security, the following is automatically redacted:

**Removed:**
- MAC addresses → `XX:XX:XX:XX:XX:XX`
- Serial numbers → `***REDACTED***`
- Private IP addresses → `***PRIVATE_IP***`
- Account/subscriber IDs → `***REDACTED***`
- Passwords/tokens → `***REDACTED***`

**Preserved (needed for parser development):**
- Channel tables and structure
- Signal levels (frequency, power, SNR)
- Error counts
- Modulation types
- Software version
- HTML structure and CSS classes
- Uptime and status messages

---

## For Netgear CM600 Users Specifically

Your modem typically:
- **IP Address:** 192.168.100.1
- **Authentication:** Usually none (public status pages)
- **Status Page:** Usually `/cmconnectionstatus.html` or similar

### Quick Start:

```bash
# Download and run the capture script
python3 tools/capture_modem_html.py

# When prompted:
# - IP: 192.168.100.1
# - Username: (press Enter - usually not needed)
# - Password: (press Enter - usually not needed)

# Attach the generated ZIP file to GitHub Issue #3
```

---

## Troubleshooting

### Script Fails with "Connection Error"
- **Check** modem IP is correct (try opening in browser)
- **Verify** you're on the same network as the modem
- **Check** firewall settings

### Script Says "No Pages Captured"
- Your modem might use different URLs
- Try accessing modem in browser first
- Note which URLs work, share in GitHub issue

### Authentication Required Error
- Your modem requires login
- Re-run script with username/password
- Usually found on modem label or ISP documentation

### Need More Help?
- Open a GitHub issue with details
- Include any error messages
- Mention your modem model and ISP

---

## Privacy and Security

### What We Do:
✅ Remove all personal identifiers automatically
✅ Open-source script (you can review the code)
✅ Local processing only (no data sent anywhere except your GitHub upload)
✅ Creates temporary files you control

### What We Don't Do:
❌ No telemetry or tracking
❌ No automatic uploads
❌ No storage of sensitive data
❌ No third-party services

### You're Always in Control:
- Review the ZIP file contents before sharing
- You choose what to upload to GitHub
- Delete capture files anytime
- Script runs locally on your machine

---

## What Happens Next?

1. **You share** the HTML capture
2. **Developer reviews** the HTML structure
3. **Developer creates** a parser for your modem
4. **Developer tests** with your HTML samples
5. **Developer releases** support in next version
6. **You test** and confirm it works
7. **Everyone with your modem** can now use the integration!

**Typical timeline:** 2-6 hours of development time once HTML is provided.

---

## Contributing

Found this helpful? Help others by:
- Documenting your modem's quirks
- Testing the integration with your modem
- Reporting any issues you find
- Helping other users in discussions

Thank you for helping expand modem support! 🎉
