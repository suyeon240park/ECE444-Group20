"""WSGI entry point: ``flask --app wsgi run`` in development, ``gunicorn wsgi:app`` in staging."""

from dotenv import load_dotenv

# Load backend/.env before the app factory reads the environment.
load_dotenv()

from app import create_app  # noqa: E402

app = create_app()
