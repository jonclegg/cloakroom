# Agent instructions

If the user asks you to log in to a site "with cloakroom" (e.g. **"Login to Amazon with cloakroom"**), follow [`skills/cloakroom/SKILL.md`](skills/cloakroom/SKILL.md).

Short version:

```bash
./cloakroom status --json          # readiness, including Messages access
./cloakroom start                  # if not ready
./cloakroom amazon-login --json    # streams JSON events; exit 0 = logged in
```

Never ask the user for their password in chat. They type it in the viewer (http://127.0.0.1:6080) or store it with `./cloakroom creds set` in their own terminal.
