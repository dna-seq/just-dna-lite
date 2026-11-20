"""Logging filters that keep warnings to one line in the dev console.

Reflex's development monitor (`reflex_base.event.processor.blocking`) warns when an event handler
holds the event loop past `event_loop_blocking_threshold` (0.2 s), and appends the handler's whole
stack, often forty frames of library code, to that warning. The first line already names the
handler and the line of our code that blocked, which is what the warning is for. A warning is
not a crash, and a traceback under every one of them buried the real errors in `uv run start`'s
console, so the stack is cut and the line kept.
"""

from __future__ import annotations

import logging

from reflex_base.event.processor import blocking

# Where the monitor's message stops being one line: everything from here on is the stack.
STACK_MARKER = "\nBlocking stack"


class WarningWithoutStack(logging.Filter):
    """Cut a record's message at `STACK_MARKER`; records without it pass unchanged."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        head, marker, _stack = message.partition(STACK_MARKER)
        if marker:
            record.msg = head
            record.args = None
        return True


def install_log_filters() -> None:
    """Attach the filters once per process; calling it again adds nothing."""
    if not any(isinstance(existing, WarningWithoutStack) for existing in blocking.logger.filters):
        blocking.logger.addFilter(WarningWithoutStack())
