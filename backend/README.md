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

CI runs the same three commands on every pull request.

## Layout

```
backend/
├── app/
│   ├── __init__.py      create_app() factory; reads configuration from the environment
│   └── routes/          one blueprint module per API area (health.py today)
├── tests/               pytest tests, one file per route module
├── wsgi.py              entry point for `flask run` and gunicorn
├── requirements.txt     runtime dependencies
├── requirements-dev.txt runtime + test + lint dependencies
├── pyproject.toml       ruff and pytest configuration
└── .env.example         every environment variable the app reads, with safe defaults
```

## Adding a route

1. Create `app/routes/<area>.py` with a `Blueprint`.
2. Register it in `create_app()` under the `/api` prefix.
3. Add `tests/test_<area>.py`. Use `create_app({"TESTING": True})` and the Flask test client, as in `tests/test_health.py`.

## Database

PostgreSQL is planned for the product cache and the ingredient knowledge base (#14, #27). A local instance is available with `docker compose up db` from the repository root; `DATABASE_URL` in `.env.example` already points at it. No code reads the database yet.
