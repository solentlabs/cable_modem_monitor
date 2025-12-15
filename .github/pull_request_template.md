## Description

<!-- Provide a clear and concise description of your changes -->

## Type of Change

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

## Related Issues

<!-- Link to related issues using keywords like "Fixes #123" or "Closes #456" -->

Fixes #

## Changes Made

<!-- Provide a bullet-point list of specific changes -->

-
-
-

## Testing

<!-- Describe the tests you ran and how to reproduce them -->

### Test Configuration

- **Integration Version**:
- **Home Assistant Version**:
- **Modem Model** (if applicable):

### Test Steps

1.
2.
3.

### Test Results

- [ ] All existing tests pass
- [ ] New tests added (if applicable)
- [ ] Manual testing completed
- [ ] Pre-commit hooks pass

## Screenshots (if applicable)

<!-- Add screenshots to demonstrate visual changes -->

## Checklist

<!-- Please check all items that apply -->

### Code Quality

- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings or errors
- [ ] I have run the linter (`make lint` or `ruff check`)
- [ ] I have run the code formatter (`make format` or `black .`)

### Testing

- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes (`make test` or `pytest`)
- [ ] I have tested this integration with a real modem (if applicable)

### Documentation

- [ ] I have updated the documentation accordingly (README, CHANGELOG, etc.)
- [ ] I have updated the CHANGELOG.md following [Keep a Changelog](https://keepachangelog.com/) format
- [ ] I have added docstrings to new functions/classes
- [ ] I have updated type hints (if applicable)

### For New Modem Support

<!-- Only applicable if adding support for a new modem model -->

- [ ] I have added a new parser in `custom_components/cable_modem_monitor/parsers/<manufacturer>/`
- [ ] I have included test fixtures (HTML samples from the modem)
- [ ] I have added tests for the new parser
- [ ] I have verified the modem appears in `tests/parsers/FIXTURES.md` (auto-generated from metadata.yaml)
- [ ] I have tested with the actual modem hardware

#### Fixture Requirements

- [ ] Created `metadata.yaml` in fixture directory (see [template](../docs/reference/FIXTURE_FORMAT.md#metadatayaml-template))
- [ ] **PII scrubbed from all fixtures:**
  - [ ] MAC addresses removed/anonymized (e.g., `00:00:00:00:00:00`)
  - [ ] Serial numbers removed/anonymized (e.g., `XXXXXXXXXXXX`)
  - [ ] Public IP addresses removed (e.g., `0.0.0.0`)
  - [ ] Account/subscriber IDs removed
- [ ] Captured ALL available status pages (downstream, upstream, system info, logs if available)

### Compliance

- [ ] My changes respect user privacy and security
- [ ] I have read and agree to follow the [Code of Conduct](../CODE_OF_CONDUCT.md)
- [ ] I have read the [Contributing Guide](../CONTRIBUTING.md)
- [ ] My commit messages follow the project's commit message guidelines

## Breaking Changes

<!-- If this PR introduces breaking changes, describe them here and provide migration instructions -->

None / N/A

## Additional Notes

<!-- Any additional information that reviewers should know -->

## For Maintainers

<!-- Maintainers only - do not fill out -->

- [ ] Version bump required?
- [ ] Release notes drafted?
- [ ] Ready to merge?
