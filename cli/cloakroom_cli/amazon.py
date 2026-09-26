import random
import time

from playwright.sync_api import sync_playwright

from cloakroom_cli import config
from cloakroom_cli import creds
from cloakroom_cli import otp

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
OTP_PAUSE_SECONDS = 5

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

def fill_otp(page, emit, code):
    type_human(page, first_present(page, OTP_INPUTS), code)
    if page.query_selector("input[name='rememberDevice']"):
        page.check("input[name='rememberDevice']")
    emit("otp_filled", detail="Code submitted.")
    click_or_enter(page, OTP_SUBMITS)

###############################################################################

def otp_wait_detail(inbox):
    return (
        "Amazon is asking for a code. "
        f"POST {{\"code\":\"...\"}} to {inbox.submit_url}. "
        "Grok Bot or Muse reads Messages and submits it. "
        "You can also type the code in the viewer."
    )

###############################################################################

def handle_otp(page, emit, inbox, state, otp_timeout):
    now = time.monotonic()
    if now < state["otp_pause_until"]:
        return True
    code = inbox.take()
    if code:
        fill_otp(page, emit, code)
        state["otp_waiting"] = False
        state["otp_timed_out"] = False
        state["otp_pause_until"] = time.monotonic() + OTP_PAUSE_SECONDS
        return True
    if not state["otp_waiting"]:
        state["otp_waiting"] = True
        state["otp_deadline"] = time.monotonic() + otp_timeout
        state["otp_timed_out"] = False
        emit("waiting_for_otp", submit_url=inbox.submit_url, detail=otp_wait_detail(inbox))
        return True
    if not state["otp_timed_out"] and now > state["otp_deadline"]:
        state["otp_timed_out"] = True
        emit(
            "otp_timeout",
            submit_url=inbox.submit_url,
            detail=(
                f"No code was provided within {otp_timeout}s. "
                f"POST it to {inbox.submit_url}, or type it in the viewer."
            ),
        )
    return True

###############################################################################

def open_page(playwright):
    browser = playwright.chromium.connect_over_cdp(config.CDP_URL)
    context = browser.contexts[0]
    page = context.new_page()
    page.bring_to_front()
    return page

###############################################################################

def step_once(page, emit, step, secrets, state, inbox, otp_timeout):
    email, password = secrets
    if step != "otp":
        state["otp_waiting"] = False
        state["otp_timed_out"] = False
        state["otp_pause_until"] = 0
    if step in state["filled"]:
        return False
    if step == "email" and email:
        state["filled"].add("email")
        do_email(page, emit, email)
        return True
    if step == "password" and password:
        state["filled"].add("password")
        do_password(page, emit, password)
        return True
    if step == "choose_device":
        state["filled"].add("choose_device")
        do_choose_device(page, emit)
        return True
    if step == "otp":
        return handle_otp(page, emit, inbox, state, otp_timeout)
    return False

###############################################################################

WAITING_HINTS = {
    "email": "Type your Amazon email in the viewer; Cloakroom continues automatically.",
    "password": "Type your Amazon password in the viewer; Cloakroom continues automatically.",
    "unknown": "Amazon is showing a page Cloakroom doesn't recognize (e.g. a puzzle). Finish it in the viewer.",
}

###############################################################################

def fresh_state():
    return {
        "filled": set(),
        "otp_waiting": False,
        "otp_deadline": 0,
        "otp_timed_out": False,
        "otp_pause_until": 0,
    }

###############################################################################

def run(emit, otp_timeout=180, total_timeout=300, otp_code=None):
    secrets = creds.amazon()
    inbox = otp.Inbox(preset=otp_code)
    inbox.start()
    state = fresh_state()
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
            acted = step_once(page, emit, step, secrets, state, inbox, otp_timeout)
            if not acted and step != last_step and step in WAITING_HINTS:
                emit("waiting_for_user", step=step, detail=WAITING_HINTS[step])
            last_step = step
            time.sleep(2)
        emit("timeout", detail=f"Login did not finish within {total_timeout}s.")
        return False
