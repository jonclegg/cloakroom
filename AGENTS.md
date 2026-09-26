# Agent instructions

If the user asks you to log in to a site "with cloakroom" (e.g. **"Login to Amazon with cloakroom"**), follow [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md).

Short version:

```bash
cloakroom status --json          # or ./cloakroom status --json from the repo
cloakroom start                  # if not ready
cloakroom amazon-login --json    # streams JSON events; exit 0 = logged in
```

When Amazon asks for a code, `amazon-login` emits `waiting_for_otp`. **You** (Grok Bot or Muse) read the code from Messages and pass it to Cloakroom. Cloakroom does not read iMessage.

Never ask the user for their password in chat. They type it in the viewer (http://127.0.0.1:6080) or store it with `cloakroom creds set` in their own terminal.
