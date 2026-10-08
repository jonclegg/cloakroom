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

**4. The OpenRouter key.** Cloakroom drives the browser with DeepSeek through OpenRouter, so it needs the user's key. **Never ask for the key in chat.** Run `cloakroom key`. It opens a local setup page in this computer's browser (it also prints the link) and then waits. Tell the user to paste their key into that page and click the button. If they don't have a key, they create one at https://openrouter.ai/keys. The command returns when the key is saved, which means OpenRouter accepted it. It also reports what happens along the way:

- **The page opened but nothing was submitted.** Remind the user to click the button.
- **OpenRouter rejected the key.** The page stays open for another try. Relay the reason.
- **The link expired** (after 15 minutes). Run `cloakroom key` again.

The page answers only on this computer (`127.0.0.1`). If the user isn't at this computer, or it has no screen, run `cloakroom key --in-browser` and `cloakroom share`. Send them the share link, and they paste the key into the page in Cloakroom's own browser, through the viewer. For a link without waiting, use `cloakroom key --json`. `cloakroom status --json` shows how far it has got under `key_setup`.

**5. Show it working.** Run `cloakroom smoke`. Cloakroom enters Amazon, Walmart, Target and Best Buy from Bing, works any bot check, takes a screenshot of each, and opens a report. Tell the user how many it reached, and show them the screenshots: `cloakroom smoke --json` lists each one's `host_screenshot` path.

**6. Done.** Tell them it's ready, how to watch the browser (the `viewer_url` from `cloakroom status --json`, normally http://127.0.0.1:6080), and that they can now ask you to do things on sites "with Cloakroom".

The ports in these instructions (9222 CDP, 6080 viewer, 8423 API) are the defaults. If something else on the computer already uses them, the user sets other ports in `~/.cloakroom/app/.env`. `cloakroom status --json` always reports the real URLs.

On Windows there is no `cloakroom` command on the host. Use `docker exec cloakroom cloakroom <command>` for `status`, `key`, `smoke`, `chat`, `run`, `notes`, `share` and `unshare`. Start and stop with `~\.cloakroom\app\start.ps1` and `stop.ps1`. For the key, run `docker exec cloakroom cloakroom key --json`, open the `setup_url` for the user with `Start-Process <url>`, then wait on that same link with `docker exec cloakroom cloakroom key --watch`.

## Using Cloakroom

```bash
cloakroom status --json          # is it ready, viewer and API URLs, key set?
cloakroom start                  # if not ready
cloakroom chat "<message>"       # Cloakroom drives the browser with DeepSeek and replies
cloakroom share --json           # console link (sessions + live browser); send the url immediately
cloakroom unshare                # stop the share when they are done
```

**Prefer talking to Cloakroom.** `cloakroom chat "search walmart.com for paper towels"` sends a message to the chat API inside the container. Cloakroom screenshots the page, DeepSeek picks the next action, and Cloakroom carries it out as real mouse and keyboard input, press-and-hold included. When it's done it replies with a status: `done`, `needs_input`, `needs_user` or `failed`. Follow up with `--session <id>` to stay in the same tab. It can read pages and save a listing's photos, and it keeps per-site notes so the next run starts out knowing more. See [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md#cloakroom-chat-cloakroom-drives-you-talk).

**Or drive it yourself** with Playwright: `connect_over_cdp("http://127.0.0.1:9222")`, then use `browser.contexts[0]`, which is the saved profile with its cookies. Send mouse and keyboard input through [`examples/humanize.py`](examples/humanize.py), not `page.mouse` or `page.keyboard`. It delivers real X11 events through Cloakroom's `/input` endpoint.

**Enter sites from Bing, and humanize input.** Do not `page.goto` the target site, and do not open a search, listing or product URL as the first navigation. Open `https://www.bing.com`, search the site name, click the organic result (official domain, skip ads), then use that site's own search and links ([`examples/bing_first.py`](examples/bing_first.py)). Starting from Google often hits `/sorry/`. Pause between actions, click a field before typing, and type character by character. If a bot check still appears, `cloakroom chat` works it.

If a site asks for a two-factor code, **you** get it (for example from Messages) and type it into the page. Cloakroom does not read texts.

When the user wants to watch Cloakroom, see what its sessions are doing, or reach the browser from a phone or anywhere else, run `cloakroom share` and send the HTTPS URL in the same turn. Do not ask them to confirm first; the command does not prompt. The link opens the **Cloakroom console**: every session with its status and conversation, the live browser, what needs them, and buttons to message a session, take over the mouse, hand back, stop, or close it. The URL is a secret capability link: anyone who has it can control the logged-in browser. When they're done, run `cloakroom unshare`; the link and every page opened from it stop working. Do **not** use Tailscale, Funnel, or port forwarding. Never expose port 9222. `cloakroom share` tunnels the console (the API on 8423, which serves the live viewer itself), never CDP, and ports 6080, 8423 and 9222 stay bound to `127.0.0.1`.

**When a run ends `needs_user`**, the page needs the user's own hands: a sign-in, a payment, or a bot check Cloakroom couldn't clear. Cloakroom has already started the share. Send the user `needs_user.task` and `needs_user.share_url` in the same turn, and say the link is secret. The link opens the console on that session: they act in the live browser there and press **Done, carry on**, which continues the session for you (watch `run.finished` on `GET /v1/events?session=<id>`, or the session's next reply). Don't assume they're at the machine running Cloakroom. If they tell you they're done instead, continue with `--session <id>` (same tab, now signed in). Run `cloakroom unshare` once nobody needs the console. Do the same yourself, with `cloakroom share --json`, whenever the user has to act in the page while you drive it over CDP.

Never ask the user for a password in chat. They type it in the viewer, through the share URL. Always send the share URL, not the localhost viewer address: the user is usually not at the machine running Cloakroom. If they're away and need to paste the OpenRouter key, run `cloakroom key --in-browser` and `cloakroom share`, and they paste it in the viewer.

On a Mac, the browser presents as a Mac: macOS persona, a Retina screen, and the Mac's own fonts. On Linux and Windows it presents as a Windows PC. Its timezone and language follow the IP its traffic leaves from.
