import uuid
import time


class Message:
    def __init__(self, body, exchange='', routing_key='', headers=None,
                 expiration=None, persistent=False):
        self.body = body
        self.exchange = exchange
        self.routing_key = routing_key
        self.headers = headers or {}
        self.message_id = str(uuid.uuid4())
        self.delivery_tag = None   # 由队列分配
        self.redelivered = False
        self.persistent = persistent
        self.created_at = time.time()
        self.expiration = expiration   # 秒
        self.consumed = False

    def is_expired(self):
        if self.expiration is not None:
            return time.time() - self.created_at > self.expiration
        return False

    def to_dict(self):
        return {
            'body': self.body,
            'exchange': self.exchange,
            'routing_key': self.routing_key,
            'headers': self.headers,
            'message_id': self.message_id,
            'delivery_tag': self.delivery_tag,
            'redelivered': self.redelivered,
            'persistent': self.persistent,
            'created_at': self.created_at,
            'expiration': self.expiration,
            'consumed': self.consumed,
        }
