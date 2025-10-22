***REMOVED*** Response Templates for User Feedback

Quick copy-paste responses for common scenarios.

---

***REMOVED******REMOVED*** Modem Not Compatible (First Response)

```markdown
Thanks for trying it out and for the feedback!

The [Modem Model] isn't one I've tested with yet. The integration works by parsing the modem's web interface HTML, and different manufacturers use different page structures.

I'd love to add support for it! If you're willing to help, here's what would be useful:

**Quick Check:**
1. Can you access your modem's web interface in a browser? (usually http://192.168.100.1)
2. Does it show a page with downstream/upstream channel data, power levels, and SNR?

If yes, I've created a guide with step-by-step instructions on how to help add support:
https://github.com/kwschulz/cable_modem_monitor/blob/main/MODEM_COMPATIBILITY_GUIDE.md

The quick version:
- View the HTML source of your modem's status page (`Ctrl+U` in browser)
- Save it and sanitize (remove MAC address, personal IPs)
- Create a GitHub issue with the HTML attached

**No worries if that's too much work** - I appreciate you trying it out and letting me know! This helps me understand which modems people want supported.
```

---

***REMOVED******REMOVED*** Modem Not Compatible (If They Provide Info)

```markdown
Thank you SO much for providing this information! This is incredibly helpful.

I'll take a look at the HTML structure and see what's needed to add support for the [Modem Model]. I've created an issue to track this: [link to issue]

A few things that will help me prioritize:
- How common is this modem model? (helps gauge how many users would benefit)
- Are there any quirks with your ISP's configuration?

I can't promise immediate support, but I'll investigate feasibility and update the issue with my findings.

Really appreciate you taking the time to help improve the integration! 🙏
```

---

***REMOVED******REMOVED*** Modem Not Compatible (If It's Feasible to Add)

```markdown
Great news! I've looked at the HTML structure and it looks feasible to add support for the [Modem Model].

I've added it to the roadmap and will work on it in an upcoming release. I'll update issue ***REMOVED***[number] when it's ready.

In the meantime, if you want to test early builds before release, let me know and I can ping you when I have something to try out.

Thanks again for providing the information - it really helps!
```

---

***REMOVED******REMOVED*** Modem Not Compatible (If It's Not Feasible)

```markdown
Thanks for providing the details! I've reviewed the HTML structure for the [Modem Model].

Unfortunately, adding support looks challenging because [specific reason]:
- The page uses JavaScript to load data dynamically
- The HTML structure is significantly different from supported modems
- Critical data isn't exposed in the web interface

[If applicable: There might be alternative approaches like SNMP, but most ISPs disable that for customers]

I know this isn't the answer you were hoping for. I'll leave this issue open in case someone from the community wants to tackle it, but I can't commit to adding support in the near term.

Really appreciate you taking the time to investigate this! If you have Python experience and want to try implementing it yourself, I'm happy to provide guidance.
```

---

***REMOVED******REMOVED*** Bug Report Response

```markdown
Thanks for reporting this! That's definitely not expected behavior.

Can you help me debug by providing:
1. Your Home Assistant version
2. Integration version (check HACS or `manifest.json`)
3. Modem model
4. Debug logs:

```yaml
logger:
  default: info
  logs:
    custom_components.cable_modem_monitor: debug
```

Then reproduce the issue and share relevant log entries (Settings → System → Logs).

This will help me understand what's happening and get it fixed. Thanks!
```

---

***REMOVED******REMOVED*** Feature Request Response (Good Idea)

```markdown
Great idea! That would be a useful feature.

I've created an issue to track this: [link]

A few questions to help me design it:
- [Specific question about use case]
- [Question about desired behavior]

No promises on timeline, but I'll add it to the roadmap. If anyone from the community wants to contribute a PR, I'm happy to review!

Thanks for the suggestion! 👍
```

---

***REMOVED******REMOVED*** Feature Request Response (Out of Scope)

```markdown
Thanks for the suggestion!

I appreciate the idea, but this feels outside the core scope of the integration. The goal is to focus on modem signal quality monitoring rather than [whatever they requested].

However, you might be able to achieve this with:
- [Suggest alternative approach if applicable]
- [Link to related integration if exists]

Hope that helps!
```

---

***REMOVED******REMOVED*** Success Story Response

```markdown
This is awesome! 🎉 Love hearing that it helped you with your ISP call.

Would you mind sharing a screenshot of your dashboard in Discussions? Other users would love to see real-world examples:
https://github.com/kwschulz/cable_modem_monitor/discussions

And if you haven't already, please ⭐ star the repo - it really helps with visibility!

Thanks for sharing your experience!
```

---

***REMOVED******REMOVED*** General Thank You Response

```markdown
Thanks for the kind words! Really glad it's working well for you.

If you find it useful, please consider:
- ⭐ Starring the repo on GitHub
- 📝 Sharing your setup in Discussions
- 🐛 Reporting any issues you encounter

Community feedback like yours helps make the integration better for everyone! 🙏
```

---

***REMOVED******REMOVED*** Pull Request Response (Good PR)

```markdown
Thank you for the contribution! This is exactly what open source is about. 🙌

I'll review this over the next few days and provide feedback. A few things I'll check:
- [ ] Tests pass
- [ ] Code follows existing patterns
- [ ] Documentation updated if needed

Really appreciate you taking the time to improve the integration!
```

---

***REMOVED******REMOVED*** Question About Supported Modems

```markdown
Good question! Here's the current compatibility status:

**Confirmed Working:**
- Motorola MB series (MB7420, MB8600, etc.)
- Arris cable modems (SB6183, SB8200, etc.)

**Being Investigated:**
- [Any modems people have reported]

**General Rule:** If your modem has a web interface (http://192.168.100.1) showing channel data with power levels and SNR, there's a good chance it will work or can be supported.

Want to try it with your [specific modem]? Worst case, it doesn't work and you've helped me learn about another modem model!

If it doesn't work, see the compatibility guide for how to help add support:
https://github.com/kwschulz/cable_modem_monitor/blob/main/MODEM_COMPATIBILITY_GUIDE.md
```

---

***REMOVED******REMOVED*** Question About Installation

```markdown
Great question! Here's the installation process:

**Via HACS (Easiest):**
1. HACS → Integrations → Three dots → Custom repositories
2. Add: `https://github.com/kwschulz/cable_modem_monitor`
3. Category: Integration
4. Search "Cable Modem Monitor" → Download
5. Restart Home Assistant
6. Settings → Devices & Services → Add Integration → "Cable Modem Monitor"

**Manual Install:**
See the README for manual installation steps: [link]

Let me know if you get stuck on any step!
```

---

***REMOVED******REMOVED*** Update Notification Template (For Big Releases)

```markdown
📢 **Update Available: v[X.X.X]**

New features:
- [Feature 1]
- [Feature 2]

Bug fixes:
- [Fix 1]

Update via HACS or download from releases: [link]

See full changelog: [link]

Thanks to everyone who provided feedback! 🙏
```

---

***REMOVED******REMOVED*** Notes on Tone

**Always:**
- ✅ Be appreciative of feedback
- ✅ Be honest about limitations
- ✅ Offer alternatives when possible
- ✅ Thank contributors
- ✅ Be professional but friendly

**Never:**
- ❌ Be defensive about bugs/limitations
- ❌ Make promises you can't keep
- ❌ Dismiss user concerns
- ❌ Ghost threads (always respond)

---

***REMOVED******REMOVED*** Quick Response Checklist

For every response:
- [ ] Acknowledge their effort/feedback
- [ ] Provide clear next steps or explanation
- [ ] Link to relevant docs if applicable
- [ ] End on a positive note
- [ ] Proofread before posting

---

**Remember:** Every interaction builds community and reputation. Be the developer you'd want to interact with!
