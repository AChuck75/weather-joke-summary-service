import asyncio
import json

import httpx

from app.config import Settings
from app.services import SummaryService, UpstreamServiceError


def test_summary_uses_anthropic_messages_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.anthropic.test/v1/messages"
        assert request.headers["x-api-key"] == "test-anthropic-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["system"].startswith("Summarize the user's text")
        assert payload["messages"] == [
            {"role": "user", "content": "A source paragraph."}
        ]
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "text", "text": " A concise "},
                    {"type": "text", "text": "summary. "},
                ]
            },
            request=request,
        )

    async def run() -> str:
        settings = Settings(
            anthropic_api_key="test-anthropic-key",
            anthropic_messages_url="https://api.anthropic.test/v1/messages",
            anthropic_model="test-model",
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await SummaryService(settings, client).summarize(
                "A source paragraph."
            )
            return result.summary

    assert asyncio.run(run()) == "A concise summary."


def test_summary_rejects_malformed_anthropic_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": []}, request=request)

    async def run() -> None:
        settings = Settings(anthropic_api_key="test-anthropic-key")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await SummaryService(settings, client).summarize("A source paragraph.")

    try:
        asyncio.run(run())
    except UpstreamServiceError as exc:
        assert exc.service == "summary"
    else:
        raise AssertionError("Expected malformed provider response to be rejected")
