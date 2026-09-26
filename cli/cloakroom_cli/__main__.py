import argparse
import json
import os
import sys

from cloakroom_cli import amazon
from cloakroom_cli import config
from cloakroom_cli import creds
from cloakroom_cli import stack

###############################################################################

def make_emit(as_json):
    def emit(event, **fields):
        if as_json:
            print(json.dumps({"event": event, **fields}), flush=True)
            return
        detail = fields.get("detail", "")
        print(f"[cloakroom] {event}: {detail}" if detail else f"[cloakroom] {event}", flush=True)
    return emit

###############################################################################

def cmd_start(args):
    stack.run_script("start.sh")
    return 0

###############################################################################

def cmd_stop(args):
    stack.run_script("stop.sh")
    return 0

###############################################################################

def cmd_status(args):
    health = stack.health()
    ready = health == "healthy"
    version = stack.browser_version() if ready else None
    email = creds.stored_email()
    data = {
        "docker_running": stack.docker_running(),
        "container": health,
        "ready": ready,
        "browser": version,
        "cdp_url": config.CDP_URL,
        "viewer_url": config.VIEWER_URL,
        "amazon_credentials": bool(email),
    }
    if args.json:
        print(json.dumps(data))
        return 0
    print(f"Docker running:    {data['docker_running']}")
    print(f"Container:         {health}")
    print(f"Browser:           {version or '-'}")
    print(f"Viewer:            {config.VIEWER_URL}")
    print(f"CDP:               {config.CDP_URL}")
    print(f"Amazon creds set:  {bool(email)}")
    return 0 if ready else 1

###############################################################################

def cmd_amazon_login(args):
    emit = make_emit(args.json)
    if stack.health() != "healthy":
        emit("starting")
        stack.run_script("start.sh")
    ok = amazon.run(
        emit,
        otp_timeout=args.otp_timeout,
        total_timeout=args.timeout,
        otp_code=args.otp,
    )
    return 0 if ok else 1

###############################################################################

def cmd_creds(args):
    if args.action in ("set", "forget") and sys.platform != "darwin":
        print("Keychain storage is Mac only. Set CLOAKROOM_AMAZON_EMAIL and CLOAKROOM_AMAZON_PASSWORD instead.")
        return 1
    if args.action == "set":
        email = args.email or input("Amazon email: ").strip()
        creds.save_amazon(email)
        print("Stored. Password is in your macOS Keychain; email is in ~/.cloakroom.")
        return 0
    if args.action == "forget":
        creds.forget_amazon()
        print("Removed stored Amazon credentials.")
        return 0
    email = creds.stored_email()
    print(f"Amazon credentials set: {bool(email)}" + (f" ({email})" if email else ""))
    return 0

###############################################################################

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser = argparse.ArgumentParser(prog="cloakroom", description="Turnkey stealth browser control for agents.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, help_text):
        return sub.add_parser(name, help=help_text, parents=[common])

    add("start", "Start the stealth browser stack.").set_defaults(func=cmd_start)
    add("stop", "Stop the stack (profile is kept).").set_defaults(func=cmd_stop)
    add("status", "Report readiness and the browser.").set_defaults(func=cmd_status)

    login = add("amazon-login", "Drive Amazon sign-in. The assistant supplies the one-time code.")
    login.add_argument(
        "--otp",
        default=os.environ.get("CLOAKROOM_OTP"),
        help="One-time code, if the assistant already has it. Or set CLOAKROOM_OTP.",
    )
    login.add_argument("--otp-timeout", type=int, default=180, help="Seconds to wait for the code.")
    login.add_argument("--timeout", type=int, default=300, help="Seconds for the whole login.")
    login.set_defaults(func=cmd_amazon_login)

    creds_cmd = add("creds", "Store Amazon credentials in the macOS Keychain.")
    creds_cmd.add_argument("action", nargs="?", default="status", choices=["set", "forget", "status"])
    creds_cmd.add_argument("--email")
    creds_cmd.set_defaults(func=cmd_creds)
    return parser

###############################################################################

def main():
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))

###############################################################################

if __name__ == "__main__":
    main()
