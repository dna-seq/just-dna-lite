"""Reflex's blocked-event-loop warning reaches the console as one line, without the stack.

Runs Reflex's own `EventLoopBlockingMonitor` against a loop that a task blocks with `time.sleep`,
so a change to the monitor's message format shows up here rather than as tracebacks in the console.
"""

from __future__ import annotations

import asyncio
import logging
import time

import pytest
from reflex_base.event.processor import blocking
from reflex_base.event.processor.blocking import EventLoopBlockingMonitor

from webui.log_filters import STACK_MARKER, WarningWithoutStack, install_log_filters

THRESHOLD_S = 0.05


async def _block_the_loop() -> None:
    time.sleep(THRESHOLD_S * 6)


def _warnings_from_a_blocked_loop(caplog: pytest.LogCaptureFixture) -> list[str]:
    async def scenario() -> None:
        monitor = EventLoopBlockingMonitor(asyncio.get_running_loop(), THRESHOLD_S, {})
        monitor.start()
        await asyncio.create_task(_block_the_loop(), name="blocker")
        await asyncio.sleep(THRESHOLD_S * 2)  # let the monitor see the loop respond
        monitor.stop()

    with caplog.at_level(logging.WARNING, logger=blocking.logger.name):
        asyncio.run(scenario())
    return [r.getMessage() for r in caplog.records if r.name == blocking.logger.name]


@pytest.fixture
def without_filters():
    saved = list(blocking.logger.filters)
    for existing in saved:
        blocking.logger.removeFilter(existing)
    yield
    for existing in list(blocking.logger.filters):
        blocking.logger.removeFilter(existing)
    for existing in saved:
        blocking.logger.addFilter(existing)


def test_reflex_appends_the_stack_when_unfiltered(without_filters, caplog: pytest.LogCaptureFixture) -> None:
    messages = _warnings_from_a_blocked_loop(caplog)
    assert any(STACK_MARKER in m for m in messages), messages


def test_the_filtered_warning_is_one_line_that_still_names_the_task(
    without_filters, caplog: pytest.LogCaptureFixture
) -> None:
    install_log_filters()
    messages = _warnings_from_a_blocked_loop(caplog)
    blocking_lines = [m for m in messages if "is blocking the event loop" in m]
    assert blocking_lines, messages
    for message in messages:
        assert "\n" not in message, message
        assert "Traceback" not in message and STACK_MARKER not in message
    assert all("'blocker'" in m for m in blocking_lines)
    assert any("blocked the event loop for" in m for m in messages)


def test_installing_twice_adds_one_filter(without_filters) -> None:
    install_log_filters()
    install_log_filters()
    assert sum(isinstance(f, WarningWithoutStack) for f in blocking.logger.filters) == 1


@pytest.mark.parametrize(
    "msg,args",
    [
        ("plain warning %s", ("x",)),
        ("unicode Ωmega warning", None),
        ("", None),
    ],
)
def test_records_without_the_stack_marker_pass_unchanged(msg: str, args: tuple | None) -> None:
    record = logging.LogRecord("any", logging.WARNING, __file__, 1, msg, args, None)
    before = record.getMessage()
    assert WarningWithoutStack().filter(record) is True
    assert record.getMessage() == before
