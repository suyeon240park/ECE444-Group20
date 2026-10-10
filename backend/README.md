# Backend

Flask API for *What's in My Food?*. Python 3.10 or newer.

## Run locally

```
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux
pip install -r requirements-dev.txt
copy .env.example .env          # Windows;  cp .env.example .env  on macOS / Linux
flask --app wsgi run --debug
```

Then open http://127.0.0.1:5000/api/health. You should see `{"status": "ok", ...}`.

## Test and lint

```
pytest
ruff check .
ruff format --check .
```

CI runs the same three commands on every pull request. `pytest` also measures coverage of `app/` and fails below 80% (configured in `pyproject.toml`).

## Layout

```
backend/
├── app/
│   ├── __init__.py      create_app() factory; reads configuration from the environment
│   ├── models/          data models; product.py is the code form of docs/api/ (#20)
│   └── routes/          one blueprint module per API area (health.py today)
├── tests/               pytest tests, one file per route or model module
├── wsgi.py              entry point for `flask run` and gunicorn
├── requirements.txt     runtime dependencies
├── requirements-dev.txt runtime + test + lint dependencies
├── pyproject.toml       ruff and pytest configuration
└── .env.example         every environment variable the app reads, with safe defaults
```

## Product lookup (`GET /api/products/<barcode>`)

Looks a barcode up in [Open Food Facts](https://openfoodfacts.github.io/openfoodfacts-server/api/) (API v3) and returns it in the contract's shape ([docs/api/](../docs/api/README.md)). Try it: `curl localhost:5000/api/products/0013000006408`.

```
routes/products.py          the endpoint; maps errors to HTTP status codes
services/product_lookup.py  validate barcode -> cache -> Open Food Facts -> normalize
services/open_food_facts.py HTTP client; timeouts and bad responses become upstream errors
services/normalize.py       OFF record -> Product (blank/missing -> null, sodium g -> mg, one basis)
services/cache.py           in-memory TTL cache for found products
```

Open Food Facts allows 15 product reads per minute per IP and asks every client to send a `User-Agent` of the form `AppName/Version (contact)`. Found products are cached in memory for a day; failures and "not found" are not cached. Settings (all in `.env.example`): `OFF_BASE_URL`, `OFF_USER_AGENT`, `OFF_TIMEOUT_SECONDS`, `PRODUCT_CACHE_TTL_SECONDS`.

Tests use responses captured from the real API (`tests/fixtures/off/`, see its README) and never touch the network. Two opt-in tests call the real API: `pytest -m live --no-cov`.

## Adding a route

1. Create `app/routes/<area>.py` with a `Blueprint`.
2. Register it in `create_app()` under the `/api` prefix.
3. Add `tests/test_<area>.py`. Use `create_app({"TESTING": True})` and the Flask test client, as in `tests/test_health.py`.

## Database

PostgreSQL is planned for the product cache and the ingredient knowledge base; for now product lookups are cached in memory. A local instance is available with `docker compose up db` from the repository root; `DATABASE_URL` in `.env.example` already points at it. No code reads the database yet.

## Product data model

`app/models/product.py` implements the product contract in [`docs/api/`](../docs/api/README.md). Build product responses from these classes and serialize them with `to_dict()`; never assemble the JSON by hand. `tests/test_contract_examples.py` fails if the examples in `docs/api/openapi.yaml` and the model's output differ, so update both together.
