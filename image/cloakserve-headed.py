import importlib.machinery
import importlib.util
import sys

HEADED_FLAG = "--headless=false"

# cloakserve forwards --headless=false to Chromium verbatim, and Chromium treats any
# --headless switch as headless mode, so nothing reaches the Xvfb display the viewer shows.
# Keep cloakserve's headed config but drop the flag from Chromium's argv.
loader = importlib.machinery.SourceFileLoader("cloakserve", "/usr/local/bin/cloakserve")
spec = importlib.util.spec_from_loader("cloakserve", loader)
cloakserve = importlib.util.module_from_spec(spec)
sys.modules["cloakserve"] = cloakserve
loader.exec_module(cloakserve)

upstream_parse = cloakserve.parse_cli_args

###############################################################################

def parse_headed(argv):
    config, passthrough = upstream_parse([HEADED_FLAG] + argv)
    return config, [arg for arg in passthrough if arg != HEADED_FLAG]

###############################################################################

cloakserve.parse_cli_args = parse_headed
cloakserve.main()
