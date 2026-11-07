"""The access key check in front of the public MCP server. No stack needed."""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from bikelake.mcp_server import RequireAccessKey

app = RequireAccessKey(Starlette(routes=[Route("/mcp", lambda r: PlainTextResponse("ok"), methods=["POST"])]), "s3cret")
client = TestClient(app)


def test_rejects_missing_or_wrong_key():
    assert client.post("/mcp").status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/mcp", headers={"Authorization": "s3cret"}).status_code == 401


def test_allows_the_right_key():
    response = client.post("/mcp", headers={"Authorization": "Bearer s3cret"})
    assert response.status_code == 200
    assert response.text == "ok"
