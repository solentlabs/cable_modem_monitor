# Motorola MB8611 Test Fixtures

**Source:** GitHub Issue #4 - User @dlindnegm
**Date Captured:** October 31, 2025
**Modem Info:**
- Model: Motorola MB8611 (DOCSIS 3.1)
- Hardware Version: V1.0
- Software Version: 8611-19.2.18
- Serial: 2251-MB8611-30-1526
- Protocol: HTTPS (port 443) with self-signed certificate

## Files

### HTML Pages (from web interface)

1. **Login.html**
   - URL: `https://192.168.100.1/Login.html`
   - Login/authentication page
   - Shows HNAP JavaScript initialization

2. **MotoHome.html**
   - URL: `https://192.168.100.1/MotoHome.html`
   - Main dashboard after login
   - Size: 8.5K

3. **MotoStatusConnection.html**
   - URL: `https://192.168.100.1/MotoStatusConnection.html`
   - Connection status page (channel data)
   - Size: 26K (largest - full channel tables)
   - Contains HNAP JavaScript references

4. **MotoStatusSoftware.html**
   - URL: `https://192.168.100.1/MotoStatusSoftware.html`
   - Advanced settings/software page
   - Size: 6.7K

5. **MotoStatusLog.html**
   - URL: `https://192.168.100.1/MotoStatusLog.html`
   - System event log
   - Size: 6.0K

**Note:** User also mentioned `MotoStatusSecurity.html` for password reset/reboot/restart (not captured yet)

## Notes

**HNAP Protocol:** The MB8611 uses HNAP (Home Network Administration Protocol), a SOAP-based API developed by Cisco/Pure Networks. This means:

- Web interface uses JavaScript to make SOAP API calls to `/HNAP1/`
- Channel data is retrieved via HNAP actions like:
  - `GetMotoStatusDownstreamChannelInfo`
  - `GetMotoStatusUpstreamChannelInfo`
  - `GetMotoStatusConnectionInfo`
  - `GetMotoStatusStartupSequence`

### HNAP API Data (JSON format)

6. **hnap_full_status.json** ✅ ADDED November 5, 2025
   - URL: `POST https://192.168.100.1/HNAP1/`
   - Complete HNAP `GetMultipleHNAPs` response
   - Contains: Startup sequence, connection info, downstream/upstream channels
   - Format: JSON (HNAP uses JSON over HTTPS, not XML)
   - Source: HAR export from user @dlindnegm
   - Data structure:
     - 33 downstream channels (including OFDM PLC)
     - 4 upstream channels
     - System uptime: "47 days 21h:15m:38s"
     - Caret-delimited channel data: `ID^Status^Mod^ChID^Freq^Power^SNR^Corr^Uncorr^`

**Status:** ✅ **We now have complete HNAP data for Phase 2 implementation!**

To implement MB8611 parser (Phase 2), we have:
- [x] HNAP response examples (JSON) - `hnap_full_status.json`
- [x] Channel data format documented (caret-delimited)
- [ ] Login HNAP action (TBD during Phase 2)

## Usage

These fixtures will be used in Phase 2 when implementing HNAP/SOAP protocol support. The parser will need to:

1. Authenticate using HNAP login action
2. Make SOAP calls to retrieve channel data
3. Parse XML responses instead of HTML scraping

## Reference

- GitHub Issue: #4
- Roadmap: Phase 2 - New Protocols (MB8611 HNAP Parser)
- Related: Phase 1 - `HNAPSessionAuthStrategy`
