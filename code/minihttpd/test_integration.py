"""Full integration test - runs server and tests all endpoints via raw sockets"""
import socket, time
import threading
import json

from main import create_app

# Start server
svr = create_app()
t = threading.Thread(target=svr.start, daemon=True)
t.start()
time.sleep(1)

# Verify server is up
for _ in range(3):
    try:
        s = socket.socket()
        s.settimeout(2)
        s.connect(("127.0.0.1", 9090))
        s.close()
        break
    except:
        time.sleep(1)
else:
    print("FAIL: Server did not start")
    exit(1)


def http(method, path, body=None):
    """Send HTTP request and return (status, body_bytes)"""
    s = socket.socket()
    s.settimeout(3)
    s.connect(("127.0.0.1", 9090))
    if body:
        req = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n\r\n"
        )
        data = req.encode() + body
    else:
        req = (
            f"{method} {path} HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Connection: close\r\n\r\n"
        )
        data = req.encode()
    s.sendall(data)
    resp = b""
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            resp += chunk
    except:
        pass
    s.close()
    status = int(resp.split(b" ")[1])
    header_end = resp.find(b"\r\n\r\n")
    body_bytes = resp[header_end + 4:] if header_end >= 0 else b""
    return status, body_bytes


failed = 0
def check(name, status, body, expected_status=200, contains=None):
    global failed
    if status != expected_status:
        print(f"FAIL: {name} -> status {status} (expected {expected_status})")
        failed += 1
        return
    if contains and contains not in body:
        print(f"FAIL: {name} -> body missing: {contains}")
        print(f"  Got: {body[:80]}")
        failed += 1
        return
    print(f"  OK: {name}")


print("=== MiniHTTPd Integration Tests ===\n")

# 1. Root
check("GET /", *http("GET", "/"), contains=b"MiniHTTPd")

# 2. Health
check("GET /health", *http("GET", "/health"))
s, b = http("GET", "/health")
data = json.loads(b)
assert data["status"] == "ok"
print("  OK: /health JSON verified")

# 3. Hello with parameter
check("GET /hello/Kai", *http("GET", "/hello/Kai"), contains=b"Kai")

# 4. API time
check("GET /api/time", *http("GET", "/api/time"))
s, b = http("GET", "/api/time")
data = json.loads(b)
assert "timestamp" in data
assert "iso" in data
print("  OK: /api/time JSON verified")

# 5. Echo with query
check("GET /api/echo?name=test", *http("GET", "/api/echo?name=test"))
s, b = http("GET", "/api/echo?name=mini&v=1")
data = json.loads(b)
assert data["query"]["name"] == "mini"
assert data["query"]["v"] == "1"
print("  OK: /api/echo query params verified")

# 6. Multi-param route
check("GET /users/42/posts/7", *http("GET", "/users/42/posts/7"),
      contains=b"User 42 - Post 7")

# 7. POST JSON
status, body = http("POST", "/api/data", b'{"msg":"hello"}')
assert status == 200, f"POST /api/data status: {status}"
data = json.loads(body)
assert data["received"]["msg"] == "hello"
print(f"  OK: POST /api/data JSON verified (size={data['size']})")

# 8. Static HTML
check("GET /index.html", *http("GET", "/index.html"), contains=b"MiniHTTPd")

# 9. Static CSS
check("GET /style.css", *http("GET", "/style.css"), contains=b"background")

# 10. 404
check("GET /nonexistent", *http("GET", "/nonexistent"), expected_status=404)

# 11. POST with invalid JSON -> 400
status, body = http("POST", "/api/data", b"not json")
assert status == 400, f"POST /api/data bad json status: {status}"
print("  OK: POST /api/data invalid JSON -> 400")

# 12. Method not allowed (HEAD by default falls through)
check("GET /notaroute", *http("GET", "/notaroute"), expected_status=404)

print()
if failed == 0:
    print("All 12 integration tests PASSED!")
else:
    print(f"{failed} tests FAILED!")
    exit(1)
