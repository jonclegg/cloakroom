# Agent instructions

If the user asks you to log in to a site "with cloakroom" (e.g. **"Login to Amazon with cloakroom"**), follow [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md).

Short version:

```bash
cloakroom status --json          # or ./cloakroom status --json from the repo
cloakroom start                  # if not ready
cloakroom amazon-login --json    # streams JSON events; exit 0 = logged in
cloakroom share --json           # phone viewer; send the url immediately
cloakroom unshare                # stop the share when they are done
```

When Amazon asks for a code, `amazon-login` emits `waiting_for_otp`. **You** (Grok Bot or Muse) read the code from Messages and pass it to Cloakroom. Cloakroom does not read iMessage. POST the code to `submit_url` from that event (localhost only).

When the user wants the viewer on a phone, away from home, or any remote noVNC access, run `cloakroom share` and send the HTTPS URL in the same turn. Do not ask them to approve or confirm first. The command does not prompt. The URL is a secret capability link: anyone with it can control the logged-in browser. When they are done, run `cloakroom unshare`. Do **not** use Tailscale. Do **not** Funnel or port-forward. Never expose port 9222; `cloakroom share` tunnels the viewer (6080) only. Ports 6080 and 9222 stay bound to `127.0.0.1`.

Never ask the user for their password in chat. They type it in the viewer (http://127.0.0.1:6080, or the share URL) or store it with `cloakroom creds set` in their own terminal.
