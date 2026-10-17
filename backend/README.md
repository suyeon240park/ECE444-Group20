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
│   ├── routes/          one blueprint module per API area (health.py, barcode.py, ...)
│   └── services/        logic the routes call (barcode.py: image validation and detection)
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

## Barcode detection (#13)

`POST /api/barcode` takes a product photo as `multipart/form-data` in the `image` field (JPEG, PNG or WebP, up to 10 MB) and returns the barcode in it. It does not look the product up; pass the result to `GET /api/products/{barcode}` (#14).

```
curl -F "image=@photo.jpg" http://127.0.0.1:5000/api/barcode
{"barcode": "5901234123457", "format": "EAN13"}
```

| Situation | HTTP | `error.code` |
|---|---|---|
| No file in the `image` field, or the request is not multipart | 400 | `missing_image` |
| Empty, corrupt or non-image file | 400 | `invalid_image` |
| Image is not JPEG, PNG or WebP | 415 | `unsupported_media_type` |
| Upload over the size limit | 413 | `file_too_large` |
| Image has too many pixels | 413 | `image_too_large` |
| Valid image, no readable EAN-8, UPC-A, EAN-13 or GTIN-14 barcode | 422 | `no_barcode_found` |

Detection uses `zxing-cpp`. A UPC-A is returned as its 12 printed digits with `format: "UPCA"`. These error codes are not in `docs/api/openapi.yaml` yet.

## Product analysis (#43)

`GET /api/analysis/<barcode>` and `POST /api/analysis/label-photo` return everything the results page shows in one response: the product, `next_step`, `package_nutrition` (#36), `explanations` (#37) and `ingredients` (#33). See [docs/api/analysis.md](../docs/api/analysis.md).

```bash
curl localhost:5000/api/analysis/0013000006408
curl -F "image=@label.jpg" -F "barcode=0013000006408" localhost:5000/api/analysis/label-photo
```

`app/services/analysis.py` computes each section on its own: one that fails is logged and returned as `null`, and the rest still arrive. The ingredient knowledge base is loaded at startup from `content/ingredients/`; if it is invalid, only the `ingredients` section is missing.

## Nutrition Facts photo (#42)

`POST /api/nutrition-label` takes a photo of a Nutrition Facts table as `multipart/form-data` in the `image` field and returns a `nutrition_only` product result ([docs/api/](../docs/api/README.md)). It needs `GEMINI_API_KEY` in `.env`; without it the endpoint answers 503 and the rest of the app still runs.

```bash
curl -F "image=@label.jpg" http://127.0.0.1:5000/api/nutrition-label
```

```
routes/nutrition_label.py      upload checks, error responses
services/label_reading.py      load_image (#13) -> shrink to 2000 px JPEG -> vision model (#16)
                               -> Serving / Package / Nutrition, every value "uncertain"
services/fallback_routing.py   build_nutrition_only (#15)
```

Every value comes back `uncertain` because the model gives no per-value confidence (Q1); the client asks the user to confirm values. Upload errors are the same as `/api/barcode` above, and a HEIC/HEIF photo is refused with 415 `unsupported_media_type` (the app converts iPhone photos to JPEG before upload). The others:

| Situation | HTTP | `error.code` |
|---|---|---|
| No Nutrition Facts table found, or too blurred | 422 | `nutrition_table_not_found` |
| Vision model and every fallback model failed or replied with something unusable | 502 | `upstream_unavailable` |
| `GEMINI_API_KEY` not set | 503 | `photo_reading_unavailable` |
| Vision model did not answer within `VISION_TIMEOUT_SECONDS` | 504 | `upstream_timeout` |

When `VISION_MODEL` fails (overloaded, rate limited, retired), the models in `VISION_FALLBACK_MODELS` are tried in order, with no 30 s rate-limit wait. A timeout is not retried on another model.

Tests replace the reader with a fake extractor, so CI makes no API calls.

## Database

PostgreSQL remains available for future persistence; product lookups are cached in memory. A local instance is available with `docker compose up db` from the repository root; `DATABASE_URL` in `.env.example` already points at it. No code reads the database yet. The ingredient knowledge base (#33) uses reviewed JSON files loaded into memory and does not require PostgreSQL.

## Ingredient knowledge base (#33)

The reusable ingredient service parses database ingredient text, matches reviewed
names/aliases/identifiers exactly, and returns deduplicated coverage, unknowns,
evidence, and flags. #43 will wire it into the analysis endpoint; #40 owns the UI.
The production collection starts empty; #34/#35 provide reviewed content.

Validate offline with `python -m scripts.validate_ingredients` from `backend/`.
See the [content authoring guide](content/ingredients/README.md) and
[service/API contract](../docs/api/ingredient-analysis.md). Deploy `content/` with
the backend code. There are no new environment variables or runtime dependencies.

## Product data model

`app/models/product.py` implements the product contract in [`docs/api/`](../docs/api/README.md). Build product responses from these classes and serialize them with `to_dict()`; never assemble the JSON by hand. `tests/test_contract_examples.py` fails if the examples in `docs/api/openapi.yaml` and the model's output differ, so update both together.
