# Cloakroom

**A stealth browser on your Mac that your AI agent can drive, for the sites that block cloud browsers.**

AI agents like Grok Bot and Muse usually browse from a cloud server. Many big sites (retailers, ticketing, travel, job boards) see a datacenter IP and an automated browser, and answer with a 403, a "press and hold" puzzle, or a Cloudflare wall. The agent is stuck before it can read a page, sign in, or do anything useful.

Cloakroom gives your agent a browser that runs on your own Mac instead. It is [CloakBrowser](https://github.com/CloakHQ/CloakBrowser), a stealth build of Chromium, running in OrbStack with a profile that stays logged in. Your agent starts it and checks on it with the `cloakroom` command, and drives pages over the standard Chrome DevTools Protocol. You can watch it work, or take over, from your Mac or your phone.

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

Then open this folder in your agent and ask it to use Cloakroom for the site that keeps blocking it.

---

## What you get

- **A stealth browser your agent can call.** Headed CloakBrowser on your Mac. `cloakroom start` and `cloakroom status --json` manage it; Playwright or Puppeteer drive it at `http://127.0.0.1:9222`.
- **Logins that stick, on any site.** The browser profile lives on your Mac. Sign in once (your agent, or you in the viewer) and the session is still there next time.
- **You stay in the loop.** A live viewer at http://127.0.0.1:6080 shows the real browser. Click and type in it to enter a password, solve a puzzle, or just watch.
- **The same window on your phone.** `cloakroom share` prints a private HTTPS link to the viewer, so you can help from anywhere.
- **Two-factor codes stay with your agent.** Cloakroom never reads your Messages or email. When a site asks for a code, your agent fetches it and enters it.
- **A worked example to copy.** `cloakroom amazon-login` is a complete sign-in flow, including handing a text-message code from the agent to the browser.

---

## Why a browser on your Mac

A cloud browser gives itself away three ways: automation fingerprints, a datacenter IP, and often a headless window. Cloakroom changes all three. CloakBrowser is built to hide the automation fingerprints, the browser runs headed (with a real window you can see in the viewer), and its traffic leaves from your Mac's internet connection, or from a proxy you choose.

**Proof point.** On September 26, 2026 we opened twelve homepages from a cloud agent on a datacenter IP, and again from Cloakroom on a Mac. The cloud browser was blocked or challenged on all twelve. Cloakroom loaded all twelve: Home Depot, Ticketmaster, Sam's Club, Sephora, Tripadvisor, Etsy, Newegg, American Airlines, Fanatics, Indeed, Glassdoor, and Vinted. Those were homepages, not logins or checkouts, and results change over time.

**"Can't I just route my agent through my Mac?"** Often, yes. Grok Bot's **Route traffic through this computer** setting sends its cloud browser's traffic out through your Mac, and that alone cleared many of the same IP blocks. Cloakroom is for when that isn't enough: when the site also checks the browser itself (Sam's Club still showed its press-and-hold page to the routed browser, and loaded in Cloakroom), or when you want a login that lives on your machine and a browser you can watch and take over.

---

## How it works

```text
Your agent ──► cloakroom CLI ─────────► start / stop / status / share
     │
     └───────► DevTools (CDP) ─────────► CloakBrowser, headed, in OrbStack on your Mac
                http://127.0.0.1:9222     ├─ saved profile: stays logged in
                                          └─ viewer: http://127.0.0.1:6080
                                                └─ cloakroom share ──► private HTTPS link (your phone)
```

- The browser runs in the background, as long as OrbStack is running, until you run `cloakroom stop`. Stopping keeps your logins.
- Every `cloakroom` command takes `--json`, so agents can read the results.
- Nothing is reachable beyond your Mac except the viewer link you create with `cloakroom share`.

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

The installer:

1. Installs **OrbStack** (not Docker Desktop) with Homebrew. Without Homebrew, it opens [orbstack.dev/download](https://orbstack.dev/download) and waits while you drag OrbStack to Applications.
2. Installs `cloudflared`, used only by `cloakroom share`.
3. Downloads Cloakroom to `~/.cloakroom/app` and puts the `cloakroom` command on your PATH.
4. Starts the browser and opens the viewer. The first start downloads about 1 GB.

You need a Mac with Python 3. If `python3` is missing, run `xcode-select --install` once. Apple Silicon runs natively.

From a checkout of this repo, `./cloakroom` is the same command.

---

## Drive it from your agent

**Point your agent at it.** Grok Bot, Muse, Cursor, Claude Code, Codex, or anything that reads repo instructions: open this folder in the agent. [`AGENTS.md`](AGENTS.md) points it to the [Cloakroom skill](skills/cloakroom/SKILL.md), which has the commands, JSON events, and rules. Skill-aware agents can also copy or symlink `skills/cloakroom` into their skills folder (for example `~/.cursor/skills/cloakroom`).

**Manage the browser with the CLI:**

| Command | What it does |
| --- | --- |
| `cloakroom start` / `stop` | Start or stop the browser. Your logins are kept. |
| `cloakroom status --json` | Is OrbStack up, is the browser ready, and the viewer, DevTools, and share URLs. |
| `cloakroom share --json` | Start a private HTTPS link to the viewer and print it. |
| `cloakroom unshare` | Stop that link. It stops working immediately. |

**Drive pages over DevTools.** Any Playwright or Puppeteer script can connect. `contexts[0]` is the saved, logged-in profile:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].new_page()
    page.goto("https://www.homedepot.com")
    print(page.title())
```

`browser.close()` on a DevTools connection only disconnects the script; the browser keeps running. [`examples/hello.py`](examples/hello.py) is the smallest example.

A simple pattern for a site that needs a login: sign in once yourself in the viewer, then let your agent reuse that session.

---

## Two-factor codes

**Your agent owns the code. Cloakroom never reads Messages, email, or your authenticator app.** It doesn't touch `~/Library/Messages/chat.db` and doesn't need Full Disk Access.

When a site asks for a code, your agent (which may already be able to read your Messages) gets it and puts it in the page, either by typing it through its own DevTools script or by passing it to Cloakroom's built-in login flow. You can always type the code in the viewer yourself.

Cloakroom's built-in login flow (today, the [Amazon example](#example-a-complete-login-flow-amazon)) takes the code on a local address. When the page asks for a code, the flow prints:

```json
{"event": "waiting_for_otp", "submit_url": "http://127.0.0.1:<port>/otp", "detail": "..."}
```

and the agent posts the code while the flow keeps running:

```bash
curl -fsS -X POST "$submit_url" \
  -H 'content-type: application/json' \
  -d '{"code":"123456"}'
```

A body with only the digits works too. The address is only reachable from your Mac, and Cloakroom never prints the code.

---

## Example: a complete login flow (Amazon)

`cloakroom amazon-login` is the built-in example of a full agent-driven sign-in. It's the flow to copy if you want the same shape for another site.

1. The agent runs `cloakroom amazon-login --json`. Cloakroom opens Amazon sign-in in the saved profile. If you're already signed in, it reports `success` right away.
2. It fills your email and password from the macOS Keychain, or waits while you type them in the viewer.
3. Amazon texts a code, and Cloakroom prints `waiting_for_otp`.
4. The agent reads the code from Messages and posts it to `submit_url`. Cloakroom types it in and ticks "don't ask again on this device".
5. Exit code `0` means signed in. The session is saved for next time.

The agent can also pass a code up front with `--otp "$CODE"`, `CLOAKROOM_OTP="$CODE"`, or a single line on stdin. To save the Amazon login this flow uses, run `cloakroom creds set` in your own terminal (the password goes into the macOS Keychain); `cloakroom creds forget` removes it.

Progress events: `browser_connected`, `waiting_for_user`, `email_filled`, `password_filled`, `sending_code`, `waiting_for_otp`, `otp_filled`, `otp_timeout`, `success`, `timeout`.

---

## Watch or take over, from your Mac or your phone

http://127.0.0.1:6080 shows the real browser, live, and you can click and type in it. `cloakroom start` opens it for you.

When you're away from your Mac, run (or have your agent run):

```bash
cloakroom share
```

It starts the browser if needed, opens a Cloudflare quick tunnel to **the viewer only**, and prints an `https://….trycloudflare.com` link. There's no confirmation step, so an agent can send you the link straight away. Open it in Safari or Chrome on your phone.

**Treat that link like a key.** Anyone who has it can control your logged-in browser. It lasts until you run `cloakroom unshare`, and every new share gets a new link. The tunnel never carries the DevTools port (9222), and two-factor codes still go to the local `submit_url`, not the share link.

---

## Settings

`cloakroom start` creates a `.env` file the first time. Edit it, then run `cloakroom stop` and `cloakroom start`.

| Setting | What it does |
| --- | --- |
| `CLOAKROOM_PROXY` | Send browser traffic through a proxy, e.g. `http://user:pass@host:8080` or `socks5://host:1080`. |
| `CLOAKROOM_FINGERPRINT_SEED` | Any number, e.g. `48213`. Keeps the same browser fingerprint across restarts. Recommended once you're logged in to sites. |
| `CLOAKBROWSER_LICENSE_KEY` | Use the newest CloakBrowser build. Free key with GitHub sign-in at [cloakbrowser.dev/free](https://cloakbrowser.dev/free). Leave blank to use the build in the image. |
| `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT` | Change only if 9222 or 6080 is already in use. Export the same variables when running `cloakroom`. |

`.env` is git-ignored and stays on your Mac.

---

## What Cloakroom doesn't promise

- **No site is guaranteed.** Bot checks change constantly. Something that loads today may be challenged tomorrow.
- **A homepage isn't a login.** Loading a storefront is not the same as signing in, checking out, or buying tickets on sale.
- **Your IP still matters.** Stealth is not magic. Traffic leaves from your Mac's connection, or from `CLOAKROOM_PROXY`. A flagged IP, VPN, or datacenter proxy can still get you challenged. A good residential connection or proxy helps.
- **It doesn't solve CAPTCHAs.** If a site shows a puzzle, you finish it in the viewer.
- **It's a browser, not a site-by-site bot.** Your agent decides what to do on each page. Amazon is the only sign-in flow Cloakroom ships ready-made.
- **Your accounts, their rules.** Use Cloakroom only with your own accounts, and follow each site's terms.

---

## Security and privacy

- **Ports 9222 and 6080 stay on `127.0.0.1`.** Port 9222 gives full control of a browser that's logged in to your accounts, and the viewer has no password. Don't publish either port, and don't expose them with Tailscale, Funnel, or a port forward. The only remote path is `cloakroom share`, which tunnels the viewer only.
- **Passwords** are typed by you in the viewer, or, for the Amazon example flow, kept in the macOS Keychain with `cloakroom creds set`. They are never kept in the repo, `.env`, or chat.
- **Two-factor codes** are fetched by your agent, received by Cloakroom only on `127.0.0.1`, typed into the browser, and never logged.
- **`.env`** (license key, proxy password) is git-ignored.

---

## Troubleshooting

**"OrbStack did not become ready".** Open OrbStack from Applications and finish its first-run setup (it may ask for your Mac password), then run `cloakroom start` again.

**"python3 not found".** Run `xcode-select --install` once.

**"permission denied: ./cloakroom".** Run `chmod +x cloakroom start.sh stop.sh install.sh` once, or use `bash cloakroom …`.

**"port is already allocated".** Something else uses 9222 or 6080, often a Chrome started with remote debugging. Close it, or change the ports in `.env`.

**"cloudflared is not installed".** Run `brew install cloudflared`, or download it from [Cloudflare's downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/) and put it on your PATH. Then run `cloakroom share` again.

**`waiting_for_otp` and no code shows up.** The agent should fetch the code and post it to `submit_url`. If it can't, type the code in the viewer. The flow keeps running.

**`otp_timeout`.** No code arrived in time. Post it to the same `submit_url`, or type it in the viewer.

**`waiting_for_user` with "a page Cloakroom doesn't recognize".** The site showed a puzzle or an extra "is this you?" step. Finish it in the viewer and the flow picks up where it left off.

**Tabs crash ("Aw, Snap!") or it's slow.** Quit other heavy apps and run `cloakroom start` again. OrbStack's memory settings are in the OrbStack app.

**"License" or "concurrent session" errors.** A free key allows one browser session at a time. Stop other CloakBrowser sessions (including `examples/cloaktest.sh`) or leave the key blank.

**Logs, or start fresh.** `docker compose logs -f cloakroom` shows the browser's log. `docker compose down -v` deletes the saved profile, which signs you out of everything.

---

## Windows

The browser and viewer also run on Windows with Docker Desktop. The one-line installer is Mac-only.

1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) (it needs WSL 2), restart, and wait for **Engine running**.
2. Download this repo (**Code > Download ZIP**, then Extract All) or `git clone` it.
3. In PowerShell, in the `cloakroom` folder: `powershell -ExecutionPolicy Bypass -File .\start.ps1`
4. Try it: `docker compose run --rm hello` opens example.com and prints its title.
5. Stop: `powershell -ExecutionPolicy Bypass -File .\stop.ps1`

For the phone viewer, install `cloudflared` (`winget install --id Cloudflare.cloudflared`) and run `cloakroom share` from Git Bash.

---

## Advanced

### What's running

- **`cloakroom` container:** the official `cloakhq/cloakbrowser` image plus x11vnc and noVNC ([`image/Dockerfile`](image/Dockerfile)). It runs [`cloakserve`](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) headed on a virtual display, which passes more bot checks and is what the viewer shows. It has `shm_size: 2gb` (Chromium crashes with the 64 MB default) and a healthcheck on `/json/version`.
- **Volumes:** `profile` holds the browser profile that keeps you logged in. `binary-cache` keeps a licensed binary so it downloads once. [`image/cloakroom-serve.sh`](image/cloakroom-serve.sh) keeps `cloakserve` from deleting the profile on exit.
- **`cloakroom` CLI** ([`cli/`](cli/)): Python with the Playwright client in `cli/.venv`, created on first run. It drives the container's browser over DevTools, so it needs no browser download of its own.

### Extra identities

Add `?fingerprint=<seed>` to the DevTools URL for a separate identity, e.g. `http://127.0.0.1:9222?fingerprint=11111&timezone=Europe/Berlin`. Only the default identity is saved to the `profile` volume. See the [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) for all parameters.

### Stealth test, updates, plain Compose

- `./examples/cloaktest.sh` runs upstream's bot-detection suite with your `.env` settings.
- `cloakroom start` always pulls the latest `cloakhq/cloakbrowser`. To pin a version, change `FROM cloakhq/cloakbrowser:latest` in `image/Dockerfile` to a tag like `0.5.11`.
- Without the scripts: `cp .env.example .env && docker compose up -d --build`, then `docker compose down`.

---

## Links and license

- CloakBrowser: <https://github.com/CloakHQ/CloakBrowser> (it targets Cloudflare Turnstile, HUMAN / PerimeterX, Akamai, DataDome, and Kasada)
- Free license key: <https://cloakbrowser.dev/free>
- Docker image: <https://hub.docker.com/r/cloakhq/cloakbrowser>
- OrbStack: <https://orbstack.dev/>

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, not affiliated with Amazon, CloakHQ, or any site mentioned here.
