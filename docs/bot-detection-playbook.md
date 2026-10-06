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

### Confirmed: challenge found and defeated

Nine sites. Six of them are PerimeterX or Cloudflare — the two checks that
account for most of what actually blocks this browser.

| # | Site | Vendor / type | Detected as | Defeated by | Where it appeared |
| --- | --- | --- | --- | --- | --- |
| 1 | walmart.com | PerimeterX press-and-hold | `press_and_hold` | `hold` 8.0–10.1 s at the button centre | homepage, then `/blocked?url=…`, then an inline overlay |
| 2 | samsclub.com | PerimeterX press-and-hold ("Let us know you're not a robot") | `press_and_hold`, `robot_or_human` | `hold` | site search results |
| 3 | bloomberg.com | PerimeterX press-and-hold | `perimeterx`, `press_and_hold` | `hold` | homepage |
| 4 | truecar.com | PerimeterX press-and-hold ("Before we continue…") | `perimeterx`, `press_and_hold` | `hold` | site search results |
| 5 | cars.com | Cloudflare interstitial + Turnstile | `cloudflare_interstitial` | passed; real homepage then loaded | homepage |
| 6 | crunchbase.com | Cloudflare interstitial | `cloudflare_interstitial` | passed | **site search results, not the homepage** |
| 7 | edmunds.com | Akamai 403 | `access_denied` | block gave way, real homepage loaded | homepage |
| 8 | kohls.com | Akamai `Access Denied` | `access_denied` | block gave way on a later attempt | homepage |
| 9 | stubhub.com | reCAPTCHA | `recaptcha` | humanized click | homepage |

### Confirmed: challenge found, not defeated

| Site | Vendor / type | Why it failed |
| --- | --- | --- |
| linkedin.com | Cloudflare hard block | Title `Attention Required! | Cloudflare`. Not the solvable interstitial — no widget, no checkbox, nothing to interact with. An IP/reputation verdict. |
| wayfair.com | PerimeterX press-and-hold | **The hold works and still loses.** The widget confirms "Human Challenge completed, please wait…", then the next page is `Access to this page has been denied`. Clearing the interaction is not the same as being authorised. |
| enterprise.com | reCAPTCHA | Widget stays present. Its real page title loads underneath, so this may be a passive v3 badge rather than a real block. |
| expedia.com | DataDome | Serves a "Bot or Not?" interstitial. Passive: it decides on fingerprint, and the solve hangs. |
| apartments.com, opentable.com | Akamai `Access Denied` | Bare 403s that did not give way. |

---

## Part 4 — Operational lessons (these cost the most time)

### A fresh browser identity is what triggers detection

The saved profile had already earned clearance on cars.com: it loaded straight
through, every time, no matter how many cookies were cleared. Cloudflare's
verdict is server-side and keyed to the browser identity, not to the cookie jar.

Connecting on a **fresh identity** flips it immediately:

```
default identity   -> title='Cars.com: Find New Cars, Used Cars, Dealerships, Prices'
fingerprint=777001 -> title='Just a moment...'
```

That is the lever for reproducible testing. Use it.

### …but each fresh identity leaks a browser process

CloakBrowser keeps a browser alive per fingerprint identity, and disconnecting
over CDP does not reap it. A sweep that used a new identity per site left
**627 Chrome processes** in the container. The CDP endpoint then answered `502`
to every new connection and 25 sites were never probed at all. `docker exec
cloakroom ps aux | grep -c chrome` shows the pile-up; `cloakroom stop && start`
reclaims it (627 → 10) and the saved profile survives.

For sites the browser has never visited, the **default identity is just as
fresh** and does not leak. Prefer it; reach for a new fingerprint only to re-arm
a challenge on a site that has already cleared you.

### A failed screenshot silently lost winnable challenges

This was the single most expensive bug. PerimeterX overlays navigate as they
arm, which destroys the page context mid-capture. `safe_screenshot` retried once
and then the whole solve returned `screenshot failed` **without ever attempting
the hold**. Sam's Club and TrueCar were both recorded as failures this way and
both cleared on the retry once the capture retried persistently. Any negative
result on a press-and-hold site is suspect until the capture succeeded.

### Retrying converts failures

Several sites only cleared on a second or third attempt: TrueCar and Kohl's both
did. A single pass understates the result — re-run `hung`, `not_defeated`, and
`error` sites rather than writing them off.

### Homepages are the easy case

Of 63 homepage probes, only 7 showed detection. Crunchbase's Cloudflare
interstitial appeared **only** when the probe drove its own search box to a
results page. Site search, listing, and product pages are where the checks live.
TrueCar and Sam's Club also surfaced theirs on search pages, not homepages.

### One hostile page could stall everything

Playwright's sync API blocks the main thread in a way `signal.alarm` cannot
interrupt, so a dead page hung the sweep indefinitely. Running one site per
subprocess with a hard kill is the only reliable bound.

### Hard blocks are not a captcha problem

`Attention Required!`, a bare `Access Denied`, and DataDome's refusal have no
interactive element. No amount of clicking or holding gets through them — only a
different browser identity or IP. Detecting them early saved ~10 minutes per
site.

---

## Part 5 — What did not work

- Scanning page HTML for vendor names. Normal sites mention `recaptcha` and
  `geetest` in their JS bundles; Cars.com's homepage reported both while showing
  no challenge at all.
- Counting vendor iframes without checking visibility. Cars.com ships a hidden
  reCAPTCHA iframe on its normal homepage.
- Straight-line drags. Rejected by path-scoring sliders.
- Holding a stale press-and-hold. No amount of hold time clears it.
- Clearing cookies to re-trigger a challenge. Cloudflare's verdict survives it.
- One fresh browser identity per site, unbounded. Exhausts the container and
  breaks every subsequent connection.

---

## Status

**9 of 20 confirmed defeats.** 63 sites probed; 12 showed bot detection; 9
defeated.

The remaining sites are mostly ones that show nothing on the homepage. The deep
search-page pass is still working through them; it found Crunchbase's Cloudflare
check where the homepage showed none, so it is the right lever, but the yield so
far is roughly one challenge per ten sites.


