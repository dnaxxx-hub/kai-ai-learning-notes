#!/usr/bin/env python3
"""MiniHTTPd 示例应用"""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from server import HTTPServer
from response import html_response, json_response


def create_app():
    server = HTTPServer(host="0.0.0.0", port=9090, static_dir="static", workers=8)

    @server.router.get("/hello/:name")
    def hello(request):
        name = request.params.get("name", "World")
        return html_response(f"<h1>Hello, {name}!</h1>")

    @server.router.get("/api/time")
    def api_time(request):
        import time
        return json_response({
            "timestamp": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })

    @server.router.get("/api/echo")
    def api_echo(request):
        return json_response({
            "method": request.method,
            "path": request.path,
            "query": request.query,
            "headers": dict(request.headers),
        })

    @server.router.post("/api/data")
    def api_data(request):
        import json
        try:
            data = json.loads(request.body)
            return json_response({"received": data, "size": len(request.body)})
        except Exception:
            from response import error_response
            return error_response(400, "Invalid JSON")

    @server.router.get("/users/:id/posts/:post_id")
    def user_post(request):
        return html_response(
            f"<h1>User {request.params['id']} - Post {request.params['post_id']}</h1>"
        )

    return server


def main():
    server = create_app()

    print("📋 Routes:")
    for route in server.router.routes:
        print(f"   {route.method:6} {route.pattern}")
    print()

    server.start()


if __name__ == "__main__":
    main()
