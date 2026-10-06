# Architecture: chat over REST

Status: **proposal, not built.** This branch exists to review it before writing code.

## 1. What changes

Today the only way to make Cloakroom do something is to drive it yourself, or run
`cloakroom do "<goal>"` on the host, which needs Python and Playwright on your Mac.

The change: **the interface to Cloakroom becomes one REST call carrying a chat
prompt.** Cloakroom owns the loop — screenshots, the model, the mouse — and it
brings what it already learned about bot detection to the job.

```bash
curl -s localhost:8423/v1/chat -H "Authorization: Bearer $(cat ~/.cloakroom/api-token)" \
  -d '{"prompt":"go to walmart.com and find 12-cup coffee makers, then tell me the cheapest"}'
```

That call runs to completion and returns a transcript. A follow-up prompt
continues in the same tab, with the conversation and the page still there.

## 2. Where things run

The service goes **inside the container**, beside the browser. That is the
decision that makes the rest simple.

```
┌─ host (macOS) ─────────────────────────────────────────────────────────┐
│                                                                        │
│  curl / your agent / curl-in-a-loop                                    │
│        │  POST /v1/chat   (Bearer token)                               │
│        ▼                                                               │
│  127.0.0.1:8423 ─────────── published ──────────┐                      │
│                                                 │                      │
│  ┌─ cloakroom container (Debian) ───────────────┼───────────────────┐  │
│  │                                             ▼                   │  │
│  │   cloakroom-api  (FastAPI/uvicorn)                              │  │
│  │     ├── session store (browser page + message history)          │  │
│  │     ├── agent loop ──▶ OpenRouter ──▶ deepseek-v4.1-flash        │  │
│  │     ├── knowledge pack (barrier recipes + site memory)          │  │
│  │     └── run log  ──▶ ~/.cloakroom/runs (steps, shots, cost)     │  │
│  │                    │                                            │  │
│  │                    │ CDP over 127.0.0.1 — never published       │  │
│  │                    ▼                                            │  │
│  │   cloakserve ──▶ Chrome  :9222                                  │  │
│  │   x11vnc + noVNC            :6080  (viewer, unchanged)          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

**Why inside the container:**

- CDP stays on `127.0.0.1` inside the container and is never published. Nothing
  new is exposed.
- It removes the current wart where `cloakroom do` needs Python and Playwright on
  the host. Cloakroom becomes self-contained again, as the README claims it is.
- One image, one `docker compose up`. No second runtime to install.

The API gets its own published port, bound to loopback exactly like 9222 and 6080
already are.

## 3. The API

```
POST   /v1/chat                    run a prompt (creates a session if none given)
POST   /v1/chat/{run}/cancel       stop a run mid-flight
GET    /v1/runs/{run}              status, steps, decisions, timings, cost
GET    /v1/runs/{run}/events       Server-Sent Events, live progress
GET    /v1/runs/{run}/shots/{n}    the screenshot for step n

POST   /v1/sessions                explicit session (own tab, own history)
GET    /v1/sessions/{id}
DELETE /v1/sessions/{id}

GET    /v1/sites                   learned per-domain memory
GET    /v1/knowledge/barriers      the recipes it is using
GET    /v1/status                  browser, core, model, key, queue depth
```

`POST /v1/chat` body:

```json
{
  "prompt": "go to walmart.com and find 12-cup coffee makers",
  "session_id": null,
  "max_steps": 15,
  "model": "deepseek/deepseek-v4.1-flash",
  "allow_barrier_bypass": true,
  "stream": false
}
```

Response:

```json
{
  "run": "r_01H...", "session": "s_01H...", "status": "succeeded",
  "summary": "Opened walmart.com via Bing, searched 'coffee maker', found 3 ...",
  "steps": [ {"n":0,"action":"open","did":"open walmart.com","blocked":["perimeterx"],
              "shot":"/v1/runs/r_01H.../shots/0"} ],
  "final_url": "https://www.walmart.com/search?q=coffee+maker",
  "usage": {"model":"deepseek/deepseek-v4.1-flash","steps":7,"tokens":18422,"cost_usd":0.011}
}
```

A **chat** shape on purpose: `summary` is prose, so the caller can just show it.
`steps` is the audit trail, so a caller can also see exactly what happened.

## 4. The loop

One iteration per step, unchanged from the working agent:

```
screenshot (CSS scale, 1 px == 1 CSS px)
   ├─ page.evaluate({innerWidth, innerHeight, dpr})
   ├─ dom_hints(): visible interactive elements + centre coordinates
   └─ detect_block(): titles, frame bodies, URLs, visible vendor widgets
        │
        ▼
build prompt = core rules + barrier recipe + site memory + goal + history + hints
        │
        ▼
deepseek/deepseek-v4.1-flash  ──▶  one JSON action
        │
        ▼
execute humanized (click | type | press | hold | drag | scroll | wait | open | goto)
        │
        ▼
done?  ── no ──▶ loop        yes ──▶ summarize + persist
```

The model is `deepseek/deepseek-v4.1-flash`, which accepts **text and image**, so
one model both sees the page and decides. No second vision model.

## 5. "Realising the notes it has"

This is the part worth getting right. Three layers, injected by relevance rather
than dumped wholesale:

| Layer | Size | When |
| --- | --- | --- |
| **Core rules** | ~600 tok | always — the action schema, detection rules, humanize discipline |
| **Barrier recipe** | ~300 tok | when `detect_block` fires — the specific vendor |
| **Site memory** | ~200 tok | when the hostname is known from a previous run |

The human playbook is ~4k tokens and is written for people. The model gets
something better: a **machine-readable knowledge pack**, structured so a recipe
is instructions rather than prose to interpret.

```yaml
# knowledge/barriers/perimeterx.yaml
id: perimeterx
detect:
  text: ["press & hold", "activate and hold", "robot or human"]
  widgets: ["#px-captcha"]
  frames: ["px-cloud.net", "captcha.px"]
recipe:
  action: hold
  hold_ms: 8000          # 8s or more
  target: "centre of the press-and-hold button"
gotchas:
  - "must be a FRESH challenge: a stale one shows no progress and never clears"
  - "a few pixels off the button fails silently - target the DOM bounding box"
  - "identity aging: retry with the same identity before trying a fresh one"
```

```yaml
# knowledge/sites/walmart.com.yaml
domain: walmart.com
last_seen: 2026-10-06
barriers: [perimeterx]
outcome: defeated
technique: "hold 8000-10000ms at the button centre"
notes: "serves /blocked?url=... after repeated automated entry, and an inline
        overlay on search results pages. Passing once sets a clearance cookie."
```

**Site memory is the compounding asset.** Every run writes back what it saw and
what worked, so the 22-site table stops being a document and becomes part of the
product. A run that beats Cloudflare on a new domain adds a row.

Injection stays deterministic — no vector search, no embeddings. `detect_block`
already names the vendor and the URL already names the host; lookup is exact.
Retrieval would add a failure mode for nothing.

## 6. Sessions

A session owns one browser page and one message history.

- `POST /v1/chat` with no `session_id` creates one, runs, and keeps it alive on an
  idle timer (default 15 min) so a follow-up continues in place.
- The page is **not** closed between turns — cookies, scroll position and the
  conversation all survive. That is what makes it feel like chat.
- Runs on one browser are **serialized through a queue.** One browser, one mouse.
  Concurrency would corrupt runs, not speed them up.

## 7. Security

The API is a remote control for a signed-in browser, so it is treated that way:

- Binds `127.0.0.1` only, published to the host's loopback. Never `0.0.0.0`.
- **Bearer token**, generated on first start, `chmod 600`, at
  `~/.cloakroom/api-token`. Rotatable with `cloakroom api-token --rotate`.
- Port 9222 is still never published.
- `allow_barrier_bypass` can be turned off so the service never touches a bot
  check — for callers who want the browser and not the bypass.
- Run logs redact form fields by default; screenshots are kept locally and never
  leave the machine except as the model input.

## 8. What is reused, what is new

**Reused as-is** — this is most of the value already built and tested:

| | |
| --- | --- |
| `examples/humanize.py` | curved mouse paths, character-by-character typing |
| `examples/bing_first.py` | Bing-first entry, organic-result picking, `ck/a` redirect handling |
| `agent/cloakroom_agent.py` | `detect_block`, vendor detection, DOM hints, the nine actions, `safe_screenshot` |
| The playbook | becomes the knowledge pack rather than prose |

**New:**

- `api/` — FastAPI app, sessions, queue, run store, SSE
- `knowledge/` — barrier recipes and site memory, plus the writer
- `Dockerfile` — add Python deps and start the API beside `cloakserve`
- `cloakroom` CLI — `do` becomes a thin HTTP client; add `api-token`, `serve`
- `compose` — publish `127.0.0.1:8423`

## 9. Latency, cost, and other honest constraints

- **A step costs one screenshot and one model call: ~8–25 s.** A 10-step goal is
  minutes, not seconds. Hence SSE and `cancel`.
- **Vision calls are the cost.** ~$0.01–0.03 per moderate run at current
  OpenRouter pricing. `/v1/status` reports spend; a `max_usd` cap per run is worth
  having.
- **One browser means one run at a time.** The queue is a feature, not a
  limitation to engineer around.
- **Seven of the 22 known sites re-arm.** A site that passed at 22:00 can
  challenge again at 23:00. Site memory records this rather than pretending a
  site is permanently solved.
- **Hard blocks stay hard.** Akamai 403s and DataDome's slider are not solved by
  this architecture; the knowledge pack records them as known-unbeaten so the
  model stops burning steps on them.

## 10. Phased delivery

1. **Service skeleton** — FastAPI in the container, `/v1/status`, `/v1/chat`
   running the existing loop with the existing model, single-shot, no sessions.
2. **Sessions + history** — conversational follow-ups, idle expiry, queue.
3. **Knowledge pack** — barrier recipes + site memory, and the write-back.
4. **Streaming + observability** — SSE, run store, cost per run.
5. **CLI as client** — `cloakroom do` posts to the API; `cloakroom chat`.

Each phase is usable on its own, and phase 1 is a small change: it wraps code
that already works.

## 11. Questions for you

1. **Port 8423** — fine, or do you want something else?
2. **`allow_barrier_bypass` default on or off?** You had me make bypass the
   default for `cloakroom do`; I would keep that here.
3. **Should the CLI keep working with no API running** — i.e. `cloakroom do` falls
   back to the in-process loop — or should it require the service?
4. **Session default lifetime** — 15 minutes of idle, or longer?
