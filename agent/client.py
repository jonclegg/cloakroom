"""`cloakroom chat`, `run`, `cancel`, `notes`, `key`, `smoke`, `status`: a client for the chat API.

Standard library only. It runs inside the container (`docker exec cloakroom
cloakroom <command>`), so the host needs nothing but Docker.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import webbrowser

API_URL = os.environ.get("CLOAKROOM_API_URL") or f"http://127.0.0.1:{os.environ.get('CLOAKROOM_API_PORT') or 8423}"
DATA_DIR = os.environ.get("CLOAKROOM_DATA_DIR") or os.path.expanduser("~/.cloakroom/data")


def token():
    path = os.path.join(DATA_DIR, "api-token")
    if not os.path.exists(path):
        raise SystemExit(f"No API token at {path}. Is Cloakroom running? Try: cloakroom start")
    with open(path) as fh:
        return fh.read().strip()


def call(method, path, body=None, timeout=None):
    request = urllib.request.Request(
        API_URL + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Cloakroom API {exc.code}: {exc.read().decode()[:500]}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot reach the Cloakroom API at {API_URL}: {exc.reason}. "
                         f"Try: cloakroom start") from exc


def print_run(run):
    print(run["reply"] or "(no reply)")
    print()
    print(f"status:  {run['status']}   steps: {run['steps']}   cost: ${run['cost_usd']:.4f}")
    if run.get("files"):
        where = run.get("host_dir") and os.path.join(run["host_dir"], "files")
        print(f"files:   {len(run['files'])} saved" + (f" in {where}" if where else ""))
    for note in run.get("notes_written") or []:
        print(f"noted:   {note['site']}: {note['text']}")
    print(f"run:     {run['run']}")
    print(f"session: {run['session']}   (continue with: cloakroom chat --session {run['session']} \"...\")")


def main():
    parser = argparse.ArgumentParser(prog="cloakroom")
    commands = parser.add_subparsers(dest="command", required=True)

    chat = commands.add_parser("chat", help="send Cloakroom a message; it works the browser and replies")
    chat.add_argument("message")
    chat.add_argument("--session", help="continue this session (same tab, same conversation)")
    chat.add_argument("--max-steps", type=int, default=40)
    chat.add_argument("--no-wait", action="store_true", help="return the run id at once")
    chat.add_argument("--json", action="store_true")

    runs = commands.add_parser("run", help="show a run: status, steps, files")
    runs.add_argument("run")
    runs.add_argument("--json", action="store_true")

    cancel = commands.add_parser("cancel", help="stop a run")
    cancel.add_argument("run")

    notes = commands.add_parser("notes", help="what Cloakroom has learned, per site")
    notes.add_argument("site", nargs="?")

    key = commands.add_parser("key", help="open a page to paste the OpenRouter key into")
    key.add_argument("--in-browser", action="store_true",
                     help="open it in Cloakroom's own browser, for use through the viewer")
    key.add_argument("--json", action="store_true", help="print the link instead of opening it")

    smoke = commands.add_parser("smoke", help="reach a few big sites and screenshot them")
    smoke.add_argument("sites", nargs="*", help="domains (default: amazon.com walmart.com target.com bestbuy.com)")
    smoke.add_argument("--json", action="store_true")

    status = commands.add_parser("status", help="browser, model, key, and queue")
    status.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "chat":
        body = {"message": args.message, "session": args.session,
                "max_steps": args.max_steps, "wait": not args.no_wait}
        run = call("POST", "/v1/chat", body)
        if args.json:
            print(json.dumps(run, indent=2))
        elif args.no_wait:
            print(f"run {run['run']} queued in session {run['session']}; check it with: cloakroom run {run['run']}")
        else:
            print_run(run)
        return 0 if run["status"] in ("done", "needs_input", "queued") else 1

    if args.command == "run":
        run = call("GET", f"/v1/runs/{args.run}")
        if args.json:
            print(json.dumps(run, indent=2))
            return 0
        for step in run.get("trace") or []:
            flag = f" [bot check: {step['block_type']}]" if step.get("blocked") else ""
            print(f"[{step['step']}] {step.get('url', '')[:90]}{flag}")
            print(f"     {step.get('observation') or ''}")
            print(f"     -> {step.get('did', '')}")
        print()
        print_run(run)
        return 0

    if args.command == "cancel":
        print(json.dumps(call("POST", f"/v1/runs/{args.run}/cancel"), indent=2))
        return 0

    if args.command == "key":
        link = call("POST", "/v1/setup-link", {"in_browser": args.in_browser})
        if args.json:
            print(json.dumps(link, indent=2))
            return 0
        if args.in_browser:
            print("Opened the key page in Cloakroom's browser. Paste the key there "
                  "(through the viewer, or `cloakroom share` from a phone).")
        elif webbrowser.open(link["setup_url"]):
            print(f"Opened {link['setup_url']}\nPaste the key there; it is checked and saved on this machine.")
        else:
            print(f"Open this on this machine and paste the key there:\n  {link['setup_url']}")
        print("The link works once and lasts 15 minutes.")
        return 0

    if args.command == "smoke":
        print("Visiting " + ", ".join(args.sites or ["amazon.com", "walmart.com", "target.com", "bestbuy.com"])
              + " from Bing, the way a person would. This takes a few minutes.", file=sys.stderr, flush=True)
        result = call("POST", "/v1/smoke", {"sites": args.sites})
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for item in result["results"]:
                mark = "ok  " if item["ok"] else "FAIL"
                cleared = " (cleared a bot check)" if item["worked_challenge"] and item["ok"] else ""
                print(f"{mark} {item['site']:16} {item.get('title') or item.get('error') or ''}{cleared}")
            print(f"\n{result['passed']} of {result['total']} reached. Report: {result['host_report'] or result['report']}")
        return 0 if result["passed"] == result["total"] else 1

    if args.command == "status":
        result = call("GET", "/v1/status")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"browser connected: {result['browser_connected']}\nmodel: {result['model']}\n"
                  f"openrouter key: {'set' if result['openrouter_key'] else 'missing (run: cloakroom key)'}\n"
                  f"queue: {result['queue_depth']}")
        return 0

    if args.command == "notes":
        if args.site:
            result = call("GET", f"/v1/notes/{args.site}")
            print("Shipped guidance:\n" + (result["guidance"] or "(none)"))
            print("\nLearned:\n" + (result["notes"] or "(none yet)"))
            print()
            for run in result["runs"]:
                blocks = f"  bot checks: {', '.join(run['blocks'])}" if run["blocks"] else ""
                print(f"{run['time'][:16]}  {run['status']:<11} {run['message'][:70]}{blocks}")
        else:
            result = call("GET", "/v1/notes")
            print("Learned notes: " + (", ".join(result["sites"]) or "none yet"))
            print("Shipped guidance: " + ", ".join(result["guided_sites"]))
            print("\nGeneral guidance:\n" + result["guidance"])
            if result["general"]:
                print("\nGeneral:\n" + result["general"])
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
