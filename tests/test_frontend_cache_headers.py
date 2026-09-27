"""Every HTML shell is served no-store, whatever its path; hashed assets stay cacheable."""

import pytest
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from webui.app import _disable_stale_frontend_cache


def _html(request) -> HTMLResponse:
    return HTMLResponse("<!doctype html><title>shell</title>")


def _js(request) -> Response:
    return Response("export {}", media_type="text/javascript")


APP = _disable_stale_frontend_cache(
    Starlette(
        routes=[
            Route("/", _html),
            Route("/annotate/", _html),
            Route("/registry/", _html),
            Route("/utils/state.js", _js),
            Route("/assets/entry.client-ClazocZO.js", _js),
        ]
    )
)


@pytest.mark.parametrize("path", ["/", "/annotate/", "/registry/", "/utils/state.js"])
def test_shells_and_the_client_runtime_are_never_cached(path: str) -> None:
    response = TestClient(APP).get(path)
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"


def test_a_hashed_asset_keeps_its_caching() -> None:
    response = TestClient(APP).get("/assets/entry.client-ClazocZO.js")
    assert "cache-control" not in response.headers
