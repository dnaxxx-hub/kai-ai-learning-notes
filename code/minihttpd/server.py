"""HTTP 服务器核心"""
import socket
import threading
import os
from urllib.parse import unquote_plus

from response import Response, html_response, file_response, error_response
from router import Router


class Request:
    """HTTP 请求"""
    def __init__(self, method: str, path: str, headers: dict, body: bytes,
                 params: dict = None, query: dict = None):
        self.method = method
        self.path = path
        self.headers = headers
        self.body = body
        self.params = params or {}
        self.query = query or {}


class HTTPServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080,
                 static_dir: str = None, workers: int = 4):
        self.host = host
        self.port = port
        self.static_dir = static_dir
        self.workers = workers
        self.router = Router()
        self._setup_defaults()

    def _setup_defaults(self):
        """设置默认路由"""
        @self.router.get("/")
        def index(request):
            return html_response("<h1>MiniHTTPd</h1><p>Your lightweight HTTP server is running!</p>")

        @self.router.get("/health")
        def health(request):
            from response import json_response
            return json_response({"status": "ok", "server": "MiniHTTPd/1.0"})

    def parse_request(self, data: bytes) -> Request | None:
        """解析原始 HTTP 请求"""
        try:
            # 分割头部和 body
            header_end = data.find(b"\r\n\r\n")
            if header_end == -1:
                return None

            header_part = data[:header_end].decode("utf-8", errors="replace")
            body = data[header_end + 4:]

            lines = header_part.split("\r\n")
            if not lines:
                return None

            # 请求行: GET /path HTTP/1.1
            request_line = lines[0].split()
            if len(request_line) < 2:
                return None

            method = request_line[0].upper()
            full_path = request_line[1]

            # 解析 headers
            headers = {}
            for line in lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            # 解析 query string
            query = {}
            if "?" in full_path:
                path_part, query_str = full_path.split("?", 1)
                for pair in query_str.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        query[unquote_plus(k)] = unquote_plus(v)
            else:
                path_part = full_path

            return Request(method, path_part, headers, body, query=query)

        except Exception:
            return None

    def handle_request(self, request: Request) -> Response:
        """处理请求"""
        if request.method not in ("GET", "POST", "PUT", "DELETE", "HEAD"):
            return error_response(405)

        # 路由匹配
        handler, params = self.router.resolve(request.method, request.path)
        if handler:
            request.params = params
            try:
                result = handler(request)
                if isinstance(result, Response):
                    return result
                return html_response(str(result))
            except Exception as e:
                return error_response(500, str(e))

        # 静态文件
        if request.method == "GET" and self.static_dir:
            filepath = os.path.join(self.static_dir, request.path.lstrip("/"))
            return file_response(filepath)

        return error_response(404)

    def handle_connection(self, client_socket: socket.socket):
        """处理单个连接"""
        try:
            client_socket.settimeout(5)
            data = client_socket.recv(8192)
            if not data:
                return

            request = self.parse_request(data)
            if not request:
                response = error_response(400, "Malformed request")
            else:
                response = self.handle_request(request)

            client_socket.sendall(response.to_bytes())

        except socket.timeout:
            pass
        except Exception as e:
            try:
                client_socket.sendall(error_response(500, str(e)).to_bytes())
            except Exception:
                pass
        finally:
            try:
                client_socket.close()
            except Exception:
                pass

    def start(self):
        """启动服务器"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(128)

        print(f"🚀 MiniHTTPd running on http://{self.host}:{self.port}")
        print(f"   Workers: {self.workers}")
        if self.static_dir:
            print(f"   Static:  {os.path.abspath(self.static_dir)}")

        def worker():
            while True:
                try:
                    client, addr = server.accept()
                    self.handle_connection(client)
                except Exception:
                    break

        threads = []
        for _ in range(self.workers):
            t = threading.Thread(target=worker, daemon=True)
            t.start()
            threads.append(t)

        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
        finally:
            server.close()
