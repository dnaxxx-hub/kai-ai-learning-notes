# 协议格式: <cmd> <args>\n
# PUT /config/db/host localhost:3306
# GET /config/db/host
# DEL /config/db/host
# LIST /config/db/
# WATCH /config/db/host
# GRANT 30    (租约)
# KEEPALIVE <lease_id>
# REVOKE <lease_id>
# ATTACH <lease_id> <key>
# STATS

import json

def encode_response(success, data=None, error=None):
    resp = {'ok': success}
    if data is not None:
        resp['data'] = data
    if error:
        resp['error'] = error
    return json.dumps(resp) + '\n'


def decode_request(data):
    parts = data.strip().split(maxsplit=1)
    if not parts:
        return None, []
    cmd = parts[0].upper()
    args = parts[1].split() if len(parts) > 1 else []
    return cmd, args
