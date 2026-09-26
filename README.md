# Cloakroom

**Let your AI assistant log in to websites for you, 2FA code included.**

Cloakroom gives agents like Grok Bot a stealth browser ([CloakBrowser](https://github.com/CloakHQ/CloakBrowser), in Docker) and a Mac companion that reads one-time codes from your Messages app. Point an agent at this repo and say one sentence.

## The demo

```text
In Grok Bot: "Login to Amazon with cloakroom"
→ Cloakroom starts stealth Chromium in Docker
→ Opens Amazon sign-in
→ You enter credentials once (or password manager fills)
→ Amazon sends a code to your iPhone/Mac Messages
→ Cloakroom reads the code from iMessage and submits it
→ You're logged in; session persists
```

What the agent actually runs (defined in [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md)):

1. `./cloakroom status --json`: is Docker up, is the browser ready, can Cloakroom read Messages, are Amazon credentials stored?
2. `./cloakroom start` if the browser isn't running. This pulls `cloakhq/cloakbrowser` and opens the live viewer at http://127.0.0.1:6080.
3. `./cloakroom amazon-login --json` opens Amazon sign-in in the persistent browser profile. It fills your email and password from the macOS Keychain, or waits while you type them in the viewer. It picks "text me a code", watches Messages for the new Amazon code, types it in, and ticks "don't ask again on this device".
4. The agent reports `success`. Next time, `amazon-login` sees the saved session and returns immediately.

The agent never sees your password. Codes are read on your Mac and typed straight into the browser. Nothing is uploaded anywhere.

---

## Set up on a Mac (once)

You need about 10 minutes and a Mac with Apple Silicon or Intel.

1. **Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)**, open it, and wait for **Engine running**.
2. **Get Cloakroom**. Clone it (`git clone https://github.com/jonclegg/cloakroom.git`) <!-- // pragma: allowlist secret --> or use **Code > Download ZIP**.
3. **Forward texts to your Mac.** Amazon sends codes as SMS. On your iPhone, open **Settings > Apps > Messages > Text Message Forwarding** and turn on your Mac. (iMessages already sync.)
4. **Let Cloakroom read Messages.** Open **System Settings > Privacy & Security > Full Disk Access** and turn on the app that will run Cloakroom: Terminal, iTerm, Cursor, or your agent's app. Quit and reopen that app. Running `./cloakroom messages-access` opens the right settings page for you.
5. **Start it**:

   ```bash
   cd cloakroom
   ./cloakroom start
   ./cloakroom status
   ```

   `status` should say `Container: healthy` and `Messages access: ok`. The first run installs a small Python helper and downloads the browser (~1 GB).

**Optional:**

- **Save your Amazon login** so you never type it again: `./cloakroom creds set`. The password goes into your macOS Keychain, never into a file or the repo. `./cloakroom creds forget` removes it.
- **Newest CloakBrowser build:** get a free key at [cloakbrowser.dev/free](https://cloakbrowser.dev/free) and put it in `.env` as `CLOAKBROWSER_LICENSE_KEY` (see [Settings](#settings)).

Now tell your agent: **"Login to Amazon with cloakroom."**

---

## Use it with an agent

- **Grok Bot, Cursor, Claude Code, Codex, or anything that reads repo instructions:** open this folder in the agent. [`AGENTS.md`](AGENTS.md) points it to the [Cloakroom skill](skills/cloakroom/SKILL.md), which has the exact commands, the JSON events, what to tell you at each step, and the rules (never ask for your password in chat).
- **Skill-aware agents:** copy or symlink `skills/cloakroom` into the agent's skills folder (for example `~/.cursor/skills/cloakroom`).

The CLI is the contract. Every command takes `--json`:

| Command | What it does |
| --- | --- |
| `./cloakroom start` / `stop` | Start or stop the browser. Your logins are kept. |
| `./cloakroom status --json` | `docker_running`, `ready`, `browser`, `viewer_url`, `cdp_url`, `messages_access` (`ok` / `no_permission` / `missing` / `mac_only`), `amazon_credentials` |
| `./cloakroom amazon-login --json` | Streams events (`browser_connected`, `waiting_for_user`, `email_filled`, `password_filled`, `sending_code`, `otp_page`, `otp_filled`, `otp_timeout`, `success`, `timeout`). Exit code `0` means logged in. |
| `./cloakroom otp --service amazon --json` | Waits for the **next** matching code in Messages and prints it. Use this for other sites and your own scripts (`--service` is the word the text must contain). |
| `./cloakroom messages-access` | Checks Messages access and opens Full Disk Access settings if needed. |
| `./cloakroom creds set` / `forget` / `status` | Manage the Amazon login in the macOS Keychain. |

You can run the same commands yourself. `./cloakroom amazon-login` works without an agent too.

---

## How the 2FA capture works

- macOS keeps your Messages (iMessage and forwarded SMS) in `~/Library/Messages/chat.db`. With Full Disk Access, Cloakroom reads that file **locally** by taking a snapshot copy, so it never locks or changes it.
- When `amazon-login` is about to trigger a code (submitting the password, or choosing "text me"), it records the time. It then checks every 2 seconds for **incoming** messages newer than that time that mention `amazon` plus a code word (`OTP`, `code`, `verification`…), and takes the 4-8 digit code. Older codes, your own sent messages, prices, times, and phone numbers are ignored.
- It handles both plain-text messages and the binary `attributedBody` format newer macOS versions use.
- The code goes into the browser and nowhere else. It isn't printed in `amazon-login` output, logged, or uploaded. The only command that prints a code is `otp`, which you or your agent run on purpose.
- Want to turn it off? Remove the app from Full Disk Access. Everything else keeps working, and you type codes in the viewer yourself.

---

## Watch and take over: the viewer

http://127.0.0.1:6080 shows the real browser, live. You can click and type in it. Use it to enter credentials the first time, solve a puzzle if Amazon shows one, or just watch the agent work. `./cloakroom start` opens it for you.

---

## Settings

`./cloakroom start` creates a `.env` file the first time. Edit it with TextEdit, then run `./cloakroom stop` and `./cloakroom start`.

| Setting | What it does |
| --- | --- |
| `CLOAKBROWSER_LICENSE_KEY` | Uses the newest CloakBrowser build. Free key via GitHub sign-in: [cloakbrowser.dev/free](https://cloakbrowser.dev/free). Leave blank to use the free build in the image. |
| `CLOAKROOM_PROXY` | Sends browser traffic through a proxy, e.g. `http://user:pass@host:8080` or `socks5://host:1080`. |
| `CLOAKROOM_FINGERPRINT_SEED` | Any number, e.g. `48213`. Keeps the same browser fingerprint across restarts, which is recommended once you're logged in to sites. |
| `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT` | Change these only if 9222 or 6080 is already in use. Export the same variables when running `./cloakroom` so the CLI finds them. |

`.env` is git-ignored and stays on your computer.

---

## Troubleshooting

**`Messages access: no_permission`**
The app running Cloakroom needs Full Disk Access (setup step 4). Macs apply this permission to the *app*, so after turning it on, fully quit and reopen that app. When the command comes from an agent app (Cursor, Grok), that app needs the permission, not Terminal.

**`otp_timeout`: the code never arrived**
Check that the text shows up in the Mac's Messages app. If it only shows on your iPhone, turn on Text Message Forwarding (setup step 3). If Amazon sent the code by email or an authenticator app instead, type it in the viewer. The login continues after that.

**`waiting_for_user` with "a page Cloakroom doesn't recognize"**
Amazon sometimes shows a puzzle or an extra "is this you?" step. Finish it in the viewer, and the command picks up where it left off.

**"Docker Desktop is not running"**
Open Docker Desktop from Applications and wait for **Engine running**, then try again.

**"python3 not found" / an install prompt appears**
Run `xcode-select --install` once to get Apple's command-line tools, which include Python.

**"permission denied: ./cloakroom"**
Run `chmod +x cloakroom start.sh stop.sh examples/cloaktest.sh` once, or use `bash cloakroom …`.

**"port is already allocated"**
Something else uses 9222 or 6080 (often a Chrome started with remote debugging). Close it, or change the ports in `.env`.

**Tabs crash ("Aw, Snap!") or it's slow**
Docker Desktop > Settings > Resources: give Docker at least 4 GB of memory.

**Apple Silicon**
Runs natively. You don't need Rosetta. Remove `DOCKER_DEFAULT_PLATFORM=linux/amd64` if you ever set it.

**"License" or "concurrent session" errors**
A free key allows one browser session at a time. Stop other CloakBrowser sessions (including `examples/cloaktest.sh`) or leave the key blank.

**Logs / start fresh**
`docker compose logs -f cloakroom` shows the browser server's log. `docker compose down -v` deletes the saved profile, which logs you out of everything.

---

## Windows

The Docker browser, viewer, and scripts work on Windows. Automatic 2FA capture is Mac-only, because it reads the Mac Messages app. On Windows, type the code in the viewer when `amazon-login` reports `otp_page`. Windows support for phone-link SMS is a possible later addition.

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
- **`./cloakroom` CLI** (on your Mac, [`cli/`](cli/)): Python with the Playwright client in `cli/.venv`, created on first run. It needs no browser download, because it drives the Docker browser over CDP. `start`/`stop` call [`start.sh`](start.sh)/[`stop.sh`](stop.sh), which also work on their own.

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

Combine it with `./cloakroom otp --json --service <site>` for 2FA on other sites. `browser.close()` on a CDP connection only disconnects your script, and the browser keeps running. [`examples/hello.py`](examples/hello.py) is the smallest example (`docker compose run --rm hello`).

### Extra identities

Add `?fingerprint=<seed>` to the CDP URL for a separate identity with its own fingerprint, e.g. `http://127.0.0.1:9222?fingerprint=11111&timezone=Europe/Berlin`. Only the default identity is saved to the `profile` volume. See [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) for all parameters.

### Stealth test, updates, plain Compose

- `./examples/cloaktest.sh` runs upstream's bot-detection suite with your `.env` settings.
- `./cloakroom start` always pulls the latest `cloakhq/cloakbrowser`. To pin a version, change `FROM cloakhq/cloakbrowser:latest` in `image/Dockerfile` to a tag like `0.5.11`.
- Without the scripts: `cp .env.example .env && docker compose up -d --build`, then `docker compose down`.

---

## Security and privacy

- **Never expose ports 9222 or 6080 to the internet or your network.** Port 9222 gives full control of a browser that's logged in to your accounts, and the viewer has no password. Both are bound to `127.0.0.1`. Keep it that way. For remote use, tunnel over SSH or Tailscale instead of opening ports.
- **Passwords** live in the macOS Keychain (`./cloakroom creds set`) or are typed by you in the viewer. They're never kept in the repo, `.env`, or agent chat. The email is kept in `~/.cloakroom/amazon.json`.
- **Messages**: read locally, only for new incoming texts during a login, and only the code is used. Nothing is sent to any server. You can turn this off anytime by removing Full Disk Access.
- `.env` (license key, proxy password) is git-ignored.

---

## Links and license

- CloakBrowser (upstream): <https://github.com/CloakHQ/CloakBrowser>
- Free license key: <https://cloakbrowser.dev/free>
- Docker image: <https://hub.docker.com/r/cloakhq/cloakbrowser>

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, isn't affiliated with Amazon or CloakHQ, and doesn't guarantee any site's bot checks will pass. Use it only with your own accounts and follow each site's terms.
