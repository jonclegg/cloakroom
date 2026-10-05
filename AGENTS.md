# Agent instructions

Cloakroom is a stealth browser (CloakBrowser) with a persistent profile, that you drive over CDP. On a Mac it runs in OrbStack. On Linux it runs in Docker Engine. Use it when a site blocks your cloud browser, when you need cookies and logins to persist between runs, or when the user asks you to do something "with cloakroom". Follow [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md). It is the full reference (commands, JSON output, settings, troubleshooting, Linux, Windows, internals); the README is only a short human quickstart.

Short version:

```bash
cloakroom status --json          # or ./cloakroom status --json from the repo
cloakroom start                  # if not ready
cloakroom do "<goal>"            # let Cloakroom drive the browser itself with DeepSeek
cloakroom share --json           # phone viewer; send the url immediately
cloakroom unshare                # stop the share when they are done
```

Drive pages with Playwright: `connect_over_cdp("http://127.0.0.1:9222")`, then use `browser.contexts[0]` (the saved profile, with its cookies).

**Or hand Cloakroom the goal and let it drive.** `cloakroom do "search walmart.com for paper towels"` runs an embedded DeepSeek loop over OpenRouter: Cloakroom screenshots the page, DeepSeek picks the next action, Cloakroom executes it humanized (including press-and-hold). It needs `OPENROUTER_API_KEY` and `python3` with Playwright on the host. Prefer this when the task is a goal rather than a script. See [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md#cloakroom-do-embedded-deepseek).

**Bing-first entry and humanized input are the default.** Do not `page.goto` the target site, and do not open a search, listing, or product URL as the first navigation. Open `https://www.bing.com`, search the site name or domain, click the organic result (official domain, skip ads), then use that site's own search and links. Google-first often hits `/sorry/` from this CDP session; Bing is the gateway. Pause between actions, move the mouse in a short curve before each click, click a field before typing, and type character by character — [`examples/bing_first.py`](examples/bing_first.py) and [`examples/humanize.py`](examples/humanize.py). That avoids needless challenges. If one still appears, `cloakroom do` works it.

If a site asks for a two-factor code, **you** (Grok Bot or Muse) get it (for example from Messages) and type it into the page. Cloakroom does not read iMessage.

When the user wants the viewer on a phone, away from home, or any remote noVNC access, run `cloakroom share` and send the HTTPS URL in the same turn. Do not ask them to approve or confirm first. The command does not prompt. The URL is a secret capability link: anyone with it can control the logged-in browser. When they are done, run `cloakroom unshare`. Do **not** use Tailscale. Do **not** Funnel or port-forward. Never expose port 9222; `cloakroom share` tunnels the viewer (6080) only. Ports 6080 and 9222 stay bound to `127.0.0.1`.

Never ask the user for their password in chat. They type it in the viewer (http://127.0.0.1:6080, or the share URL).

## Linux

Docker Engine and the `docker compose` plugin, on amd64 or arm64. `docker info` must succeed for this user (start the service, and add the user to the `docker` group if permission is denied).

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

Or from a clone: `./cloakroom start`. CDP stays `http://127.0.0.1:9222`. Bing-first entry is unchanged. Ports stay on `127.0.0.1`. `cloakroom share` tunnels the viewer (6080) only.
