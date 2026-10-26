"""FastAPI ASGI entry point."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .schemas import JokeResponse, SummaryRequest, SummaryResponse, WeatherResponse
from .services import (
    CityNotFoundError,
    JokeService,
    SummaryService,
    UpstreamServiceError,
    WeatherService,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Create one shared outbound HTTP client and close it during shutdown."""
    settings = get_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.external_timeout_seconds),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        follow_redirects=False,
        headers={"User-Agent": settings.user_agent},
    )
    application.state.http_client = client
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(
    title="Weather, Joke, and Summary Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(CityNotFoundError)
async def city_not_found_handler(
    _request: Request, _exc: CityNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "City not found"},
    )


@app.exception_handler(UpstreamServiceError)
async def upstream_service_error_handler(
    _request: Request, exc: UpstreamServiceError
) -> JSONResponse:
    logger.warning("Upstream dependency failed: %s", exc.service)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "An upstream service is unavailable. Please try again later."},
    )


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


def get_weather_service(
    settings: Settings = Depends(get_settings),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> WeatherService:
    return WeatherService(settings, client)


def get_joke_service(
    settings: Settings = Depends(get_settings),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> JokeService:
    return JokeService(settings, client)


def get_summary_service(
    settings: Settings = Depends(get_settings),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> SummaryService:
    return SummaryService(settings, client)


async def require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Require a configured client API key without leaking comparison details."""
    expected_key = settings.service_api_key.get_secret_value()
    is_valid = False

    if expected_key and x_api_key:
        try:
            is_valid = secrets.compare_digest(
                x_api_key.encode("utf-8"), expected_key.encode("utf-8")
            )
        except UnicodeError:
            is_valid = False

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )


@app.get("/weather", response_model=WeatherResponse, tags=["weather"])
async def get_weather(
    city: str = Query(..., min_length=1, max_length=100),
    weather_service: WeatherService = Depends(get_weather_service),
) -> WeatherResponse:
    normalized_city = city.strip()
    if not normalized_city:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="city must not be blank",
        )
    return await weather_service.get_weather(normalized_city)


@app.get("/joke", response_model=JokeResponse, tags=["joke"])
async def get_joke(
    joke_service: JokeService = Depends(get_joke_service),
) -> JokeResponse:
    return await joke_service.get_joke()


@app.post(
    "/summary",
    response_model=SummaryResponse,
    tags=["summary"],
    dependencies=[Depends(require_api_key)],
)
async def create_summary(
    request_body: SummaryRequest,
    settings: Settings = Depends(get_settings),
    summary_service: SummaryService = Depends(get_summary_service),
) -> SummaryResponse:
    cleaned_text = request_body.text.strip()
    if not cleaned_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text must not be blank",
        )

    if len(request_body.text) > settings.max_summary_text_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "text exceeds the maximum length of "
                f"{settings.max_summary_text_length} characters"
            ),
        )

    return await summary_service.summarize(cleaned_text)


@app.get("/health", include_in_schema=False)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
