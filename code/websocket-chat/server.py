"""WebSocket 聊天服务器 - RFC 6455"""

import socket
import selectors
import json

from frame import encode_frame, decode_frame
from handshake import parse_handshake, generate_accept_key


class WSChatServer:
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.clients = {}  # {fd: {buffer, nick, handshake, conn}}
        self.selector = selectors.DefaultSelector()

    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.listen(10)
        sock.setblocking(False)
        self.selector.register(sock, selectors.EVENT_READ, self._accept)
        print(f"🟢 WebSocket server on ws://{self.host}:{self.port}")
        self._run()

    def _accept(self, sock, mask):
        conn, addr = sock.accept()
        conn.setblocking(False)
        self.clients[conn.fileno()] = {
            'buffer': b'',
            'nick': f'User_{conn.fileno()}',
            'handshake': False,
            'conn': conn,
        }
        self.selector.register(conn, selectors.EVENT_READ, self._read)
        print(f"🔗 新连接: {addr}")

    def _read(self, conn, mask):
        client = self.clients.get(conn.fileno())
        if not client:
            return
        try:
            data = conn.recv(4096)
            if not data:
                self._disconnect(conn)
                return
        except Exception:
            self._disconnect(conn)
            return

        if not client['handshake']:
            self._do_handshake(conn, data, client)
            return

        client['buffer'] += data
        while True:
            frame, remaining = decode_frame(client['buffer'])
            if frame is None:
                break
            client['buffer'] = remaining
            self._handle_frame(conn, frame)

    def _do_handshake(self, conn, data, client):
        req = data.decode('utf-8', errors='ignore')
        parsed = parse_handshake(req)
        if not parsed:
            conn.close()
            return

        accept = generate_accept_key(parsed['key'])
        response = (
            'HTTP/1.1 101 Switching Protocols\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Accept: {accept}\r\n\r\n'
        )
        conn.sendall(response.encode())
        client['handshake'] = True

        # 广播加入
        self._broadcast({'type': 'system', 'msg': f'{client["nick"]} 进入聊天室'})
        print(f"👋 {client['nick']} 进入聊天室")

    def _handle_frame(self, conn, frame):
        opcode = frame['opcode']
        payload = frame['payload']
        client = self.clients.get(conn.fileno())
        if not client:
            return

        if opcode == 0x8:  # Close
            print(f"🚪 {client['nick']} 关闭连接")
            self._disconnect(conn)
        elif opcode == 0x9:  # Ping
            conn.sendall(encode_frame(payload, opcode=0xA))
        elif opcode == 0x1:  # Text
            msg = payload.decode('utf-8', errors='ignore').strip()
            if msg.startswith('/'):
                self._handle_command(conn, msg, client)
            elif msg:
                self._broadcast({'type': 'chat', 'nick': client['nick'], 'msg': msg})
                print(f"💬 {client['nick']}: {msg}")

    def _handle_command(self, conn, cmd, client):
        parts = cmd.split(maxsplit=1)
        cmd_name = parts[0].lower()

        if cmd_name == '/nick' and len(parts) > 1:
            old = client['nick']
            client['nick'] = parts[1][:20]
            self._broadcast({'type': 'system', 'msg': f'{old} → {client["nick"]}'})
            print(f"🏷️  {old} → {client['nick']}")
        elif cmd_name == '/list':
            nicks = [c['nick'] for c in self.clients.values()]
            msg = f'在线: {", ".join(nicks)}'
            conn.sendall(
                encode_frame(
                    json.dumps({'type': 'system', 'msg': msg}).encode()
                )
            )
        elif cmd_name == '/quit':
            self._disconnect(conn)

    def _broadcast(self, msg):
        data = json.dumps(msg, ensure_ascii=False).encode()
        for fd, client in list(self.clients.items()):
            if client.get('handshake'):
                try:
                    client['conn'].sendall(encode_frame(data))
                except Exception:
                    pass

    def _disconnect(self, conn):
        client = self.clients.pop(conn.fileno(), None)
        if client and client.get('handshake'):
            self._broadcast({'type': 'system', 'msg': f'{client["nick"]} 离开聊天室'})
        try:
            self.selector.unregister(conn)
            conn.close()
        except Exception:
            pass

    def _run(self):
        try:
            while True:
                events = self.selector.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj, mask)
        except KeyboardInterrupt:
            print("\n🛑 服务器关闭")
            for fd, client in list(self.clients.items()):
                try:
                    client['conn'].close()
                except Exception:
                    pass
            self.selector.close()
