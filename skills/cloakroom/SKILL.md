---
name: cloakroom
description: Log in to websites (Amazon first) in a stealth CloakBrowser running in Docker on the user's Mac, auto-filling the SMS/iMessage 2FA code from the Messages app. Use when the user says "login to Amazon with cloakroom", "use cloakroom", or asks to sign in to a site with a stealth/persistent browser.
---

# Cloakroom skill

Cloakroom is a local CLI in this repo: `./cloakroom`. Run every command from the repo root.
It controls a stealth Chromium in Docker (`cloakhq/cloakbrowser`) and reads one-time codes from the Mac's Messages database. Nothing leaves the machine.

## Trigger

User: **"Login to Amazon with cloakroom"** (or "sign in to Amazon using cloakroom", "use cloakroom for Amazon").

## Playbook

1. **Check readiness**

   ```bash
   ./cloakroom status --json
   ```

   Handle each field, in order, and stop to tell the user when something needs them:

   | Field | Value | What you do |
   | --- | --- | --- |
   | `docker_running` | `false` | Ask the user to open Docker Desktop and wait for "Engine running". Re-check. |
   | `ready` | `false` | Run `./cloakroom start` (first run downloads ~1 GB; allow up to 10 minutes). |
   | `messages_access` | `mac_only` | This is not a Mac. Tell the user to type the 2FA code in the viewer. Do not wait on Messages. |
   | `messages_access` | `no_permission` | Run `./cloakroom messages-access`, then tell the user: *"Turn on Full Disk Access for this app in the window that just opened, then quit and reopen the app."* Re-check after they confirm. |
   | `messages_access` | `missing` | This Mac has no Messages history. Ask the user to sign in to Messages and turn on iPhone > Settings > Messages > Text Message Forwarding for this Mac. |
   | `amazon_credentials` | `false` | Fine. The user types credentials in the viewer (step 3). Offer `./cloakroom creds set` for next time. **Never ask for or handle the password in chat.** |

2. **Run the login**

   ```bash
   ./cloakroom amazon-login --json
   ```

   It prints one JSON object per line. Relay progress to the user in plain words:

   | `event` | Tell the user |
   | --- | --- |
   | `browser_connected` | "Opening Amazon in Cloakroom. You can watch at http://127.0.0.1:6080." |
   | `waiting_for_user` | Repeat `detail`, and point to the viewer URL. The command keeps running and continues when they're done. |
   | `email_filled` / `password_filled` | "Signed in with your saved credentials…" |
   | `sending_code` / `otp_page` | "Amazon is texting a code. I'll read it from Messages." |
   | `otp_filled` | "Got the code from Messages and entered it." Never repeat the code itself. |
   | `otp_timeout` | "No code arrived. Check your phone forwards texts to this Mac, or type the code in the viewer." |
   | `success` | "You're logged in to Amazon. The session is saved for next time." |
   | `timeout` | Summarize the last event and suggest finishing in the viewer, then re-run. |

   Exit code `0` means logged in. `1` means not logged in.

3. **Report** success, or the last blocking step, in one or two sentences.

## Other commands

- `./cloakroom otp --json --service amazon --timeout 120` waits for the next matching code and prints `{"found": true, "code": "..."}`. Use it only when you must fill a code yourself.
- `./cloakroom creds set` stores the Amazon email and password in the macOS Keychain. **The user runs this in their own terminal**, since it prompts for the password.
- `./cloakroom stop` stops the browser. The session is kept.
- Scripting other sites: connect Playwright to `http://127.0.0.1:9222` with `connect_over_cdp` and use `browser.contexts[0]`, which is the persistent profile.

## Rules

- Never print, log, or store the user's password or OTP codes in chat or files.
- Never expose ports 9222/6080 beyond `127.0.0.1`.
- Don't bypass CAPTCHAs. When `waiting_for_user` reports an unrecognized page, the user finishes it in the viewer.
