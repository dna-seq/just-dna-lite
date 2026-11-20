"""A real OpenAI-compatible server for tests: FastAPI under uvicorn on a free localhost port.

It speaks the wire format the SDK reads (`GET /v1/models` and a server-sent-event stream from
`POST /v1/chat/completions`), so nothing of ours is mocked. Import the fixtures by name into a test
module (`from fake_openai import FakeUpstream, env, upstream`). Nothing leaves the machine.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from webui import local_llm

PROXY_VARS = ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


class FakeUpstream:
    """An OpenAI-compatible server whose model list and received requests a test can see."""

    def __init__(self) -> None:
        self.models: list[str] = ["fake-small", "fake-large"]
        #: Models that send part of an answer and then drop the connection.
        self.breaks: set[str] = set()
        self.received: list[dict] = []
        self.base_url = ""

    @staticmethod
    def answer_for(model: str, prompt: str) -> str:
        """What the fake model says: derived from its input, so a test can recompute it."""
        return f"{model} read {len(prompt)} characters. First line: {prompt.splitlines()[0]}"

    def app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/v1/models")
        async def models() -> dict:
            return {
                "object": "list",
                "data": [{"id": m, "object": "model", "created": 0, "owned_by": "test"} for m in self.models],
            }

        @app.post("/v1/chat/completions", response_model=None)
        async def completions(request: Request) -> StreamingResponse | JSONResponse:
            body = await request.json()
            self.received.append(body)
            model = body["model"]
            if model not in self.models:
                return JSONResponse(
                    {"error": {"message": f"model '{model}' not found", "type": "not_found"}},
                    status_code=404,
                )
            text = self.answer_for(model, body["messages"][-1]["content"])
            pieces = [text[i:i + 7] for i in range(0, len(text), 7)]

            def events() -> Iterator[str]:
                for index, piece in enumerate(pieces):
                    if model in self.breaks and index == 2:
                        raise RuntimeError("upstream dropped the connection")
                    chunk = {
                        "id": "c1", "object": "chat.completion.chunk", "created": 0, "model": model,
                        "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(events(), media_type="text/event-stream")

        return app


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def upstream() -> Iterator[FakeUpstream]:
    fake = FakeUpstream()
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(fake.app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        assert time.monotonic() < deadline, "fake upstream did not start"
        time.sleep(0.05)
    fake.base_url = f"http://127.0.0.1:{port}/v1"
    yield fake
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """A clean environment: not immutable, no local model, no proxy between us and localhost."""
    monkeypatch.setenv("JUST_DNA_IMMUTABLE_MODE", "false")
    for name in (local_llm.BASE_URL_ENV, local_llm.MODEL_ENV, local_llm.API_KEY_ENV, *PROXY_VARS):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch
