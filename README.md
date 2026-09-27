# Cloakroom

**A stealth browser on your Mac for AI agents: fewer bot walls, and logins that stick.**

Agents like Grok Bot and Muse browse from cloud servers, so many big sites see a datacenter IP and an automated browser and block them. Their cookies also vanish after every session.

Cloakroom runs [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (stealth Chromium) on your own Mac, with one saved profile. Your agent drives it; you can watch it and step in from your Mac or your phone.

**Proof point:** on September 26, 2026, a cloud browser was blocked on twelve big homepages (Home Depot, Ticketmaster, Sam's Club, and others). Cloakroom loaded all twelve.

## Quickstart

1. **Install** (Mac):

   ```bash
   curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
   ```

   This installs OrbStack and Cloakroom, then starts the browser. The first start downloads about 1 GB.

2. **Start the browser** any time later:

   ```bash
   cloakroom start
   ```

3. **Watch the browser** at <http://127.0.0.1:6080>. You can click and type in it, for example to sign in once or finish a puzzle.

4. **Point your agent at it.** Open this folder in Grok Bot, Muse, Cursor, Claude Code, or Codex, and ask it to use Cloakroom for the site that keeps blocking it.

5. **Watch from your phone:**

   ```bash
   cloakroom share
   ```

   This prints a private link. Anyone with that link can control your logged-in browser, so keep it to yourself. Run `cloakroom unshare` when you're done.

`cloakroom stop` stops the browser. Your logins are kept.

## Good to know

- No site is guaranteed to work, and Cloakroom doesn't solve CAPTCHAs for you.
- Your IP still matters. Traffic leaves from your Mac's connection, or from a proxy you set in `.env` (see `.env.example`).
- Only your Mac can reach the browser. `cloakroom share` is the one way to reach it from elsewhere, and it only exposes the viewer.
- Windows, troubleshooting, and the technical details are in [the agent guide](skills/cloakroom/SKILL.md).

## License

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, not affiliated with CloakHQ or any site mentioned here.
