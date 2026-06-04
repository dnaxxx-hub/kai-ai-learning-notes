"""HTTP 响应构造"""
import json
import os
import time
import mimetypes


class Response:
    def __init__(self, body: bytes = b"", status: int = 200,
                 content_type: str = "text/html; charset=utf-8",
                 headers: dict = None):
        self.status = status
        self.body = body
        self.content_type = content_type
        self.headers = headers or {}

    STATUS_TEXTS = {
        200: "OK", 201: "Created", 204: "No Content",
        301: "Moved Permanently", 302: "Found",
        304: "Not Modified",
        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
        404: "Not Found", 405: "Method Not Allowed",
        500: "Internal Server Error", 502: "Bad Gateway",
    }

    def to_bytes(self) -> bytes:
        """构造 HTTP 响应字节流"""
        status_text = self.STATUS_TEXTS.get(self.status, "Unknown")
        lines = [f"HTTP/1.1 {self.status} {status_text}"]
        lines.append(f"Content-Type: {self.content_type}")
        lines.append(f"Content-Length: {len(self.body)}")
        lines.append(f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())}")
        lines.append("Server: MiniHTTPd/1.0")
        lines.append("Connection: close")

        for k, v in self.headers.items():
            lines.append(f"{k}: {v}")

        lines.append("")
        lines.append("")
        return "\r\n".join(lines).encode() + self.body


def html_response(body: str, status: int = 200) -> Response:
    return Response(body.encode(), status)


def json_response(data: dict, status: int = 200) -> Response:
    return Response(
        json.dumps(data, ensure_ascii=False).encode(),
        status,
        content_type="application/json"
    )


def text_response(text: str, status: int = 200) -> Response:
    return Response(text.encode(), status, content_type="text/plain")


def file_response(filepath: str) -> Response:
    """读取文件并返回"""
    import os.path

    if not os.path.isfile(filepath):
        return html_response(f"<h1>404 Not Found</h1><p>{filepath}</p>", 404)

    # 检查路径安全
    if ".." in filepath:
        return html_response("<h1>403 Forbidden</h1>", 403)

    with open(filepath, 'rb') as f:
        body = f.read()

    content_type, _ = mimetypes.guess_type(filepath)
    if not content_type:
        content_type = "application/octet-stream"

    return Response(body, content_type=content_type)


def error_response(status: int, message: str = "") -> Response:
    status_text = Response.STATUS_TEXTS.get(status, "Error")
    body = f"""<!DOCTYPE html>
<html>
<head><title>{status} {status_text}</title></head>
<body style="font-family:sans-serif;padding:2em;background:#1a1a2e;color:#eee">
<h1>{status}</h1>
<p>{status_text}</p>
<p style="color:#888">{message}</p>
<hr><small>MiniHTTPd/1.0</small>
</body>
</html>"""
    return Response(body.encode(), status)
