# Cloakroom

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

That installs Cloakroom on a Mac and starts it. It uses **OrbStack**, not Docker Desktop. If OrbStack is missing, the installer installs it with Homebrew, or opens [orbstack.dev/download](https://orbstack.dev/download) and waits while you drag the app to Applications. It also installs `cloudflared` (Homebrew `cloudflared`, or the official binary from [Cloudflare's downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/)) so the viewer can be opened on a phone.

After it finishes, these work from any terminal:

```bash
cloakroom start
cloakroom stop
cloakroom status
cloakroom amazon-login
```

**Let your AI assistant log in to websites for you.** Cloakroom runs a stealth browser ([CloakBrowser](https://github.com/CloakHQ/CloakBrowser)) in OrbStack. When Amazon texts a code, **Grok Bot or Muse** reads it from Messages and hands it to Cloakroom. Cloakroom does not read iMessage.

## The demo

```text
In Grok Bot: "Login to Amazon with cloakroom"
→ Cloakroom starts stealth Chromium in OrbStack
→ Opens Amazon sign-in
→ You enter credentials once (or the saved login fills them)
→ Amazon texts a code
→ Grok Bot or Muse reads the code from Messages and passes it to Cloakroom
→ Cloakroom types it in
→ You're logged in; the session persists
```

What the agent actually runs (defined in [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md)):

1. `cloakroom status --json`: is OrbStack up, and is the browser ready?
2. `cloakroom start` if the browser isn't running. This pulls `cloakhq/cloakbrowser` and opens the live viewer at http://127.0.0.1:6080.
3. `cloakroom amazon-login --json` opens Amazon sign-in in the persistent browser profile. It fills your email and password from the macOS Keychain, or waits while you type them in the viewer. When Amazon asks for a code, it emits `waiting_for_otp`. The assistant reads Messages, then submits the code. Cloakroom types it in and ticks "don't ask again on this device".
4. The agent reports `success`. Next time, `amazon-login` sees the saved session and returns immediately.

The agent never sees your password. The code is passed only to Cloakroom on this computer and typed straight into the browser.

From a checkout of this repo, `./cloakroom` is the same command.

---

## Why Cloakroom

A normal agent browser in a cloud VM looks like automation. It shows webdriver signals, a TLS fingerprint such as JA3, a datacenter IP, and often a headless window. Retail, travel, and ticket sites treat that as a bot, and the login stops early.

Cloakroom runs headed [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (stealth Chromium) in OrbStack on your Mac. Chromium is headed on the virtual display the viewer shows, and the profile stays on your machine. The session looks like a real browser. Amazon login is the demo because those device checks are the kind of wall this is for. The same idea covers sites behind Cloudflare Turnstile, DataDome, Akamai, and similar checks.

The sites below are examples of hard targets. Stock Playwright, a headless browser, or a browser in a datacenter VM often fails, gets challenged, or gets flagged on them. IP reputation (a datacenter address versus a home or residential one), cookies, and account history still decide a lot of what happens. Cloakroom doesn't guarantee any site's bot checks will pass.

[CloakBrowser's own tests](https://github.com/CloakHQ/CloakBrowser) claim stock Playwright fails Cloudflare Turnstile, FingerprintJS, and BrowserScan, and that CloakBrowser passes those checks. That report is upstream's. Cloakroom has not re-tested these twelve sites for this page.

| Site | Why a normal VM or automation browser often struggles |
| --- | --- |
| **Amazon** ([amazon.com](https://www.amazon.com)) | Login and account flows. Amazon's bot and device checks are the north-star demo for Cloakroom. |
| **Ticketmaster** ([ticketmaster.com](https://www.ticketmaster.com)) | Akamai Bot Manager. Simple HTTP clients often get a 403. |
| **Foot Locker** ([footlocker.com](https://www.footlocker.com)) | DataDome. Aggressive e-commerce bot protection. |
| **Hermès** ([hermes.com](https://www.hermes.com)) | DataDome (`x-datadome: protected`). |
| **Helly Hansen** ([hellyhansen.com](https://www.hellyhansen.com)) | DataDome. CloakBrowser maintainers discuss this site as a DataDome target. A residential IP still matters. |
| **StubHub** ([stubhub.com](https://www.stubhub.com)) | DataDome. |
| **Tripadvisor** ([tripadvisor.com](https://www.tripadvisor.com)) | DataDome. |
| **Zillow** ([zillow.com](https://www.zillow.com)) | HUMAN / PerimeterX-style blocks (`x-px-blocked` on non-browser clients). |
| **Expedia** ([expedia.com](https://www.expedia.com)) | Akamai. Automated clients often hit a rate or bot wall (for example 429). |
| **Nike** ([nike.com](https://www.nike.com)) | Akamai at the edge. Checkout and login flows are famously hostile to automation. |
| **Reddit** ([reddit.com](https://www.reddit.com)) | Blocks naive automated clients (403). |
| **FingerprintJS Playground** ([demo.fingerprint.com/playground](https://demo.fingerprint.com/playground)) | A public detection demo. Stock Playwright is flagged there, and CloakBrowser's docs claim a pass. [browserscan.net](https://browserscan.net) is the related check in those same docs. |

---

## How the code gets in

Cloakroom does not read Messages, `~/Library/Messages/chat.db`, or Full Disk Access. That is the assistant's job.

When the sign-in page asks for a code, `amazon-login` prints:

```json
{"event": "waiting_for_otp", "submit_url": "http://127.0.0.1:<port>/otp", "detail": "..."}
```

Grok Bot or Muse reads the new Amazon code from Messages and submits it while `amazon-login` is still running:

```bash
curl -fsS -X POST "$submit_url" \
  -H 'content-type: application/json' \
  -d '{"code":"123456"}'
```

A body that is only the digits works too. The port is chosen when the login starts and is only reachable on this computer.

If the assistant already has the code, it can pass it at the start instead:

```bash
cloakroom amazon-login --otp "$CODE" --json
CLOAKROOM_OTP="$CODE" cloakroom amazon-login --json
```

A single line on that command's stdin is also accepted. You can always type the code in the viewer yourself.

The code is not printed in `amazon-login` output.

---

## Use it with an agent

- **Grok Bot, Muse, Cursor, Claude Code, Codex, or anything that reads repo instructions:** open this folder in the agent. [`AGENTS.md`](AGENTS.md) points it to the [Cloakroom skill](skills/cloakroom/SKILL.md), which has the exact commands, the JSON events, and the rules (the assistant fetches the iMessage code; never ask for the password in chat).
- **Skill-aware agents:** copy or symlink `skills/cloakroom` into the agent's skills folder (for example `~/.cursor/skills/cloakroom`).

The CLI is the contract. Every command takes `--json`:

| Command | What it does |
| --- | --- |
| `cloakroom start` / `stop` | Start or stop the browser. Your logins are kept. |
| `cloakroom status --json` | `docker_running`, `ready`, `browser`, `viewer_url`, `cdp_url`, `share_url`, `amazon_credentials` |
| `cloakroom share` / `share --json` | One command. Starts a temporary HTTPS link to the viewer and prints it. No confirmation. `{"event":"share_ready","url":"https://….trycloudflare.com","viewer_local":"http://127.0.0.1:6080"}`. |
| `cloakroom unshare` / `share stop` | Stop that link. The URL stops working. |
| `cloakroom amazon-login --json` | Streams events (`browser_connected`, `waiting_for_user`, `email_filled`, `password_filled`, `sending_code`, `waiting_for_otp`, `otp_filled`, `otp_timeout`, `success`, `timeout`). Exit code `0` means logged in. |
| `cloakroom creds set` / `forget` / `status` | Manage the Amazon login in the macOS Keychain. |

**Optional:** save your Amazon login so you never type it again: `cloakroom creds set`. The password goes into your macOS Keychain, never into a file or the repo. `cloakroom creds forget` removes it.

**Newest CloakBrowser build:** get a free key at [cloakbrowser.dev/free](https://cloakbrowser.dev/free) and put it in `.env` as `CLOAKBROWSER_LICENSE_KEY` (see [Settings](#settings)).

---

## Watch and take over: the viewer

http://127.0.0.1:6080 shows the real browser, live. You can click and type in it. Use it to enter credentials the first time, solve a puzzle if Amazon shows one, type a code yourself, or just watch the agent work. `cloakroom start` opens it for you.

### On your phone

`cloakroom share` is one command. It starts the browser if it is not already running, opens a Cloudflare quick tunnel to **the viewer only**, and prints an `https://….trycloudflare.com` link. It does not ask you to confirm. Open that link in Safari or Chrome. An agent (Grok Bot or Muse) should run `cloakroom share` and send you the link immediately, with no approval step. The pid and URL are saved in `~/.cloakroom/share.json`. `cloakroom status` shows the link while it is active.

```bash
cloakroom share
cloakroom unshare
```

That link is a secret capability URL: anyone who has it can control the logged-in browser. Stop it with `cloakroom unshare` (or `cloakroom share stop`) when you are done. Each new share gets a new link; the old one dies.

This is the remote path. Do not use Tailscale, Cloudflare Funnel, or a port forward. Ports 6080 and 9222 stay on `127.0.0.1`. The tunnel never carries port 9222 (the DevTools port). Amazon codes are still submitted to the localhost `submit_url` from `waiting_for_otp`, not to the share link.

---

## Settings

`cloakroom start` creates a `.env` file the first time. Edit it with TextEdit, then run `cloakroom stop` and `cloakroom start`.

| Setting | What it does |
| --- | --- |
| `CLOAKBROWSER_LICENSE_KEY` | Uses the newest CloakBrowser build. Free key via GitHub sign-in: [cloakbrowser.dev/free](https://cloakbrowser.dev/free). Leave blank to use the free build in the image. |
| `CLOAKROOM_PROXY` | Sends browser traffic through a proxy, e.g. `http://user:pass@host:8080` or `socks5://host:1080`. |
| `CLOAKROOM_FINGERPRINT_SEED` | Any number, e.g. `48213`. Keeps the same browser fingerprint across restarts, which is recommended once you're logged in to sites. |
| `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT` | Change these only if 9222 or 6080 is already in use. Export the same variables when running `cloakroom` so the CLI finds them. |

`.env` is git-ignored and stays on your computer.

---

## Troubleshooting

**`waiting_for_otp` and no code shows up**
The assistant reads Messages and POSTs the code to `submit_url`. If it can't see the text, type the code in the viewer. The login keeps running.

**`otp_timeout`**
No code was handed to Cloakroom in time. Submit it to the same `submit_url`, or type it in the viewer.

**`waiting_for_user` with "a page Cloakroom doesn't recognize"**
Amazon sometimes shows a puzzle or an extra "is this you?" step. Finish it in the viewer, and the command picks up where it left off.

**"OrbStack did not become ready"**
Open OrbStack from Applications and finish its first-run setup (it may ask for your Mac password). Then run `cloakroom start` again. Download: https://orbstack.dev/download

**"python3 not found"**
Run `xcode-select --install` once to get Apple's command-line tools, which include Python.

**"permission denied: ./cloakroom"**
Run `chmod +x cloakroom start.sh stop.sh install.sh` once, or use `bash cloakroom …`.

**"cloudflared is not installed"**
On a Mac: `brew install cloudflared`. Without Homebrew, download the binary from [Cloudflare's downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/) and put `cloudflared` on your PATH (the Mac installer does this). Then run `cloakroom share` again.

**"port is already allocated"**
Something else uses 9222 or 6080 (often a Chrome started with remote debugging). Close it, or change the ports in `.env`.

**Tabs crash ("Aw, Snap!") or it's slow**
Quit other heavy apps and run `cloakroom start` again. OrbStack's memory settings are in the OrbStack app.

**Apple Silicon**
Runs natively. You don't need Rosetta.

**"License" or "concurrent session" errors**
A free key allows one browser session at a time. Stop other CloakBrowser sessions (including `examples/cloaktest.sh`) or leave the key blank.

**Logs / start fresh**
`docker compose logs -f cloakroom` shows the browser server's log. `docker compose down -v` deletes the saved profile, which logs you out of everything.

---

## Windows

The browser and viewer work on Windows with Docker Desktop. The one-line installer is Mac-only because it sets up OrbStack. The code handoff is the same: `amazon-login` emits `waiting_for_otp`, and the assistant POSTs the code. You can also type the code in the viewer.

Phone viewer: install [cloudflared](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/) (`winget install --id Cloudflare.cloudflared`), then run `cloakroom share` from Git Bash or the same `./cloakroom` launcher. `cloakroom unshare` stops it.

1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/). It needs **WSL 2**, and the installer offers to turn it on. Restart, open Docker Desktop, and wait for **Engine running**.
2. Download this repo (**Code > Download ZIP**, then Extract All) or `git clone` it.
3. In PowerShell, in the `cloakroom` folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

4. Try it: `docker compose run --rm hello` opens example.com in the browser and prints its title.
5. Stop: `powershell -ExecutionPolicy Bypass -File .\stop.ps1`

---

## Advanced

### What's running

- **`cloakroom` container**: built from the official `cloakhq/cloakbrowser` image plus x11vnc and noVNC ([`image/Dockerfile`](image/Dockerfile)). It runs [`cloakserve`](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) with `--headless=false`, so Chromium is headed on a virtual display (Xvfb). Headed mode passes more bot checks, and it's what the viewer shows. It has `shm_size: 2gb` (Chromium crashes with Docker's 64 MB default) and a healthcheck on `/json/version`.
- **Volumes**: `profile` holds the browser profile (`/profile/default`, which keeps you logged in), and `binary-cache` (`~/.cloakbrowser`) keeps a licensed binary so it downloads once. `cloakserve` normally deletes its profile folder on exit. [`image/cloakroom-serve.sh`](image/cloakroom-serve.sh) points that folder at the volume through a symlink that `cloakserve` refuses to delete.
- **`cloakroom` CLI** (on your Mac, [`cli/`](cli/)): Python with the Playwright client in `cli/.venv`, created on first run. It needs no browser download, because it drives the Docker browser over CDP. `start`/`stop` call [`start.sh`](start.sh)/[`stop.sh`](stop.sh), which also work on their own.

### Connect your own scripts (CDP)

The browser speaks the Chrome DevTools Protocol at `http://127.0.0.1:9222`:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].new_page()   # contexts[0] = the saved, logged-in profile
    page.goto("https://www.amazon.com/gp/css/order-history")
    print(page.title())
```

`browser.close()` on a CDP connection only disconnects your script, and the browser keeps running. [`examples/hello.py`](examples/hello.py) is the smallest example (`docker compose run --rm hello`).

### Extra identities

Add `?fingerprint=<seed>` to the CDP URL for a separate identity with its own fingerprint, e.g. `http://127.0.0.1:9222?fingerprint=11111&timezone=Europe/Berlin`. Only the default identity is saved to the `profile` volume. See [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) for all parameters.

### Stealth test, updates, plain Compose

- `./examples/cloaktest.sh` runs upstream's bot-detection suite with your `.env` settings.
- `cloakroom start` always pulls the latest `cloakhq/cloakbrowser`. To pin a version, change `FROM cloakhq/cloakbrowser:latest` in `image/Dockerfile` to a tag like `0.5.11`.
- Without the scripts: `cp .env.example .env && docker compose up -d --build`, then `docker compose down`.

---

## Security and privacy

- **Ports 9222 and 6080 stay on `127.0.0.1`.** Port 9222 gives full control of a browser that's logged in to your accounts, and the viewer has no password. Do not publish either port, and do not use Tailscale or Funnel. The phone path is `cloakroom share`: a Cloudflare quick tunnel to the viewer only. The `https://….trycloudflare.com` link is a capability URL — anyone who has it can control the logged-in browser. Run `cloakroom unshare` when you are done. The link changes every time you share. The tunnel never includes port 9222.
- **Passwords** live in the macOS Keychain (`cloakroom creds set`) or are typed by you in the viewer. They're never kept in the repo, `.env`, or agent chat. The email is kept in `~/.cloakroom/amazon.json`.
- **One-time codes** are read by the assistant (Grok Bot or Muse) from Messages. Cloakroom only receives the code on `127.0.0.1` and types it into the browser. It does not read Messages, and it does not log the code.
- `.env` (license key, proxy password) is git-ignored.

---

## Links and license

- CloakBrowser (upstream): <https://github.com/CloakHQ/CloakBrowser>
- Free license key: <https://cloakbrowser.dev/free>
- Docker image: <https://hub.docker.com/r/cloakhq/cloakbrowser>
- OrbStack: <https://orbstack.dev/>

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, isn't affiliated with Amazon or CloakHQ, and doesn't guarantee any site's bot checks will pass. Use it only with your own accounts and follow each site's terms.
