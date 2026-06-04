"""WebSocket 帧编码/解码 - RFC 6455 Section 5.2"""

import struct
import os

OPCODES = {
    'CONTINUE': 0x0,
    'TEXT': 0x1,
    'BINARY': 0x2,
    'CLOSE': 0x8,
    'PING': 0x9,
    'PONG': 0xA,
}


def encode_frame(payload, opcode=0x1, mask=False):
    """编码 WebSocket 帧为 bytes"""
    frame = bytearray()
    b0 = 0x80 | opcode  # FIN + opcode
    frame.append(b0)

    length = len(payload)
    if length < 126:
        b1 = (0x80 if mask else 0x00) | length
        frame.append(b1)
    elif length < 65536:
        b1 = (0x80 if mask else 0x00) | 126
        frame.append(b1)
        frame.extend(struct.pack('!H', length))
    else:
        b1 = (0x80 if mask else 0x00) | 127
        frame.append(b1)
        frame.extend(struct.pack('!Q', length))

    if mask:
        mask_key = os.urandom(4)
        frame.extend(mask_key)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        frame.extend(masked)
    else:
        frame.extend(payload)

    return bytes(frame)


def decode_frame(data):
    """解码 WebSocket 帧"""
    if len(data) < 2:
        return None, data

    b0 = data[0]
    b1 = data[1]
    opcode = b0 & 0x0F
    fin = bool(b0 & 0x80)
    mask = bool(b1 & 0x80)
    length = b1 & 0x7F

    offset = 2
    if length == 126:
        if len(data) < 4:
            return None, data
        length = struct.unpack('!H', data[2:4])[0]
        offset = 4
    elif length == 127:
        if len(data) < 10:
            return None, data
        length = struct.unpack('!Q', data[2:10])[0]
        offset = 10

    mask_key = None
    if mask:
        if len(data) < offset + 4:
            return None, data
        mask_key = data[offset:offset + 4]
        offset += 4

    if len(data) < offset + length:
        return None, data  # 不完整

    payload = data[offset:offset + length]
    if mask:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    return (
        {'fin': fin, 'opcode': opcode, 'payload': payload},
        data[offset + length:],
    )
