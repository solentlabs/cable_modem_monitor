# Similar Projects Research

## Executive Summary

This document summarizes research into existing open-source cable modem monitoring projects. The goal is to identify code, parsing strategies, and modem support that can be leveraged (with proper attribution) to accelerate development of cable_modem_monitor.

**📋 See also:** [LICENSE_AND_COMPARISON_ANALYSIS.md](LICENSE_AND_COMPARISON_ANALYSIS.md) for:
- License compatibility assessment (what we can legally use)
- Detailed MB8600 vs MB8611 code comparison
- SNMP viability evaluation with recommendation

**Key Findings:**
- Most projects use Python with HTML/XPath parsing approaches
- Arris SB8200, SB6183, and Motorola MB8600 have multiple implementations to reference
- Several projects offer modular architectures suitable for adaptation
- **Only 2 projects have compatible licenses:** andresp/cablemodem-status (MIT), PyPNM (MIT)
- **SNMP is not viable** for residential cable modems (ISPs lock it down)

---

## Detailed Project Analysis

### 1. twstokes/arris-scrape
**Repository:** https://github.com/twstokes/arris-scrape
**Language:** Python (99.3%)
**License:** Not specified
**Stars:** Not available

**Supported Modems:**
- Arris cable modems (generic support with extensibility)

**Parsing Approach:**
- XPath queries for extracting data from HTML status pages
- Modular architecture allowing subclassing for different modems

**Data Extracted:**
- Downstream: SNR, DCID, Frequency, Power, Octets, Correcteds, Uncorrectables
- Upstream: UCID, Frequency, Power, Symbol Rate
- Additional metadata: Modulation type, Channel Type

**Notable Features:**
- InfluxDB integration for time-series storage
- Grafana dashboard with signal-level alerts
- PrinterOutputter for debugging
- Supports both local HTML files and remote scraping
- Docker containerization

**Potential Reuse:**
- XPath parsing patterns for Arris modems
- InfluxDB output module design
- Modular outputter architecture

---

### 2. emresaglam/netgear-cable-modem-status-scraper
**Repository:** https://github.com/emresaglam/netgear-cable-modem-status-scraper
**Language:** Python (100%)
**License:** GPL-3.0
**Stars:** Not available

**Supported Modems:**
- Netgear cable modems (specific models not documented)

**Parsing Approach:**
- QT4 WebKit rendering to handle JavaScript-heavy pages
- Requires xvfb-run for headless operation
- Targets "Downstream Bonded Channels" section

**Data Extracted:**
- Downstream bonded channel data (JSON format)

**Notable Features:**
- JavaScript rendering capability via WebKit
- JSON output format
- Headless execution support

**Potential Reuse:**
- JavaScript rendering approach for modern modem interfaces
- JSON output structure

**Limitations:**
- Documentation marked "TBW" (To Be Written)
- Heavy dependency on Qt framework
- Limited to downstream channels only

---

### 3. sarabveer/cable-modem-stats
**Repository:** https://github.com/sarabveer/cable-modem-stats
**Language:** Python (99.4%)
**License:** Not specified
**Stars:** Not available

**Supported Modems:**
- Arris SB8200
- Arris S33
- Comcast XB8

**Parsing Approach:**
- Direct web interface scraping
- Authentication handling for firmware-specific requirements
- Session management for modem limitations

**Data Extracted:**
- Operational metrics for time-series monitoring

**Notable Features:**
- Configuration via config.ini or environment variables
- Docker containerization
- InfluxDB 2.x integration
- Grafana dashboard templates (SB8200)
- Model-specific authentication handling
- Debug logging
- SSL support

**Potential Reuse:**
- SB8200 and S33 parsing implementation
- Authentication handling patterns
- Configuration management approach
- InfluxDB 2.x integration code

---

### 4. andrewfraley/arris_cable_modem_stats
**Repository:** https://github.com/andrewfraley/arris_cable_modem_stats
**Language:** Python (43.1%), HTML (55.0%)
**License:** Not specified
**Stars:** Not available
**Status:** EOL (maintainer no longer has cable internet)

**Supported Modems:**
- Arris SB8200
- Arris SB6183
- Arris T25

**Parsing Approach:**
- HTML scraping from web interface (default: https://192.168.100.1/cmconnectionstatus.html)
- Model-specific handlers
- Authentication support for Comcast firmware

**Data Extracted:**
- Cable modem operational statistics
- Performance metrics for monitoring

**Notable Features:**
- Multiple database backends: InfluxDB (1.x & 2.x), AWS Timestream, Splunk
- Modular design with separate model handlers
- Grafana dashboard integration
- Docker deployment with automatic monthly rebuilds
- Configuration via config.ini or environment variables
- Token refresh mechanisms
- Comprehensive error handling
- 152 commits showing active development history

**Potential Reuse:**
- SB8200, SB6183, T25 parser implementations
- Multi-database backend architecture
- Model-specific handler pattern
- Authentication and session management

---

### 5. andresp/cablemodem-status
**Repository:** https://github.com/andresp/cablemodem-status
**Language:** Python 3 (97.7%)
**License:** Not specified
**Stars:** Not available

**Supported Modems:**
- Hitron Coda56
- Motorola MB8600
- Netgear CM2000
- Technicolor XB7/XB8
- Arris International Touchstone TG3492 (UPC.CH Switzerland)

**Parsing Approach:**
- Web scraping from built-in HTML portals
- Device-specific implementations under src/docsismodem/

**Data Extracted:**
- Channel information
- SNR (Signal-to-Noise Ratio)
- DOCSIS performance metrics

**Notable Features:**
- Configuration via configuration.ini
- InfluxDB 2.0 integration
- Loki event logging
- Docker containerization
- Comprehensive testing framework (pytest)
- Cron job scheduling support
- Docker Compose compatibility
- Grafana-ready data formatting

**Potential Reuse:**
- **MB8600 parser** (we already support this modem, can compare approaches)
- Hitron Coda56, Netgear CM2000, Technicolor XB7/XB8, TG3492 parsers
- Modular src/docsismodem/ structure
- Testing framework approach
- Loki logging integration

**High Priority:**
This project has the most diverse modem support and testing infrastructure.

---

### 6. jhclark/tattletale
**Repository:** https://github.com/jhclark/tattletale
**Language:** Python (98.9%), Shell (1.1%)
**License:** Not specified
**Stars:** Not available

**Supported Modems:**
- Generic (works with any modem accessible via ping)

**Parsing Approach:**
- Network connectivity testing (ping-based)
- No HTML/data parsing

**Data Extracted:**
- Connectivity status (router, modem, ISP)
- Uptime statistics
- Timestamps

**Notable Features:**
- SQLite database for event storage
- CSV export capability
- Gmail integration for reports
- Twitter integration for ISP "shaming"
- Raspberry Pi LED status indicators
- Background daemon operation via nohup

**Potential Reuse:**
- Connectivity monitoring as supplementary feature
- Event notification patterns (email, social media)
- SQLite logging approach

**Limitations:**
- Does not parse modem statistics
- Focused on uptime monitoring, not channel diagnostics

---

## GitHub Topics Exploration

### DOCSIS Topic (27 repositories)
**URL:** https://github.com/topics/docsis

**Notable Projects:**

#### modem-stats (Go, 30 stars)
- Exports channel diagnostics to Telegraf or Prometheus
- Alternative to Python-based solutions
- Could provide reference for metric export formats

#### PyPNM (Python, 3 stars)
- Python toolkit for DOCSIS 3.0/3.1/4.0 Proactive Network Maintenance
- Advanced telemetry parsing and visualization
- Could enable PNM feature support

#### Oscar (Java, 35 stars)
- DOCSIS, PacketCable, DPoE Configuration Editor
- Configuration file format handling
- Less relevant for monitoring

#### os-provisioning (PHP, 70 stars)
- Network provisioning for DOCSIS, FTTH, DSL, WiFi
- CableLabs-managed enterprise solution
- Likely too complex for integration

#### docsis-cable-load-monitor (Shell, 66 stars)
- Downstream capacity utilization tracking
- Could provide network-level monitoring insights

---

### DOCSIS Monitoring Topic (8 repositories)
**URL:** https://github.com/topics/docsis-monitoring

**Notable Projects:**

#### pyDocsisMon (Python, 7 stars)
- SNMP-based DOCSIS attribute access
- Alternative to web scraping approach
- Could enable SNMP fallback for modems without web interfaces

#### docker-vodafone-station-exporter (Go, 8 stars)
- Prometheus exporter for Vodafone Station (CGA4233DE, CGA6444VF)
- European market modems
- Reference for Prometheus integration

#### GroupDelay (Java, 4 stars)
- OFDM/OFDMA group delay calculations
- Advanced signal analysis
- Niche use case for DOCSIS 3.1+

---

## Modem Coverage Analysis

### Currently Supported by cable_modem_monitor
Based on the repository structure:
- Motorola MB8611
- Arris SB6190
- (Other models may exist - would need to check parsers/)

### Modems Supported Across Similar Projects

| Modem Model | Projects Supporting It |
|-------------|------------------------|
| **Arris SB8200** | sarabveer/cable-modem-stats, andrewfraley/arris_cable_modem_stats |
| **Arris SB6183** | andrewfraley/arris_cable_modem_stats |
| **Arris S33** | sarabveer/cable-modem-stats |
| **Arris T25** | andrewfraley/arris_cable_modem_stats |
| **Arris TG3492** | andresp/cablemodem-status |
| **Motorola MB8600** | andresp/cablemodem-status |
| **Netgear CM2000** | andresp/cablemodem-status |
| **Netgear (generic)** | emresaglam/netgear-cable-modem-status-scraper |
| **Hitron Coda56** | andresp/cablemodem-status |
| **Technicolor XB7/XB8** | andresp/cablemodem-status |
| **Comcast XB8** | sarabveer/cable-modem-stats |
| **Vodafone CGA4233DE** | docker-vodafone-station-exporter |
| **Vodafone CGA6444VF** | docker-vodafone-station-exporter |

---

## Parsing Strategies Comparison

### 1. HTML/XPath Parsing
**Projects:** twstokes/arris-scrape, andrewfraley/arris_cable_modem_stats
**Advantages:**
- Precise element targeting
- Works with static HTML
- Lightweight dependencies

**Disadvantages:**
- Fragile to HTML structure changes
- Requires XPath expertise

### 2. JavaScript Rendering (WebKit)
**Projects:** emresaglam/netgear-cable-modem-status-scraper
**Advantages:**
- Handles JavaScript-heavy interfaces
- Accurate rendering of modern web UIs

**Disadvantages:**
- Heavy dependencies (Qt framework)
- Resource intensive
- Complex headless setup

### 3. Direct HTML Scraping
**Projects:** sarabveer/cable-modem-stats, andresp/cablemodem-status
**Advantages:**
- Simple implementation
- Minimal dependencies
- Fast execution

**Disadvantages:**
- Requires stable HTML structure
- May miss JavaScript-rendered content

### 4. SNMP-Based Access
**Projects:** pyDocsisMon, PyPNM
**Advantages:**
- Standardized protocol
- Structured data access
- No web interface dependency

**Disadvantages:**
- Requires SNMP enabled on modem
- Not universally supported
- May require authentication/configuration

---

## Recommended Actions

### High Priority: Examine Code for Direct Reuse

1. **andresp/cablemodem-status** - MB8600 implementation
   - Compare with our existing MB8611 parser
   - Review Hitron Coda56, Netgear CM2000, Technicolor XB7/XB8, TG3492 parsers
   - Examine testing framework structure

2. **andrewfraley/arris_cable_modem_stats** - Arris model parsers
   - SB8200, SB6183, T25 implementations
   - Multi-database backend architecture
   - Authentication handling patterns

3. **sarabveer/cable-modem-stats** - Modern Arris models
   - SB8200 and S33 parsers
   - InfluxDB 2.x integration
   - Session management approach

### Medium Priority: Architecture Patterns

4. **twstokes/arris-scrape**
   - Modular outputter design
   - XPath parsing patterns
   - Grafana dashboard configurations

5. **pyDocsisMon or PyPNM**
   - SNMP fallback capability
   - DOCSIS 3.1+ PNM support
   - Standardized attribute access

### Low Priority: Supplementary Features

6. **jhclark/tattletale**
   - Uptime monitoring
   - Notification system patterns

7. **modem-stats (Go)**
   - Telegraf/Prometheus export formats

---

## Licensing Considerations

**Confirmed Licenses:**
- emresaglam/netgear-cable-modem-status-scraper: **GPL-3.0**

**Unknown Licenses:**
- twstokes/arris-scrape
- sarabveer/cable-modem-stats
- andrewfraley/arris_cable_modem_stats
- andresp/cablemodem-status
- jhclark/tattletale

**Action Required:**
Before adapting any code:
1. Check repository LICENSE files directly
2. Contact maintainers if unclear
3. Ensure compatibility with cable_modem_monitor's license
4. Add proper attribution in code comments and documentation

---

## Next Steps

1. **Clone high-priority repositories locally** for detailed code review
2. **Check LICENSE files** for all projects before code reuse
3. **Create comparison matrix** of our MB8611 parser vs andresp's MB8600 implementation
4. **Identify quick wins** - modems with existing parsers that can be adapted
5. **Design abstraction layer** if adopting multi-backend approach
6. **Document attribution** requirements for any adapted code
7. **Consider SNMP support** as alternative/fallback to web scraping

---

## Summary Statistics

- **Projects Reviewed:** 6 direct + 2 GitHub topics (35+ repositories)
- **Primary Language:** Python (5/6 projects)
- **Unique Modems Identified:** 13+ models
- **Parsing Approaches:** 4 distinct strategies
- **Database Backends Found:** InfluxDB 1.x/2.x, AWS Timestream, Splunk, SQLite
- **Visualization Tools:** Grafana (most common), custom dashboards

---

*Research conducted: 2025-11-12*
*Researcher: Claude (Anthropic)*
*Purpose: Accelerate cable_modem_monitor development through code reuse and knowledge sharing*
