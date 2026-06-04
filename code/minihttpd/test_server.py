"""MiniHTTPd 测试"""
import unittest
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from response import Response, html_response, json_response, error_response, file_response
from router import Router
from server import HTTPServer, Request
import tempfile
import socket as _socket


class TestResponse(unittest.TestCase):
    def test_ok_response(self):
        r = html_response("<h1>OK</h1>")
        data = r.to_bytes()
        self.assertIn(b"200 OK", data)
        self.assertIn(b"<h1>OK</h1>", data)

    def test_json_response(self):
        r = json_response({"key": "value"})
        data = r.to_bytes()
        self.assertIn(b"application/json", data)
        self.assertIn(b'"key"', data)

    def test_404_response(self):
        r = error_response(404, "Not found")
        data = r.to_bytes()
        self.assertIn(b"404 Not Found", data)
        self.assertIn(b"Not found", data)

    def test_file_response(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write("<h1>test</h1>")
            f.flush()
            fname = f.name
        r = file_response(fname)
        data = r.to_bytes()
        self.assertIn(b"<h1>test</h1>", data)
        os.unlink(fname)

    def test_content_length(self):
        r = html_response("hello")
        data = r.to_bytes()
        lines = data.decode().split("\r\n")
        cl_line = [l for l in lines if l.startswith("Content-Length")]
        self.assertTrue(cl_line)
        self.assertEqual(cl_line[0], "Content-Length: 5")


class TestRouter(unittest.TestCase):
    def setUp(self):
        self.router = Router()

        @self.router.get("/users/:id")
        def get_user(req):
            return json_response({"id": req.params["id"]})

    def test_simple_route(self):
        handler, params = self.router.resolve("GET", "/users/42")
        self.assertIsNotNone(handler)
        self.assertEqual(params["id"], "42")

    def test_no_match(self):
        handler, params = self.router.resolve("GET", "/nonexistent")
        self.assertIsNone(handler)

    def test_wrong_method(self):
        handler, params = self.router.resolve("POST", "/users/42")
        self.assertIsNone(handler)


class TestServer(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(static_dir="static")

    def test_parse_get(self):
        data = b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = self.server.parse_request(data)
        self.assertIsNotNone(req)
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.path, "/health")

    def test_parse_post(self):
        body = b'{"key":"value"}'
        data = b"POST /api/data HTTP/1.1\r\nContent-Type: application/json\r\nContent-Length: 15\r\n\r\n" + body
        req = self.server.parse_request(data)
        self.assertIsNotNone(req)
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.path, "/api/data")
        self.assertEqual(req.body, body)

    def test_parse_query(self):
        data = b"GET /api/echo?name=test&count=3 HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = self.server.parse_request(data)
        self.assertIsNotNone(req)
        self.assertEqual(req.query["name"], "test")
        self.assertEqual(req.query["count"], "3")

    def test_health_endpoint(self):
        data = b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = self.server.parse_request(data)
        self.assertIsNotNone(req)
        resp = self.server.handle_request(req)
        data = resp.to_bytes()
        self.assertIn(b'"status"', data)
        self.assertIn(b'"ok"', data)

    def test_404(self):
        data = b"GET /nonexistent HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = self.server.parse_request(data)
        self.assertIsNotNone(req)
        resp = self.server.handle_request(req)
        data = resp.to_bytes()
        self.assertIn(b"404", data)

    def test_static_file(self):
        os.makedirs("static", exist_ok=True)
        test_path = os.path.join("static", "_test.txt")
        with open(test_path, "w") as f:
            f.write("test content")

        data = b"GET /_test.txt HTTP/1.1\r\nHost: localhost\r\n\r\n"
        req = self.server.parse_request(data)
        self.assertIsNotNone(req)
        resp = self.server.handle_request(req)
        data = resp.to_bytes()
        self.assertIn(b"test content", data)

        os.remove(test_path)

    def test_routed_param(self):
        """Test route with URL parameter"""
        from main import create_app
        app = create_app()
        req = Request("GET", "/hello/World", {}, b"")
        resp = app.handle_request(req)
        data = resp.to_bytes()
        self.assertIn(b"Hello, World!", data)

    def test_internal_routes(self):
        """Test all routes defined in create_app()"""
        from main import create_app
        app = create_app()

        # Test /hello/:name
        req = Request("GET", "/hello/Test", {}, b"")
        resp = app.handle_request(req)
        self.assertIn(b"Test", resp.to_bytes())

        # Test /api/time
        req = Request("GET", "/api/time", {}, b"")
        resp = app.handle_request(req)
        data = json.loads(resp.body)
        self.assertIn("timestamp", data)
        self.assertIn("iso", data)

        # Test /api/echo
        req = Request("GET", "/api/echo", {}, b"", query={"foo": "bar"})
        resp = app.handle_request(req)
        data = json.loads(resp.body)
        self.assertEqual(data["query"]["foo"], "bar")

        # Test /api/data POST
        req = Request("POST", "/api/data", {}, b'{"msg":"hi"}')
        resp = app.handle_request(req)
        data = json.loads(resp.body)
        self.assertEqual(data["received"]["msg"], "hi")

        # Test /users/:id/posts/:post_id
        req = Request("GET", "/users/42/posts/7", {}, b"")
        resp = app.handle_request(req)
        self.assertIn(b"User 42 - Post 7", resp.to_bytes())


if __name__ == '__main__':
    unittest.main()
