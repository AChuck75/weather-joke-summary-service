# Weather, Joke, and Summary Service

A small FastAPI microservice with three independent endpoints:

- `GET /weather?city=...` obtains current weather from OpenWeatherMap.
- `GET /joke` obtains one safe, single-part joke from JokeAPI.
- `POST /summary` authenticates a caller and sends text to an LLM for summarization.

The ASGI application is `app.main:app`.

## Summary provider and behavior

The summary endpoint uses the **Anthropic Messages API**. Its default model is **`claude-sonnet-4-5-20250929`**. The service sends the input text as a user message and uses a system prompt that asks for:

- plain-language wording;
- at most three short bullet points, or one short paragraph when bullets are awkward;
- no more than **120 words** by default;
- preservation of important facts and uncertainty without inventing details.

`SUMMARY_MAX_WORDS` changes the word limit, and the service enforces that limit after it receives the model response. `SUMMARY_MAX_TOKENS` is an additional output cap sent to Anthropic. Text supplied to `/summary` is limited to **5,000 characters** by default through `MAX_SUMMARY_TEXT_LENGTH`.

## Project layout

```text
app/
  main.py       # ASGI app, routes, dependency wiring, and error handlers
  config.py     # Environment-backed settings
  schemas.py    # Request and response models
  services.py   # OpenWeatherMap, JokeAPI, and Anthropic clients
tests/
  test_main.py  # Endpoint behavior tests
.env.example
requirements.txt
```

## Setup

Use Python 3.11 or newer.

1. Create and activate a virtual environment.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example configuration and replace every placeholder value:

   ```bash
   cp .env.example .env
   ```

4. Obtain an OpenWeatherMap API key for `WEATHER_API_KEY` and an Anthropic API key for `ANTHROPIC_API_KEY`. Set `SERVICE_API_KEY` to a long random value that callers will use in the `X-API-Key` header.

The app reads environment variables directly and also reads `.env` when it is started from the project root. Environment variables take precedence over `.env` values.

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For local development, append `--reload`. Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## Example requests

```bash
curl --get http://127.0.0.1:8000/weather --data-urlencode 'city=London'

curl http://127.0.0.1:8000/joke

curl -X POST http://127.0.0.1:8000/summary \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: replace_with_your_service_key' \
  -d '{"text":"FastAPI is a Python framework for building APIs quickly."}'
```

Weather temperatures are returned in Celsius because the OpenWeatherMap request uses metric units. The `city` field is the provider's normalized city name when one is supplied.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SERVICE_API_KEY` | Yes for `/summary` | Empty | Client key accepted in `X-API-Key`. |
| `WEATHER_API_KEY` | Yes for `/weather` | Empty | OpenWeatherMap credential. |
| `ANTHROPIC_API_KEY` | Yes for `/summary` | Empty | Anthropic credential. |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-5-20250929` | Anthropic model used for summaries. |
| `WEATHER_BASE_URL` | No | OpenWeatherMap URL | Allows a controlled provider endpoint override. |
| `JOKE_API_URL` | No | JokeAPI URL | Allows a controlled provider endpoint override. |
| `ANTHROPIC_MESSAGES_URL` | No | Anthropic Messages API URL | Allows a controlled provider endpoint override. |
| `EXTERNAL_TIMEOUT_SECONDS` | No | `8` | Timeout for every external request; valid range is 1-60 seconds. |
| `MAX_SUMMARY_TEXT_LENGTH` | No | `5000` | Maximum input character count for `/summary`. |
| `SUMMARY_MAX_WORDS` | No | `120` | Maximum words retained in a summary. |
| `SUMMARY_MAX_TOKENS` | No | `180` | Anthropic completion token cap. |

Do not commit `.env`. Use a secret manager or deployment platform environment variables outside local development.

## Error behavior

- A weather-provider city miss returns `404` with `{"detail":"City not found"}`.
- Weather network failures, timeouts, unexpected provider responses, and non-city weather errors return `502`.
- JokeAPI and Anthropic failures also return a generic `502` response without exposing provider details.
- Missing or incorrect `X-API-Key` values return `401` from `/summary`.
- Blank text or text longer than `MAX_SUMMARY_TEXT_LENGTH` returns `400` from `/summary`.
- Invalid JSON or fields with the wrong JSON type are handled by FastAPI with its normal `422` validation response.

If a required provider credential is absent, the related external endpoint safely returns `502`; the health endpoint and unrelated endpoints remain available.

## Tests

The tests replace external services with small fakes, so they do not need real API keys or network access.

```bash
pytest -q
```

## Operational notes

The service uses one shared asynchronous HTTP client, connection limits, an eight-second default outbound timeout, and generic upstream error messages. In production, place it behind TLS, apply rate limiting and request-size limits at the edge, and inject secrets through your platform's secret-management system.