"""PRS results get "Explain with your local model" through `LocalModelExplainMixin`.

The question is prs-ui's own prompt for the selected (or first) score or trait, the one its Ask-AI
bar hands ChatGPT and the others; the answer streams from the configured OpenAI-compatible server
(a real one, `fake_openai`). Rows carry the `ai_ask` payload exactly as prs-ui builds it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from prs_ui.mixin import _build_ai_links

from fake_openai import FakeUpstream, env, free_port, upstream  # noqa: F401 - fixtures by name
from webui import local_llm
from webui.components.local_explain import local_explain_panel
from webui.local_explain import ExplanationUpdate, LocalExplainRequest, stream_explanation
from webui.local_llm import MAX_PROMPT_CHARS, LocalLlmConfig
from webui.pages.annotate import _prs_tab_content
from webui.state import PRSState, _prs_local_explain_request


def _score_row(pgs_id: str, trait: str) -> dict[str, Any]:
    raw = {"pgs_id": pgs_id, "trait_reported": trait, "percentile": 91.2, "score": 1.3}
    return {**raw, "ai_ask": json.dumps(_build_ai_links("score", raw))}


def _trait_row(trait: str) -> dict[str, Any]:
    raw = {"trait": trait, "models": 3}
    return {**raw, "ai_ask": json.dumps(_build_ai_links("trait_summary", raw))}


def _full_prompt(row: dict[str, Any]) -> str:
    """The copy-only Ask-AI entry: prs-ui's whole prompt, uncut by any site's URL limit."""
    (prompt,) = [link["copyText"] for link in json.loads(row["ai_ask"]) if link["copyText"]]
    return prompt


SCORES = [_score_row("PGS000018", "Coronary artery disease"), _score_row("PGS002237", "Höhe ünïcode")]
TRAITS = [_trait_row("Height"), _trait_row("Type 2 diabetes")]


@pytest.mark.parametrize(
    "view_mode,selected,expected_row,expected_subject",
    [
        ("individual", "PGS002237", SCORES[1], "PGS002237 (Höhe ünïcode)"),
        ("individual", "", SCORES[0], "PGS000018 (Coronary artery disease)"),
        ("individual", "PGS999999", SCORES[0], "PGS000018 (Coronary artery disease)"),
        ("grouped", "Type 2 diabetes", TRAITS[1], "Type 2 diabetes"),
        ("grouped", "", TRAITS[0], "Height"),
    ],
)
def test_the_question_is_prs_uis_own_prompt_for_the_selected_row(
    view_mode: str, selected: str, expected_row: dict[str, Any], expected_subject: str
) -> None:
    request = _prs_local_explain_request(view_mode, selected, SCORES, TRAITS)
    assert request == LocalExplainRequest(subject=expected_subject, prompt=_full_prompt(expected_row))
    # The whole prompt, longer than what any prefilled-URL button carries.
    url_prompts = [link["url"] for link in json.loads(expected_row["ai_ask"]) if link["url"]]
    assert all(len(request.prompt) >= len(u.split("=", 1)[1]) / 3 for u in url_prompts)


@pytest.mark.parametrize(
    "scores,traits",
    [([], []), ([{"pgs_id": "PGS000001"}], []), ([{"pgs_id": "PGS000001", "ai_ask": "not json"}], [])],
)
def test_no_rows_or_no_prompt_means_nothing_to_explain(scores: list[dict], traits: list[dict]) -> None:
    assert _prs_local_explain_request("individual", "", scores, traits) is None


# --------------------------------------------------------------------------- the streamed answer


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _updates(config: LocalLlmConfig, prompt: str) -> list[ExplanationUpdate]:
    return [update async for update in stream_explanation(config, prompt, push_interval_s=0)]


@pytest.mark.anyio
async def test_the_answer_accumulates_and_ends_done(upstream: FakeUpstream, env: pytest.MonkeyPatch) -> None:
    prompt = _full_prompt(SCORES[0])
    updates = await _updates(LocalLlmConfig(base_url=upstream.base_url, model="fake-large"), prompt)

    expected = FakeUpstream.answer_for("fake-large", prompt)
    assert updates[-1] == ExplanationUpdate(expected, model="fake-large", done=True)
    texts = [u.text for u in updates]
    assert all(expected.startswith(t) for t in texts)
    assert texts == sorted(texts, key=len)  # only ever grows
    assert [u.done for u in updates].count(True) == 1
    assert upstream.received[-1]["messages"] == [{"role": "user", "content": prompt}]


@pytest.mark.anyio
async def test_a_dead_server_is_one_error_naming_it(env: pytest.MonkeyPatch) -> None:
    dead = f"http://127.0.0.1:{free_port()}/v1"
    updates = await _updates(LocalLlmConfig(base_url=dead, model="m"), "Explain PGS000018")
    assert len(updates) == 1 and updates[0].done and updates[0].text == ""
    assert dead in updates[0].error and "Could not connect" in updates[0].error


@pytest.mark.anyio
async def test_an_overlong_question_is_refused_before_anything_is_sent(
    upstream: FakeUpstream, env: pytest.MonkeyPatch
) -> None:
    before = len(upstream.received)
    updates = await _updates(LocalLlmConfig(base_url=upstream.base_url), "x" * (MAX_PROMPT_CHARS + 1))
    assert len(updates) == 1 and str(MAX_PROMPT_CHARS) in updates[0].error
    assert len(upstream.received) == before


@pytest.mark.anyio
async def test_an_answer_cut_off_halfway_ends_with_the_reason(
    upstream: FakeUpstream, env: pytest.MonkeyPatch
) -> None:
    env.setattr(upstream, "breaks", {"fake-small"})
    updates = await _updates(LocalLlmConfig(base_url=upstream.base_url, model="fake-small"), "Explain PGS1")
    assert updates[-1].done and updates[-1].error == ""
    assert "[The answer stopped: " in updates[-1].text and upstream.base_url in updates[-1].text


# --------------------------------------------------------------------------- the state


def _state_with_results(env: pytest.MonkeyPatch, base_url: str = "") -> PRSState:
    if base_url:
        env.setenv(local_llm.BASE_URL_ENV, base_url)
        env.setenv(local_llm.MODEL_ENV, "fake-small")
    state = PRSState()
    state.prs_view_mode = "individual"
    state.prs_results_rows = list(SCORES)
    state.selected_result_id = "PGS002237"
    return state


def test_starting_marks_busy_and_names_the_subject(env: pytest.MonkeyPatch, upstream: FakeUpstream) -> None:
    state = _state_with_results(env, upstream.base_url)
    state.local_explain_text = "an older answer"

    config, request, token = state._begin_local_explanation()

    assert config.base_url == upstream.base_url and config.model == "fake-small"
    assert request.prompt == _full_prompt(SCORES[1])
    assert state.local_explain_busy and state.local_explain_subject == "PGS002237 (Höhe ünïcode)"
    assert state.local_explain_text == "" and state.local_explain_token == token
    assert state._begin_local_explanation() is None  # one answer at a time


def test_an_update_for_an_old_question_is_dropped(env: pytest.MonkeyPatch, upstream: FakeUpstream) -> None:
    state = _state_with_results(env, upstream.base_url)
    _config, _request, token = state._begin_local_explanation()

    assert state._apply_explanation_update(token, ExplanationUpdate("Your score", model="fake-small"))
    assert state.local_explain_text == "Your score" and state.local_explain_busy

    state.clear_local_explanation()  # the reader cleared it, or switched genome
    assert not state._apply_explanation_update(token, ExplanationUpdate("Your score is high", done=True))
    assert state.local_explain_text == "" and not state.local_explain_busy


def test_switching_genome_clears_the_answer(env: pytest.MonkeyPatch, upstream: FakeUpstream) -> None:
    state = _state_with_results(env, upstream.base_url)
    _config, _request, token = state._begin_local_explanation()
    state._apply_explanation_update(token, ExplanationUpdate("about the old genome", done=True))

    state._clear_prs_sample_state()

    assert (state.local_explain_text, state.local_explain_subject, state.local_explain_busy) == ("", "", False)
    assert state.local_explain_token > token


@pytest.mark.parametrize("immutable,configured", [("true", True), ("false", False)])
def test_no_model_or_the_public_demo_offers_nothing(
    env: pytest.MonkeyPatch, upstream: FakeUpstream, immutable: str, configured: bool
) -> None:
    env.setenv("JUST_DNA_IMMUTABLE_MODE", immutable)
    state = _state_with_results(env, upstream.base_url if configured else "")
    state.refresh_local_explain()
    assert state.local_explain_ready is False
    assert state._begin_local_explanation() is None
    assert state.local_explain_busy is False


def test_nothing_to_explain_says_so(env: pytest.MonkeyPatch, upstream: FakeUpstream) -> None:
    state = _state_with_results(env, upstream.base_url)
    state.prs_results_rows = []
    assert state._begin_local_explanation() is None
    assert state.local_explain_error == "There is no result to explain yet."


def test_the_prs_tab_carries_the_panel_which_rereads_the_settings_on_mount() -> None:
    rendered = str(_prs_tab_content().render())
    assert "explain_with_local_model" in rendered
    assert "local_explain_ready" in rendered
    panel = local_explain_panel(PRSState, PRSState.local_explain_target, "the question")
    assert "refresh_local_explain" in str(panel.event_triggers["on_mount"])
