***REMOVED*** Project Governance

This document outlines the governance model for the Cable Modem Monitor project.

***REMOVED******REMOVED*** Project Overview

Cable Modem Monitor is a community-driven open-source project that provides Home Assistant integration for monitoring cable modem statistics. The project is maintained by volunteers who contribute their time and expertise.

***REMOVED******REMOVED*** Roles and Responsibilities

***REMOVED******REMOVED******REMOVED*** Maintainer

**Current Maintainer:** @kwschulz

**Responsibilities:**
- Review and merge pull requests
- Triage and respond to issues
- Make final decisions on project direction and feature acceptance
- Manage releases and versioning
- Enforce the Code of Conduct
- Maintain project infrastructure (CI/CD, documentation, etc.)

**Decision Making:**
- The maintainer has final decision authority on all aspects of the project
- Major changes should be discussed in issues before implementation
- Community feedback is valued and considered in decisions

***REMOVED******REMOVED******REMOVED*** Contributors

Anyone who contributes to the project through code, documentation, testing, or issue reporting.

**How to Become a Contributor:**
1. Read the [Contributing Guide](CONTRIBUTING.md)
2. Review the [Code of Conduct](CODE_OF_CONDUCT.md)
3. Submit a pull request or open an issue

**Contributor Expectations:**
- Follow the project's coding standards and guidelines
- Write tests for new features and bug fixes
- Update documentation as needed
- Be respectful and collaborative
- Respond to feedback on pull requests

***REMOVED******REMOVED******REMOVED*** Community Members

Users of the integration who may report issues, suggest features, or help others.

***REMOVED******REMOVED*** Contribution Process

***REMOVED******REMOVED******REMOVED*** 1. Issue Creation

- Check for existing issues before creating new ones
- Use the appropriate issue template (bug report or feature request)
- Provide clear, detailed information
- Be patient and respectful

***REMOVED******REMOVED******REMOVED*** 2. Pull Request Workflow

```
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run pre-commit hooks and tests locally
5. Update CHANGELOG.md
6. Submit a pull request
7. Respond to review feedback
8. Maintainer merges when approved
```

***REMOVED******REMOVED******REMOVED*** 3. Review Process

- All pull requests require review by the maintainer
- Reviews should be completed within 2 weeks when possible
- Contributors should respond to feedback within 2 weeks
- PRs may be closed if inactive for 30+ days

***REMOVED******REMOVED******REMOVED*** 4. Merging Requirements

Pull requests must meet these requirements before merging:

- [ ] All CI checks pass (tests, linting, type checking)
- [ ] Code coverage meets minimum threshold (60%)
- [ ] Changes are documented in CHANGELOG.md
- [ ] Documentation is updated if needed
- [ ] Commit messages follow conventional commits format
- [ ] Maintainer approval

***REMOVED******REMOVED*** Release Process

***REMOVED******REMOVED******REMOVED*** Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (x.X.0): New features, backward compatible
- **PATCH** (x.x.X): Bug fixes, backward compatible

***REMOVED******REMOVED******REMOVED*** Release Workflow

1. **Preparation**
   - Update version in `manifest.json`
   - Update CHANGELOG.md with release notes
   - Ensure all tests pass
   - Create release commit

2. **Tagging**
   - Create annotated tag: `git tag -a vX.Y.Z -m "Release X.Y.Z"`
   - Push tag: `git push origin vX.Y.Z`

3. **Automation**
   - GitHub Actions automatically creates the release
   - Release notes are extracted from CHANGELOG.md
   - Assets are attached automatically

4. **Announcement**
   - GitHub release is published
   - Users are notified via HACS

***REMOVED******REMOVED******REMOVED*** Release Schedule

- **Patch releases**: As needed for bug fixes
- **Minor releases**: When new features are ready (typically monthly)
- **Major releases**: When breaking changes are necessary (rare)

***REMOVED******REMOVED*** Decision Making Process

***REMOVED******REMOVED******REMOVED*** Feature Acceptance

New features are evaluated based on:

1. **Alignment with project goals**: Does it help monitor cable modems?
2. **Maintenance burden**: Can it be reasonably maintained?
3. **User benefit**: Will it help a significant number of users?
4. **Code quality**: Is it well-tested and documented?
5. **Breaking changes**: Are they necessary and justified?

***REMOVED******REMOVED******REMOVED*** Priority Levels

1. **Critical**: Security vulnerabilities, data loss bugs
2. **High**: Crashes, major functionality broken
3. **Medium**: Feature requests, enhancements
4. **Low**: Nice-to-have improvements, cosmetic changes

***REMOVED******REMOVED*** Communication Channels

***REMOVED******REMOVED******REMOVED*** GitHub Issues
- Bug reports
- Feature requests
- Technical discussions

***REMOVED******REMOVED******REMOVED*** GitHub Discussions
- General questions
- Community support
- Ideas and proposals

***REMOVED******REMOVED******REMOVED*** Pull Requests
- Code review
- Implementation discussion
- Technical decisions

***REMOVED******REMOVED*** Code of Conduct Enforcement

The maintainer is responsible for enforcing the [Code of Conduct](CODE_OF_CONDUCT.md).

***REMOVED******REMOVED******REMOVED*** Enforcement Process

1. **Warning**: First violation receives a private warning
2. **Temporary Ban**: Repeated violations result in temporary ban (30-90 days)
3. **Permanent Ban**: Serious or continued violations result in permanent ban

***REMOVED******REMOVED******REMOVED*** Appeals

Appeals can be submitted to the maintainer via email. Decisions on appeals are final.

***REMOVED******REMOVED*** Changes to Governance

This governance document may be updated by the maintainer as the project evolves. Major changes will be announced via GitHub release notes.

***REMOVED******REMOVED******REMOVED*** Amendment Process

1. Propose changes via pull request
2. Allow 2 weeks for community feedback
3. Maintainer makes final decision
4. Update effective date

***REMOVED******REMOVED*** License

This project is licensed under the MIT License. All contributions are made under this license.

***REMOVED******REMOVED*** Acknowledgments

This project would not be possible without:

- The Home Assistant community
- Contributors who add support for new modem models
- Users who report issues and provide feedback
- The broader open-source community

---

**Last Updated:** 2025-11-06
**Effective Date:** 2025-11-06
**Maintainer:** @kwschulz
