***REMOVED******REMOVED*** Description

<!-- Provide a clear and concise description of your changes -->

***REMOVED******REMOVED*** Type of Change

<!-- Please check the relevant option(s) -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] Test improvement
- [ ] CI/CD improvement
- [ ] Dependency update

***REMOVED******REMOVED*** Related Issues

<!-- Link to related issues using keywords like "Fixes ***REMOVED***123" or "Closes ***REMOVED***456" -->

Fixes ***REMOVED***

***REMOVED******REMOVED*** Changes Made

<!-- Provide a bullet-point list of specific changes -->

-
-
-

***REMOVED******REMOVED*** Testing

<!-- Describe the tests you ran and how to reproduce them -->

***REMOVED******REMOVED******REMOVED*** Test Configuration

- **Integration Version**:
- **Home Assistant Version**:
- **Modem Model** (if applicable):

***REMOVED******REMOVED******REMOVED*** Test Steps

1.
2.
3.

***REMOVED******REMOVED******REMOVED*** Test Results

- [ ] All existing tests pass
- [ ] New tests added (if applicable)
- [ ] Manual testing completed
- [ ] Pre-commit hooks pass

***REMOVED******REMOVED*** Screenshots (if applicable)

<!-- Add screenshots to demonstrate visual changes -->

***REMOVED******REMOVED*** Checklist

<!-- Please check all items that apply -->

***REMOVED******REMOVED******REMOVED*** Code Quality

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings or errors
- [ ] I have run the linter (`make lint` or `ruff check`)
- [ ] I have run the code formatter (`make format` or `black .`)

***REMOVED******REMOVED******REMOVED*** Testing

- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes (`make test` or `pytest`)
- [ ] I have tested this integration with a real modem (if applicable)

***REMOVED******REMOVED******REMOVED*** Documentation

- [ ] I have updated the documentation accordingly (README, CHANGELOG, etc.)
- [ ] I have updated the CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/) format
- [ ] I have added docstrings to new functions/classes
- [ ] I have updated type hints (if applicable)

***REMOVED******REMOVED******REMOVED*** For New Modem Support

<!-- Only applicable if adding support for a new modem model -->

- [ ] I have added a new parser in `custom_components/cable_modem_monitor/parsers/<manufacturer>/`
- [ ] I have included test fixtures (HTML samples from the modem)
- [ ] I have added tests for the new parser
- [ ] I have updated `docs/MODEM_COMPATIBILITY_GUIDE.md`
- [ ] I have tested with the actual modem hardware

***REMOVED******REMOVED******REMOVED******REMOVED*** Fixture Requirements

- [ ] Created `metadata.yaml` in fixture directory (see [template](../docs/FIXTURE_REQUIREMENTS.md***REMOVED***metadatayaml-template))
- [ ] **PII scrubbed from all fixtures:**
  - [ ] MAC addresses removed/anonymized (e.g., `00:00:00:00:00:00`)
  - [ ] Serial numbers removed/anonymized (e.g., `XXXXXXXXXXXX`)
  - [ ] Public IP addresses removed (e.g., `0.0.0.0`)
  - [ ] Account/subscriber IDs removed
- [ ] Captured ALL available status pages (downstream, upstream, system info, logs if available)

***REMOVED******REMOVED******REMOVED*** Compliance

- [ ] My changes respect user privacy and security
- [ ] I have read and agree to follow the [Code of Conduct](../CODE_OF_CONDUCT.md)
- [ ] I have read the [Contributing Guide](../CONTRIBUTING.md)
- [ ] My commit messages follow the project's commit message guidelines

***REMOVED******REMOVED*** Breaking Changes

<!-- If this PR introduces breaking changes, describe them here and provide migration instructions -->

None / N/A

***REMOVED******REMOVED*** Additional Notes

<!-- Any additional information that reviewers should know -->

***REMOVED******REMOVED*** For Maintainers

<!-- Maintainers only - do not fill out -->

- [ ] Version bump required?
- [ ] Release notes drafted?
- [ ] Ready to merge?
