import json


def encode_response(success, data=None, error=None):
    resp = {'ok': success}
    if data is not None:
        resp['data'] = data
    if error is not None:
        resp['error'] = error
    return json.dumps(resp) + '\n'


def decode_request(data):
    parts = data.strip().split(maxsplit=1)
    cmd = parts[0].upper() if parts else ''
    if len(parts) > 1:
        args = parts[1].split()
    else:
        args = []
    return cmd, args
