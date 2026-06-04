import socket
import json


def connect(host='127.0.0.1', port=8700):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    return sock


def send_cmd(sock, cmd, data=None):
    line = cmd
    if data:
        line += ' ' + json.dumps(data)
    sock.sendall((line + '\n').encode())
    resp = b''
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        resp += chunk
        if b'\n' in chunk:
            break
    line, _, _ = resp.partition(b'\n')
    return json.loads(line.decode().strip())


def submit(name, args=None, kwargs=None, priority=0, schedule_time=None):
    sock = connect()
    try:
        data = {'name': name, 'args': args or [],
                'kwargs': kwargs or {}, 'priority': priority,
                'schedule_time': schedule_time}
        return send_cmd(sock, 'SUBMIT', data)
    finally:
        sock.close()


def result(task_id):
    sock = connect()
    try:
        return send_cmd(sock, 'RESULT', {'task_id': task_id})
    finally:
        sock.close()


def recent(status=None):
    sock = connect()
    try:
        return send_cmd(sock, 'RECENT', {'status': status} if status else {})
    finally:
        sock.close()


def queue_size():
    sock = connect()
    try:
        return send_cmd(sock, 'QUEUE_SIZE')
    finally:
        sock.close()


def workers():
    sock = connect()
    try:
        return send_cmd(sock, 'WORKERS')
    finally:
        sock.close()


def schedule(name, task_name, args=None, kwargs=None, interval=60):
    sock = connect()
    try:
        data = {'name': name, 'task_name': task_name,
                'args': args or [], 'kwargs': kwargs or {},
                'interval': interval}
        return send_cmd(sock, 'SCHEDULE', data)
    finally:
        sock.close()
