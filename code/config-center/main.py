#!/usr/bin/env python3
"""
配置中心入口
用法:
    python main.py server                  # 启动服务端
    python main.py put <key> <value>       # 设置键值
    python main.py get <key>               # 获取键值
    python main.py del <key>               # 删除键
    python main.py list <prefix>           # 前缀查询
    python main.py grant <ttl>             # 创建租约
    python main.py keepalive <lease_id>    # 续约
    python main.py revoke <lease_id>       # 撤销租约
    python main.py attach <lease_id> <key> # 键关联租约
    python main.py stats                   # 统计信息
"""

import sys
from server import ConfigServer
from client import ConfigClient


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1].lower()
    
    if cmd == 'server':
        host = sys.argv[2] if len(sys.argv) > 2 else '0.0.0.0'
        port = int(sys.argv[3]) if len(sys.argv) > 3 else 8500
        server = ConfigServer(host=host, port=port)
        server.start()
        return
    
    # Client commands
    client = ConfigClient()
    
    if cmd == 'put' and len(sys.argv) >= 4:
        key = sys.argv[2]
        value = ' '.join(sys.argv[3:])
        resp = client.put(key, value)
        print(f"PUT {key} = {value}")
        print(json_dumps(resp))
    
    elif cmd == 'get' and len(sys.argv) >= 3:
        key = sys.argv[2]
        resp = client.get(key)
        print(json_dumps(resp))
    
    elif cmd == 'del' and len(sys.argv) >= 3:
        key = sys.argv[2]
        resp = client.delete(key)
        print(json_dumps(resp))
    
    elif cmd == 'list':
        prefix = sys.argv[2] if len(sys.argv) >= 3 else '/'
        resp = client.list_prefix(prefix)
        print(json_dumps(resp))
    
    elif cmd == 'grant':
        ttl = int(sys.argv[2]) if len(sys.argv) >= 3 else 60
        resp = client.grant(ttl)
        print(json_dumps(resp))
    
    elif cmd == 'keepalive' and len(sys.argv) >= 3:
        resp = client.keepalive(sys.argv[2])
        print(json_dumps(resp))
    
    elif cmd == 'revoke' and len(sys.argv) >= 3:
        resp = client.revoke(sys.argv[2])
        print(json_dumps(resp))
    
    elif cmd == 'attach' and len(sys.argv) >= 4:
        resp = client.attach(sys.argv[2], sys.argv[3])
        print(json_dumps(resp))
    
    elif cmd == 'stats':
        resp = client.stats()
        print(json_dumps(resp))
    
    else:
        print(__doc__)


def json_dumps(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    import json
    main()
