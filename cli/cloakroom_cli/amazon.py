import random
import time

from playwright.sync_api import sync_playwright

from cloakroom_cli import config
from cloakroom_cli import creds
from cloakroom_cli import imessage

EMAIL_INPUTS = ("#ap_email", "#ap_email_login", "input[type='email']")
OTP_INPUTS = (
    "#auth-mfa-otpcode",
    "input[name='otpCode']",
    "input[autocomplete='one-time-code']",
    "#input-box-otp input",
    "#cvf-input-code",
    "input[name='code']",
)
OTP_SUBMITS = ("#auth-signin-button", "#cvf-submit-otp-button input", "#cvf-submit-otp-button")
CONTINUE_BUTTONS = ("#continue input[type='submit']", "#continue")
SEND_CODE_BUTTONS = ("#auth-send-code",) + CONTINUE_BUTTONS
SMS_CHOICES = ("input[type='radio'][value*='SMS']", "input[type='radio'][value*='sms']")

###############################################################################

def type_human(page, selector, text):
    page.click(selector)
    page.fill(selector, "")
    page.type(selector, text, delay=random.randint(60, 140))

###############################################################################

def first_present(page, selectors):
    for selector in selectors:
        if page.query_selector(selector):
            return selector
    return None

###############################################################################

def click_or_enter(page, selectors):
    selector = first_present(page, selectors)
    if selector:
        page.click(selector)
        return
    page.keyboard.press("Enter")

###############################################################################

def logged_in(page):
    if "/ap/" in page.url:
        return False
    greeting = page.query_selector("#nav-link-accountList-nav-line-1")
    if not greeting:
        return False
    return "sign in" not in greeting.inner_text().lower()

###############################################################################

def detect_step(page):
    if page.query_selector("#ap_password"):
        return "password"
    if first_present(page, OTP_INPUTS):
        return "otp"
    if page.query_selector("#auth-select-device-form"):
        return "choose_device"
    if first_present(page, EMAIL_INPUTS):
        return "email"
    if logged_in(page):
        return "done"
    return "unknown"

###############################################################################

def do_email(page, emit, email):
    type_human(page, first_present(page, EMAIL_INPUTS), email)
    emit("email_filled")
    click_or_enter(page, CONTINUE_BUTTONS)

###############################################################################

def do_password(page, emit, password):
    type_human(page, "#ap_password", password)
    if page.query_selector("input[name='rememberMe']"):
        page.check("input[name='rememberMe']")
    emit("password_filled")
    page.click("#signInSubmit")

###############################################################################

def do_choose_device(page, emit):
    sms = first_present(page, SMS_CHOICES)
    if sms:
        page.check(sms)
    emit("sending_code", detail="Asked Amazon to text a code.")
    click_or_enter(page, SEND_CODE_BUTTONS)

###############################################################################

def do_otp(page, emit, service, otp_timeout, since):
    emit("otp_page", detail="Waiting for the code to arrive in Messages.")
    code = imessage.wait_for_code(service, otp_timeout, since_mac_ns=since)
    if not code:
        emit("otp_timeout", detail=f"No matching code arrived in Messages within {otp_timeout}s.")
        return False
    type_human(page, first_present(page, OTP_INPUTS), code)
    if page.query_selector("input[name='rememberDevice']"):
        page.check("input[name='rememberDevice']")
    emit("otp_filled", detail="Code read from Messages and submitted.")
    click_or_enter(page, OTP_SUBMITS)
    return True

###############################################################################

def open_page(playwright):
    browser = playwright.chromium.connect_over_cdp(config.CDP_URL)
    context = browser.contexts[0]
    page = context.new_page()
    page.bring_to_front()
    return page

###############################################################################

def step_once(page, emit, step, secrets, state, otp_service, otp_timeout):
    email, password = secrets
    # Auto-fill credentials once; a repeat means Amazon rejected them, so hand over to the user.
    if step in state["filled"]:
        return False
    if step == "email" and email:
        state["filled"].add("email")
        do_email(page, emit, email)
        return True
    if step == "password" and password:
        state["filled"].add("password")
        state["otp_since"] = imessage.now_mac_ns()
        do_password(page, emit, password)
        return True
    if step == "choose_device":
        state["otp_since"] = imessage.now_mac_ns()
        do_choose_device(page, emit)
        return True
    if step == "otp" and state["messages_access"] != "ok":
        if not state["otp_hint_sent"]:
            state["otp_hint_sent"] = True
            if state["messages_access"] == "mac_only":
                detail = "iMessage 2FA capture is Mac only. Type the code in the viewer."
            else:
                detail = "Cloakroom can't read Messages (run ./cloakroom messages-access). Type the code in the viewer."
            emit(
                "waiting_for_user",
                step="otp",
                messages_access=state["messages_access"],
                detail=detail,
            )
        return True
    if step == "otp":
        submitted = do_otp(page, emit, otp_service, otp_timeout, state["otp_since"])
        state["otp_since"] = imessage.now_mac_ns()
        return submitted
    return False

###############################################################################

WAITING_HINTS = {
    "email": "Type your Amazon email in the viewer; Cloakroom continues automatically.",
    "password": "Type your Amazon password in the viewer; Cloakroom continues automatically.",
    "unknown": "Amazon is showing a page Cloakroom doesn't recognize (e.g. a puzzle). Finish it in the viewer.",
}

###############################################################################

def run(emit, otp_service="amazon", otp_timeout=180, total_timeout=300):
    secrets = creds.amazon()
    state = {
        "otp_since": imessage.now_mac_ns(),
        "filled": set(),
        "messages_access": imessage.check_access(),
        "otp_hint_sent": False,
    }
    with sync_playwright() as playwright:
        page = open_page(playwright)
        emit("browser_connected", detail=f"Watch along at {config.VIEWER_URL}")
        page.goto(config.AMAZON_HOME_URL, wait_until="domcontentloaded")
        if logged_in(page):
            emit("success", detail="Already logged in to Amazon (saved session).")
            return True
        page.goto(config.AMAZON_SIGNIN_URL, wait_until="domcontentloaded")
        deadline = time.monotonic() + total_timeout
        last_step = None
        while time.monotonic() < deadline:
            page.wait_for_load_state("domcontentloaded")
            step = detect_step(page)
            if step == "done":
                emit("success", detail="Logged in to Amazon. The session is saved in the Cloakroom profile.")
                return True
            acted = step_once(page, emit, step, secrets, state, otp_service, otp_timeout)
            if not acted and step != last_step and step in WAITING_HINTS:
                emit("waiting_for_user", step=step, detail=WAITING_HINTS[step])
            last_step = step
            time.sleep(2)
        emit("timeout", detail=f"Login did not finish within {total_timeout}s.")
        return False
