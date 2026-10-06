# Bot detection and CAPTCHA playbook

How Cloakroom gets through bot detection: what each check looks like, how it is
detected, and exactly what defeats it.

Everything here was observed live, in this order: enter the site Bing-first with
humanized input, detect the challenge from the DOM, read the screen with DeepSeek
vision, then act. Screenshots for each site are under `~/.cloakroom/hunt/shots/`.
Raw per-site records (including every model decision) are in
`~/.cloakroom/hunt/results.json`.

Status: **work in progress.** The per-site log at the bottom tracks which sites
have a confirmed challenge and whether it was defeated.

---

## Part 1 — The method that does the work

These apply to every vendor. Vendor-specific notes are in Part 2.

### 1. Enter through Bing, never straight to the target

`page.goto` of the target is the single biggest trigger. A direct load arrives
with no referrer, no click trail, and no site-search history:

1. `page.goto("https://www.bing.com")`
2. Type the domain, click search
3. Click the **organic** result (`li.b_algo`, skipping `.b_ad`)
4. Use the site's own search box from there

Google-first from a CDP session lands on `/sorry/` often. Bing is the gateway.

### 2. Humanize every input

- Random pauses, a few tenths of a second to a couple of seconds
- A curved `mouse.move` with jitter before each click, never an instant jump
- Click the field before typing; never `fill()`
- Type character by character with jittered delays

This is what avoids most challenges. It does not by itself defeat one that has
already appeared.

### 3. Detect the challenge, don't guess

Two traps, both hit during this work:

- **The wording is often in a cross-origin iframe.** Cloudflare's interstitial
  puts "Just a moment..." in the `<title>` and nothing useful in `body`. A
  body-text scan misses it entirely.
- **Passive widgets look like challenges.** Cars.com's normal homepage ships a
  hidden reCAPTCHA iframe. Counting invisible vendor frames produces false
  positives on a page that is not blocking anyone.

So detection checks, in order:

1. `title` + main-frame `body` + every frame's `body`
2. the URL (`/blocked`, `/sorry/`, `/cdn-cgi/challenge`)
3. **visible** vendor widgets only (an element with a real bounding box
   ≥ 60×30 px)

### 4. Read the screen, then aim with DOM coordinates

Screenshots are captured at CSS scale, so one screenshot pixel is one CSS pixel.
The model is told the exact image size. Visible interactive elements are pulled
from the DOM with their centre coordinates and handed to the model as hints.

That combination is what makes targeting land: on Walmart's PerimeterX
press-and-hold the model picked the button centre to the pixel, matching the DOM
ground truth exactly.

### 5. A challenge has to be fresh

A PerimeterX press-and-hold that has been sitting on screen goes inert. Holding
it produces no progress and never clears, no matter how long you hold. Every
failure observed was a stale challenge; every fresh one passed.

### 6. Clear only that site's cookies when you need a fresh challenge

A clearance cookie from a previous pass hides the challenge. `cloakroom do`'s
hunt harness deletes cookies for the target domain only (via CDP
`Network.deleteCookies`), never the whole profile, so the rest of the logged-in
session survives.

### 7. Passing once buys quiet

Walmart stopped challenging after one successful hold. Cars.com's Cloudflare
interstitial cleared once and the real homepage then loaded on later visits.
Budget for this: a site that challenges once may not challenge again for a while,
which makes "did my fix work?" hard to answer without clearing state.

---

## Part 2 — Vendor by vendor

### Cloudflare (interstitial / Turnstile)

**Looks like** — title `Just a moment...`, body "Performing security
verification", "Verify you are human", and a Turnstile checkbox. Frame URLs
contain `challenges.cloudflare.com`.

**Detected by** — `cloudflare_interstitial` (title/body text) and
`cloudflare_turnstile` (visible `challenges.cloudflare.com` iframe or
`.cf-turnstile`).

**Defeated by** — the healthy path is that it clears by itself once the browser
fingerprint and IP look right. Where a checkbox is shown, a humanized click on
it. A browser that already looks human usually gets an automatic pass
(`cf_clearance` cookie set).

**Sites** — cars.com (see log).

### PerimeterX / HUMAN

**Looks like** — title `Robot or human?`, body "Activate and hold the button to
confirm that you're human", a `#px-captcha` container and a large button reading
`PRESS & HOLD`. Page or overlay, served from `/blocked?url=...`.

**Detected by** — `press_and_hold`, from `#px-captcha` or the body text
`press & hold` / `activate and hold`.

**Defeated by** — `hold` at the button centre for **8000 ms or more**. The button
must be targeted precisely: a few pixels off and it fails silently with no error
and no progress indicator. Hold with no mouse movement is fine.

**Sites** — walmart.com (see log).

### Sliders (Geetest, Alibaba, and friends)

**Looks like** — a track with a handle to drag to a gap or to the end.

**Detected by** — `slider`, from `slide to verify` / `drag the slider`, or a
visible `.geetest_panel`.

**Defeated by** — `drag` from the handle to the target. **The path is scored, not
the endpoints**: a straight teleport is rejected. The implementation eases in and
out, adds jitter per step, overshoots slightly, then settles back. Verified
against a test page that rejects any drag with fewer than 8 move events or a path
shorter than 60% of the travel.

### reCAPTCHA

**Looks like** — either a badge (invisible, passive) or a visible "I'm not a
robot" checkbox / image grid, in an iframe under `google.com/recaptcha`.

**Detected by** — `recaptcha`, only when the widget is **visible** and
appropriately sized.

**Defeated by** — checkbox: a humanized click. Image grid: best-effort, the model
reads the prompt and clicks matching tiles one per step. Not yet proven here.

### hCaptcha, Akamai, DataDome, Kasada

Detection only so far. See the per-site log for what was observed.

- **Akamai** — often no visible puzzle at all; `_abck`/`bm_sz` cookies and a
  redirect. Usually won on fingerprint, not on a click.
- **DataDome / Kasada** — likewise mostly passive: they score the browser and
  either serve content or a bare block page.
- **hCaptcha** — iframe under `hcaptcha.com`, checkbox or image grid.

---

## Part 3 — Per-site log

"Defeated" means the challenge was present and the real page then loaded.

### Confirmed: challenge found and defeated (22 sites)

Every one of these was seen serving a bot check, and the real page loaded after
Cloakroom worked it. The last column is a live re-check run afterwards: some
vendors re-arm, so a site can pass and be challenged again later.

| # | Site | Vendor / type | Defeated by | Passes now |
| --- | --- | --- | --- | --- |
| 1 | walmart.com | PerimeterX press-and-hold | `hold` 8–10 s at the button centre | yes |
| 2 | samsclub.com | PerimeterX press-and-hold | `hold` | yes |
| 3 | bloomberg.com | PerimeterX press-and-hold | `hold` | yes |
| 4 | truecar.com | PerimeterX press-and-hold | `hold` | yes |
| 5 | academy.com | PerimeterX (blocked URL + hold) | `hold` | yes |
| 6 | wayfair.com | PerimeterX hard denial | identity aging | yes |
| 7 | skyscanner.com | PerimeterX press-and-hold | `hold` | yes |
| 8 | thenorthface.com | PerimeterX press-and-hold | `hold` | yes |
| 9 | cars.com | Cloudflare interstitial + Turnstile | passed | re-arms |
| 10 | crunchbase.com | Cloudflare interstitial | passed | yes |
| 11 | linkedin.com | Cloudflare `Attention Required!` | identity aging | yes |
| 12 | turo.com | Cloudflare interstitial | passed | re-arms |
| 13 | axs.com | Cloudflare interstitial | passed | re-arms |
| 14 | quora.com | Cloudflare interstitial | passed | yes |
| 15 | ssense.com | Cloudflare interstitial | passed | re-arms |
| 16 | stackoverflow.com | Cloudflare interstitial | passed | yes |
| 17 | stackexchange.com | Cloudflare interstitial | passed | yes |
| 18 | edmunds.com | Akamai 403 | block gave way | re-arms |
| 19 | kohls.com | Akamai `Access Denied` | gave way on a later attempt | re-arms |
| 20 | cabelas.com | Akamai `Access Denied` | gave way | yes |
| 21 | basspro.com | Akamai `Access Denied` | gave way (intermittent) | re-arms |
| 22 | stubhub.com | reCAPTCHA | humanized click | yes |

**15 of the 22 pass clean on a later visit; 7 re-arm.** That is the honest shape
of the result: clearing a challenge is not the same as being permanently cleared.

### Still blocked

| Site | Vendor | Note |
| --- | --- | --- |
| apartments.com, homes.com, marriott.com, opentable.com | Akamai `Access Denied` | Bare 403s that never gave way |
| expedia.com, hotels.com, orbitz.com | DataDome | Serves a "Bot or Not?" **slider**. The drag fires and the widget rejects it — DataDome scores more than the trajectory |
| enterprise.com | reCAPTCHA | Widget lingers while the real page title loads — likely a passive v3 badge |

---

## Part 4 — Operational lessons (these cost the most time)

### The single biggest lever: let the identity age

Counter-intuitive, and the reason a first pass badly understates the result.
Cloudflare, PerimeterX, and Akamai **accrue trust to a browser identity over
time**. A brand-new identity gets challenged; the same identity later walks
through.

Measured on LinkedIn, seconds apart:

```
default (aged) identity -> 'LinkedIn: Log In or Sign Up'   blocks=[]
fresh identity          -> 'Attention Required! | Cloudflare'
```

LinkedIn, Bass Pro, and Wayfair were all first recorded as hard-blocked failures
and later loaded clean **with the same identity**. Nothing about the technique
changed; only the identity's history did.

So: when a vendor refuses, retry later with the profile's own identity before
concluding anything. **Do not "fix" a hard block by rotating to a fresh identity
— that makes it worse.**

### …and fresh identities are for *triggering*, not for passing

The two halves pull in opposite directions, and both are real:

- A **fresh** identity makes a check appear at all on a site that has already
  cleared you (Cars.com: `default` → clean, `fingerprint=777001` → "Just a
  moment...").
- An **aged** identity gets through a check on a site that is refusing you.

Use fresh identities to reproduce a challenge; use the aged one to clear it.

### Challenges re-arm

A site that passed cleanly at 22:00 can serve a fresh "Just a moment..." at 23:00.
Seven of the 22 above do exactly that. Any claim of the form "site X is solved"
is only true for the moment it was tested; the durable property is that the
technique clears the check when it appears.

### A fresh browser identity leaks a browser process

CloakBrowser keeps a browser alive per fingerprint identity and disconnecting over
CDP does not reap it. A sweep using a new identity per site left **627 Chrome
processes**; the CDP endpoint then answered `502` to everything and 25 sites were
never probed. `docker exec cloakroom ps aux | grep -c chrome` shows the pile-up;
`cloakroom stop && start` reclaims it and the saved profile survives.

### A failed screenshot silently lost winnable challenges

PerimeterX overlays navigate as they arm, destroying the page context mid-capture.
`safe_screenshot` retried once, then the whole solve returned `screenshot failed`
**without ever attempting the hold**. Sam's Club and TrueCar were both recorded as
failures that way and both cleared once the capture retried persistently. A
negative result on a press-and-hold site is not trustworthy unless the capture
succeeded.

### The browser clock was UTC on a US residential IP

`cloakserve` derives a timezone from GeoIP **only when a proxy is set**. With
`CLOAKROOM_PROXY` blank — the normal case — the browser reported
`Intl...timeZone === "UTC"` while the UA said Windows and traffic exited from
Texas. A US Windows desktop on UTC is a recognisable tell. `start.sh` now reads
the host timezone and forwards it; the browser reports `America/Chicago`.

Set it per-container: cloakserve logs *"first-launch wins"* and ignores
`?timezone=` for a seed already running.

### Homepages are the easy case

Of ~180 homepage probes, only a minority showed detection, and several of the
defeats above surfaced **only** on a site-search results page (Crunchbase, TrueCar,
Sam's Club). Driving the site's own search box roughly doubles the hit rate.

### One hostile page could stall everything

Playwright's sync API blocks the main thread in a way `signal.alarm` cannot
interrupt. One site per subprocess with a hard kill is the only reliable bound.

---

## Part 5 — What did not work

- Scanning page HTML for vendor names. Normal sites mention `recaptcha` and
  `geetest` in their bundles; Cars.com's homepage reported both while blocking
  nobody.
- Counting vendor iframes without checking visibility. Cars.com ships a hidden
  reCAPTCHA iframe on its normal homepage.
- Straight-line drags. Rejected by path-scoring sliders.
- Holding a stale press-and-hold. No amount of hold time clears it.
- Clearing cookies to re-trigger a challenge. The vendor's verdict survives it.
- **Rotating to a fresh identity to escape a hard block.** It is the opposite of
  the fix.
- **Humanising the DataDome slider.** The drag fires correctly, at the right
  coordinates, and is still rejected. Motion alone is not the test.
- One fresh identity per site, unbounded. Exhausts the container.

---

## Status

**Objective met: 22 sites with a confirmed bot check and a confirmed defeat**,
out of ~180 probed. Fifteen pass clean on a later visit; seven re-arm.




