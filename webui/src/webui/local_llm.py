"""Explain a report result with a model the user runs themselves (Ollama, vLLM, LM Studio, llama.cpp).

The report's four assistant buttons open a third-party chat with the question prefilled. This is the
fifth: the same question goes to an OpenAI-compatible endpoint the user configured, through our own
backend, and the answer streams back into a panel on the report.

Configuration is read from the environment **at call time**, never at import, so the settings form
in the web UI (which writes ``os.environ`` and ``.env``) takes effect without a restart:

* ``LOCAL_LLM_BASE_URL``: the endpoint, ending in ``/v1`` for most servers
  (``http://127.0.0.1:11434/v1`` for Ollama). Unset or empty turns the feature off.
* ``LOCAL_LLM_MODEL``: optional; when empty the first id the endpoint lists under ``/models`` is used.
* ``LOCAL_LLM_API_KEY``: optional; most local servers need none, and the SDK gets a placeholder.

The endpoint comes only from this configuration, never from a request, so the explain route cannot be
pointed at an arbitrary host. Prompts carry genotypes, so they are never logged; only their length is.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx2
from eliot import log_message
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AsyncStream,
    AuthenticationError,
    NotFoundError,
    OpenAIError,
    PermissionDeniedError,
    Timeout,
)
from openai.types.chat import ChatCompletionChunk
from pydantic import BaseModel, ConfigDict, field_validator

from just_dna_pipelines.annotation.report_logic import LOCAL_MODEL_EXPLAIN_SNIPPET
from just_dna_pipelines.module_config import is_immutable_mode

BASE_URL_ENV = "LOCAL_LLM_BASE_URL"
MODEL_ENV = "LOCAL_LLM_MODEL"
API_KEY_ENV = "LOCAL_LLM_API_KEY"

#: The longest prompt the explain route accepts. A report's longest prompts (a phenotype result
#: with every defining position) are a few thousand characters; this leaves room and stops a
#: runaway request from becoming a large upload to the model server.
MAX_PROMPT_CHARS: int = 16_000

#: A local model can take minutes to load and answer; connecting should not.
CONNECT_TIMEOUT_S: float = 10.0
READ_TIMEOUT_S: float = 300.0

#: Sent when no key is configured. The SDK refuses to build a client without one, and the servers
#: this is for ignore the Authorization header.
_PLACEHOLDER_API_KEY = "not-needed"

_HEAD_CLOSE_RE = re.compile(r"</head\s*>", flags=re.IGNORECASE)

#: The global the report snippet reads. Also the marker that a page already carries the injection.
REPORT_CONFIG_GLOBAL = "JUST_DNA_LOCAL_LLM"


class LocalModelError(Exception):
    """The endpoint answered, but not with something we can use (e.g. it lists no models)."""


def is_valid_base_url(url: str) -> bool:
    """True for an absolute ``http`` or ``https`` URL with a host."""
    parts = urlsplit(url.strip())
    return parts.scheme in ("http", "https") and bool(parts.netloc)


class LocalLlmConfig(BaseModel):
    """Where the local model lives and which one to ask."""

    model_config = ConfigDict(frozen=True)

    base_url: str
    model: str = ""
    api_key: str = ""

    @field_validator("base_url")
    @classmethod
    def _absolute_http_url(cls, value: str) -> str:
        if not is_valid_base_url(value):
            raise ValueError(f"not an http(s) URL: {value!r}")
        return value.strip().rstrip("/")

    @property
    def model_label(self) -> str:
        """The model as a reader should see it before the first answer names it."""
        return self.model or "the first model the server lists"


def local_llm_config() -> LocalLlmConfig | None:
    """The configured endpoint, or ``None`` when the feature is off.

    A base URL that is not an http(s) URL counts as off and is logged, so a typo in ``.env`` does
    not put a button on every report that can only fail.
    """
    base_url = os.getenv(BASE_URL_ENV, "").strip()
    if not base_url:
        return None
    if not is_valid_base_url(base_url):
        log_message(message_type="local_llm:invalid_base_url", base_url=base_url)
        return None
    return LocalLlmConfig(
        base_url=base_url,
        model=os.getenv(MODEL_ENV, "").strip(),
        api_key=os.getenv(API_KEY_ENV, "").strip(),
    )


def available_local_llm_config() -> LocalLlmConfig | None:
    """The configuration the report button and the explain route may use.

    ``None`` in immutable (public demo) mode whatever the environment says: on a public box the
    endpoint would be the server's own, and visitors would be sending genotypes to it.
    """
    if is_immutable_mode():
        return None
    return local_llm_config()


def _client(config: LocalLlmConfig) -> AsyncOpenAI:
    """An SDK client for the endpoint; no retries, so a dead server is reported in seconds."""
    return AsyncOpenAI(
        base_url=config.base_url,
        api_key=config.api_key or _PLACEHOLDER_API_KEY,
        timeout=Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
        max_retries=0,
    )


async def _model_ids(client: AsyncOpenAI) -> list[str]:
    return [model.id async for model in client.models.list()]


async def list_model_ids(config: LocalLlmConfig) -> list[str]:
    """Every model id the endpoint lists under ``/models``."""
    async with _client(config) as client:
        return await _model_ids(client)


async def _resolve_model(client: AsyncOpenAI, config: LocalLlmConfig) -> str:
    if config.model:
        return config.model
    ids = await _model_ids(client)
    if not ids:
        raise LocalModelError(
            f"The local model server at {config.base_url} lists no models. "
            f"Load one there, or set {MODEL_ENV}."
        )
    return ids[0]


def _root_cause(exc: BaseException) -> BaseException:
    """The innermost exception in the chain (``__cause__``, else ``__context__``), loop-safe."""
    seen: set[int] = set()
    current = exc
    while id(current) not in seen:
        seen.add(id(current))
        nxt = current.__cause__ or current.__context__
        if nxt is None:
            break
        current = nxt
    return current


def describe_local_llm_failure(config: LocalLlmConfig, exc: BaseException, model: str = "") -> str:
    """Why the local model gave no answer, naming the endpoint and what to check."""
    url = config.base_url
    if isinstance(exc, LocalModelError):
        return str(exc)
    if isinstance(exc, APITimeoutError):
        return (
            f"The local model at {url} did not answer in time. A large model can take minutes to "
            "load; try again, or pick a smaller one."
        )
    if isinstance(exc, APIConnectionError):
        cause = _root_cause(exc)
        detail = f" ({cause})" if cause is not exc and str(cause) else ""
        return (
            f"Could not connect to the local model at {url}{detail}. Check that the server is "
            "running and that the address and port are right."
        )
    if isinstance(exc, NotFoundError):
        named = f" for model '{model}'" if model else ""
        return (
            f"The local model server at {url} answered 404{named}. The model may not be loaded "
            "there, or the address may be missing its /v1 suffix."
        )
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return f"The local model server at {url} refused the API key (HTTP {exc.status_code}). Check {API_KEY_ENV}."
    if isinstance(exc, APIStatusError):
        return f"The local model server at {url} answered HTTP {exc.status_code}: {exc.message}"
    return f"The local model at {url} failed: {exc}"


def describe_interruption(config: LocalLlmConfig, exc: BaseException) -> str:
    """Why an answer that had started stopped. Never "could not connect": it had connected."""
    if isinstance(exc, APITimeoutError):
        return f"the local model at {config.base_url} went quiet for longer than {READ_TIMEOUT_S:.0f} seconds"
    return f"the connection to the local model at {config.base_url} broke off ({_root_cause(exc)})"


class LocalExplanation:
    """One streamed answer. ``open()`` raises before any text, ``chunks()`` never raises.

    Split in two so the route can turn a failure to start (server down, unknown model) into an
    HTTP error with a readable body, while a failure halfway through becomes the last words of the
    answer: by then the response status has been sent.
    """

    def __init__(self, config: LocalLlmConfig, prompt: str) -> None:
        self.config = config
        self.prompt = prompt
        self.model = ""
        self._client = _client(config)
        self._stream: AsyncStream[ChatCompletionChunk] | None = None

    async def open(self) -> str:
        """Pick the model and start the completion; returns the model id actually used."""
        self.model = await _resolve_model(self._client, self.config)
        self._stream = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": self.prompt}],
            stream=True,
        )
        log_message(
            message_type="local_llm:explain_started",
            endpoint=self.config.base_url,
            model=self.model,
            prompt_chars=len(self.prompt),
        )
        return self.model

    async def aclose(self) -> None:
        await self._client.close()

    async def chunks(self) -> AsyncIterator[str]:
        """The answer's text as it arrives; a mid-answer failure ends it with the reason."""
        assert self._stream is not None, "open() must succeed before chunks()"
        streamed = 0
        try:
            async for chunk in self._stream:
                for choice in chunk.choices:
                    text = choice.delta.content if choice.delta else None
                    if text:
                        streamed += len(text)
                        yield text
        except (OpenAIError, httpx2.HTTPError) as exc:
            message = describe_interruption(self.config, exc)
            log_message(
                message_type="local_llm:explain_interrupted",
                endpoint=self.config.base_url,
                model=self.model,
                error=repr(exc),
            )
            yield f"\n\n[The answer stopped: {message}]"
        finally:
            await self.aclose()
        log_message(
            message_type="local_llm:explain_finished",
            endpoint=self.config.base_url,
            model=self.model,
            answer_chars=streamed,
        )


def report_injection(config: LocalLlmConfig, endpoint_path: str) -> str:
    """The markup a served report gets before ``</head>``: its settings, then the button's code.

    The settings are JSON inside a ``<script>``; ``<``, ``>`` and ``&`` are escaped as JSON unicode
    escapes so a value containing ``</script>`` cannot end the element early.
    """
    settings = {
        "endpoint": endpoint_path,
        "model": config.model,
        "modelLabel": config.model_label,
        "baseUrl": config.base_url,
    }
    encoded = (
        json.dumps(settings, ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    snippet = LOCAL_MODEL_EXPLAIN_SNIPPET.read_text(encoding="utf-8")
    return f"<script>window.{REPORT_CONFIG_GLOBAL} = {encoded};</script>\n{snippet}"


def inject_local_model_button(html_text: str, endpoint_path: str) -> str:
    """Add the local-model button to a report being served, or return it unchanged.

    Unchanged when the feature is off, in immutable mode, or when the page already carries it.
    Done at serve time so reports generated before the model was configured gain the button too,
    and so a downloaded copy, which has no backend to talk to, never shows one.
    """
    config = available_local_llm_config()
    if config is None or f"window.{REPORT_CONFIG_GLOBAL}" in html_text:
        return html_text
    block = report_injection(config, endpoint_path)
    match = _HEAD_CLOSE_RE.search(html_text)
    if match is None:
        return f"{block}\n{html_text}"
    return f"{html_text[:match.start()]}{block}\n{html_text[match.start():]}"


async def check_connection(config: LocalLlmConfig) -> tuple[bool, str]:
    """The settings form's Test connection: whether explanations would work, and one line why.

    True only when the endpoint answers and lists the configured model (or, with none configured,
    any model at all).
    """
    try:
        ids = await list_model_ids(config)
    except OpenAIError as exc:
        return False, describe_local_llm_failure(config, exc)
    usable = bool(ids) and (not config.model or config.model in ids)
    return usable, connection_summary(config, ids)


def connection_summary(config: LocalLlmConfig, ids: list[str]) -> str:
    """One line for the settings form's Test connection toast."""
    if not ids:
        return f"Connected to {config.base_url}, but it lists no models."
    shown = ", ".join(ids[:5]) + (f" and {len(ids) - 5} more" if len(ids) > 5 else "")
    if config.model and config.model not in ids:
        return (
            f"Connected to {config.base_url}, but it does not list '{config.model}'. "
            f"It lists: {shown}."
        )
    using = config.model or ids[0]
    return f"Connected to {config.base_url}. Explanations will use {using}. Models: {shown}."

