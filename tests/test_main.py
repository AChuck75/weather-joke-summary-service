"""Endpoint tests using dependency overrides instead of live external APIs."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import (
    app,
    get_joke_service,
    get_settings,
    get_summary_service,
    get_weather_service,
)
from app.schemas import JokeResponse, SummaryResponse, WeatherResponse
from app.services import CityNotFoundError, UpstreamServiceError


@pytest.fixture
def configured_settings() -> Settings:
    return Settings(
        service_api_key="test-client-key",
        weather_api_key="test-weather-key",
        openai_api_key="test-openai-key",
        max_summary_text_length=20,
    )


@pytest.fixture
def client(configured_settings: Settings) -> Generator[TestClient, None, None]:
    app.dependency_overrides.clear()
    app.dependency_overrides[get_settings] = lambda: configured_settings
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_weather_returns_expected_json(client: TestClient) -> None:
    class WeatherOK:
        async def get_weather(self, city: str) -> WeatherResponse:
            return WeatherResponse(
                city=city.title(),
                temperature=18.5,
                condition="clear sky",
                humidity=62,
            )

    app.dependency_overrides[get_weather_service] = lambda: WeatherOK()

    response = client.get("/weather", params={"city": "london"})

    assert response.status_code == 200
    assert response.json() == {
        "city": "London",
        "temperature": 18.5,
        "condition": "clear sky",
        "humidity": 62,
    }


def test_weather_maps_missing_city_to_404(client: TestClient) -> None:
    class MissingWeather:
        async def get_weather(self, city: str) -> WeatherResponse:
            raise CityNotFoundError()

    app.dependency_overrides[get_weather_service] = lambda: MissingWeather()

    response = client.get("/weather", params={"city": "Atlantis"})

    assert response.status_code == 404
    assert response.json()["detail"] == "City not found"


def test_weather_maps_provider_failure_to_502(client: TestClient) -> None:
    class BrokenWeather:
        async def get_weather(self, city: str) -> WeatherResponse:
            raise UpstreamServiceError("weather")

    app.dependency_overrides[get_weather_service] = lambda: BrokenWeather()

    response = client.get("/weather", params={"city": "London"})

    assert response.status_code == 502


def test_joke_returns_expected_json(client: TestClient) -> None:
    class JokeOK:
        async def get_joke(self) -> JokeResponse:
            return JokeResponse(joke="Why did the byte cross the bus?", category="Programming")

    app.dependency_overrides[get_joke_service] = lambda: JokeOK()

    response = client.get("/joke")

    assert response.status_code == 200
    assert response.json() == {
        "joke": "Why did the byte cross the bus?",
        "category": "Programming",
    }


def test_summary_requires_a_valid_api_key(client: TestClient) -> None:
    class SummaryOK:
        def __init__(self) -> None:
            self.received_text: str | None = None

        async def summarize(self, text: str) -> SummaryResponse:
            self.received_text = text
            return SummaryResponse(summary="A concise summary.")

    fake_service = SummaryOK()
    app.dependency_overrides[get_summary_service] = lambda: fake_service

    missing_key = client.post("/summary", json={"text": "Short source."})
    invalid_key = client.post(
        "/summary",
        headers={"X-API-Key": "wrong-key"},
        json={"text": "Short source."},
    )

    assert missing_key.status_code == 401
    assert invalid_key.status_code == 401
    assert fake_service.received_text is None


def test_summary_rejects_blank_and_overlong_text(client: TestClient) -> None:
    class SummaryOK:
        async def summarize(self, text: str) -> SummaryResponse:
            return SummaryResponse(summary="A concise summary.")

    app.dependency_overrides[get_summary_service] = lambda: SummaryOK()
    headers = {"X-API-Key": "test-client-key"}

    blank = client.post("/summary", headers=headers, json={"text": "   "})
    overlong = client.post("/summary", headers=headers, json={"text": "x" * 21})

    assert blank.status_code == 400
    assert overlong.status_code == 400


def test_summary_returns_llm_result(client: TestClient) -> None:
    class SummaryOK:
        def __init__(self) -> None:
            self.received_text: str | None = None

        async def summarize(self, text: str) -> SummaryResponse:
            self.received_text = text
            return SummaryResponse(summary="The source is short.")

    fake_service = SummaryOK()
    app.dependency_overrides[get_summary_service] = lambda: fake_service

    response = client.post(
        "/summary",
        headers={"X-API-Key": "test-client-key"},
        json={"text": "Short source."},
    )

    assert response.status_code == 200
    assert response.json() == {"summary": "The source is short."}
    assert fake_service.received_text == "Short source."