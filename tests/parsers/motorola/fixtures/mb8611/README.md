***REMOVED*** Motorola MB8611 Test Fixtures

**Source:** GitHub Issue ***REMOVED***4 - User @dlindnegm
**Date Captured:** October 31, 2025
**Modem Info:**
- Model: Motorola MB8611 (DOCSIS 3.1)
- Hardware Version: V1.0
- Software Version: 8611-19.2.18
- Serial: 2251-MB8611-30-1526

***REMOVED******REMOVED*** Files

***REMOVED******REMOVED******REMOVED*** HTML Pages (from web interface)

1. **mb8611_login_page.txt**
   - Login/authentication page
   - Shows HNAP JavaScript initialization

2. **mb8611_landing_page.txt**
   - Main dashboard after login
   - Size: 8.5K

3. **mb8611_connection_page.txt**
   - Connection status page (likely contains channel data)
   - Size: 26K (largest - probably has full channel tables)
   - Contains HNAP JavaScript references

4. **mb8611_advanced_page.txt**
   - Advanced settings page
   - Size: 6.7K

5. **mb8611_event_log_page.txt**
   - System event log
   - Size: 6.0K

***REMOVED******REMOVED*** Notes

**HNAP Protocol:** The MB8611 uses HNAP (Home Network Administration Protocol), a SOAP-based API developed by Cisco/Pure Networks. This means:

- Web interface uses JavaScript to make SOAP API calls to `/HNAP1/`
- Channel data is retrieved via HNAP actions like:
  - `GetMotoStatusDownstreamChannelInfo`
  - `GetMotoStatusUpstreamChannelInfo`
  - `GetMotoStatusConnectionInfo`
  - `GetMotoStatusStartupSequence`

**What's Missing:**

We still need the actual HNAP SOAP request/response XML samples. These HTML files show the web interface structure, but the actual channel data comes from HNAP API calls.

To implement MB8611 parser (Phase 2), we need:
- [ ] HNAP SOAP request examples (XML)
- [ ] HNAP SOAP response examples (XML)
- [ ] Login HNAP action (if SOAP-based)

***REMOVED******REMOVED*** Usage

These fixtures will be used in Phase 2 when implementing HNAP/SOAP protocol support. The parser will need to:

1. Authenticate using HNAP login action
2. Make SOAP calls to retrieve channel data
3. Parse XML responses instead of HTML scraping

***REMOVED******REMOVED*** Reference

- GitHub Issue: ***REMOVED***4
- Roadmap: Phase 2 - New Protocols (MB8611 HNAP Parser)
- Related: Phase 1 - `HNAPSessionAuthStrategy`
