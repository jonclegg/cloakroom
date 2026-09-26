# Cloakroom

**Run [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) on your own computer with one command.**

CloakBrowser is a stealth Chromium browser that looks like a normal person's browser to websites. Cloakroom is a ready-to-go setup for it: you install Docker Desktop, run `./start.sh`, and you get the browser running in a browser tab. Scripts can drive it too.

- **Mac first** (Apple Silicon and Intel). Windows works too, see [Windows](#windows).
- Uses the **official** `cloakhq/cloakbrowser` image. Cloakroom doesn't change the browser itself.
- Logins and cookies are **kept between restarts**.
- Only your computer can connect. Nothing is opened to the internet.

---

## Mac: get started

### 1. Install Docker Desktop

Download [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/). Pick **Apple Silicon** for M1/M2/M3/M4 Macs and **Intel** for older Macs (Apple menu > About This Mac tells you which one you have). Open Docker Desktop once and wait until it says **Engine running**.

### 2. Download Cloakroom

Either:

- Click **Code > Download ZIP** on this page, then double-click the ZIP in your Downloads folder, **or**
- In Terminal: `git clone https://github.com/jonclegg/cloakroom.git` <!-- // pragma: allowlist secret -->

### 3. Start it

Open **Terminal** (press Cmd+Space, type `Terminal`, press Enter). Type `cd ` (with a space after it), drag the `cloakroom` folder onto the Terminal window, and press Enter. Then run:

```bash
./start.sh
```

The first start downloads about 1 GB, so it can take a few minutes. When it's done you'll see:

```
You're ready!

  See the browser:    http://127.0.0.1:6080
  Try an example:     docker compose run --rm hello
  Stop everything:    ./stop.sh
```

The browser opens in a Safari/Chrome tab by itself. You can click, type, and log in to sites there like in a normal browser.

### 4. Try the example

```bash
docker compose run --rm hello
```

It opens `example.com` in your CloakBrowser and prints `Page title: Example Domain`. The new tab shows up in the viewer.

### Stop it

```bash
./stop.sh
```

Your browser profile (cookies, logins, history) is saved. Run `./start.sh` again whenever you want it back.

---

## Settings

The first `./start.sh` creates a file called `.env` in the `cloakroom` folder. Open it with TextEdit to change settings, then run `./stop.sh` and `./start.sh` again.

| Setting | What it does |
| --- | --- |
| `CLOAKBROWSER_LICENSE_KEY` | Uses the newest CloakBrowser build. Get a free key by signing in with GitHub at [cloakbrowser.dev/free](https://cloakbrowser.dev/free). Leave it blank to use the free build included in the image. |
| `CLOAKROOM_PROXY` | Sends all browser traffic through a proxy, e.g. `http://user:pass@host:8080` or `socks5://host:1080`. |
| `CLOAKROOM_FINGERPRINT_SEED` | Any number, e.g. `48213`. Keeps the same browser fingerprint every time you start. If you leave it blank, you get a new fingerprint on every start. |
| `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT` | Change these only if another app already uses port 9222 or 6080. |

Your `.env` file stays on your computer. It's never uploaded to GitHub.

---

## Troubleshooting

**"Docker Desktop is not running"**
Open Docker Desktop from Applications and wait for **Engine running** (the whale icon in the menu bar stops animating). Then run `./start.sh` again.

**"permission denied: ./start.sh"**
Run `bash start.sh` instead (and `bash stop.sh` to stop). Or fix it once with `chmod +x start.sh stop.sh examples/cloaktest.sh`.

**"port is already allocated" / "address already in use"**
Something else is using port 9222 or 6080 (often a Chrome started with remote debugging). Close it, or change `CLOAKROOM_CDP_PORT` / `CLOAKROOM_VIEWER_PORT` in `.env` (for example to `9223` and `6081`) and start again.

**The viewer is black or says "Disconnected"**
Give it a few seconds, since it reconnects by itself. If it stays that way, run `./stop.sh` then `./start.sh`.

**Tabs crash ("Aw, Snap!") or the browser is slow**
In Docker Desktop, open Settings > Resources and give Docker at least 4 GB of memory.

**Apple Silicon (M1/M2/M3/M4)**
Everything runs natively. You don't need Rosetta or any special settings. If you had previously set `DOCKER_DEFAULT_PLATFORM=linux/amd64` in your shell, remove it.

**"License" or "concurrent session" errors**
A free key allows one browser session at a time. Close other CloakBrowser sessions (including `examples/cloaktest.sh` runs) or leave the key blank.

**See what's going on**
`docker compose logs -f cloakroom` shows the browser server's log. Press Ctrl+C to stop watching.

**Start over with a fresh profile**
`docker compose down -v` deletes the saved profile (logins, cookies), then run `./start.sh` again.

---

## Windows

Windows uses the same setup, with PowerShell scripts instead.

1. Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/). It needs **WSL 2**, and the installer offers to turn it on. Restart when it asks, open Docker Desktop, and wait for **Engine running**.
2. Download this repo (**Code > Download ZIP**, then right-click > Extract All) or `git clone` it.
3. Open **PowerShell** in the `cloakroom` folder (in File Explorer, Shift+right-click the folder > *Open PowerShell window here*) and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

4. Try the example: `docker compose run --rm hello`
5. Stop: `powershell -ExecutionPolicy Bypass -File .\stop.ps1`

The `-ExecutionPolicy Bypass` part lets this one script run without changing your system settings. Settings live in `.env` just like on Mac (open it with Notepad).

---

## Advanced

### What's running

`docker compose` runs a single container, `cloakroom`:

- It's built from the official `cloakhq/cloakbrowser` image, plus x11vnc and noVNC for the web viewer ([`image/Dockerfile`](image/Dockerfile)).
- It runs [`cloakserve`](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) with `--headless=false`, so Chromium runs *headed* on a virtual display (Xvfb). Headed mode passes more bot checks, and it's what the viewer shows you.
- It uses `shm_size: 2gb`, because Chromium crashes with Docker's default 64 MB shared memory.
- It has a healthcheck against `/json/version`, and `start.sh` waits for it.
- It uses two named volumes: `profile` (browser profile at `/profile/default`) and `binary-cache` (`~/.cloakbrowser`, so a licensed binary downloads only once).

`cloakserve` normally deletes its profile folder when it stops. [`image/cloakroom-serve.sh`](image/cloakroom-serve.sh) points that folder at the `profile` volume through a symlink that `cloakserve` refuses to delete, so your default profile survives restarts.

### Connect your own scripts (CDP)

The browser speaks the Chrome DevTools Protocol at `http://localhost:9222`. Any Playwright/Puppeteer script on your Mac can connect:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    page = browser.contexts[0].new_page()   # contexts[0] = your saved profile
    page.goto("https://example.com")
    print(page.title())
```

```js
// hello.mjs  (npm i playwright-core)
import { chromium } from "playwright-core";
const browser = await chromium.connectOverCDP("http://localhost:9222");
const page = await browser.contexts()[0].newPage();
```

Run the bundled example from your Mac instead of Docker with `pip install playwright && python examples/hello.py`. It reads `CDP_URL` and defaults to `http://localhost:9222`. No `playwright install` is needed, because the browser is the one in Docker.

`browser.close()` on a CDP connection only disconnects your script. The browser keeps running.

### Extra identities

`cloakserve` can run separate browser identities side by side. Add `?fingerprint=<seed>` to the URL:

```python
pw.chromium.connect_over_cdp("http://localhost:9222?fingerprint=11111&timezone=Europe/Berlin&locale=de-DE")
```

Each seed gets its own Chrome process and fingerprint. Only the default identity (no seed, or the one set by `CLOAKROOM_FINGERPRINT_SEED`) is saved to the `profile` volume. Other seeds are temporary. You can see them in the viewer too. See [upstream docs](https://github.com/CloakHQ/CloakBrowser#cdp-server-mode) for all query parameters. `curl http://localhost:9222/` lists running identities.

### Run CloakBrowser's stealth test

```bash
./examples/cloaktest.sh
```

This runs upstream's `cloaktest` bot-detection suite in a throwaway container with your `.env` settings.

### Update

`./start.sh` always pulls the latest `cloakhq/cloakbrowser` and rebuilds, so running it again updates you. To pin a version, change `FROM cloakhq/cloakbrowser:latest` in `image/Dockerfile` (and the `hello` image in `docker-compose.yml`) to a tag like `0.5.11`.

### Plain Docker Compose

The scripts are thin helpers. You can also use Compose directly: `cp .env.example .env && docker compose up -d --build`, then `docker compose down`.

---

## Security

- **Never expose ports 9222 or 6080 to the internet or your local network.** Anyone who can reach port 9222 gets full control of the browser: they can read every page, your cookies, and your logins. The viewer on port 6080 has no password.
- Cloakroom binds both ports to `127.0.0.1`, so only your own computer can connect. Don't change `127.0.0.1` in `docker-compose.yml` to `0.0.0.0`.
- If you need remote access, use an SSH tunnel (`ssh -L 9222:localhost:9222 you@server`) or a VPN like Tailscale. Don't open a port.
- Keep your license key and proxy password in `.env`, which is git-ignored. Don't commit it.

---

## Links and license

- CloakBrowser (upstream): <https://github.com/CloakHQ/CloakBrowser>
- Free license key: <https://cloakbrowser.dev/free>
- Docker image: <https://hub.docker.com/r/cloakhq/cloakbrowser>

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser browser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is a community project and isn't affiliated with CloakHQ. Cloakroom doesn't guarantee that any site's bot detection will pass. For that, see upstream's test results.
