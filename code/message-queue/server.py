import socket
import selectors
import json
import threading
import time

from queue import MessageEngine
from protocol import encode_response, decode_request


class MQServer:
    def __init__(self, host='0.0.0.0', port=5672):
        self.host = host
        self.port = port
        self.engine = MessageEngine()
        self.selector = selectors.DefaultSelector()
        self.buffers = {}
        self.client_data = {}  # fileno -> {queue_name, consumer_tag, etc}
        self.running = False

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(50)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)

        # 消息投递线程
        self.running = True
        t = threading.Thread(target=self._delivery_loop, daemon=True)
        t.start()

        print(f"🟢 Message Queue on {self.host}:{self.port}")

        try:
            while self.running:
                events = self.selector.select(timeout=1)
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except KeyboardInterrupt:
            self.running = False
            print("\n🛑 服务器关闭")
        finally:
            sock.close()

    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.buffers[conn.fileno()] = b''
        self.client_data[conn.fileno()] = {}
        self.selector.register(conn, selectors.EVENT_READ, self._read)

    def _read(self, conn, mask):
        try:
            data = conn.recv(4096)
            if not data:
                self._disconnect(conn)
                return
        except Exception:
            self._disconnect(conn)
            return

        buf = self.buffers.get(conn.fileno(), b'')
        buf += data
        self.buffers[conn.fileno()] = buf

        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            self.buffers[conn.fileno()] = buf
            self._handle_request(conn,
                                 line.decode('utf-8', errors='ignore').strip())

    def _handle_request(self, conn, line):
        if not line:
            return
        cmd, args = decode_request(line)

        try:
            if cmd == 'PUBLISH':
                body = args.get('body', '')
                exchange = args.get('exchange', '')
                routing_key = args.get('routing_key', '')
                headers = args.get('headers')
                persistent = args.get('persistent', False)
                result = self.engine.publish(
                    body, exchange, routing_key,
                    headers=headers, persistent=persistent
                )
                conn.sendall(encode_response(
                    result is not None,
                    {'delivered': result is not None}
                ).encode())

            elif cmd == 'DECLARE_QUEUE':
                name = args.get('name', '')
                durable = args.get('durable', False)
                self.engine.create_queue(name, durable)
                conn.sendall(encode_response(True,
                              {'queue': name}).encode())

            elif cmd == 'DECLARE_EXCHANGE':
                name = args.get('name', '')
                etype = args.get('type', 'direct')
                self.engine.create_exchange(name, etype)
                conn.sendall(encode_response(True,
                              {'exchange': name}).encode())

            elif cmd == 'BIND':
                queue = args.get('queue', '')
                exchange = args.get('exchange', '')
                routing_key = args.get('routing_key', '')
                headers = args.get('headers')
                result = self.engine.bind(queue, exchange, routing_key,
                                          headers=headers)
                conn.sendall(encode_response(result).encode())

            elif cmd == 'ACK':
                tag = args.get('delivery_tag', 0)
                ok = self.engine.ack(tag)
                conn.sendall(encode_response(ok).encode())

            elif cmd == 'NACK':
                tag = args.get('delivery_tag', 0)
                requeue = args.get('requeue', True)
                ok = False
                for q in self.engine.queues.values():
                    if q.nack(tag, requeue=requeue):
                        ok = True
                        break
                conn.sendall(encode_response(ok).encode())

            elif cmd == 'STATUS':
                status = {}
                for name, queue in self.engine.queues.items():
                    status[name] = {
                        'messages': queue.message_count(),
                        'consumers': queue.consumer_count(),
                    }
                conn.sendall(encode_response(True, status).encode())

            else:
                conn.sendall(encode_response(False,
                              error=f'未知命令: {cmd}').encode())
        except Exception as e:
            conn.sendall(encode_response(False, error=str(e)).encode())

    def _delivery_loop(self):
        while self.running:
            for queue in list(self.engine.queues.values()):
                try:
                    queue.deliver()
                except Exception:
                    pass
            time.sleep(0.01)

    def _disconnect(self, conn):
        self.buffers.pop(conn.fileno(), None)
        self.client_data.pop(conn.fileno(), None)
        try:
            self.selector.unregister(conn)
            conn.close()
        except Exception:
            pass
