---
name: cloakroom
description: Drive a stealth CloakBrowser running under OrbStack on the user's Mac, over CDP, with a persistent profile that keeps cookies and logins. Use when a site bot-walls your cloud browser, when a session needs to survive between runs, or when the user says "use cloakroom", "do X with cloakroom", or "share the viewer". If a site asks for a two-factor code, you (Grok Bot or Muse) get it and type it in; Cloakroom never reads Messages. When the user wants the viewer on a phone or away from home, run `cloakroom share` and send the HTTPS URL immediately. Do not ask them to confirm. Do not use Tailscale.
---

# Cloakroom skill

Cloakroom is a local CLI: `cloakroom`, or `./cloakroom` from this repo.
It controls a stealth Chromium in OrbStack (`cloakhq/cloakbrowser`). The browser, the viewer, and the saved profile stay on the machine.

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

   ```python
   browser = pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
   page = browser.contexts[0].new_page()
   ```

   `browser.contexts[0]` is the persistent profile: cookies and logins from earlier runs are already there. Don't create a new context unless you want a clean session. `browser.close()` only disconnects you; the browser keeps running.

3. **Bring in the user when needed**

   If a page needs a password, a puzzle, or a step you can't do, tell the user to finish it in the viewer at http://127.0.0.1:6080 (or run `cloakroom share` if they're away from the Mac), then continue. Never ask for a password in chat.

4. **Two-factor codes**

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

## Other commands

- `cloakroom stop` stops the browser. The profile is kept.

## Rules

- Never print, log, or store the user's password or two-factor codes in chat or files.
- Cloakroom does not read iMessage. You do, if a code is needed.
- Ports 9222 and 6080 stay on `127.0.0.1`.
- Remote viewer access is one command: `cloakroom share`. Run it and send the URL immediately. Do not ask for approval first, and do not add a confirmation step. The URL is a secret capability link. Run `cloakroom unshare` when the user is done. Do not use Tailscale, Funnel, or port forwards. Never tunnel 9222.
- Don't bypass CAPTCHAs. When a page shows a puzzle, the user finishes it in the viewer.
