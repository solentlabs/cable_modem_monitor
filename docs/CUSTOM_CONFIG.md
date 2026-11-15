# Add Modem with Custom Config

When setup fails for your modem, or your modem isn't in the catalog but
a close one is, you can edit that modem's config yourself and test it
against your modem in the setup dialog, without waiting for a new
release. An AI assistant can help you read the results.

Setup contract: [CONFIG_FLOW_SPEC.md § Custom Config Setup](../custom_components/cable_modem_monitor/docs/CONFIG_FLOW_SPEC.md#custom-config-setup).

## Steps

1. **Settings → Devices & services → Add integration → Cable Modem
   Monitor**, then choose **Add modem with custom config**.
2. Pick your modem (or the closest one) and its variant, then enter
   the host and credentials as in a normal setup.
3. The next screen shows that modem's `modem.yaml`. Edit it, or submit
   it unchanged to see what happens with the project's config. To
   change the host or login, start the setup again. To switch between
   HTTP and HTTPS, put `http://` or `https://` in front of the host on
   the previous screen.
4. Select **Submit**. Each submit is one login attempt.
   - **Passed:** the modem is added with your config.
   - **Failed:** the form stays open with your text. Open
     **Settings → System → Logs** and search for
     `custom config report`. That one entry holds the whole attempt:
     every request and what the modem answered.
5. Change the config and submit again.

Keep a copy of your config in a text file as you go. Closing the dialog
discards your edits.

Only `modem.yaml` is editable. How the modem's pages are read
(`parser.yaml`) comes from the catalog.

## Working with an AI assistant

Paste the following into your assistant, followed by your current
config and the latest report:

```text
I'm adjusting a Cable Modem Monitor modem config (modem.yaml) so my
cable modem works with it. The format is defined here; use only keys
and values it defines:
https://github.com/solentlabs/cable_modem_monitor/blob/main/packages/cable_modem_monitor_core/docs/MODEM_YAML_SPEC.md
Login strategies are described in the auth section of that spec.

Below are my current modem.yaml and the "custom config report" from my
last attempt. Find the first request that went wrong, explain what the
modem answered, and suggest one change to try next. A login failure can
come from my edited config as well as from my username or password. Explain why it
should help. If the fix needs something modem.yaml cannot express, say
so plainly instead of inventing a key.
```

Guidelines for a productive session:

- **Change one thing per attempt.** The next report then tells you what
  that change did.
- **The schema is checked first.** Unknown keys or wrong types are
  rejected before anything is sent to the modem; the report names the
  problem.
- **Stop when the config can't express the fix.** If the assistant
  concludes the modem needs something modem.yaml has no setting for,
  that is a useful finding. Post it (below).
- **Reports are scrubbed** of your password and the hashed or encrypted
  forms of it, but still read one before posting it publicly.

## Sending your findings back

Every finding helps the next person with your modem.

- **It works:** open the modem's device page, select **Download
  diagnostics**, and attach the file to a
  [GitHub issue](https://github.com/solentlabs/cable_modem_monitor/issues).
  The file includes the difference between your config and the
  project's, which is exactly what needs to go into the catalog.
- **You got stuck:** open an issue with your last config and its
  report, and say what you tried.

When your change lands in the catalog, you're credited in that modem's
catalog entry. Your modem then switches back to the project's config on
its own (Home Assistant shows a notification) and gets future fixes
like everyone else.

## When the project's config changes

A modem added with custom config keeps your config. At each Home
Assistant start it compares your config with the project's:

- **Same as yours** (comments and formatting aside): it switches to the
  project's config and notifies you.
- **Changed since you started:** a repair appears under
  **Settings → System → Repairs**. Its fix tests the project's config
  against your modem once and switches only if the test passes.

To go back to the project's config at any time, delete the modem and
add it again with **Add modem**.
