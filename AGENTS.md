# Agent instructions

Cloakroom is a stealth browser (CloakBrowser) with a persistent profile, running in a container on the user's own computer. You give it goals with `cloakroom chat`, or drive it yourself over CDP. Use it when a site blocks your cloud browser, when cookies and logins need to persist between runs, or when the user asks you to do something "with cloakroom". [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md) is the full reference.

## Installing Cloakroom for the user

When the user points you at this repo, install it for them. They should not have to run anything themselves. Go through these steps in order, and tell the user in one short line what you're doing at each one.

**1. Already installed?** Run `cloakroom status --json`. If it prints `"ready": true` and `"openrouter_key": true`, skip to step 5.

**2. Run the installer.** It downloads Cloakroom, pulls its image, and starts it.

macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

Windows (PowerShell):

```powershell
irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex # // pragma: allowlist secret
```

The first run takes a few minutes. It downloads the image (about 1 GB), and on first start the container downloads the browser itself from CloakHQ.

**3. If it stops with `CLOAKROOM_NEEDS: docker`** (exit code 3), the computer has no container engine, and the installer changed nothing. **Ask the user** whether to install one, and say which one the output names: OrbStack on a Mac, Docker Engine on Linux, Docker Desktop on Windows. If they agree, run the installer again with consent:

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | CLOAKROOM_INSTALL_DOCKER=yes sh # // pragma: allowlist secret
```

```powershell
$env:CLOAKROOM_INSTALL_DOCKER = "yes"; irm https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.ps1 | iex # // pragma: allowlist secret
```

If it stops with `CLOAKROOM_NEEDS: user` (exit code 4), it needs something only the user can do. Examples: typing a sudo password in their own terminal, finishing Docker Desktop's first-run setup, or logging out and back in. Relay the message as it is, wait until they say it's done, then run the installer again.

**4. The OpenRouter key.** Cloakroom drives the browser with DeepSeek through OpenRouter, so it needs the user's key. **Never ask for the key in chat.** Run `cloakroom key`. It opens a page on their computer where they paste it, and Cloakroom checks it with OpenRouter. Tell them to create a key at https://openrouter.ai/keys if they don't have one, and to paste it into that page. Then wait until `cloakroom status --json` shows `"openrouter_key": true`.

**5. Show it working.** Run `cloakroom smoke`. Cloakroom enters Amazon, Walmart, Target and Best Buy from Bing, works any bot check, takes a screenshot of each, and opens a report. Tell the user how many it reached, and show them the screenshots: `cloakroom smoke --json` lists each one's `host_screenshot` path.

**6. Done.** Tell them it's ready, how to watch the browser (http://127.0.0.1:6080), and that they can now ask you to do things on sites "with Cloakroom".

On Windows there is no `cloakroom` command on the host. Use `docker exec cloakroom cloakroom <command>` for `status`, `key`, `smoke`, `chat`, `run` and `notes`. Start and stop with `~\.cloakroom\app\start.ps1` and `stop.ps1`. The `key` command prints the link; open it for the user with `Start-Process <url>`.

## Using Cloakroom

```bash
cloakroom status --json          # is it ready, viewer and API URLs, key set?
cloakroom start                  # if not ready
cloakroom chat "<message>"       # Cloakroom drives the browser with DeepSeek and replies
cloakroom share --json           # phone viewer; send the url immediately
cloakroom unshare                # stop the share when they are done
```

**Prefer talking to Cloakroom.** `cloakroom chat "search walmart.com for paper towels"` sends a message to the chat API inside the container. Cloakroom screenshots the page, DeepSeek picks the next action, and Cloakroom carries it out as real mouse and keyboard input, press-and-hold included. When it's done it replies with a status: `done`, `needs_input`, `blocked` or `failed`. Follow up with `--session <id>` to stay in the same tab. It can read pages and save a listing's photos, and it keeps per-site notes so the next run starts out knowing more. See [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md#cloakroom-chat-cloakroom-drives-you-talk).

**Or drive it yourself** with Playwright: `connect_over_cdp("http://127.0.0.1:9222")`, then use `browser.contexts[0]`, which is the saved profile with its cookies. Send mouse and keyboard input through [`examples/humanize.py`](examples/humanize.py), not `page.mouse` or `page.keyboard`. It delivers real X11 events through Cloakroom's `/input` endpoint.

**Enter sites from Bing, and humanize input.** Do not `page.goto` the target site, and do not open a search, listing or product URL as the first navigation. Open `https://www.bing.com`, search the site name, click the organic result (official domain, skip ads), then use that site's own search and links ([`examples/bing_first.py`](examples/bing_first.py)). Starting from Google often hits `/sorry/`. Pause between actions, click a field before typing, and type character by character. If a bot check still appears, `cloakroom chat` works it.

If a site asks for a two-factor code, **you** get it (for example from Messages) and type it into the page. Cloakroom does not read texts.

When the user wants the viewer on a phone, away from home, or any remote access, run `cloakroom share` and send the HTTPS URL in the same turn. Do not ask them to confirm first; the command does not prompt. The URL is a secret capability link: anyone who has it can control the logged-in browser. When they're done, run `cloakroom unshare`. Do **not** use Tailscale, Funnel, or port forwarding. Never expose port 9222. `cloakroom share` tunnels only the viewer (6080), and ports 6080, 8423 and 9222 stay bound to `127.0.0.1`.

Never ask the user for a password in chat. They type it in the viewer (http://127.0.0.1:6080, or the share URL). If they're away and need to paste the OpenRouter key, run `cloakroom key --in-browser` and `cloakroom share`, and they paste it in the viewer.

On a Mac, the browser presents as a Mac: macOS persona, a Retina screen, and the Mac's own fonts. On Linux and Windows it presents as a Windows PC. Its timezone and language follow the IP its traffic leaves from.
