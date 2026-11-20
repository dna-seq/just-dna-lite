"""The report's "Local model" button and the route behind it.

The upstream here is a real OpenAI-compatible server (FastAPI under uvicorn on a free localhost
port) speaking the wire format the SDK reads: `GET /v1/models` and a server-sent-event stream from
`POST /v1/chat/completions`. Nothing of ours is mocked, so these tests cover the SDK calls, the
model auto-pick, the streaming and the error wording together. Nothing leaves the machine.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from webui import local_llm
from webui.app import api
from webui.local_llm import MAX_PROMPT_CHARS, LocalLlmConfig, connection_summary, report_injection

REPORT_HTML = (
    "<!DOCTYPE html><html><head><title>Genomic Annotation Report</title>\n</head>"
    '<body><div class="ai-explain-links"><a class="ai-explain-link chatgpt" '
    'href="https://chatgpt.com/?q=Explain%20rs1">x</a></div></body></html>'
)
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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def upstream() -> Iterator[FakeUpstream]:
    fake = FakeUpstream()
    port = _free_port()
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


@pytest.fixture
def client() -> TestClient:
    return TestClient(api)


@pytest.fixture
def report_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    report_dir = tmp_path / "anonymous" / "sample1" / "reports"
    report_dir.mkdir(parents=True)
    path = report_dir / "report.html"
    path.write_text(REPORT_HTML, encoding="utf-8")
    monkeypatch.setattr("webui.app.get_user_output_dir", lambda: tmp_path)
    # Analytics would change the served bytes on its own; these tests are about the button.
    monkeypatch.setattr("webui.app.inject_umami_tracker", lambda html: html)
    return path


VIEW = "/api/report/anonymous/sample1/report.html"
DOWNLOAD = "/api/download-report/anonymous/sample1/report.html"


# --------------------------------------------------------------------------- injection at serve time

def test_a_configured_model_puts_its_settings_and_the_button_code_before_head_close(
    env: pytest.MonkeyPatch, client: TestClient, report_file: Path
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, "http://127.0.0.1:11434/v1/")
    env.setenv(local_llm.MODEL_ENV, "llama3.2")
    served = client.get(VIEW)
    assert served.status_code == 200
    html = served.text

    marker = "window.JUST_DNA_LOCAL_LLM = "
    assert html.count(marker) == 1
    assert html.index(marker) < html.lower().index("</head>")
    settings = json.loads(html[html.index(marker) + len(marker):html.index(";</script>")])
    assert settings == {
        "endpoint": "/api/explain-local",
        "model": "llama3.2",
        "modelLabel": "llama3.2",
        "baseUrl": "http://127.0.0.1:11434/v1",
    }
    assert local_llm.LOCAL_MODEL_EXPLAIN_SNIPPET.read_text(encoding="utf-8") in html
    # Everything the generator wrote is still there, unchanged and in order.
    assert html.replace(report_injection(LocalLlmConfig(base_url="http://127.0.0.1:11434/v1", model="llama3.2"),
                                         "/api/explain-local") + "\n", "") == REPORT_HTML


@pytest.mark.parametrize("immutable", ["false", "true"])
def test_without_a_usable_model_the_report_is_served_byte_identical(
    env: pytest.MonkeyPatch, client: TestClient, report_file: Path, immutable: str
) -> None:
    env.setenv("JUST_DNA_IMMUTABLE_MODE", immutable)
    if immutable == "true":
        # Configured, but a public demo must never offer it.
        env.setenv(local_llm.BASE_URL_ENV, "http://127.0.0.1:11434/v1")
    served = client.get(VIEW)
    assert served.status_code == 200
    assert served.content == report_file.read_bytes()


def test_an_address_that_is_not_an_http_url_counts_as_unset(
    env: pytest.MonkeyPatch, client: TestClient, report_file: Path
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, "127.0.0.1:11434")
    assert local_llm.local_llm_config() is None
    assert client.get(VIEW).content == report_file.read_bytes()


def test_the_download_stays_byte_identical_with_a_model_configured(
    env: pytest.MonkeyPatch, client: TestClient, report_file: Path
) -> None:
    """A downloaded copy has no backend to talk to, so it must not carry a button."""
    env.setenv(local_llm.BASE_URL_ENV, "http://127.0.0.1:11434/v1")
    assert "JUST_DNA_LOCAL_LLM" in client.get(VIEW).text
    downloaded = client.get(DOWNLOAD)
    assert downloaded.status_code == 200
    assert downloaded.content == report_file.read_bytes()


def test_a_value_containing_a_closing_script_tag_cannot_end_the_settings_script() -> None:
    hostile = "http://evil.test/</script><script>alert(1)</script>"
    block = report_injection(LocalLlmConfig(base_url=hostile, model="m</script>&"), "/api/explain-local")
    settings_script = block[:block.index("</script>") + len("</script>")]
    assert "<script>alert(1)" not in settings_script
    assert settings_script.count("<") == 2  # its own <script> and </script>
    payload = settings_script[len("<script>window.JUST_DNA_LOCAL_LLM = "):-len(";</script>")]
    assert json.loads(payload)["baseUrl"] == hostile
    assert json.loads(payload)["model"] == "m</script>&"


def test_injection_happens_once_even_if_the_page_already_carries_it(env: pytest.MonkeyPatch) -> None:
    env.setenv(local_llm.BASE_URL_ENV, "http://127.0.0.1:11434/v1")
    once = local_llm.inject_local_model_button(REPORT_HTML, "/api/explain-local")
    assert once != REPORT_HTML
    assert local_llm.inject_local_model_button(once, "/api/explain-local") == once


# --------------------------------------------------------------------------- the explain route

def test_the_answer_streams_from_the_configured_model(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    env.setenv(local_llm.MODEL_ENV, "fake-large")
    prompt = "Explain this rsID from my DNA\nRSID: rs429358\nGene: APOE"
    before = len(upstream.received)

    with client.stream("POST", "/api/explain-local", json={"prompt": prompt}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert response.headers["x-local-model"] == "fake-large"
        pieces = list(response.iter_text())

    assert "".join(pieces) == FakeUpstream.answer_for("fake-large", prompt)
    sent = upstream.received[before:]
    assert len(sent) == 1
    assert sent[0]["model"] == "fake-large"
    assert sent[0]["stream"] is True
    assert sent[0]["messages"] == [{"role": "user", "content": prompt}]


def test_without_a_model_name_the_first_listed_model_answers(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    response = client.post("/api/explain-local", json={"prompt": "Explain rs1"})
    assert response.status_code == 200
    assert response.headers["x-local-model"] == upstream.models[0]
    assert upstream.received[-1]["model"] == upstream.models[0]
    assert response.text == FakeUpstream.answer_for(upstream.models[0], "Explain rs1")


def test_an_endpoint_listing_no_models_says_so_and_names_itself(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    env.setattr(upstream, "models", [])
    response = client.post("/api/explain-local", json={"prompt": "Explain rs1"})
    assert response.status_code == 502
    assert upstream.base_url in response.text
    assert "lists no models" in response.text


def test_an_unknown_model_is_a_readable_502_naming_the_endpoint_and_model(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    env.setenv(local_llm.MODEL_ENV, "not-pulled")
    response = client.post("/api/explain-local", json={"prompt": "Explain rs1"})
    assert response.status_code == 502
    assert upstream.base_url in response.text
    assert "404" in response.text and "not-pulled" in response.text


def test_a_server_that_is_not_running_is_named_in_the_error(
    env: pytest.MonkeyPatch, client: TestClient
) -> None:
    dead = f"http://127.0.0.1:{_free_port()}/v1"
    env.setenv(local_llm.BASE_URL_ENV, dead)
    env.setenv(local_llm.MODEL_ENV, "anything")
    started = time.monotonic()
    response = client.post("/api/explain-local", json={"prompt": "Explain rs1"})
    assert response.status_code == 502
    assert dead in response.text
    assert "Could not connect" in response.text
    # No retries: a dead local server is reported at once, not after the SDK's backoff.
    assert time.monotonic() - started < local_llm.CONNECT_TIMEOUT_S


def test_an_answer_cut_off_halfway_ends_with_the_reason(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    """By then the status line has gone out, so the reason is the answer's last words."""
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    env.setenv(local_llm.MODEL_ENV, "fake-small")
    env.setattr(upstream, "breaks", {"fake-small"})
    response = client.post("/api/explain-local", json={"prompt": "Explain rs1"})
    assert response.status_code == 200
    full = FakeUpstream.answer_for("fake-small", "Explain rs1")
    head, _, tail = response.text.partition("\n\n[The answer stopped: ")
    assert head == full[:14]
    assert upstream.base_url in tail and "broke off" in tail and tail.endswith("]")


@pytest.mark.parametrize(
    "setup,prompt,status,needle",
    [
        ("immutable", "Explain rs1", 403, "public demo"),
        ("unconfigured", "Explain rs1", 503, "LOCAL_LLM_BASE_URL"),
        ("configured", "x" * (MAX_PROMPT_CHARS + 1), 413, str(MAX_PROMPT_CHARS)),
        ("configured", "   ", 422, "empty"),
    ],
)
def test_refusals_say_why(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream,
    setup: str, prompt: str, status: int, needle: str,
) -> None:
    if setup in ("immutable", "configured"):
        env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    if setup == "immutable":
        env.setenv("JUST_DNA_IMMUTABLE_MODE", "true")
    before = len(upstream.received)
    response = client.post("/api/explain-local", json={"prompt": prompt})
    assert response.status_code == status
    assert needle in response.json()["detail"]
    assert len(upstream.received) == before, "a refused request must not reach the model"


def test_a_cross_site_form_post_cannot_start_the_model(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    """Only a JSON body is read. Another site can send `text/plain` without a CORS preflight, so
    that must not reach the model; `application/json` needs the preflight, which nothing answers."""
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    before = len(upstream.received)
    response = client.post(
        "/api/explain-local", content=b'{"prompt": "Explain rs1"}', headers={"content-type": "text/plain"}
    )
    assert response.status_code == 422
    preflight = client.options(
        "/api/explain-local",
        headers={"origin": "https://elsewhere.test", "access-control-request-method": "POST"},
    )
    assert "access-control-allow-origin" not in preflight.headers
    assert len(upstream.received) == before


def test_a_prompt_at_the_limit_is_accepted(
    env: pytest.MonkeyPatch, client: TestClient, upstream: FakeUpstream
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, upstream.base_url)
    prompt = "y" * MAX_PROMPT_CHARS
    response = client.post("/api/explain-local", json={"prompt": prompt})
    assert response.status_code == 200
    assert response.text == FakeUpstream.answer_for(upstream.models[0], prompt)


# --------------------------------------------------------------------------- the settings form's test

@pytest.mark.anyio
async def test_test_connection_lists_the_models(upstream: FakeUpstream, env: pytest.MonkeyPatch) -> None:
    config = LocalLlmConfig(base_url=upstream.base_url)
    ids = await local_llm.list_model_ids(config)
    assert ids == upstream.models
    summary = connection_summary(config, ids)
    assert upstream.base_url in summary and upstream.models[0] in summary
    missing = connection_summary(LocalLlmConfig(base_url=upstream.base_url, model="nope"), ids)
    assert "does not list 'nope'" in missing


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
