# Agent instructions

Cloakroom is a stealth browser (CloakBrowser in OrbStack) on the user's Mac that you can drive when a site blocks your cloud browser. If the user asks you to use Cloakroom, or to do something on a site "with cloakroom" (e.g. **"Login to Amazon with cloakroom"**), follow [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md).

Short version:

```bash
cloakroom status --json          # or ./cloakroom status --json from the repo
cloakroom start                  # if not ready
cloakroom share --json           # phone viewer; send the url immediately
cloakroom unshare                # stop the share when they are done
```

Drive pages with Playwright: `connect_over_cdp("http://127.0.0.1:9222")`, then use `browser.contexts[0]` (the saved, logged-in profile).

Built-in example flow: `cloakroom amazon-login --json` streams JSON events; exit 0 = logged in. When Amazon asks for a code, it emits `waiting_for_otp`. POST the code to `submit_url` from that event (localhost only).

**You** (Grok Bot or Muse) own two-factor codes on every site: read the code from Messages yourself and enter it (through your own script, or `submit_url` in the built-in flow). Cloakroom does not read iMessage.

When the user wants the viewer on a phone, away from home, or any remote noVNC access, run `cloakroom share` and send the HTTPS URL in the same turn. Do not ask them to approve or confirm first. The command does not prompt. The URL is a secret capability link: anyone with it can control the logged-in browser. When they are done, run `cloakroom unshare`. Do **not** use Tailscale. Do **not** Funnel or port-forward. Never expose port 9222; `cloakroom share` tunnels the viewer (6080) only. Ports 6080 and 9222 stay bound to `127.0.0.1`.

Never ask the user for their password in chat. They type it in the viewer (http://127.0.0.1:6080, or the share URL), or, for the Amazon flow, store it with `cloakroom creds set` in their own terminal.
