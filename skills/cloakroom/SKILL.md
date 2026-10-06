---
name: cloakroom
description: Drive a stealth CloakBrowser on the user's Mac (OrbStack) or Linux machine (Docker Engine), over CDP, with a persistent profile that keeps cookies and logins. Use when a site bot-walls your cloud browser, when a session needs to survive between runs, or when the user says "use cloakroom", "do X with cloakroom", or "share the viewer". Talk to Cloakroom with `cloakroom chat` and it drives the browser itself with DeepSeek, working bot checks as they come up, and replies. Enter sites through a Bing organic result and humanize Playwright input; do not open the target with page.goto. If a site asks for a two-factor code, you (Grok Bot or Muse) get it and type it in; Cloakroom never reads Messages. When the user wants the viewer on a phone or away from home, run `cloakroom share` and send the HTTPS URL immediately. Do not ask them to confirm. Do not use Tailscale.
---

# Cloakroom skill

Cloakroom is a local CLI: `cloakroom`, or `./cloakroom` from this repo. It is plain bash and needs only Docker; `chat`, `run`, `notes`, `key` and `smoke` run inside the container, so from any shell (PowerShell too) they also work as `docker exec cloakroom cloakroom <command>`.
It controls a stealth Chromium (CloakBrowser, from the [jonclegg fork](https://github.com/jonclegg/CloakBrowser/tree/cloakroom-fixes)) in OrbStack on a Mac, Docker Engine on Linux, or Docker Desktop on Windows. The browser, the viewer, and the saved profile stay on the machine.

```text
Your agent ──► cloakroom ───────────────► start / stop / status / share
     │
     └───────► CDP  http://127.0.0.1:9222 ─► CloakBrowser, headed (OrbStack on Mac, Docker Engine on Linux)
                                              ├─ saved profile: cookies and logins persist
                                              └─ viewer: http://127.0.0.1:6080
                                                   └─ cloakroom share ──► private HTTPS link (phone)
```

The browser keeps running in the background (as long as OrbStack or Docker Engine runs) until `cloakroom stop`. Stopping keeps the profile.

## Playbook

1. **Check readiness**

   ```bash
   cloakroom status --json
   ```

   | Field | Value | What you do |
   | --- | --- | --- |
   | `docker_running` | `false` | Run `cloakroom start`. On a Mac with OrbStack that opens OrbStack; otherwise it uses the running Docker engine (Docker Desktop, Colima). If there's no engine at all, re-run the installer: it says exactly what to install. On Linux, Docker Engine must already be installed and `docker info` must succeed. |
   | `ready` | `false` | Run `cloakroom start` (first run downloads ~1 GB; allow up to 10 minutes). |
   | `openrouter_key` | `false` | Needed only for `cloakroom chat`. Run `cloakroom key`: it opens the setup page on this computer and waits until the key is saved (it says if OpenRouter rejected it or the link expired). Away from the computer: `cloakroom key --in-browser` plus `cloakroom share`. See [The OpenRouter key](#the-openrouter-key). Never ask for the key in chat. |

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

   The one direct-URL exception: the user handed you one exact page to open (a login URL they named, a doc they linked). You may open that URL. Still humanize everything after it loads. If that URL is challenged, work the challenge (`cloakroom chat`) rather than retreating; fall back to Bing and the site's own UI only if the challenge won't clear.

4. **Humanize interactions**

   Drive the page like a person whenever you are on Bing or on the destination site. [`examples/humanize.py`](../../examples/humanize.py) is the default implementation (`pause`, `human_move`, `human_click`, `click_at`, `human_type`, `press`, `scroll`, `hold`, `drag`). Import it in ad-hoc scripts rather than calling `page.mouse` / `page.keyboard`: it delivers real X11 mouse and keyboard events through cloakserve's `POST /input` endpoint instead of CDP's synthetic input.

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

   This is how you avoid needless challenges. If a challenge does appear, `cloakroom chat` works it (see [`cloakroom chat`](#cloakroom-chat-cloakroom-drives-you-talk)), or the user finishes it in the viewer.

5. **Bring in the user when needed**

   If a page needs a password or a step you can't do, tell the user to finish it in the viewer at http://127.0.0.1:6080 (or run `cloakroom share` if they're away from this computer), then continue. Never ask for a password in chat.

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
| `cloakroom status --json` | Is the container engine up, is the browser ready, and the viewer, CDP, and share URLs. Exits non-zero in text mode when not ready. |
| `cloakroom chat "<message>"` | Talk to Cloakroom; it drives the browser with DeepSeek and replies. See below. |
| `cloakroom run <id>` / `cancel <id>` | A run's steps, reply and files; or stop it. |
| `cloakroom notes [site]` | The guidance Cloakroom ships with, and what it has learned, per site. |
| `cloakroom share --json` | Start a private HTTPS link to the viewer and print it. |
| `cloakroom unshare` | Stop that link. It stops working immediately. |

`start` / `stop` run [`start.sh`](../../start.sh) / [`stop.sh`](../../stop.sh), which also work on their own. `share` / `unshare` run [`share.sh`](../../share.sh).

## `cloakroom chat` (Cloakroom drives, you talk)

Instead of scripting Playwright yourself, talk to Cloakroom. It works the browser with
DeepSeek and replies when it is finished or needs you:

```bash
cloakroom chat "go to walmart.com and search for paper towels"
cloakroom chat --session s_... "now sort by price and tell me the cheapest"
cloakroom chat --json "find the order status page on amazon.com"
cloakroom run r_...            # every step, the reply, saved files
cloakroom notes cars.com       # what it has learned about a site
```

The chat API runs inside the container ([`agent/server.py`](../../agent/server.py)), so
CDP never leaves loopback and the host needs nothing but Docker. Each
message is one run: screenshot, ask DeepSeek (via OpenRouter) for one action, execute it
humanized, repeat until the model replies or hits `--max-steps` (default 40).

| Reply status | Meaning | What you do |
| --- | --- | --- |
| `done` | Finished. The reply has what you asked for. | Use it. |
| `needs_input` | It needs something: a two-factor code, a choice. | Answer with `--session`. Codes: you fetch them, as always. |
| `blocked` | A bot check it could not clear. | The user finishes it in the viewer, then you continue the session. |
| `failed` / `step_limit` | It did not get there. | Read `cloakroom run <id>`; rephrase, or raise `--max-steps`. |

A **session** is one tab and its conversation. Without `--session` you get a new tab. Pass
the session id from the last reply to follow up in the same tab. Sessions expire after 30
idle minutes. One browser has one mouse, so runs queue.

**What it can do beyond clicking:** `read` (the page's text and links, for prices and listing
URLs), `back`, `goto` (only on a site it has already entered; other sites go through
Bing-first `open`), and `save_images` (the photo gallery of the item on the page, downloaded
through the browser session, one file per photo at its largest size). Saved files are in
`~/.cloakroom/data/runs/<run>/files/`, and the reply lists them.

**Sharing the browser.** Other CDP clients can use the same browser while a run is going.
If one shrinks the window or closes Cloakroom's tab, the run maximizes the window or
moves to another tab on the same site, and lists that under `repairs` in `cloakroom run <id>
--json`. Avoid driving the session's tab yourself while a run is working it.

**It starts with guidance.** [`agent/guidance/`](../../agent/guidance/) ships with Cloakroom: general
rules for each kind of bot check, and a note for each of the 30 sites in
[`docs/bot-detection-playbook.md`](../../docs/bot-detection-playbook.md) (what the check looks like, what
beat it, whether it re-arms, and which ones are not worth spending steps on). The general
rules are in every prompt. A site's note is added when the browser is on that site or a
subdomain of it. Edit those files to change what every install starts with.

**It keeps notes for itself.** During a run it can `remember` facts it will need later in
that message (old steps scroll out of its prompt). When it learns something about a site
(a bot check and what cleared it, where a feature lives), it writes a `note` to that site's
notebook. Every run is logged per site, and a run that hit trouble ends with one extra call
that turns the step log into lessons. The notebook for the site on screen goes into every
prompt, so the next run starts knowing. All of it is plain files under
`~/.cloakroom/data/notes/sites/` (`<site>.md` for lessons, `<site>.jsonl` for the run log).

**The model** is `deepseek/deepseek-v4.1-flash` (set `CLOAKROOM_MODEL` in `.env` to change
it). Of OpenRouter's DeepSeek models only the Flash line accepts images; V3.x, V4 and V4 Pro
reject image input. It needs an OpenRouter key, set up as below; until then `cloakroom chat`
answers 412 and says so.

### The OpenRouter key

The user gives the key to Cloakroom, not to you. **Never ask for it in chat**, never read
`~/.cloakroom/data/openrouter.key`, and never echo it if the user pastes it anyway (tell them
to revoke it at https://openrouter.ai/keys and use the page instead).

| The user is | You run | They do |
| --- | --- | --- |
| At this machine | `cloakroom key --json`, then send them `setup_url` | Open it here and paste the key. |
| Away (phone, another computer) | `cloakroom key --in-browser`, then `cloakroom share --json` and send the share URL | Paste the key into the page that is already open in Cloakroom's browser, through the viewer. |

The page checks the key with OpenRouter, saves it to `~/.cloakroom/data/openrouter.key`
(mode 600), and shows the credit left if the key has a limit. Each link works once and lasts
15 minutes, and answers only on `localhost`. Nothing restarts: the next `cloakroom chat` uses
the key. `cloakroom status --json` shows `"openrouter_key": true` once it is set. To replace a
key, run `cloakroom key` again.

**The API itself**, if you would rather call it than the CLI: `POST
http://127.0.0.1:8423/v1/chat` with `{"message": "...", "session": null}` and
`Authorization: Bearer $(cat ~/.cloakroom/data/api-token)`. The other routes are listed at
the top of [`agent/server.py`](../../agent/server.py).

**How it targets things.** Screenshots are captured at CSS scale, so one screenshot pixel is
one CSS pixel, and the model is told the exact image size. Cloakroom also reads the visible
interactive elements out of the DOM and hands the model their centre coordinates as hints.
That is what makes clicks land: on Walmart's PerimeterX press-and-hold the model picks the
button centre to the pixel.

**Bot checks.** A run reports bot checks in its steps (`blocked`, `block_type`) and works
them, picking the action by kind:

| `block_type` | Action | Notes |
| --- | --- | --- |
| `press_and_hold` | `hold` | PerimeterX and similar. 8s or more, at the button centre. |
| `slider` | `drag` | Geetest, Alibaba. Eased path with jitter, not a teleport — these score the path, not just the endpoints. |
| `checkbox` | `click` | reCAPTCHA v2 checkbox, Turnstile. Often just a click. |
| `image_captcha` | `click` per tile | Best-effort: the model reads the prompt and clicks matching tiles one step at a time. Harder than the rest, and some of these run in cross-origin frames. |

Two things to know about the hold:

- **The challenge has to be fresh.** A PerimeterX press-and-hold that has been sitting on
  screen goes inert: holding it produces no progress and never clears. Hold a freshly served
  challenge, not one that has been open for a minute.
- **Target the button precisely.** A hold a few pixels off the button fails silently, with no
  error and no progress ring. The DOM hints exist for this reason.

Walmart serves this challenge as `/blocked?url=...` after repeated automated entry, and also
as an inline overlay on a normal-looking page (`https://www.walmart.com/search?q=...`). Passing
it once sets a clearance cookie, and Walmart stops challenging for a while.

## Rules

- Never print, log, or store the user's password or two-factor codes in chat or files.
- Never ask for the OpenRouter key in chat. `cloakroom key` gives the user a local page for it.
- Cloakroom does not read iMessage. You do, if a code is needed.
- Ports 9222, 6080 and 8423 stay on `127.0.0.1`.
- Remote viewer access is one command: `cloakroom share`. Run it and send the URL immediately. Do not ask for approval first, and do not add a confirmation step. The URL is a secret capability link. Run `cloakroom unshare` when the user is done. Do not use Tailscale, Funnel, or port forwards. Never tunnel 9222.
- Enter sites through Bing: search the name or domain, click the organic result, then use the site's own UI. Do not `page.goto` the target, and do not open search, listing, or product URLs as the first navigation. Google-first often hits `/sorry/` from Cloakroom CDP; Bing is the gateway.
- Humanize Playwright input by default: random pauses, a curved `mouse.move` before clicks, click a field before typing, type character by character. Do not `fill()` bot-sensitive forms. Helpers: [`examples/humanize.py`](../../examples/humanize.py), entry: [`examples/bing_first.py`](../../examples/bing_first.py).
- When a challenge appears, `cloakroom chat` works it (press-and-hold and the like). The user can also finish it in the viewer.

## Reference

### Install

`install.sh` (macOS, Linux) and `install.ps1` (Windows) install and update the same way. Run them again any time to update.

- The app is downloaded as a GitHub tarball (zip on Windows) into `~/.cloakroom/app` and replaced wholesale on every run, so local edits never block an update. `.env` carries over; the previous copy is kept in `~/.cloakroom/app.previous`. No git needed. Don't edit files in `~/.cloakroom/app`; put settings in `.env`.
- `install.sh` is POSIX `sh` (dash, BusyBox ash, bash, zsh) and refuses to run under `sudo`. It installs `cloudflared` (official binary) into `~/.local/bin`, links `cloakroom` into `/usr/local/bin` when writable or `~/.local/bin` (added to `~/.profile`, `~/.zprofile`, `~/.zshrc`, `~/.bashrc`), then runs `cloakroom start`.
- **No container engine:** the installer changes nothing and exits 3 after a line `CLOAKROOM_NEEDS: docker` naming what it would install. Ask the user; with their yes, run it again with `CLOAKROOM_INSTALL_DOCKER=yes` (PowerShell: `$env:CLOAKROOM_INSTALL_DOCKER = "yes"`). Exit 4 after `CLOAKROOM_NEEDS: user` is a step only the user can do (a sudo password, Docker Desktop's first-run setup, logging in again); relay it and run the installer again afterwards.
- **Mac:** uses OrbStack if it's installed, else a Docker engine that's already running (Docker Desktop, Colima). With neither and consent, it installs OrbStack on macOS 14+ (Homebrew, or opens https://orbstack.dev/download and waits); on older macOS it explains how to install Colima or Docker Desktop. Cloakroom selects OrbStack per command (`DOCKER_CONTEXT`) and never changes your default Docker context.
- **Linux (amd64 or arm64):** uses Docker Engine with the Compose plugin. With consent it installs it with Docker's script (`get.docker.com`), starts it, adds the user to the `docker` group, and grants the socket for the current session (installing `acl` if needed) so no re-login is required.
- **Windows:** `irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex` in PowerShell. Needs Docker Desktop running Linux containers (WSL 2); with consent it installs it with `winget` and starts it. Works in Windows PowerShell 5.1 and PowerShell 7. <!-- pragma: allowlist secret -->
- **Image:** `cloakroom start` pulls `ghcr.io/jonclegg/cloakroom` (amd64 and arm64, published by CI from `main`). It holds no browser binary: the first start downloads it from CloakHQ into the `binary-cache` volume, so the first start takes a few minutes.
- `CLOAKROOM_TARBALL_URL` (`CLOAKROOM_ZIP_URL` on Windows) installs from another archive, such as a fork or a tag.

### Settings

Optional knobs live in `.env` (created from [`.env.example`](../../.env.example) on first start): license key, proxy, fingerprint seed, timezone, and ports. Edit `.env`, then `cloakroom start`. `cloakroom status` and `cloakroom share` read the ports from `.env` too. The browser's timezone and language come from GeoIP of the IP its traffic leaves from (the proxy's, when one is set). `TZ` in `.env` sets only the container's own clock.

### Limits

- Bot checks change and new ones appear. `cloakroom chat` works the kinds it implements — press-and-hold today (PerimeterX and similar); others land as they come up. When it can't clear one, the user finishes it in the viewer and the agent carries on from there.
- A loaded homepage is not a login or a checkout. The profile carries cookies and logins across runs, but a challenge can still appear later in a flow.
- Traffic leaves from this computer's connection or `CLOAKROOM_PROXY`. A home connection is the strongest; a flagged IP, VPN, or datacenter proxy draws more challenges.
- Grok Bot's **Route traffic through this computer** setting alone clears many IP blocks. Cloakroom is for sites that also fingerprint the browser (e.g. Sam's Club's press-and-hold page), or when the user wants a persistent local profile they can watch.
- Cloakroom has no site-specific scripts. Use it only with the user's own accounts and within each site's terms.

### Security

- Port 9222 is full control of a signed-in browser, and the viewer has no password. Neither is published beyond `127.0.0.1`.
- The profile lives in the `profile` Docker volume. `docker compose down -v` deletes it and signs the user out of everything.
- Cloakroom does not store passwords or codes. `.env` (license key, proxy password) is git-ignored.
- The chat API (8423) drives the same signed-in browser, so it takes a bearer token: `~/.cloakroom/data/api-token`, created on first start, mode 600.
- The OpenRouter key is in `~/.cloakroom/data/openrouter.key`, mode 600, outside the install folder, so reinstalling and updating keep it. Only the setup page writes it. The page has no bearer token, so it requires a one-time code and a `localhost` Host header; another website open in the user's browser cannot replace the key.

### Troubleshooting

| Symptom | Fix |
| --- | --- |
| "OrbStack did not become ready" | User opens OrbStack from Applications, finishes first-run setup (may ask for the Mac password), then `cloakroom start`. |
| "permission denied: ./cloakroom" | `chmod +x cloakroom start.sh stop.sh share.sh install.sh`, or `bash cloakroom …`. |
| "port is already allocated" | Something else uses 9222 or 6080 (often a Chrome with remote debugging). Close it, or change the ports in `.env`. |
| "cloudflared is not installed" | Re-run `install.sh`, or download `cloudflared-linux-amd64` / `cloudflared-linux-arm64` from https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/ into `~/.local/bin`. |
| "`docker info` failed" / permission denied | On Linux, start Docker (`sudo systemctl enable --now docker`) and add the user to the `docker` group (`sudo usermod -aG docker "$USER"`), then log in again. |
| Tabs crash ("Aw, Snap!") or slow | Quit heavy apps and `cloakroom start`. Memory settings are in the OrbStack app. |
| "License" / "concurrent session" errors | A free key allows one session at a time. Stop other CloakBrowser sessions (including `examples/cloaktest.sh`) or blank the key. |
| Need logs | `docker compose logs -f cloakroom` from the repo. |
| Direct URL shows a challenge, homepage would not | Do not reload the hot search or product URL. Enter through Bing, click the organic homepage, then search with the site's own box using humanized input. If a challenge is already up, `cloakroom chat` works it, or the user solves it in the viewer. |

### Linux

Browser and viewer run on Linux with Docker Engine (amd64 or arm64). The image is already headed on Xvfb, so a server does not need a monitor.

Prerequisites:

- [Docker Engine](https://docs.docker.com/engine/install/)
- The Compose plugin: `docker compose version` must succeed. On Debian or Ubuntu: `sudo apt-get install docker-compose-plugin`
- `docker info` must succeed for this user. If it says permission denied: `sudo usermod -aG docker "$USER"`, then log in again.

Install:

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

From a clone, once Docker is working:

```bash
./cloakroom start
```

CDP stays `http://127.0.0.1:9222`. The Bing-first playbook above is unchanged. Ports stay on `127.0.0.1`. `cloakroom share` tunnels the viewer (6080) only.

Upstream CloakBrowser runs headed on Xvfb inside the image, so a server needs no monitor. `cloakserve` passes `--ignore-gpu-blocklist` so WebGL still works on that software GPU ([issue #58](https://github.com/CloakHQ/CloakBrowser/issues/58)). A home machine uses that machine's IP; a datacenter IP draws more challenges.

### Windows

Browser and viewer run on Windows with Docker Desktop (WSL 2, Linux containers).

1. Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), restart, wait for **Engine running**.
2. In PowerShell: `irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex` <!-- pragma: allowlist secret -->
3. Later: `& "$HOME\.cloakroom\app\start.ps1"` to start, `& "$HOME\.cloakroom\app\stop.ps1"` to stop. (In a fresh session where scripts are blocked: `powershell -ExecutionPolicy Bypass -File "$HOME\.cloakroom\app\start.ps1"`.)
4. Commands: `docker exec cloakroom cloakroom status | key | smoke | chat "..."`. `key` prints a link to open on this machine; `smoke` writes its report to `~\.cloakroom\data\smoke\`.

For the phone viewer: `winget install --id Cloudflare.cloudflared`, then `cloakroom share` from Git Bash.

### Internals

- **`cloakroom` container:** `ghcr.io/jonclegg/cloakroom`, CloakBrowser from the [jonclegg/CloakBrowser](https://github.com/jonclegg/CloakBrowser/tree/cloakroom-fixes) fork plus x11vnc, noVNC and the chat API. `CLOAKROOM_DEV=1 cloakroom start` builds it from this folder instead ([`docker-compose.dev.yml`](../../docker-compose.dev.yml); `CLOAKBROWSER_SOURCE` points the base at a local fork checkout) ([`image/Dockerfile`](../../image/Dockerfile)). Runs [`cloakserve`](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) headed on a virtual display (passes more bot checks; it's what the viewer shows). `shm_size: 2gb` (Chromium crashes at the 64 MB default). Healthcheck on `/json/version`.
- **Volumes:** `profile` (cookies and logins) and `binary-cache` (licensed binary, downloaded once). [`image/cloakroom-serve.sh`](../../image/cloakroom-serve.sh) keeps `cloakserve` from deleting the profile on exit.
- **Fork changes:** the default identity's seed is saved in the profile (`.cloakserve-seed`), so the fingerprint survives restarts with the cookies. Timezone and locale come from GeoIP of the egress IP (`--geoip`). The window is sized so the geometry pages read stays on screen, GPU/CPU/memory come from one coherent profile per seed, and `POST /input` gives real X11 input.
- **Persona:** on a Mac, `start.sh` adds `COMPOSE_FILE=docker-compose.yml:docker-compose.mac.yml` to `.env`, so the browser presents as a Mac (Apple GPU, a 1440x900 Retina screen, the Mac's own fonts mounted read-only). On an Apple Silicon host that persona clears DataDome and Cloudflare checks the Windows persona fails. Linux hosts keep the Windows persona. Delete that line from `.env` to go back to Windows.
- **Extra identities:** add `?fingerprint=<seed>` to the CDP URL, e.g. `http://127.0.0.1:9222?fingerprint=11111&timezone=Europe/Berlin`. Only the default identity is saved to `profile`. Idle extra identities close after 5 minutes, and at most 8 browsers run at once (the least recently used idle one closes to make room). Reconnecting to a running identity with different settings returns `409`; `POST /fingerprint/<seed>/close` first. See the [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode).
- **Stealth test:** `./examples/cloaktest.sh` runs upstream's bot-detection suite with the `.env` settings.
- **Updates:** run the installer again; `cloakroom start` pulls the newest image. `CLOAKROOM_IMAGE` in `.env` pins another tag (CI publishes `:latest` from `main`, `:<branch>` from branches, and `:sha-<commit>`).
- **Smoke test:** `cloakroom smoke [sites]` enters each site (default Amazon, Walmart, Target, Best Buy) from Bing on the API's browser worker, works any bot check when the OpenRouter key is set, and writes `report.html`, the screenshots and `result.json` to `~/.cloakroom/data/smoke/<id>/`.
- **Plain Compose:** `cp .env.example .env && docker compose up -d`, then `docker compose down`.

### Links

- CloakBrowser: https://github.com/CloakHQ/CloakBrowser (targets Cloudflare Turnstile, HUMAN / PerimeterX, Akamai, DataDome, Kasada)
- Free license key: https://cloakbrowser.dev/free
- Cloakroom image: https://github.com/jonclegg/cloakroom/pkgs/container/cloakroom
- OrbStack: https://orbstack.dev/
- Docker Engine: https://docs.docker.com/engine/install/
