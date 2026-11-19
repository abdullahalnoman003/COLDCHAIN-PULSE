# Vercel entrypoint (serverless). Vercel serves the ASGI `app` object.
from app.main import app  # noqa: F401
