# Cloakroom

**A stealth browser on your Mac for AI agents: fewer bot walls, and logins that stick.**

## Quickstart

Tell your agent (Grok Bot, Muse, Cursor, Claude Code, Codex) to install Cloakroom:

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

Or just hand it this repo's URL. That's the whole setup. Your agent reads the instructions here and handles the rest. Mac only.

## Why

Cloud agents browse from datacenter servers. Big sites see a datacenter IP and an automated browser, and they put up a bot wall. Every session also starts fresh, so the login from yesterday is gone today.

Cloakroom brings the browser home. It runs [CloakBrowser](https://github.com/CloakHQ/CloakBrowser), a stealth build of Chromium, on your own Mac with one saved profile. Your agent drives it from wherever it runs.

## What you get

- **Harder to detect.** A stealth browser on your own connection, not an automated browser in a datacenter.
- **Sessions that persist.** Sign in once. Cookies and logins stay in the profile across runs and restarts.
- **You can watch and help.** Open the live viewer on your Mac, or have your agent run `cloakroom share` to get a private link for your phone. Click, type, or sign in when the agent gets stuck.
- **Standard CDP.** Playwright, Puppeteer, or anything else that speaks the Chrome DevTools Protocol connects to `127.0.0.1:9222`. No SDK.

**Proof:** on September 26, 2026, a cloud browser was blocked on twelve big homepages (Home Depot, Ticketmaster, Sam's Club, and others). Cloakroom loaded all twelve.

## Good to know

- No guarantees. Some sites will still block you, and Cloakroom doesn't solve CAPTCHAs.
- Your IP still matters. Traffic leaves from your Mac's connection, or from a proxy you set.
- Only your Mac can reach the browser. `cloakroom share` is the one way in from elsewhere, and it exposes only the viewer. Anyone with that link can control your logged-in browser, so keep it private and run `cloakroom unshare` when you're done.
- The full reference for agents (and the curious) is in [AGENTS.md](AGENTS.md) and [the agent guide](skills/cloakroom/SKILL.md).

## License

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, not affiliated with CloakHQ or any site mentioned here.
