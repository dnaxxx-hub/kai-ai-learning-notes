"""RESP (REdis Serialization Protocol) 编码/解码器"""

def encode_simple(s):
    """编码 Simple String: +OK\r\n"""
    return f'+{s}\r\n'.encode()

def encode_error(msg):
    """编码 Error: -ERR message\r\n"""
    return f'-{msg}\r\n'.encode()

def encode_integer(i):
    """编码 Integer: :1\r\n"""
    return f':{i}\r\n'.encode()

def encode_bulk(s):
    """编码 Bulk String: $5\r\nhello\r\n ($-1\r\n = null)"""
    if s is None:
        return b'$-1\r\n'
    if isinstance(s, str):
        data = s.encode()
    elif isinstance(s, bytes):
        data = s
    else:
        data = str(s).encode()
    return f'${len(data)}\r\n'.encode() + data + b'\r\n'

def encode_array(arr):
    """编码 Array: *2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n"""
    if arr is None:
        return b'*-1\r\n'
    result = f'*{len(arr)}\r\n'.encode()
    for item in arr:
        if item is None:
            result += encode_bulk(None)
        elif isinstance(item, str):
            result += encode_bulk(item)
        elif isinstance(item, bytes):
            result += encode_bulk(item)
        elif isinstance(item, int):
            result += encode_integer(item)
        else:
            result += encode_error(str(item))
    return result

def encode_value(v):
    """自动选择编码方式"""
    if v is None:
        return encode_bulk(None)
    if isinstance(v, str):
        return encode_bulk(v)
    if isinstance(v, bytes):
        return encode_bulk(v)
    if isinstance(v, int):
        return encode_integer(v)
    if isinstance(v, list):
        return encode_array(v)
    return encode_bulk(str(v))


def decode(data):
    """解码 RESP 数据 → (value, remaining_bytes)
    
    返回 (decoded_value, remaining_bytes)
    如果数据不完整，decoded_value 为 None，remaining 为原始数据
    """
    if not data:
        return None, b''
    
    t = data[0:1]
    
    if t == b'+':  # Simple String
        idx = data.find(b'\r\n')
        if idx == -1:
            return None, data
        return data[1:idx].decode(), data[idx+2:]
    
    if t == b'-':  # Error
        idx = data.find(b'\r\n')
        if idx == -1:
            return None, data
        msg = data[1:idx].decode()
        # 用 Exception 来标记错误类型
        return Exception(msg), data[idx+2:]
    
    if t == b':':  # Integer
        idx = data.find(b'\r\n')
        if idx == -1:
            return None, data
        return int(data[1:idx]), data[idx+2:]
    
    if t == b'$':  # Bulk String
        idx = data.find(b'\r\n')
        if idx == -1:
            return None, data
        length = int(data[1:idx])
        if length == -1:
            return None, data[idx+2:]
        start = idx + 2
        end = start + length
        if len(data) < end + 2:
            return None, data
        val = data[start:end]
        # 尝试解码为字符串，失败则保留 bytes
        try:
            val = val.decode()
        except UnicodeDecodeError:
            pass
        return val, data[end+2:]
    
    if t == b'*':  # Array
        idx = data.find(b'\r\n')
        if idx == -1:
            return None, data
        count = int(data[1:idx])
        if count == -1:
            return None, data[idx+2:]
        result = []
        remaining = data[idx+2:]
        for _ in range(count):
            val, remaining = decode(remaining)
            if val is None and remaining == b'':
                # 数据不完整
                return None, data
            result.append(val)
        return result, remaining
    
    return None, data


def decode_request(data):
    """解码客户端请求 → [command, arg1, arg2, ...]"""
    decoded, _ = decode(data)
    if isinstance(decoded, list):
        return decoded
    return None
