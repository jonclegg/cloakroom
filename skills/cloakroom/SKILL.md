---
name: cloakroom
description: Drive a stealth CloakBrowser running under OrbStack on the user's Mac, over CDP, with a persistent profile that keeps cookies and logins. Use when a site bot-walls your cloud browser, when a session needs to survive between runs, or when the user says "use cloakroom", "do X with cloakroom", or "share the viewer". Enter sites through a Bing organic result and humanize Playwright input; do not open the target with page.goto. If a site asks for a two-factor code, you (Grok Bot or Muse) get it and type it in; Cloakroom never reads Messages. When the user wants the viewer on a phone or away from home, run `cloakroom share` and send the HTTPS URL immediately. Do not ask them to confirm. Do not use Tailscale.
---

# Cloakroom skill

Cloakroom is a local CLI: `cloakroom`, or `./cloakroom` from this repo. It is plain bash (no Python needed on the host).
It controls a stealth Chromium in OrbStack (`cloakhq/cloakbrowser`). The browser, the viewer, and the saved profile stay on the machine.

```text
Your agent ──► cloakroom ───────────────► start / stop / status / share
     │
     └───────► CDP  http://127.0.0.1:9222 ─► CloakBrowser, headed, in OrbStack on the Mac
                                              ├─ saved profile: cookies and logins persist
                                              └─ viewer: http://127.0.0.1:6080
                                                   └─ cloakroom share ──► private HTTPS link (phone)
```

The browser keeps running in the background (as long as OrbStack runs) until `cloakroom stop`. Stopping keeps the profile.

## Playbook

1. **Check readiness**

   ```bash
   cloakroom status --json
   ```

   | Field | Value | What you do |
   | --- | --- | --- |
   | `docker_running` | `false` | Run `cloakroom start`. That opens OrbStack (not Docker Desktop) and starts the browser. If OrbStack is missing, the user installs it from https://orbstack.dev/download. |
   | `ready` | `false` | Run `cloakroom start` (first run downloads ~1 GB; allow up to 10 minutes). |

2. **Drive the browser over CDP**

   Connect, then enter the site with Bing (step 3). [`examples/hello.py`](../../examples/hello.py) runs that path for `example.com`. The steps live in [`examples/bing_first.py`](../../examples/bing_first.py); mouse and typing live in [`examples/humanize.py`](../../examples/humanize.py).

   ```python
   from playwright.sync_api import sync_playwright
   import bing_first  # examples/bing_first.py

   with sync_playwright() as pw:
       browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
       page = browser.contexts[0].new_page()
       # Bing gateway, then the organic result. Not page.goto of the target.
       landed = bing_first.open_via_bing(page, "example.com")
       print(landed.title())
   ```

   Puppeteer or any tool that attaches to an existing Chrome works too. Same entry rule: Bing first, then humanized input on the site.

   If Playwright isn't installed, `pip install playwright` is enough. Skip `playwright install`: you attach to the running browser, so no browser download is needed.

   `browser.contexts[0]` is the persistent profile: cookies and logins from earlier runs are already there. Don't create a new context unless you want a clean session. `browser.close()` only disconnects you; the browser keeps running.

3. **Entering a website**

   Default for every new site:

   1. `page.goto("https://www.bing.com")` — this is the gateway, not the destination.
   2. Search the site name or domain. Click the search button.
   3. Click the **organic** result for that site. Prefer the official domain. Skip ads (`li.b_algo` is Bing's organic block; skip `.b_ad`).
   4. Stay on that site. Use its own search box and links.

   Do **not** open the target with `page.goto` as the first navigation. Do **not** jump straight to a search, listing, or product URL (`/trade/search`, deep product SERPs, and the same kind of hot scrape URL on other sites). Those direct loads are what get challenged.

   Google-first search from this CDP session often lands on Google `/sorry/` (unusual-traffic reCAPTCHA). **Bing is the search gateway** for Cloakroom. Do not start at Google.

   The one direct-URL exception: the user handed you one exact page to open (a login URL they named, a doc they linked). You may open that URL. Still humanize everything after it loads. If that URL is challenged and the homepage is not, leave it and come back through Bing, then use the site's own UI.

4. **Humanize interactions**

   Drive the page like a person whenever you are on Bing or on the destination site. [`examples/humanize.py`](../../examples/humanize.py) is the default implementation (`pause`, `human_move`, `human_click`, `human_type`). Copy that behavior in ad-hoc scripts too.

   - Short random pauses between actions (a few tenths of a second up to a couple of seconds).
   - Before each click, `mouse.move` along a short curved path with a little jitter, then click. A single instant jump to the target reads as a script.
   - Click the input with the mouse before typing. Do not `fill()` on a bot-sensitive site.
   - Type character by character with jittered delays, including a slightly longer pause after some spaces.
   - Prefer clicking real buttons and links over `page.goto` once you are on the site. In-site search goes through the site's search box, then its Search button:

   ```python
   import humanize  # examples/humanize.py

   box = page.locator("input[type='search']").first
   humanize.human_click(page, box)
   humanize.human_type(page, "your query")
   humanize.human_click(page, page.get_by_role("button", name="Search"))
   ```

   This is how you avoid extra challenges. It is not a captcha bypass. Do not drag sliders, call solving services, or replay challenge tokens. If a puzzle is on screen, stop and let the user finish it in the viewer.

5. **Bring in the user when needed**

   If a page needs a password, a puzzle, or a step you can't do, tell the user to finish it in the viewer at http://127.0.0.1:6080 (or run `cloakroom share` if they're away from the Mac), then continue. Never ask for a password in chat.

6. **Two-factor codes**

   You fetch codes. Cloakroom does not. It never reads Messages, `chat.db`, or Full Disk Access. When a site asks for a code, read it yourself (for example from Messages) and type it into the page. If you can't read it, ask the user to type it in the viewer. Do not ask them to paste it into chat, and never repeat the code.

## Phone / remote viewer

User wants the viewer on a phone, away from home, or says "remote VNC" / "share the browser".

Run this immediately. Do not ask the user to approve, confirm, or opt in. There is no confirmation step in the CLI. Send `url` in the same turn.

```bash
cloakroom share --json
```

That one command starts the browser if it is not already running, then starts a Cloudflare quick tunnel to the viewer only (`http://127.0.0.1:6080` by default) and prints the URL. It does not prompt. State (pid and URL) is in `~/.cloakroom/share.json`.

```json
{"event":"share_ready","url":"https://….trycloudflare.com","viewer_local":"http://127.0.0.1:6080","reused":false}
```

`url` is a secret capability link. Anyone with it can control the logged-in browser. Tell the user that when you send it. When they are done, run `cloakroom unshare` (same as `cloakroom share stop`). A new share gets a new link. `cloakroom status --json` includes `share_url` while the tunnel is running (`null` when it is not).

Do **not** use Tailscale. Do **not** Funnel or port-forward 6080 or 9222 yourself. The only remote path is `cloakroom share`, and it tunnels the viewer only. Never point a tunnel at port 9222. Do not add an approval gate of your own.

## Commands

Every command takes `--json`.

| Command | What it does |
| --- | --- |
| `cloakroom start` / `stop` | Start or stop the browser. The profile is kept. |
| `cloakroom status --json` | Is OrbStack up, is the browser ready, and the viewer, CDP, and share URLs. Exits non-zero in text mode when not ready. |
| `cloakroom share --json` | Start a private HTTPS link to the viewer and print it. |
| `cloakroom unshare` | Stop that link. It stops working immediately. |

`start` / `stop` run [`start.sh`](../../start.sh) / [`stop.sh`](../../stop.sh), which also work on their own. `share` / `unshare` run [`share.sh`](../../share.sh).

## Rules

- Never print, log, or store the user's password or two-factor codes in chat or files.
- Cloakroom does not read iMessage. You do, if a code is needed.
- Ports 9222 and 6080 stay on `127.0.0.1`.
- Remote viewer access is one command: `cloakroom share`. Run it and send the URL immediately. Do not ask for approval first, and do not add a confirmation step. The URL is a secret capability link. Run `cloakroom unshare` when the user is done. Do not use Tailscale, Funnel, or port forwards. Never tunnel 9222.
- Enter sites through Bing: search the name or domain, click the organic result, then use the site's own UI. Do not `page.goto` the target, and do not open search, listing, or product URLs as the first navigation. Google-first often hits `/sorry/` from Cloakroom CDP; Bing is the gateway.
- Humanize Playwright input by default: random pauses, a curved `mouse.move` before clicks, click a field before typing, type character by character. Do not `fill()` bot-sensitive forms. Helpers: [`examples/humanize.py`](../../examples/humanize.py), entry: [`examples/bing_first.py`](../../examples/bing_first.py).
- Don't bypass CAPTCHAs. Humanizing is how you avoid needless challenges. When a page shows a puzzle, the user finishes it in the viewer.

## Reference

### Install

`install.sh` (Mac only): installs OrbStack with Homebrew (or opens https://orbstack.dev/download and waits for it in Applications), installs `cloudflared` (Homebrew, else the official binary into `~/.local/bin`), downloads Cloakroom to `~/.cloakroom/app`, links `cloakroom` onto the PATH, and runs `cloakroom start`. Apple Silicon runs natively.

### Settings

Optional knobs live in `.env` (created from [`.env.example`](../../.env.example) on first start): license key, proxy, fingerprint seed, and ports. Edit `.env`, then `cloakroom stop` and `cloakroom start`. If you change `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT`, export the same variables when running `cloakroom`.

### Limits

- No site is guaranteed. Bot checks change. A loaded homepage is not a login or a checkout.
- Traffic leaves from the Mac's connection or `CLOAKROOM_PROXY`. A flagged IP, VPN, or datacenter proxy can still be challenged.
- Grok Bot's **Route traffic through this computer** setting alone clears many IP blocks. Cloakroom is for sites that also fingerprint the browser (e.g. Sam's Club's press-and-hold page), or when the user wants a persistent local profile they can watch.
- Cloakroom has no site-specific scripts. Use it only with the user's own accounts and within each site's terms.

### Security

- Port 9222 is full control of a signed-in browser, and the viewer has no password. Neither is published beyond `127.0.0.1`.
- The profile lives in the `profile` Docker volume. `docker compose down -v` deletes it and signs the user out of everything.
- Cloakroom does not store passwords or codes. `.env` (license key, proxy password) is git-ignored.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| "OrbStack did not become ready" | User opens OrbStack from Applications, finishes first-run setup (may ask for the Mac password), then `cloakroom start`. |
| "permission denied: ./cloakroom" | `chmod +x cloakroom start.sh stop.sh share.sh install.sh`, or `bash cloakroom …`. |
| "port is already allocated" | Something else uses 9222 or 6080 (often a Chrome with remote debugging). Close it, or change the ports in `.env`. |
| "cloudflared is not installed" | `brew install cloudflared`, or download from https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/ and put it on the PATH. |
| Tabs crash ("Aw, Snap!") or slow | Quit heavy apps and `cloakroom start`. Memory settings are in the OrbStack app. |
| "License" / "concurrent session" errors | A free key allows one session at a time. Stop other CloakBrowser sessions (including `examples/cloaktest.sh`) or blank the key. |
| Need logs | `docker compose logs -f cloakroom` from the repo. |
| Direct URL shows a challenge, homepage would not | Do not reload the hot search or product URL. Enter through Bing, click the organic homepage, then search with the site's own box using humanized input. If a puzzle is already up, the user solves it in the viewer. |

### Windows

Browser and viewer run on Windows with Docker Desktop (WSL 2); the one-line installer is Mac-only.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), restart, wait for **Engine running**.
2. Get the repo (Download ZIP or `git clone`).
3. In PowerShell in the repo: `powershell -ExecutionPolicy Bypass -File .\start.ps1`
4. Test: `docker compose run --rm hello` enters example.com through Bing and prints the title.
5. Stop: `powershell -ExecutionPolicy Bypass -File .\stop.ps1`

For the phone viewer: `winget install --id Cloudflare.cloudflared`, then `cloakroom share` from Git Bash.

### Internals

- **`cloakroom` container:** official `cloakhq/cloakbrowser` plus x11vnc and noVNC ([`image/Dockerfile`](../../image/Dockerfile)). Runs [`cloakserve`](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) headed on a virtual display (passes more bot checks; it's what the viewer shows). `shm_size: 2gb` (Chromium crashes at the 64 MB default). Healthcheck on `/json/version`.
- **Volumes:** `profile` (cookies and logins) and `binary-cache` (licensed binary, downloaded once). [`image/cloakroom-serve.sh`](../../image/cloakroom-serve.sh) keeps `cloakserve` from deleting the profile on exit.
- **Extra identities:** add `?fingerprint=<seed>` to the CDP URL, e.g. `http://127.0.0.1:9222?fingerprint=11111&timezone=Europe/Berlin`. Only the default identity is saved to `profile`. See the [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode).
- **Stealth test:** `./examples/cloaktest.sh` runs upstream's bot-detection suite with the `.env` settings.
- **Updates:** `cloakroom start` always pulls the latest `cloakhq/cloakbrowser`. To pin, change `FROM cloakhq/cloakbrowser:latest` in `image/Dockerfile` to a tag like `0.5.11`.
- **Plain Compose:** `cp .env.example .env && docker compose up -d --build`, then `docker compose down`.

### Links

- CloakBrowser: https://github.com/CloakHQ/CloakBrowser (targets Cloudflare Turnstile, HUMAN / PerimeterX, Akamai, DataDome, Kasada)
- Free license key: https://cloakbrowser.dev/free
- Docker image: https://hub.docker.com/r/cloakhq/cloakbrowser
- OrbStack: https://orbstack.dev/
