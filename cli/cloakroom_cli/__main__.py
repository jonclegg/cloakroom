import argparse
import json
import subprocess
import sys

from cloakroom_cli import amazon
from cloakroom_cli import config
from cloakroom_cli import creds
from cloakroom_cli import imessage
from cloakroom_cli import stack

FULL_DISK_ACCESS_PANE = "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
MAC_ONLY = (
    "iMessage 2FA capture is Mac only. "
    "On this computer, type the code in the viewer at http://127.0.0.1:6080."
)

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

def output(as_json, human, **data):
    if as_json:
        print(json.dumps(data))
        return
    print(human)

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
    messages = imessage.check_access()
    email = creds.stored_email()
    data = {
        "docker_running": stack.docker_running(),
        "container": health,
        "ready": ready,
        "browser": version,
        "cdp_url": config.CDP_URL,
        "viewer_url": config.VIEWER_URL,
        "messages_access": messages,
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
    print(f"Messages access:   {messages}")
    print(f"Amazon creds set:  {bool(email)}")
    return 0 if ready else 1

###############################################################################

def cmd_amazon_login(args):
    emit = make_emit(args.json)
    if stack.health() != "healthy":
        emit("starting")
        stack.run_script("start.sh")
    ok = amazon.run(emit, otp_service=args.service, otp_timeout=args.otp_timeout, total_timeout=args.timeout)
    return 0 if ok else 1

###############################################################################

def cmd_otp(args):
    access = imessage.check_access()
    if access == "mac_only":
        output(args.json, MAC_ONLY, found=False, messages_access=access, message=MAC_ONLY)
        return 1
    if access != "ok":
        output(args.json, f"Can't read Messages ({access}). Run: ./cloakroom messages-access", found=False, messages_access=access)
        return 1
    code = imessage.wait_for_code(args.service, args.timeout)
    if not code:
        output(args.json, "No matching code found.", found=False)
        return 1
    output(args.json, code, found=True, code=code)
    return 0

###############################################################################

def cmd_messages_access(args):
    access = imessage.check_access()
    if access == "mac_only":
        output(args.json, MAC_ONLY, messages_access=access, message=MAC_ONLY)
        return 1
    if access == "ok":
        output(args.json, "Messages access OK.", messages_access=access)
        return 0
    subprocess.run(["open", FULL_DISK_ACCESS_PANE])
    output(
        args.json,
        "Opened System Settings > Privacy & Security > Full Disk Access.\n"
        "Turn on the app that runs Cloakroom (Terminal, iTerm, Cursor, or your agent app), "
        "quit and reopen that app, then run: ./cloakroom status",
        messages_access=access,
        opened_settings=True,
    )
    return 1

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
    add("status", "Report readiness, browser, and Messages access.").set_defaults(func=cmd_status)

    login = add("amazon-login", "Drive Amazon sign-in, capturing the OTP from Messages.")
    login.add_argument("--service", default="amazon", help="Keyword the OTP text must contain.")
    login.add_argument("--otp-timeout", type=int, default=180, help="Seconds to wait for the code.")
    login.add_argument("--timeout", type=int, default=300, help="Seconds for the whole login.")
    login.set_defaults(func=cmd_amazon_login)

    otp = add("otp", "Wait for a new OTP to arrive in Messages and print it.")
    otp.add_argument("--service", default="amazon")
    otp.add_argument("--timeout", type=int, default=120)
    otp.set_defaults(func=cmd_otp)

    add("messages-access", "Check Messages access; open the Full Disk Access pane if missing.").set_defaults(
        func=cmd_messages_access
    )

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
