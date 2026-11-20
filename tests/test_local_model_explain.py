"""The report's "Local model" button and the route behind it.

The upstream here is a real OpenAI-compatible server (FastAPI under uvicorn on a free localhost
port) speaking the wire format the SDK reads: `GET /v1/models` and a server-sent-event stream from
`POST /v1/chat/completions`. Nothing of ours is mocked, so these tests cover the SDK calls, the
model auto-pick, the streaming and the error wording together. Nothing leaves the machine.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fake_openai import FakeUpstream, env, free_port, upstream  # noqa: F401 - fixtures by name
from webui import local_llm
from webui.app import api
from webui.local_llm import MAX_PROMPT_CHARS, LocalLlmConfig, report_injection
from webui.pages.annotate import _local_model_settings
from webui.state import LocalModelState

REPORT_HTML = (
    "<!DOCTYPE html><html><head><title>Genomic Annotation Report</title>\n</head>"
    '<body><div class="ai-explain-links"><a class="ai-explain-link chatgpt" '
    'href="https://chatgpt.com/?q=Explain%20rs1">x</a></div></body></html>'
)


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
    dead = f"http://127.0.0.1:{free_port()}/v1"
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


# --------------------------------------------------------------------------- the settings form

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model,usable,needle",
    [
        ("", True, "Explanations will use fake-small"),
        ("fake-large", True, "Explanations will use fake-large"),
        ("nope", False, "does not list 'nope'"),
    ],
)
async def test_test_connection_reports_what_the_server_lists(
    upstream: FakeUpstream, env: pytest.MonkeyPatch, model: str, usable: bool, needle: str
) -> None:
    config = LocalLlmConfig(base_url=upstream.base_url, model=model)
    assert await local_llm.list_model_ids(config) == upstream.models
    ok, message = await local_llm.check_connection(config)
    assert ok is usable
    assert needle in message and upstream.base_url in message


@pytest.mark.anyio
async def test_test_connection_names_a_dead_server(env: pytest.MonkeyPatch) -> None:
    dead = f"http://127.0.0.1:{free_port()}/v1"
    ok, message = await local_llm.check_connection(LocalLlmConfig(base_url=dead))
    assert ok is False
    assert dead in message and "Could not connect" in message


@pytest.fixture
def saved_env(env: pytest.MonkeyPatch) -> dict[str, str]:
    """`set_env_var` without touching the checkout's `.env`: records the write, sets os.environ."""
    written: dict[str, str] = {}

    def record(name: str, value: str) -> None:
        written[name] = value
        env.setenv(name, value)

    env.setattr("webui.state.set_env_var", record)
    return written


def test_saving_the_form_configures_the_report_button(saved_env: dict[str, str]) -> None:
    state = LocalModelState()
    state.local_model_base_url = " http://127.0.0.1:11434/v1/ "
    state.local_model_name = "llama3.2"
    state.set_local_model_key("  secret  ")
    previous_key = state.local_model_form_key

    state.save_local_model()

    assert saved_env == {
        local_llm.BASE_URL_ENV: "http://127.0.0.1:11434/v1",
        local_llm.MODEL_ENV: "llama3.2",
        local_llm.API_KEY_ENV: "secret",
    }
    assert local_llm.local_llm_config() == LocalLlmConfig(
        base_url="http://127.0.0.1:11434/v1", model="llama3.2", api_key="secret"
    )
    assert state.local_model_configured and state.local_model_key_set
    assert state.local_model_form_key == previous_key + 1
    assert state.local_model_key_placeholder == "Already set, type to replace"


def test_an_empty_key_keeps_the_saved_one_and_an_empty_address_turns_it_off(
    saved_env: dict[str, str], env: pytest.MonkeyPatch
) -> None:
    env.setenv(local_llm.BASE_URL_ENV, "http://127.0.0.1:11434/v1")
    env.setenv(local_llm.API_KEY_ENV, "kept")
    state = LocalModelState()
    state.load_local_model_settings()
    assert state.local_model_configured
    state.local_model_base_url = ""

    state.save_local_model()

    assert local_llm.API_KEY_ENV not in saved_env
    assert saved_env[local_llm.BASE_URL_ENV] == ""
    assert local_llm.local_llm_config() is None
    assert state.local_model_configured is False


@pytest.mark.parametrize("immutable,address", [("false", "127.0.0.1:11434"), ("true", "http://127.0.0.1:11434/v1")])
def test_the_form_refuses_a_non_url_and_the_public_demo(
    saved_env: dict[str, str], env: pytest.MonkeyPatch, immutable: str, address: str
) -> None:
    env.setenv("JUST_DNA_IMMUTABLE_MODE", immutable)
    state = LocalModelState()
    state.local_model_base_url = address
    state.save_local_model()
    assert saved_env == {}


def test_the_api_key_never_reaches_the_client() -> None:
    assert "_local_model_key_input" not in LocalModelState.base_vars
    assert "local_model_form_key" in LocalModelState.base_vars


def test_the_settings_form_builds_and_hides_in_immutable_mode() -> None:
    rendered = str(_local_model_settings().render())
    assert "local-model-settings" in rendered
    assert "is_immutable_mode" in rendered
    assert "toggle_local_model" in rendered
