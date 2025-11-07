# Feature Requests

This directory contains documented feature requests for future versions of the Cable Modem Monitor integration.

---

## 📊 Status Overview

| Feature | Priority | Status | Effort | Target Version |
|---------|----------|--------|--------|----------------|
| **Smart Polling Sensor** | Low | ⏸️ Deferred | 2-3 hours | v3.1.0+ |
| **Netgear CM600 Parser** | Medium | 🆕 Awaiting samples | 4-6 hours | v3.1.0 |
| **Phase 4: JSON Configs** | Low | ⏸️ Conditional | 2-3 weeks | v4.0.0-alpha |
| **Phase 5: Community Platform** | Very Low | ⏸️ May not build | 4-6 weeks | v4.0.0 |

---

## 🎯 Near-Term Features (v3.1.0)

### [Netgear CM600 Parser](netgear_cm600_parser.md)
**Status:** 🆕 Awaiting HTML samples from user
**Priority:** Medium
**Effort:** 4-6 hours

Add support for Netgear CM600 cable modem (Issue #3). **Blocked on user providing HTML samples.**

---

## 💡 Optional Features (Post-v3.0.0)

### [Smart Polling Sensor](smart_polling_sensor.md)
**Status:** ⏸️ Deferred - Foundation exists
**Priority:** Low
**Effort:** 2-3 hours

Diagnostic sensor that monitors polling health and recommends optimal polling intervals based on signal stability. The `SignalQualityAnalyzer` class already exists, just needs sensor wrapper.

**Build when:** Users request it or you want better polling diagnostics.

---

## 🚀 Major Future Enhancements (v4.0.0+)

### [Phase 4: Data-Driven JSON Configs](phase_4_json_configs.md)
**Status:** ⏸️ DEFERRED - Build only when needed
**Priority:** Low
**Effort:** 2-3 weeks
**Trigger:** Parser count > 10 OR maintenance burden significant

Replace Python-based parsers with JSON configuration files interpreted by a generic parser. Makes it easier for community to add modem support without writing Python code.

**Current:** 6 parsers, Python works fine. **WAIT.**

---

### [Phase 5: Community Platform & Config Builder](phase_5_community_platform.md)
**Status:** ⏸️ DEFERRED - May never build
**Priority:** Very Low
**Effort:** 4-6 weeks
**Trigger:** Phase 4 successful AND community specifically requests easier tooling

CLI tool and optional HA wizard to help users generate JSON parser configurations interactively.

**Build ONLY if:** Phase 4 exists for 6+ months, 10+ contributors using it, and hand-editing JSON proves to be a bottleneck.

---

## 📝 How to Use This Directory

### For Users
- **Vote** on features by upvoting (👍) the GitHub issues
- **Comment** with use cases and suggestions
- **Request** new features by opening GitHub issues

### For Contributors
- **Reference** these documents when implementing features
- **Update** status when work begins or completes
- **Add** new feature requests as markdown files

### For Maintainers
- **Review** before planning releases
- **Prioritize** based on votes and community feedback
- **Update** status as features are implemented or deferred

---

## 🗂️ Feature Request Template

When adding new feature requests:

```markdown
# Feature Request: [Name]

**Status:** [New/In Progress/Deferred/Complete]
**Priority:** [Low/Medium/High]
**Effort:** [Hours/Days/Weeks]
**Target Version:** [vX.Y.Z]
**Related Issue:** #[number]

---

## Summary
Brief description of the feature

## Problem It Solves
What user pain point does this address?

## Proposed Solution
How would this be implemented?

## Benefits
Why should this be built?

## Challenges
What makes this difficult?

## Success Criteria
- [ ] Measurable goals

---

**Vote with 👍 if you want this feature!**
```

---

## 🔄 Status Definitions

| Status | Meaning |
|--------|---------|
| 🆕 **New** | Newly proposed, not yet evaluated |
| ⏸️ **Deferred** | Intentionally postponed, build only when triggered |
| 🚧 **In Progress** | Actively being implemented |
| ✅ **Complete** | Implemented and released |
| ❌ **Rejected** | Decided not to implement |
| 🆘 **Blocked** | Waiting on external dependency |

---

## 📋 Roadmap Integration

These feature requests align with the [Architecture Roadmap](../ARCHITECTURE_ROADMAP.md):

- ✅ **Phase 1** - Authentication Abstraction (v3.0.0) **COMPLETE**
- ✅ **Phase 2** - HNAP/SOAP Protocol Support (v3.0.0) **COMPLETE**
- ✅ **Phase 3** - Enhanced Discovery (v3.0.0) **COMPLETE**
- ⏸️ **Phase 4** - Data-Driven JSON Configs (v4.0.0-alpha) **DEFERRED**
- ⏸️ **Phase 5** - Community Platform (v4.0.0) **CONDITIONAL**

---

## 🤝 Contributing

Have a feature idea?

1. Check if it already exists in this directory
2. If not, open a GitHub issue first for discussion
3. If approved, create a markdown file here documenting it
4. Follow the template above
5. Submit a PR with just the documentation

---

**Last Updated:** November 7, 2025
**Version:** v3.0.0
