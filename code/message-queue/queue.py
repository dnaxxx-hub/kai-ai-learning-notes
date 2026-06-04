import threading
import time
import json
import os

from message import Message
from exchange import Exchange


class Queue:
    def __init__(self, name, durable=False, auto_delete=False):
        self.name = name
        self.durable = durable
        self.auto_delete = auto_delete
        self.messages = []       # [Message]
        self.consumers = {}      # {consumer_tag: callback}
        self._delivery_count = 0
        self._lock = threading.Lock()
        self._not_empty = threading.Event()

    def publish(self, message):
        with self._lock:
            self._delivery_count += 1
            message.delivery_tag = self._delivery_count
            self.messages.append(message)
            self._not_empty.set()
        return message.delivery_tag

    def consume(self, callback):
        """注册消费者"""
        consumer_tag = f'consumer_{id(callback)}'
        with self._lock:
            self.consumers[consumer_tag] = callback
        return consumer_tag

    def cancel_consume(self, consumer_tag):
        with self._lock:
            return self.consumers.pop(consumer_tag, None) is not None

    def deliver(self):
        """将消息投递给消费者"""
        with self._lock:
            if not self.messages:
                self._not_empty.clear()
                return False

            # 清理头部过期消息
            while self.messages and self.messages[0].is_expired():
                self.messages.pop(0)

            if not self.messages or not self.consumers:
                self._not_empty.clear()
                return False

            msg = self.messages[0]
            # 投递给第一个消费者
            for tag, callback in list(self.consumers.items()):
                try:
                    callback(msg)
                    msg.consumed = True
                    return True
                except Exception:
                    continue
            return False

    def ack(self, delivery_tag):
        """消息确认"""
        with self._lock:
            for i, msg in enumerate(self.messages):
                if msg.delivery_tag == delivery_tag:
                    self.messages.pop(i)
                    return True
            return False

    def nack(self, delivery_tag, requeue=True):
        """消息拒绝"""
        with self._lock:
            for i, msg in enumerate(self.messages):
                if msg.delivery_tag == delivery_tag:
                    if requeue:
                        msg.redelivered = True
                    else:
                        self.messages.pop(i)
                    return True
            return False

    def purge(self):
        with self._lock:
            count = len(self.messages)
            self.messages.clear()
            return count

    def message_count(self):
        with self._lock:
            return len(self.messages)

    def consumer_count(self):
        with self._lock:
            return len(self.consumers)


class Binding:
    def __init__(self, queue_name, exchange_name, routing_key='', headers=None):
        self.queue_name = queue_name
        self.exchange_name = exchange_name
        self.routing_key = routing_key
        self.headers = headers or {}


class MessageEngine:
    def __init__(self, data_path='mq_data'):
        self.queues = {}        # {queue_name: Queue}
        self.exchanges = {}     # {exchange_name: Exchange}
        self.bindings = []      # [Binding]
        self._lock = threading.Lock()
        self.data_path = data_path
        os.makedirs(data_path, exist_ok=True)
        self._create_defaults()
        self._load()

    def _create_defaults(self):
        if '' not in self.exchanges:
            default = Exchange('', 'direct')
            self.exchanges[''] = default

    def create_exchange(self, name, exchange_type='direct'):
        with self._lock:
            if name in self.exchanges:
                return False
            self.exchanges[name] = Exchange(name, exchange_type)
            return True

    def create_queue(self, name, durable=False, auto_delete=False):
        with self._lock:
            if name in self.queues:
                return False
            self.queues[name] = Queue(name, durable, auto_delete)
            self._save()
            return True

    def bind(self, queue_name, exchange_name, routing_key='', headers=None):
        with self._lock:
            if queue_name not in self.queues or exchange_name not in self.exchanges:
                return False
            binding = Binding(queue_name, exchange_name, routing_key, headers)
            self.bindings.append(binding)

            # 如果是 headers exchange，保存绑定 headers 用于匹配
            ex = self.exchanges[exchange_name]
            if ex.type == 'headers':
                ex._bind_headers = headers or {}

            self._save()
            return True

    def _match_bindings(self, exchange_name, routing_key, exchange_type, headers):
        """返回匹配的队列名集合"""
        matched = set()
        for b in self.bindings:
            if b.exchange_name != exchange_name:
                continue
            if exchange_type == 'fanout':
                matched.add(b.queue_name)
            elif exchange_type == 'direct':
                if b.routing_key == routing_key:
                    matched.add(b.queue_name)
            elif exchange_type == 'topic':
                if Exchange._topic_match(b.routing_key, routing_key):
                    matched.add(b.queue_name)
            elif exchange_type == 'headers':
                if headers and b.headers:
                    if all(headers.get(k) == v for k, v in b.headers.items()):
                        matched.add(b.queue_name)
        return matched

    def publish(self, body, exchange_name='', routing_key='', headers=None,
                persistent=False):
        msg = Message(body, exchange_name, routing_key, headers,
                      persistent=persistent)
        with self._lock:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                return None

            # 默认 exchange: 直接路由到同名队列
            if exchange_name == '':
                queue = self.queues.get(routing_key)
                if queue:
                    tag = queue.publish(msg)
                    self._save()
                    return tag
                return None

            # 查找匹配的 bindings
            matched_queues = self._match_bindings(
                exchange_name, routing_key, exchange.type, headers
            )

            if not matched_queues:
                return None

            tag = None
            for qname in matched_queues:
                queue = self.queues.get(qname)
                if queue:
                    tag = queue.publish(msg)
            self._save()
            return True

    def consume(self, queue_name, callback):
        with self._lock:
            queue = self.queues.get(queue_name)
            if not queue:
                return None
            return queue.consume(callback)

    def ack(self, delivery_tag):
        for queue in self.queues.values():
            if queue.ack(delivery_tag):
                self._save()
                return True
        return False

    def _save(self):
        data = {
            'queues': [(name, q.durable) for name, q in self.queues.items()],
            'bindings': [(b.queue_name, b.exchange_name, b.routing_key,
                         b.headers) for b in self.bindings],
            'exchanges': [(name, ex.type) for name, ex in self.exchanges.items()
                          if name],
        }
        with open(os.path.join(self.data_path, 'mq_meta.json'), 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self):
        path = os.path.join(self.data_path, 'mq_meta.json')
        if not os.path.exists(path):
            return
        with open(path) as f:
            data = json.load(f)
        for qname, durable in data.get('queues', []):
            self.queues[qname] = Queue(qname, durable)
        for ename, etype in data.get('exchanges', []):
            self.exchanges[ename] = Exchange(ename, etype)
        for item in data.get('bindings', []):
            if len(item) == 4:
                bq, be, br, bh = item
            else:
                bq, be, br = item
                bh = {}
            self.bindings.append(Binding(bq, be, br, bh or {}))
            # restore headers exchange bind headers
            if be in self.exchanges and self.exchanges[be].type == 'headers':
                self.exchanges[be]._bind_headers = bh or {}
