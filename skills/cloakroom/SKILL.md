---
name: cloakroom
description: Log in to websites (Amazon first) in a stealth CloakBrowser running under OrbStack on the user's Mac. When Amazon asks for a code, you (Grok Bot or Muse) read it from Messages and pass it to Cloakroom. When the user wants the viewer on a phone or away from home, run `cloakroom share` and give them the HTTPS URL. Do not use Tailscale. Use when the user says "login to Amazon with cloakroom", "use cloakroom", "share the viewer", or asks to sign in to a site with a stealth/persistent browser.
---

# Cloakroom skill

Cloakroom is a local CLI: `cloakroom`, or `./cloakroom` from this repo.
It controls a stealth Chromium in OrbStack (`cloakhq/cloakbrowser`). The browser, the viewer, and the saved login stay on the machine.

**You fetch the iMessage OTP. Cloakroom does not.** Cloakroom never reads Messages, `chat.db`, or Full Disk Access. When Amazon asks for a code, you (Grok Bot or Muse) read Messages, extract the code, and hand it to Cloakroom.

## Trigger

User: **"Login to Amazon with cloakroom"** (or "sign in to Amazon using cloakroom", "use cloakroom for Amazon").

## Playbook

1. **Check readiness**

   ```bash
   cloakroom status --json
   ```

   Handle each field, in order, and stop to tell the user when something needs them:

   | Field | Value | What you do |
   | --- | --- | --- |
   | `docker_running` | `false` | Run `cloakroom start`. That opens OrbStack (not Docker Desktop) and starts the browser. If OrbStack is missing, the user installs it from https://orbstack.dev/download. |
   | `ready` | `false` | Run `cloakroom start` (first run downloads ~1 GB; allow up to 10 minutes). |
   | `amazon_credentials` | `false` | Fine. The user types credentials in the viewer (step 3). Offer `cloakroom creds set` for next time. **Never ask for or handle the password in chat.** |

2. **Run the login**

   ```bash
   cloakroom amazon-login --json
   ```

   It prints one JSON object per line. Relay progress to the user in plain words:

   | `event` | Tell the user |
   | --- | --- |
   | `browser_connected` | "Opening Amazon in Cloakroom. You can watch at http://127.0.0.1:6080." |
   | `waiting_for_user` | Repeat `detail`, and point to the viewer URL. The command keeps running and continues when they're done. |
   | `email_filled` / `password_filled` | "Signed in with your saved credentials…" |
   | `sending_code` | "Amazon is texting a code. I'll get it from Messages." |
   | `waiting_for_otp` | Read Messages yourself, extract the new Amazon code, and submit it (below). Tell the user you're entering the code. Never repeat the code. |
   | `otp_filled` | "Entered the code." Never repeat the code itself. |
   | `otp_timeout` | Read Messages again and submit the code. If you cannot read Messages, tell the user to type it in the viewer. |
   | `success` | "You're logged in to Amazon. The session is saved for next time." |
   | `timeout` | Summarize the last event and suggest finishing in the viewer, then re-run. |

   Exit code `0` means logged in. `1` means not logged in.

3. **On `waiting_for_otp`, hand the code to Cloakroom**

   You already can read the user's Messages. Find the new Amazon code and POST it to `submit_url` from the event. Do this from another shell while `amazon-login` keeps running:

   ```bash
   curl -fsS -X POST "$submit_url" \
     -H 'content-type: application/json' \
     -d '{"code":"123456"}'
   ```

   Use the real code in place of `123456`. A body that is only the digits also works.

   If you already have the code before starting login, pass it up front instead:

   ```bash
   cloakroom amazon-login --otp "$CODE" --json
   # or
   CLOAKROOM_OTP="$CODE" cloakroom amazon-login --json
   ```

   A line on that process's stdin (`123456`) is accepted too.

   Do not ask the user to paste the code into chat when you can read Messages. If you cannot read Messages, tell them to type it in the viewer. Do not ask them to paste it into chat.

4. **Report** success, or the last blocking step, in one or two sentences.

## Phone / remote viewer

User wants the viewer on a phone, away from home, or says "remote VNC" / "share the browser".

```bash
cloakroom share --json
```

That starts the browser if it is not already running, then runs a Cloudflare quick tunnel to the viewer only (`http://127.0.0.1:6080` by default). It returns after the tunnel is up. State (pid and URL) is in `~/.cloakroom/share.json`.

```json
{"event":"share_ready","url":"https://….trycloudflare.com","viewer_local":"http://127.0.0.1:6080","reused":false}
```

Give the user `url`. Open it in the phone browser. It is a **secret**: anyone with it can click and type in the logged-in browser. When they are done, run `cloakroom unshare` (same as `cloakroom share stop`). A new share gets a new link. `cloakroom status --json` includes `share_url` while the tunnel is running (`null` when it is not).

Do **not** use Tailscale. Do **not** Funnel or port-forward 6080 or 9222 yourself. The only remote path is `cloakroom share`, and it tunnels the viewer only. Never point a tunnel at port 9222.

Amazon login is unchanged. On `waiting_for_otp`, read Messages and POST the code to `submit_url` on `127.0.0.1`. Do not send the code to the share URL.

## Other commands

- `cloakroom creds set` stores the Amazon email and password in the macOS Keychain. **The user runs this in their own terminal**, since it prompts for the password.
- `cloakroom stop` stops the browser. The session is kept.
- Scripting other sites: connect Playwright to `http://127.0.0.1:9222` with `connect_over_cdp` and use `browser.contexts[0]`, which is the persistent profile. Cloakroom's built-in code handoff is `amazon-login`.

## Rules

- Never print, log, or store the user's password or OTP codes in chat or files.
- Cloakroom does not read iMessage. You do, and you pass only the code in.
- Ports 9222 and 6080 stay on `127.0.0.1`. The OTP `submit_url` is localhost-only too.
- Remote viewer access is `cloakroom share` only (viewer port, Cloudflare quick tunnel). Do not use Tailscale, Funnel, or port forwards. Never tunnel 9222. Treat the share URL as a secret and run `cloakroom unshare` when the user is done.
- Don't bypass CAPTCHAs. When `waiting_for_user` reports an unrecognized page, the user finishes it in the viewer.
