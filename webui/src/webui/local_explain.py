"""Explain a result in the web UI with the configured local model: a Reflex state mixin.

The HTML reports get a "Local model" button from `webui.local_llm` (injected when the backend serves
a report). Results that live in the web UI itself, PRS first, get the same model through this mixin:
a state mixes in `LocalModelExplainMixin` and overrides `_local_explain_request` to say what the
selected result is and which question to ask about it. The answer streams into state and
`webui.components.local_explain.local_explain_panel` shows it.

Same rules as the report button: the endpoint comes from configuration only (never the client),
nothing is offered in immutable (public demo) mode, the prompt is never logged (only its length,
by `LocalExplanation`), and a question longer than `MAX_PROMPT_CHARS` is refused.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

import reflex as rx
from openai import OpenAIError
from pydantic import BaseModel

from webui.local_llm import (
    MAX_PROMPT_CHARS,
    LocalExplanation,
    LocalLlmConfig,
    LocalModelError,
    available_local_llm_config,
    describe_local_llm_failure,
)

# How often a streaming answer is pushed to the browser; each push is a state delta.
PUSH_INTERVAL_S = 0.25


class LocalExplainRequest(BaseModel):
    """What to explain: a short name for the reader, and the question sent to the model."""

    subject: str
    prompt: str


@dataclass(frozen=True)
class ExplanationUpdate:
    """The answer so far. `error` is set when no answer could start; `done` on the last update."""

    text: str
    model: str = ""
    error: str = ""
    done: bool = False


async def stream_explanation(
    config: LocalLlmConfig,
    prompt: str,
    push_interval_s: float = PUSH_INTERVAL_S,
) -> AsyncGenerator[ExplanationUpdate, None]:
    """The local model's answer to *prompt*, as accumulated text at most every `push_interval_s`.

    Never raises for the model's sake: a refusal or a failure to start is an update with `error`
    naming the endpoint; a failure halfway ends the text with the reason (`LocalExplanation`).
    """
    if len(prompt) > MAX_PROMPT_CHARS:
        yield ExplanationUpdate(
            "",
            error=f"The question is {len(prompt)} characters long; the local model is sent at most {MAX_PROMPT_CHARS}.",
            done=True,
        )
        return
    explanation = LocalExplanation(config, prompt)
    try:
        model = await explanation.open()
    except (OpenAIError, LocalModelError) as exc:
        await explanation.aclose()
        yield ExplanationUpdate("", error=describe_local_llm_failure(config, exc, config.model), done=True)
        return
    yield ExplanationUpdate("", model=model)
    text = ""
    last_push = time.monotonic()
    # aclosing: a reader that stops early (a newer question) closes the stream to the model too.
    async with contextlib.aclosing(explanation.chunks()) as chunks:
        async for chunk in chunks:
            text += chunk
            if time.monotonic() - last_push >= push_interval_s:
                yield ExplanationUpdate(text, model=model)
                last_push = time.monotonic()
    yield ExplanationUpdate(text, model=model, done=True)


class LocalModelExplainMixin(rx.State, mixin=True):
    """Adds "Explain with your local model" to a state; override `_local_explain_request`."""

    local_explain_ready: bool = False
    # Which model and where, for the panel's one line, e.g. "gemma3:12b at http://127.0.0.1:11434/v1".
    local_explain_where: str = ""
    local_explain_busy: bool = False
    local_explain_subject: str = ""
    local_explain_model: str = ""
    local_explain_text: str = ""
    local_explain_error: str = ""
    # Bumped by every new question and every reset, so a late chunk of an old answer is dropped.
    local_explain_token: int = 0

    def _local_explain_request(self) -> LocalExplainRequest | None:
        """The selected result and its question, or None when there is nothing to explain."""
        raise NotImplementedError(f"{type(self).__name__} must say what its local model explains")

    def _reset_local_explanation(self) -> None:
        self.local_explain_token += 1
        self.local_explain_busy = False
        self.local_explain_subject = ""
        self.local_explain_model = ""
        self.local_explain_text = ""
        self.local_explain_error = ""

    def _refresh_local_explain_config(self) -> LocalLlmConfig | None:
        config = available_local_llm_config()
        self.local_explain_ready = config is not None
        self.local_explain_where = f"{config.model_label} at {config.base_url}" if config else ""
        return config

    @rx.event
    def refresh_local_explain(self) -> None:
        """Re-read the settings (the Reports tab's form can change them without a restart)."""
        self._refresh_local_explain_config()

    @rx.event
    def clear_local_explanation(self) -> None:
        self._reset_local_explanation()

    def _begin_local_explanation(self) -> tuple[LocalLlmConfig, LocalExplainRequest, int] | None:
        """Start a question under the state lock: the settings, the request and its token, or None.

        None when no model is usable (unset, invalid, immutable mode), an answer is still streaming,
        or there is nothing to explain (then the panel says so).
        """
        config = self._refresh_local_explain_config()
        if config is None or self.local_explain_busy:
            return None
        request = self._local_explain_request()
        self._reset_local_explanation()
        if request is None:
            self.local_explain_error = "There is no result to explain yet."
            return None
        self.local_explain_busy = True
        self.local_explain_subject = request.subject
        return config, request, self.local_explain_token

    def _apply_explanation_update(self, token: int, update: ExplanationUpdate) -> bool:
        """Show *update* if it belongs to the current question; False once it no longer does."""
        if self.local_explain_token != token:
            return False
        self.local_explain_text = update.text
        self.local_explain_model = update.model or self.local_explain_model
        self.local_explain_error = update.error
        if update.done:
            self.local_explain_busy = False
        return True

    @rx.event(background=True)
    async def explain_with_local_model(self) -> None:
        """Ask the local model about the selected result and stream its answer into state."""
        async with self:
            started = self._begin_local_explanation()
        if started is None:
            return
        config, request, token = started
        async with contextlib.aclosing(stream_explanation(config, request.prompt)) as updates:
            async for update in updates:
                async with self:
                    if not self._apply_explanation_update(token, update):
                        return
        async with self:
            if self.local_explain_token == token:
                self.local_explain_busy = False
