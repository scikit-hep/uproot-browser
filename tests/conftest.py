from textual import _wait

from uproot_browser.tui.browser import Browser

# Textual's pilot polls for an idle process in 20 ms steps after every key
# press and pause. A finer step makes those waits as short as the real work.
_wait.SLEEP_GRANULARITY = 0.001
_wait.SLEEP_IDLE = _wait.SLEEP_GRANULARITY / 20.0

# Tests read app._notifications, which drops expired entries. Slow CI runners
# can take longer than the default 5 s timeout between notify and the assert.
Browser.NOTIFICATION_TIMEOUT = 600
