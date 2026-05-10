from pathlib import Path

from dotenv import load_dotenv

# Load backend-local environment first (web/backend/.env),
# then allow project-root .env as fallback.
_here = Path(__file__).resolve().parent
load_dotenv(_here / ".env", override=False)
load_dotenv(_here.parent.parent / ".env", override=False)

from .app import app
