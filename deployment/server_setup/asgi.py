"""Same-origin Operation frontend/API, for loopback behind an authenticated gateway."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / '.env', override=True)

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

from apps.api.app.main import app


class Frontend(StaticFiles):
    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            normalized = path.replace('\\', '/').lstrip('/')
            if exc.status_code != 404 or normalized.startswith(('api/', 'health', 'assets/')):
                raise
            return await super().get_response('index.html', scope)


app.mount('/', Frontend(directory=Path(__file__).resolve().parents[2] / 'apps/web/dist', html=True), name='frontend')
