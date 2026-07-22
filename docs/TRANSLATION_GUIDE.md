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

```text
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

### Translated Scope Is Deliberately Limited

Only the config and options flows are translated. Two things are
explicitly **out of scope** and stay English:

- **Service (action) names and descriptions**
- **Entity names** — sensors, buttons, and their per-channel variants

This is a maintenance decision, not an oversight. Home Assistant falls
back to English per key, so an untranslated surface degrades cleanly.
The config and options flows are a small, stable set that a user meets
once during setup, which is where translation earns the most and costs
the least. Entity names in particular are dominated by per-channel
sensors whose text is mostly standardized technical vocabulary
(`DS`, `QAM`, `SNR`, channel numbers) that is not translated in any
language — localizing them would change roughly one word in five while
adding hundreds of strings to maintain in every language, forever.

`strings.json` and `translations/en.json` still carry every section,
including services. Only the other language files are scope-limited.

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

## Translation Glossary

Ratified terms, and the record of corrections. **Read this before
translating anything.** When a user reports a bad translation, fix the
string and add the ruling here — that is what stops the same mistake
being made again on the next pass.

Entries are added when a choice has actually been contested or is easy
to get wrong. An empty section means no ruling has been needed yet.

| Language | English | Use | Note |
| -------- | ------- | --- | ---- |
| de | Channel Naming | Kanalbenennung | |
| es | modem | módem | Accented; `modem` is a common de-accenting error |
| fr | modem | modem | Unaccented in French, unlike Spanish |
| it | is (as in "is correct") | è | `e` means "and" — dropping the accent inverts the meaning |

### Accent Integrity

`check-translations-sync.py` enforces a minimum diacritic density per
language, because stripped accents are a real and recurring failure mode
here, not a cosmetic one. If a legitimate change lowers a language's
density, update the floor in that script deliberately rather than
working around the check.

Two languages cannot be protected this way: **Dutch** uses no diacritics
in this content, and **Italian** uses very few. Damage to those is only
visible by reading the diff.

### Translation Quality Guidelines

- Use formal but approachable tone
- Match Home Assistant's existing terminology for your language
- Keep error messages helpful and actionable
- Preserve placeholders like `{detected_modem}` and `{parser_selected_at}`
- Test that the JSON is valid before submitting

## For Developers

### Adding or Changing Strings

This is the common case, and the one that previously had no process —
four services shipped with English text sitting in every language file
because adding keys to satisfy the sync check was easier than
translating them.

1. Add the string to `strings.json`
2. Copy `strings.json` over `translations/en.json` — they must match exactly
3. If the string is **in scope** (config or options flow), translate it in
   all other language files. If it is out of scope (a service or entity
   name), do nothing — the other files should not carry it at all
4. Run `python3 scripts/dev/check-translations-sync.py`

> **Translate only the keys that changed. Never regenerate a whole language
> file.** This is the single most important rule here, and it is written in
> blood: commit `cd0376a1` regenerated all twelve locales while restructuring
> the config flow. French lost 80 accented characters, Italian's "è corretto"
> ("is correct") became "e corretto" ("and correct"), a six-step troubleshooting
> message was deleted outright, and four services shipped in English for four
> months. Regeneration is how good translations get silently replaced by worse
> ones. Touch the deltas.

Translations are produced with LLM assistance (see [Translation
Glossary](#translation-glossary) for terms that must be used). When a user
reports a bad translation, fix the string **and** add a glossary entry, so the
correction survives the next translation pass instead of being overwritten.

The checker enforces all three rules: `en.json` matches `strings.json`,
every language covers the in-scope keys and nothing beyond them, and no
language holds a value identical to English.

That last check is what catches an untranslated string. A key holding
English text is worse than a missing key — a missing key falls back to
English cleanly, while an English value inside `de.json` is presented to
the user *as German*, and nothing downstream can tell it is wrong.

If a string is genuinely identical in a target language — a product name,
or a loanword like `Password` in Italian or `Variant` in Dutch — add it to
`_ALLOW_IDENTICAL` in the checker rather than inventing a translation.

### Adding a New Language

1. Copy `en.json` to `{language_code}.json`
2. Remove any sections outside the translated scope (see above) — keep
   `config` and `options`
3. Translate all remaining string values
4. Test the integration with Home Assistant in that language
5. Run `python3 scripts/dev/check-translations-sync.py`
6. Submit a PR

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
