# Cloakroom

**A stealth browser on your Mac for AI agents. It gets into the sites that block cloud browsers, and your logins stick.**

## Quickstart

Tell your agent (Grok Bot, Muse, Cursor, Claude Code, Codex) to install Cloakroom:

```bash
curl -fsSL https://raw.githubusercontent.com/jonclegg/cloakroom/main/install.sh | sh # // pragma: allowlist secret
```

Or just hand it this repo's URL. That's the whole setup. Your agent reads the instructions here and handles the rest. Mac only.

## Why

Cloud agents browse from datacenter servers. Big sites see a datacenter IP and an automated browser, and they put up a bot wall. Every session also starts fresh, so the login from yesterday is gone today.

Cloakroom brings the browser home. It runs [CloakBrowser](https://github.com/CloakHQ/CloakBrowser), a stealth build of Chromium, on your own Mac with one saved profile. Your agent drives it from wherever it runs.

## Where cloud agents get blocked, Cloakroom gets in

On September 26, 2026, a typical cloud agent browser (Grok Bot, browsing from a datacenter) was sent to the homepages of some of the biggest names online. Twelve of them turned it away with an access-denied page or a bot challenge. Cloakroom, running on a Mac, walked into every one:

- **Shopping:** Home Depot, Sam's Club, Sephora, Etsy, Newegg, Fanatics, Vinted
- **Tickets and travel:** Ticketmaster, American Airlines, Tripadvisor
- **Jobs:** Indeed, Glassdoor

Twelve for twelve. These are the sites people actually want an agent to shop, book, and search on, and exactly the ones that shut a datacenter browser out.

Some of that win comes from leaving through a home connection instead of a datacenter. The rest is the browser: Sam's Club still challenged ordinary Chrome routed through the same Mac, and Cloakroom loaded the storefront. This was a homepage check, not logins or checkouts, and sites change their defenses often.

## What you get

- **Harder to detect.** A stealth browser on your own connection, not an automated browser in a datacenter.
- **Sessions that persist.** Sign in once. Cookies and logins stay in the profile across runs and restarts.
- **You can watch and help.** Open the live viewer on your Mac, or have your agent run `cloakroom share` to get a private link for your phone. Click, type, or sign in when the agent gets stuck.
- **Standard CDP.** Playwright, Puppeteer, or anything else that speaks the Chrome DevTools Protocol connects to `127.0.0.1:9222`. No SDK.

## Good to know

- No guarantees. Some sites will still block you, and Cloakroom doesn't solve CAPTCHAs.
- Your IP still matters. Traffic leaves from your Mac's connection, or from a proxy you set.
- Only your Mac can reach the browser. `cloakroom share` is the one way in from elsewhere, and it exposes only the viewer. Anyone with that link can control your logged-in browser, so keep it private and run `cloakroom unshare` when you're done.
- The full reference for agents (and the curious) is in [AGENTS.md](AGENTS.md) and [the agent guide](skills/cloakroom/SKILL.md).

## License

Cloakroom's own code is [MIT licensed](LICENSE). The CloakBrowser binary inside the official image belongs to CloakHQ and has its own [Binary License](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md). See [NOTICE](NOTICE). Cloakroom is an independent community project, not affiliated with CloakHQ or any site mentioned here.
