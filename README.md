# Cloakroom

**A stealth browser on your Mac for AI agents: better automation, sessions that persist, and fewer bot walls.**

AI agents like Grok Bot and Muse usually browse from a cloud server. Many big sites (retailers, ticketing, travel, job boards) see a datacenter IP and an automated browser, and answer with a 403, a "press and hold" puzzle, or a Cloudflare wall. Even when a page loads, the agent's cookies vanish with the session, so it has to sign in again every time.

Cloakroom gives your agent a browser that runs on your own Mac instead:

- **Harder to detect.** It's [CloakBrowser](https://github.com/CloakHQ/CloakBrowser), a stealth build of Chromium, running headed on your Mac's connection instead of a datacenter's.
- **Sessions that persist.** One saved profile keeps cookies and logins across runs and restarts. Sign in once, and every later run is already signed in.
- **Standard automation.** Your agent drives it over the Chrome DevTools Protocol (CDP) with Playwright, Puppeteer, or any tool that can attach to an existing Chrome.
- **You can watch and help.** A live viewer shows the real browser, on your Mac or your phone, so you can type a password or solve a puzzle when the agent can't.

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

Then open this folder in your agent and ask it to use Cloakroom for the site that keeps blocking it.

---

## Why a browser on your Mac

A cloud browser gives itself away three ways: automation fingerprints, a datacenter IP, and often a headless window. Cloakroom changes all three. CloakBrowser is built to hide the automation fingerprints, the browser runs headed (with a real window you can see in the viewer), and its traffic leaves from your Mac's internet connection, or from a proxy you choose.

**Proof point.** On September 26, 2026 we opened twelve homepages from a cloud agent on a datacenter IP, and again from Cloakroom on a Mac. The cloud browser was blocked or challenged on all twelve. Cloakroom loaded all twelve: Home Depot, Ticketmaster, Sam's Club, Sephora, Tripadvisor, Etsy, Newegg, American Airlines, Fanatics, Indeed, Glassdoor, and Vinted. Those were homepages, not logins or checkouts, and results change over time.

**"Can't I just route my agent through my Mac?"** Often, yes. Grok Bot's **Route traffic through this computer** setting sends its cloud browser's traffic out through your Mac, and that alone cleared many of the same IP blocks. Cloakroom is for when that isn't enough: when the site also checks the browser itself (Sam's Club still showed its press-and-hold page to the routed browser, and loaded in Cloakroom), or when you want cookies and logins that live on your machine and a browser you can watch and take over.

---

## How it works

```text
Your agent ──► cloakroom ───────────────► start / stop / status / share
     │
     └───────► CDP  http://127.0.0.1:9222 ─► CloakBrowser, headed, in OrbStack on your Mac
                                              ├─ saved profile: cookies and logins persist
                                              └─ viewer: http://127.0.0.1:6080
                                                   └─ cloakroom share ──► private HTTPS link (your phone)
```

- The browser runs in the background, as long as OrbStack is running, until you run `cloakroom stop`. Stopping keeps the profile.
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

## Use it from your agent

**Point your agent at it.** Grok Bot, Muse, Cursor, Claude Code, Codex, or anything that reads repo instructions: open this folder in the agent. [`AGENTS.md`](AGENTS.md) points it to the [Cloakroom skill](skills/cloakroom/SKILL.md). Skill-aware agents can also copy or symlink `skills/cloakroom` into their skills folder (for example `~/.cursor/skills/cloakroom`).

**Drive pages over CDP.** `contexts[0]` is the saved profile, with all its cookies:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
    page = browser.contexts[0].new_page()
    page.goto("https://www.homedepot.com")
    print(page.title())
```

`browser.close()` on a CDP connection only disconnects the script; the browser and its cookies stay. [`examples/hello.py`](examples/hello.py) is the smallest example.

**Manage the browser with `cloakroom`.** Every command takes `--json`:

| Command | What it does |
| --- | --- |
| `cloakroom start` / `stop` | Start or stop the browser. The profile is kept. |
| `cloakroom status --json` | Is OrbStack up, is the browser ready, and the viewer, CDP, and share URLs. |
| `cloakroom share --json` | Start a private HTTPS link to the viewer and print it. |
| `cloakroom unshare` | Stop that link. It stops working immediately. |

**Signing in.** The simplest pattern: sign in once yourself in the viewer, then let your agent reuse the session. Or let the agent sign in, and step into the viewer when it hits something it can't do.

**Two-factor codes.** Cloakroom never reads your Messages, email, or authenticator app. If a site asks for a code, your agent gets it (some agents can read your Messages) and types it into the page, or you type it in the viewer.

---

## Watch or take over, from your Mac or your phone

http://127.0.0.1:6080 shows the real browser, live, and you can click and type in it. `cloakroom start` opens it for you.

When you're away from your Mac, run (or have your agent run):

```bash
cloakroom share
```

It starts the browser if needed, opens a Cloudflare quick tunnel to **the viewer only**, and prints an `https://….trycloudflare.com` link. There's no confirmation step, so an agent can send you the link straight away. Open it in Safari or Chrome on your phone.

**Treat that link like a key.** Anyone who has it can control your logged-in browser. It lasts until you run `cloakroom unshare`, and every new share gets a new link. The tunnel never carries the CDP port (9222).

---

## Settings

`cloakroom start` creates a `.env` file the first time. Edit it, then run `cloakroom stop` and `cloakroom start`.

| Setting | What it does |
| --- | --- |
| `CLOAKROOM_PROXY` | Send browser traffic through a proxy, e.g. `http://user:pass@host:8080` or `socks5://host:1080`. |
| `CLOAKROOM_FINGERPRINT_SEED` | Any number, e.g. `48213`. Keeps the same browser fingerprint across restarts. Recommended once you're signed in to sites, so they keep seeing the same browser. |
| `CLOAKBROWSER_LICENSE_KEY` | Use the newest CloakBrowser build. Free key with GitHub sign-in at [cloakbrowser.dev/free](https://cloakbrowser.dev/free). Leave blank to use the build in the image. |
| `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT` | Change only if 9222 or 6080 is already in use. Export the same variables when running `cloakroom`. |

`.env` is git-ignored and stays on your Mac.

---

## What Cloakroom doesn't promise

- **No site is guaranteed.** Bot checks change constantly. Something that loads today may be challenged tomorrow.
- **A homepage isn't a login.** Loading a storefront is not the same as signing in, checking out, or buying tickets on sale.
- **Your IP still matters.** Stealth is not magic. Traffic leaves from your Mac's connection, or from `CLOAKROOM_PROXY`. A flagged IP, VPN, or datacenter proxy can still get you challenged. A good residential connection or proxy helps.
- **It doesn't solve CAPTCHAs.** If a site shows a puzzle, you finish it in the viewer.
- **It's a browser, not a bot.** Your agent decides what to do on each page. Cloakroom has no site-specific scripts.
- **Your accounts, their rules.** Use Cloakroom only with your own accounts, and follow each site's terms.

---

## Security and privacy

- **Ports 9222 and 6080 stay on `127.0.0.1`.** Port 9222 gives full control of a browser that's signed in to your accounts, and the viewer has no password. Don't publish either port, and don't expose them with Tailscale, Funnel, or a port forward. The only remote path is `cloakroom share`, which tunnels the viewer only.
- **The profile** (cookies, logins) lives in a volume on your Mac. `docker compose down -v` deletes it.
- **Passwords and codes** are typed by your agent or by you, into the browser. Cloakroom doesn't store them.
- **`.env`** (license key, proxy password) is git-ignored.

---

## Troubleshooting

**"OrbStack did not become ready".** Open OrbStack from Applications and finish its first-run setup (it may ask for your Mac password), then run `cloakroom start` again.

**"python3 not found".** Run `xcode-select --install` once.

**"permission denied: ./cloakroom".** Run `chmod +x cloakroom start.sh stop.sh install.sh` once, or use `bash cloakroom …`.

**"port is already allocated".** Something else uses 9222 or 6080, often a Chrome started with remote debugging. Close it, or change the ports in `.env`.

**"cloudflared is not installed".** Run `brew install cloudflared`, or download it from [Cloudflare's downloads](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/) and put it on your PATH. Then run `cloakroom share` again.

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
- **Volumes:** `profile` holds the browser profile (cookies and logins). `binary-cache` keeps a licensed binary so it downloads once. [`image/cloakroom-serve.sh`](image/cloakroom-serve.sh) keeps `cloakserve` from deleting the profile on exit.
- **`cloakroom` command** ([`cli/`](cli/)): a small Python tool with no dependencies. `start`/`stop` run [`start.sh`](start.sh)/[`stop.sh`](stop.sh), which also work on their own; `share` runs `cloudflared`.

### Extra identities

Add `?fingerprint=<seed>` to the CDP URL for a separate identity, e.g. `http://127.0.0.1:9222?fingerprint=11111&timezone=Europe/Berlin`. Only the default identity is saved to the `profile` volume. See the [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) for all parameters.

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

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, not affiliated with CloakHQ or any site mentioned here.
