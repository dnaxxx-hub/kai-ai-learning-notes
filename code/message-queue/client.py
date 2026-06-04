import socket
import json


class MQClient:
    """简单的同步 TCP 客户端"""

    def __init__(self, host='127.0.0.1', port=5672):
        self.host = host
        self.port = port
        self.sock = None
        self.buffer = b''

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.buffer = b''
        return self

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def _send(self, cmd, args=None):
        if args is None:
            args = {}
        line = cmd.upper()
        if args:
            line += ' ' + json.dumps(args)
        line += '\n'
        self.sock.sendall(line.encode())

    def _recv_line(self):
        while b'\n' not in self.buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError('Connection closed')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        return json.loads(line.decode('utf-8', errors='ignore'))

    def declare_queue(self, name, durable=False):
        self._send('DECLARE_QUEUE', {'name': name, 'durable': durable})
        return self._recv_line()

    def declare_exchange(self, name, exchange_type='direct'):
        self._send('DECLARE_EXCHANGE',
                    {'name': name, 'type': exchange_type})
        return self._recv_line()

    def bind(self, queue, exchange, routing_key='', headers=None):
        args = {'queue': queue, 'exchange': exchange,
                'routing_key': routing_key}
        if headers:
            args['headers'] = headers
        self._send('BIND', args)
        return self._recv_line()

    def publish(self, body, exchange='', routing_key='',
                headers=None, persistent=False):
        args = {
            'body': body,
            'exchange': exchange,
            'routing_key': routing_key,
            'persistent': persistent,
        }
        if headers:
            args['headers'] = headers
        self._send('PUBLISH', args)
        return self._recv_line()

    def ack(self, delivery_tag):
        self._send('ACK', {'delivery_tag': delivery_tag})
        return self._recv_line()

    def nack(self, delivery_tag, requeue=True):
        self._send('NACK', {'delivery_tag': delivery_tag, 'requeue': requeue})
        return self._recv_line()

    def status(self):
        self._send('STATUS')
        return self._recv_line()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()


class SimpleConsumer:
    """简单的消费者辅助类"""
    def __init__(self, auto_ack=True):
        self.auto_ack = auto_ack
        self.received = []

    def callback(self, msg):
        self.received.append(msg)
        if self.auto_ack:
            # In direct mode, we track delivery tags
            pass
