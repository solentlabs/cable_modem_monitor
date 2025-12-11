# Translation Guide

This guide explains how Cable Modem Monitor handles internationalization (i18n) with AI-assisted translations and community contributions.

## Supported Languages

| Code | Language | Status |
|------|----------|--------|
| en | English (US) | Source |
| de | German | ✓ |
| nl | Dutch | ✓ |
| fr | French | ✓ |
| zh-CN | Chinese (Simplified) | ✓ |
| it | Italian | ✓ |
| es | Spanish | ✓ |
| pl | Polish | ✓ |
| sv | Swedish | ✓ |
| ru | Russian | ✓ |
| pt-BR | Portuguese (Brazil) | ✓ |
| uk | Ukrainian | ✓ |

Languages are selected based on [Home Assistant user demographics](https://analytics.home-assistant.io/).

## File Structure

```
custom_components/cable_modem_monitor/translations/
├── en.json              # Source of truth (English)
├── de.json              # German
├── nl.json              # Dutch
├── fr.json              # French
├── zh-CN.json           # Chinese (Simplified)
├── it.json              # Italian
├── es.json              # Spanish
├── pl.json              # Polish
├── sv.json              # Swedish
├── ru.json              # Russian
├── pt-BR.json           # Portuguese (Brazil)
└── uk.json              # Ukrainian
```

## How Home Assistant Uses These Files

Home Assistant automatically loads the appropriate translation file based on the user's language setting. The translation files contain strings for:

- **Config flow**: Setup wizard titles, descriptions, field labels, and error messages
- **Options flow**: Settings page titles, descriptions, and field labels

## For Translators

### Correcting a Translation

If you find an error in a translation:

1. Fork the repository
2. Edit the translation file directly (e.g., `translations/de.json`)
3. Only change the string values that need correction
4. Submit a PR with your correction

**Example**: Fixing a German error message

```json
// Before
"invalid_auth": "Authentifizierung fehlgeschlagen..."

// After (corrected)
"invalid_auth": "Anmeldung fehlgeschlagen..."
```

### What NOT to Translate

Keep these terms unchanged:
- Cable Modem Monitor
- Home Assistant
- DOCSIS
- HNAP
- IP address formats (192.168.100.1)
- Technical terms: ping, HTTP, VPN, WiFi

### Translation Quality Guidelines

- Use formal but approachable tone
- Match Home Assistant's existing terminology for your language
- Keep error messages helpful and actionable
- Preserve placeholders like `{detected_modem}` and `{last_detection}`
- Test that the JSON is valid before submitting

## For Developers

### Adding a New Language

1. Copy `en.json` to `{language_code}.json`
2. Translate all string values
3. Test the integration with Home Assistant in that language
4. Submit a PR

### Validating JSON

```bash
# Check all translation files are valid JSON
for f in custom_components/cable_modem_monitor/translations/*.json; do
  python3 -c "import json; json.load(open('$f'))" && echo "OK: $f"
done
```

### JSON Structure

The translation files follow Home Assistant's [translation format](https://developers.home-assistant.io/docs/internationalization/core/):

```json
{
  "config": {
    "step": {
      "user": {
        "title": "...",
        "description": "...",
        "data": { ... },
        "data_description": { ... }
      }
    },
    "error": { ... },
    "abort": { ... },
    "progress": { ... }
  },
  "options": {
    "step": {
      "init": { ... }
    }
  }
}
```

## Testing Translations

1. Install the integration in Home Assistant
2. Change your HA language setting to the target language
3. Add a new Cable Modem Monitor instance
4. Verify all strings display correctly in the config flow
5. Check the options page for the integration

## Questions?

Open an issue or reach out on [GitHub](https://github.com/solentlabs/cable_modem_monitor).
