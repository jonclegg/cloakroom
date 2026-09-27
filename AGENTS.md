# Agent instructions

Cloakroom is a stealth browser (CloakBrowser in OrbStack) on the user's Mac, with a persistent profile, that you drive over CDP. Use it when a site blocks your cloud browser, when you need cookies and logins to persist between runs, or when the user asks you to do something "with cloakroom". Follow [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md). It is the full reference (commands, JSON output, settings, troubleshooting, Windows, internals); the README is only a short human quickstart.

Short version:

```bash
cloakroom status --json          # or ./cloakroom status --json from the repo
cloakroom start                  # if not ready
cloakroom share --json           # phone viewer; send the url immediately
cloakroom unshare                # stop the share when they are done
```

Drive pages with Playwright: `connect_over_cdp("http://127.0.0.1:9222")`, then use `browser.contexts[0]` (the saved profile, with its cookies).

If a site asks for a two-factor code, **you** (Grok Bot or Muse) get it (for example from Messages) and type it into the page. Cloakroom does not read iMessage.

When the user wants the viewer on a phone, away from home, or any remote noVNC access, run `cloakroom share` and send the HTTPS URL in the same turn. Do not ask them to approve or confirm first. The command does not prompt. The URL is a secret capability link: anyone with it can control the logged-in browser. When they are done, run `cloakroom unshare`. Do **not** use Tailscale. Do **not** Funnel or port-forward. Never expose port 9222; `cloakroom share` tunnels the viewer (6080) only. Ports 6080 and 9222 stay bound to `127.0.0.1`.

Never ask the user for their password in chat. They type it in the viewer (http://127.0.0.1:6080, or the share URL).
