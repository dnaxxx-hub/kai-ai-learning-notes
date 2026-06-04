"""
server.py — 聊天服务器 (selectors 多路复用)
支持多客户端实时群聊
"""

import socket
import selectors
import json
import struct
import signal
import sys

from protocol import pack, parse_stream


class ChatServer:
    MAX_CLIENTS = 50
    BUFFER_SIZE = 4096

    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.clients = {}  # {fd: {'nick': str, 'buffer': bytes, 'addr': str, 'conn': socket}}
        self.server_sock = None
        self._running = False

    def start(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen()
        self.server_sock.setblocking(False)
        self.selector.register(self.server_sock, selectors.EVENT_READ, self._accept)

        # 信号处理 (只在主线程注册)
        self._running = True
        print(f"🟢 Chat server on {self.host}:{self.port}")
        self._run()

    def _run(self):
        while self._running:
            events = self.selector.select(timeout=1)
            for key, mask in events:
                callback = key.data
                try:
                    callback(key.fileobj, mask)
                except Exception as e:
                    print(f"[error] {e}", file=sys.stderr)

    def _signal_handler(self, signum, frame):
        print("\n🛑 Shutting down gracefully...")
        self._running = False
        self.shutdown()

    def shutdown(self):
        # 广播下线通知
        self._broadcast({'type': 'system', 'msg': '服务器关闭中...'})
        # 关闭所有客户端连接
        for fd in list(self.clients.keys()):
            try:
                self.selector.unregister(self.clients[fd]['conn'])
                self.clients[fd]['conn'].close()
            except Exception:
                pass
        self.clients.clear()
        # 关闭服务器
        if self.server_sock:
            try:
                self.selector.unregister(self.server_sock)
                self.server_sock.close()
            except Exception:
                pass
        self.selector.close()
        print("👋 Server stopped.")

    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.clients[conn.fileno()] = {
            'nick': None,
            'buffer': b'',
            'addr': str(addr),
            'conn': conn
        }
        self.selector.register(conn, selectors.EVENT_READ, self._read)
        self._send(conn, {'type': 'system', 'msg': '欢迎! 输入你的昵称:'})
        print(f"[connect] {addr}")

    def _read(self, conn, mask):
        try:
            data = conn.recv(self.BUFFER_SIZE)
            if not data:
                self._disconnect(conn)
                return

            client = self.clients.get(conn.fileno())
            if not client:
                return
            client['buffer'] += data
            self._process_buffer(conn)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            self._disconnect(conn)
        except Exception:
            self._disconnect(conn)

    def _process_buffer(self, conn):
        client = self.clients.get(conn.fileno())
        if not client:
            return
        messages, client['buffer'] = parse_stream(client['buffer'])
        for msg in messages:
            self._handle_msg(conn, msg)

    def _handle_msg(self, conn, msg):
        client = self.clients.get(conn.fileno())
        if not client:
            return

        # 首次连接, 第一条消息作为昵称
        if client['nick'] is None:
            nick = msg.get('msg', f'User_{conn.fileno()}')[:20]
            client['nick'] = nick
            self._broadcast({'type': 'join', 'nick': nick})
            self._send(conn, {'type': 'system', 'msg': f'已进入聊天室, 昵称: {nick}'})
            print(f"[nick] {nick} 进入聊天室")
            return

        msg_type = msg.get('type', '')
        if msg_type == 'chat':
            text = msg.get('msg', '').strip()
            if text.startswith('/'):
                self._handle_command(conn, text)
            elif text:
                self._broadcast({
                    'type': 'chat',
                    'nick': client['nick'],
                    'msg': text
                })

    def _handle_command(self, conn, cmd):
        client = self.clients.get(conn.fileno())
        if not client:
            return

        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()

        if command == '/list':
            nicks = [c['nick'] for fd, c in self.clients.items()
                     if c['nick'] is not None]
            msg = f'在线 ({len(nicks)}): {", ".join(nicks)}'
            self._send(conn, {'type': 'system', 'msg': msg})

        elif command == '/nick' and len(parts) > 1:
            old_nick = client['nick']
            new_nick = parts[1][:20]
            client['nick'] = new_nick
            self._broadcast({
                'type': 'system',
                'msg': f'{old_nick} 改名为 {new_nick}'
            })

        elif command == '/quit':
            self._disconnect(conn)

        else:
            self._send(conn, {
                'type': 'system',
                'msg': f'未知命令: {command}. 可用: /list, /nick <昵称>, /quit'
            })

    def _broadcast(self, msg):
        """广播消息给所有已登录的客户端"""
        data = pack(msg)
        for fd in list(self.clients.keys()):
            try:
                self.clients[fd]['conn'].sendall(data)
            except Exception:
                pass

    def _send(self, conn, msg):
        """发送消息给指定连接"""
        try:
            conn.sendall(pack(msg))
        except Exception:
            self._disconnect(conn)

    def _disconnect(self, conn):
        client = self.clients.pop(conn.fileno(), None)
        if client and client['nick']:
            self._broadcast({'type': 'leave', 'nick': client['nick']})
            print(f"[leave] {client['nick']} 离开聊天室")
        try:
            self.selector.unregister(conn)
            conn.close()
        except Exception:
            pass


def run_server(host='0.0.0.0', port=9999):
    server = ChatServer(host=host, port=port)
    server.start()
