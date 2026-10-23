from textual import _wait

# Textual's pilot polls for an idle process in 20 ms steps after every key
# press and pause. A finer step makes those waits as short as the real work.
_wait.SLEEP_GRANULARITY = 0.001
_wait.SLEEP_IDLE = _wait.SLEEP_GRANULARITY / 20.0
