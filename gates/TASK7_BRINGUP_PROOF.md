========================================================================
TASK 7 PHASE 1 - standalone bring-up: browser.credentials + browser.login
========================================================================
(Hand-invoked primitives - no executor, no LLM. The master plan's rule:
a primitive that can't be proven standalone doesn't get called by the
executor.)

Proved, with raw output:
  1. credentials('github') reads the entry from GPG-encrypted pass -
     values redacted in the output AND in the L0 log.
  2. goto + handle probes land on the real GitHub login form (each
     candidate handle resolves through the fallback chain).
  3. login(service, username_sel, password_sel, submit_sel) fills and
     submits with the REAL credentials; the url leaves /login.
  4. logged-in state verified (Dashboard marker).
  5. redaction DoD: the password value appears NOWHERE in the run's L0
     lines.

Defects found & fixed inside this phase (the point of bring-up):
  a. SECURITY - the password leaked into the L0 log. Two leaks:
       * login() filled the password via the contract-registered type_text,
         whose 'text' ARG (the actual password) is logged.
       * credentials()'s RESULT is the credential dict itself - a secret
         by construction.
     Fixed structurally (not papered over):
       * @contract/@observe gained redact_result=True; browser.credentials
         now logs its result as <redacted>.
       * login() fills both fields through a private, un-instrumented
         _fill_field (the same logic type_text uses) - a secret never
         rides a logged 'text' argument.
       * the one leaked log line was scrubbed from var/logs/friday.jsonl.
  b. Pre-logged-in profile: the persistent Playwright profile kept the
     session from the first run, so goto(/login) redirected straight to
     the home page. Fixed: the script logs out first - github.com/logout
     now shows a CONFIRMATION page with a "Sign out" button, which the
     script clicks (harmless skip when no session exists).
  c. Marker: GitHub's current home is a "Dashboard" view ("Repositories"
     was the old layout).
  d. Render timing: right after submit the page is still rendering; the
     script polls read_page_text until the marker appears (bounded wait,
     mirroring how L2 checks poll).

Raw run output (credentials -> login -> logged-in state; values redacted):
========================================================================
========================================================================
TASK 7 PHASE 1 - standalone bring-up: credentials + login
========================================================================

--- 1. credentials(service) from pass ---
credentials('github') -> keys=['password', 'username'] username=<str, len=27> password=<str, len=13> (values never printed)

--- 2. prepare: log out any existing session, land on login form ---
goto('https://github.com/logout') -> {'url': 'https://github.com/logout', 'title': 'Logout'}
click('Sign out') -> {'clicked': 'Sign out', 'url': 'https://github.com/'}
goto('https://github.com/login') -> {'url': 'https://github.com/login', 'title': 'Sign in to GitHub · GitHub'}
--- login page text (first 25 lines) ---
Skip to content
Sign in to GitHub
Username or email address
Password
Forgot password?

New to GitHub? Create an account

Terms
Privacy
Docs
Contact GitHub Support
Manage cookies
Do not share my personal information
  handle 'Username or email address' -> <Locator frame=<Frame name= url='https://github.com/login'> selector='internal:label="Username or email address"i >> nth=0'>
  handle 'Password' -> <Locator frame=<Frame name= url='https://github.com/login'> selector='[name*="Password" i] >> nth=0'>
  handle 'Sign in' -> <Locator frame=<Frame name= url='https://github.com/login'> selector='internal:role=button[name=/Sign\\ in/i] >> nth=0'>

--- 3. login(service, username, password, submit) ---
login result: {'service': 'github', 'url': 'https://github.com/'}

--- 4. post-login state ---
--- post-login page text (first 15 lines) ---
Skip to content
Dashboard
Type / to search
Loading

Dashboard
Home

=== BRING-UP DoD ===
  OK: credentials parsed from pass (values redacted)
  OK: login filled + submitted; url=https://github.com/
  OK: logged-in marker 'Dashboard' present
  OK: password appears nowhere in the L0 trace

BRING-UP: DONE (credentials -> login -> logged-in state; raw output above)
