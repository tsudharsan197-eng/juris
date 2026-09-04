from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse

from .document_security_service import PRIVATE_RESPONSE_HEADERS


class UploadBodyLimitMiddleware:
    """Bound multipart bytes before they can exhaust parser spool storage."""

    def __init__(self, app, *, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or scope["path"].rstrip("/") != "/api/documents/upload"
        ):
            await self.app(scope, receive, send)
            return

        detail = "Upload request is too large. The file limit is 25 MB."
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
                if size < 0:
                    raise ValueError()
            except ValueError:
                await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400, headers=PRIVATE_RESPONSE_HEADERS)(scope, receive, send)
                return
            if size > self.max_bytes:
                await JSONResponse({"detail": detail}, status_code=413, headers=PRIVATE_RESPONSE_HEADERS)(scope, receive, send)
                return

        received = 0
        exceeded = False

        async def limited_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    exceeded = True
                    # This exception tells Starlette's multipart parser to close
                    # all partial temporary files before returning its error.
                    raise MultiPartException(detail)
            return message

        async def limited_send(message):
            if exceeded and message["type"] == "http.response.start":
                message = {**message, "status": 413}
            await send(message)

        await self.app(scope, limited_receive, limited_send)
