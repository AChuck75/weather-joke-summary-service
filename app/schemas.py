"""Pydantic models used by the HTTP API."""

from pydantic import BaseModel, Field


class WeatherResponse(BaseModel):
    city: str
    temperature: float
    condition: str
    humidity: int = Field(ge=0, le=100)


class JokeResponse(BaseModel):
    joke: str
    category: str


class SummaryRequest(BaseModel):
    text: str


class SummaryResponse(BaseModel):
    summary: str
