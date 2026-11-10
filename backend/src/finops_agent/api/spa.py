"""Serve application routes without masking missing API endpoints or assets."""

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code == 404
                and scope["method"] in {"GET", "HEAD"}
                and path.startswith("clients/")
                and "." not in path
            ):
                return await super().get_response("index.html", scope)
            raise
