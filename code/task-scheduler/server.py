import socket
import selectors
import json
from task import Task, get_task_func, list_tasks
from queue import TaskQueue
from worker import Worker
from scheduler import Scheduler
from backend import ResultBackend


def encode(resp):
    return json.dumps(resp) + '\n'


def decode(line):
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].upper() if parts else ''
    args_str = parts[1] if len(parts) > 1 else ''
    try:
        args = json.loads(args_str) if args_str else {}
    except Exception:
        args = {}
    return cmd, args


class TaskSchedulerServer:
    def __init__(self, host='127.0.0.1', port=8700):
        self.host = host
        self.port = port
        self.task_queue = TaskQueue()
        self.backend = ResultBackend()
        self.worker = Worker('worker-1', concurrency=4)
        self.scheduler = Scheduler(self.task_queue)
        self.selector = selectors.DefaultSelector()
        self.buffers = {}
        self._running = False

    def start(self):
        self._running = True
        self.scheduler.start()
        self.worker.start(self.task_queue, self.backend)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(50)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)
        print(f"Task Scheduler on {self.host}:{self.port}")

        try:
            while self._running:
                events = self.selector.select(timeout=1)
                for key, mask in events:
                    key.data(key.fileobj, mask)
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup(sock)

    def stop(self):
        self._running = False
        self.worker.stop()
        self.scheduler.stop()

    def _cleanup(self, sock):
        self.worker.stop()
        self.scheduler.stop()
        try:
            self.selector.unregister(sock)
            sock.close()
        except Exception:
            pass
        print("Server stopped")

    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.buffers[conn.fileno()] = b''
        self.selector.register(conn, selectors.EVENT_READ, self._read)

    def _read(self, conn, mask):
        try:
            data = conn.recv(65536)
            if not data:
                return self._disconnect(conn)
        except Exception:
            self._disconnect(conn)
            return

        buf = self.buffers.get(conn.fileno(), b'')
        buf += data
        self.buffers[conn.fileno()] = buf

        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            self.buffers[conn.fileno()] = buf
            self._handle(conn, line.decode().strip())

    def _handle(self, conn, line):
        if not line:
            return
        cmd, args = decode(line)

        try:
            if cmd == 'SUBMIT':
                task = Task(
                    args.get('name', ''),
                    args.get('args', []),
                    args.get('kwargs', {}),
                    priority=args.get('priority', 0),
                    schedule_time=args.get('schedule_time')
                )
                self.task_queue.put(task)
                conn.sendall(encode({'ok': True, 'task_id': task.task_id}).encode())

            elif cmd == 'RESULT':
                task_id = args.get('task_id', '')
                result = self.backend.get_result(task_id)
                conn.sendall(
                    encode({'ok': result is not None, 'result': result}).encode()
                )

            elif cmd == 'SCHEDULE':
                name = args.get('name', '')
                task_name = args.get('task_name', '')
                interval = args.get('interval', 60)
                self.scheduler.add_task(
                    name, task_name,
                    args.get('args'), args.get('kwargs'), interval
                )
                conn.sendall(encode({'ok': True}).encode())

            elif cmd == 'WORKERS':
                conn.sendall(encode({
                    'ok': True,
                    'worker_id': self.worker.worker_id,
                    'concurrency': self.worker.concurrency,
                    'running': self.worker._running,
                }).encode())

            elif cmd == 'QUEUE_SIZE':
                conn.sendall(
                    encode({'ok': True, 'size': self.task_queue.size()}).encode()
                )

            elif cmd == 'TASKS':
                conn.sendall(
                    encode({'ok': True, 'tasks': list_tasks()}).encode()
                )

            elif cmd == 'RECENT':
                status = args.get('status')
                results = self.backend.list_results(status=status)
                conn.sendall(
                    encode({'ok': True, 'results': results}).encode()
                )

            else:
                conn.sendall(
                    encode({'ok': False, 'error': f'unknown: {cmd}'}).encode()
                )
        except Exception as e:
            conn.sendall(encode({'ok': False, 'error': str(e)}).encode())

    def _disconnect(self, conn):
        fd = conn.fileno()
        self.buffers.pop(fd, None)
        try:
            self.selector.unregister(conn)
            conn.close()
        except Exception:
            pass
