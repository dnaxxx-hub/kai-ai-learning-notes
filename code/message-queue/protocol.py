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
    args_str = parts[1] if len(parts) > 1 else ''
    try:
        args = json.loads(args_str) if args_str else {}
    except (json.JSONDecodeError, ValueError):
        args = {'raw': args_str}
    return cmd, args
