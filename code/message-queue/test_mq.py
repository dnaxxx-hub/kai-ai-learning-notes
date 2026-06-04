"""消息队列单元测试"""
import unittest
import time
import json
import os
import sys
import tempfile
import shutil

# 确保导入路径正确
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from message import Message
from exchange import Exchange
from queue import Queue, Binding, MessageEngine


class TestMessage(unittest.TestCase):
    """1. 消息创建"""

    def test_message_creation(self):
        msg = Message('hello', exchange='ex1', routing_key='rk1',
                      headers={'k': 'v'}, expiration=60, persistent=True)
        self.assertEqual(msg.body, 'hello')
        self.assertEqual(msg.exchange, 'ex1')
        self.assertEqual(msg.routing_key, 'rk1')
        self.assertEqual(msg.headers, {'k': 'v'})
        self.assertIsNotNone(msg.message_id)
        self.assertIsNone(msg.delivery_tag)
        self.assertFalse(msg.redelivered)
        self.assertTrue(msg.persistent)
        self.assertFalse(msg.consumed)
        self.assertEqual(msg.expiration, 60)

    """2. 消息过期"""

    def test_message_expiration(self):
        msg = Message('ephemeral', expiration=0.01)
        self.assertFalse(msg.is_expired())
        time.sleep(0.02)
        self.assertTrue(msg.is_expired())

    def test_message_no_expiration(self):
        msg = Message('persistent')
        self.assertFalse(msg.is_expired())

    def test_message_to_dict(self):
        msg = Message('test', exchange='ex', routing_key='rk',
                      headers={'a': 1}, persistent=True)
        d = msg.to_dict()
        self.assertEqual(d['body'], 'test')
        self.assertEqual(d['exchange'], 'ex')
        self.assertEqual(d['routing_key'], 'rk')
        self.assertEqual(d['headers'], {'a': 1})
        self.assertTrue(d['persistent'])


class TestExchange(unittest.TestCase):
    """3. Exchange: direct 匹配"""

    def test_direct_match(self):
        ex = Exchange('my_ex', 'direct')
        # direct match is done via binding routing_key in engine,
        # but Exchange.match does basic check
        self.assertTrue(ex.match('anything'))

    """4. Exchange: fanout 匹配"""

    def test_fanout_match(self):
        ex = Exchange('fan_ex', 'fanout')
        self.assertTrue(ex.match('anything'))
        self.assertTrue(ex.match(''))

    """5. Exchange: topic 通配符 *"""

    def test_topic_star(self):
        self.assertTrue(Exchange._topic_match('a.*.c', 'a.b.c'))
        self.assertTrue(Exchange._topic_match('*.*', 'a.b'))
        self.assertFalse(Exchange._topic_match('a.*.c', 'a.b.d'))

    """6. Exchange: topic 通配符 #"""

    def test_topic_hash(self):
        self.assertTrue(Exchange._topic_match('a.#', 'a.b.c'))
        self.assertTrue(Exchange._topic_match('a.#', 'a'))
        self.assertTrue(Exchange._topic_match('#', 'a.b.c.d'))
        self.assertTrue(Exchange._topic_match('a.#', 'a.b'))
        self.assertFalse(Exchange._topic_match('a.#', 'b.a'))

    """7. Exchange: headers 匹配"""

    def test_headers_match(self):
        ex = Exchange('hdr_ex', 'headers')
        ex._bind_headers = {'k1': 'v1', 'k2': 'v2'}
        self.assertFalse(ex.match('', None))
        self.assertFalse(ex.match('', {}))
        self.assertFalse(ex.match('', {'k1': 'wrong'}))
        self.assertFalse(ex.match('', {'k1': 'v1'}))
        self.assertTrue(ex.match('', {'k1': 'v1', 'k2': 'v2'}))
        self.assertTrue(ex.match('', {'k1': 'v1', 'k2': 'v2', 'extra': 'ok'}))


class TestQueue(unittest.TestCase):
    """8. Queue: 入队出队"""

    def test_publish_and_deliver(self):
        q = Queue('test_q')
        msg = Message('hello')
        tag = q.publish(msg)
        self.assertEqual(tag, 1)
        self.assertEqual(q.message_count(), 1)

    """9. Queue: 消费者注册"""

    def test_consumer_registration(self):
        q = Queue('test_q')
        received = []

        def cb(m):
            received.append(m)
        tag = q.consume(cb)
        self.assertIsNotNone(tag)
        self.assertEqual(q.consumer_count(), 1)

        # 发布消息并投递
        msg = Message('hello')
        q.publish(msg)
        result = q.deliver()
        self.assertTrue(result)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].body, 'hello')

    def test_cancel_consumer(self):
        q = Queue('test_q')

        def cb(m):
            pass
        tag = q.consume(cb)
        self.assertTrue(q.cancel_consume(tag))
        self.assertFalse(q.cancel_consume(tag))

    """10. Queue: 消息确认 (ACK)"""

    def test_ack(self):
        q = Queue('test_q')
        msg = Message('ack_me')
        tag = q.publish(msg)
        self.assertEqual(q.message_count(), 1)
        self.assertTrue(q.ack(tag))
        self.assertEqual(q.message_count(), 0)

    def test_ack_nonexistent(self):
        q = Queue('test_q')
        self.assertFalse(q.ack(999))

    """11. Queue: 消息拒绝 (NACK)"""

    def test_nack_requeue(self):
        q = Queue('test_q')
        msg = Message('nack_me')
        tag = q.publish(msg)
        self.assertTrue(q.nack(tag, requeue=True))
        self.assertTrue(msg.redelivered)
        # 消息还在队列中
        self.assertEqual(q.message_count(), 1)

    def test_nack_discard(self):
        q = Queue('test_q')
        msg = Message('discard_me')
        tag = q.publish(msg)
        self.assertTrue(q.nack(tag, requeue=False))
        self.assertEqual(q.message_count(), 0)

    """12. Queue: purge 清空"""

    def test_purge(self):
        q = Queue('test_q')
        for i in range(5):
            q.publish(Message(f'msg_{i}'))
        self.assertEqual(q.message_count(), 5)
        count = q.purge()
        self.assertEqual(count, 5)
        self.assertEqual(q.message_count(), 0)

    def test_queue_with_durable_flag(self):
        q = Queue('durable_q', durable=True)
        self.assertTrue(q.durable)
        self.assertEqual(q.name, 'durable_q')
        self.assertFalse(q.auto_delete)


class TestMessageEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = MessageEngine(data_path=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    """13. Engine: 创建队列"""

    def test_create_queue(self):
        result = self.engine.create_queue('q1')
        self.assertTrue(result)
        # 重复创建
        result = self.engine.create_queue('q1')
        self.assertFalse(result)
        self.assertIn('q1', self.engine.queues)

    """14. Engine: 创建 Exchange"""

    def test_create_exchange(self):
        result = self.engine.create_exchange('ex1', 'topic')
        self.assertTrue(result)
        result = self.engine.create_exchange('ex1', 'fanout')
        self.assertFalse(result)
        self.assertIn('ex1', self.engine.exchanges)
        self.assertEqual(self.engine.exchanges['ex1'].type, 'topic')

    """15. Engine: Bind + Publish (direct)"""

    def test_direct_publish(self):
        self.engine.create_exchange('direct_ex', 'direct')
        self.engine.create_queue('q_a')
        self.engine.create_queue('q_b')
        self.engine.bind('q_a', 'direct_ex', 'key_a')
        self.engine.bind('q_b', 'direct_ex', 'key_b')

        # 发布到 key_a
        result = self.engine.publish('to_a', 'direct_ex', 'key_a')
        self.assertIsNotNone(result)
        self.assertEqual(self.engine.queues['q_a'].message_count(), 1)
        self.assertEqual(self.engine.queues['q_b'].message_count(), 0)

    """16. Engine: Bind + Publish (fanout)"""

    def test_fanout_publish(self):
        self.engine.create_exchange('fan_ex', 'fanout')
        self.engine.create_queue('q1')
        self.engine.create_queue('q2')
        self.engine.bind('q1', 'fan_ex')
        self.engine.bind('q2', 'fan_ex')

        result = self.engine.publish('broadcast', 'fan_ex', 'ignored')
        self.assertIsNotNone(result)
        self.assertEqual(self.engine.queues['q1'].message_count(), 1)
        self.assertEqual(self.engine.queues['q2'].message_count(), 1)

    """17. Engine: 默认 Exchange 直连"""

    def test_default_exchange(self):
        self.engine.create_queue('direct_q')
        result = self.engine.publish('direct_msg', '', 'direct_q')
        self.assertIsNotNone(result)
        self.assertEqual(self.engine.queues['direct_q'].message_count(), 1)

        # 不存在的队列
        result = self.engine.publish('nowhere', '', 'nonexistent')
        self.assertIsNone(result)

    """18. Engine: 持久化保存/加载"""

    def test_persistence(self):
        self.engine.create_exchange('persist_ex', 'direct')
        self.engine.create_queue('persist_q')
        self.engine.bind('persist_q', 'persist_ex', 'key')

        # 创建新的 engine 加载
        engine2 = MessageEngine(data_path=self.test_dir)
        self.assertIn('persist_q', engine2.queues)
        self.assertIn('persist_ex', engine2.exchanges)
        self.assertEqual(len(engine2.bindings), 1)

    """19. Engine: 消息投递"""

    def test_engine_delivery(self):
        self.engine.create_queue('deliver_q')
        received = []

        def cb(msg):
            received.append(msg)

        self.engine.consume('deliver_q', cb)
        self.engine.publish('deliver_me', '', 'deliver_q')
        # 手动触发投递
        for q in self.engine.queues.values():
            q.deliver()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].body, 'deliver_me')

    """20. Engine: ACK 确认"""

    def test_engine_ack(self):
        self.engine.create_queue('ack_q')
        tag = self.engine.publish('ack_me', '', 'ack_q')
        self.assertIsNotNone(tag)
        self.assertEqual(self.engine.queues['ack_q'].message_count(), 1)
        # ACK
        result = self.engine.ack(tag)
        self.assertTrue(result)
        self.assertEqual(self.engine.queues['ack_q'].message_count(), 0)

    """21. Engine: Topic 通配符发布"""

    def test_topic_publish(self):
        self.engine.create_exchange('topic_ex', 'topic')
        self.engine.create_queue('animals_dog')
        self.engine.create_queue('animals_all')
        self.engine.create_queue('all')
        self.engine.bind('animals_dog', 'topic_ex', 'animal.dog')
        self.engine.bind('animals_all', 'topic_ex', 'animal.#')
        self.engine.bind('all', 'topic_ex', '#')

        self.engine.publish('dog_message', 'topic_ex', 'animal.dog')
        self.assertEqual(
            self.engine.queues['animals_dog'].message_count(), 1)
        self.assertEqual(
            self.engine.queues['animals_all'].message_count(), 1)
        self.assertEqual(self.engine.queues['all'].message_count(), 1)

        # 第二次发布不同 routing key
        self.engine.publish('cat_message', 'topic_ex', 'animal.cat')
        self.assertEqual(
            self.engine.queues['animals_dog'].message_count(), 1)
        self.assertEqual(
            self.engine.queues['animals_all'].message_count(), 2)
        self.assertEqual(self.engine.queues['all'].message_count(), 2)

    """22. Engine: Headers 匹配发布"""

    def test_headers_publish(self):
        self.engine.create_exchange('hdr_ex', 'headers')
        self.engine.create_queue('hdr_q1')
        self.engine.create_queue('hdr_q2')
        self.engine.bind('hdr_q1', 'hdr_ex',
                          headers={'type': 'important', 'format': 'json'})
        self.engine.bind('hdr_q2', 'hdr_ex',
                          headers={'type': 'normal'})

        result = self.engine.publish(
            'important_json', 'hdr_ex', '',
            headers={'type': 'important', 'format': 'json'}
        )
        self.assertIsNotNone(result)
        self.assertEqual(self.engine.queues['hdr_q1'].message_count(), 1)
        self.assertEqual(self.engine.queues['hdr_q2'].message_count(), 0)

    def test_expired_message_dropped(self):
        """过期消息被丢弃"""
        self.engine.create_queue('exp_q')
        msg = Message('expired', expiration=0.01)
        self.engine.queues['exp_q'].publish(msg)
        time.sleep(0.02)
        self.engine.queues['exp_q'].deliver()
        self.assertEqual(self.engine.queues['exp_q'].message_count(), 0)

    def test_exchange_not_found(self):
        """发布到不存在的 exchange 返回 None"""
        result = self.engine.publish('test', 'nonexistent_exchange', 'key')
        self.assertIsNone(result)

    def test_bind_nonexistent(self):
        """绑定不存在的队列或 exchange 返回 False"""
        result = self.engine.bind('no_queue', 'no_exchange', 'key')
        self.assertFalse(result)


class TestBinding(unittest.TestCase):
    def test_binding_creation(self):
        b = Binding('q', 'ex', 'rk', {'k': 'v'})
        self.assertEqual(b.queue_name, 'q')
        self.assertEqual(b.exchange_name, 'ex')
        self.assertEqual(b.routing_key, 'rk')
        self.assertEqual(b.headers, {'k': 'v'})

    def test_binding_defaults(self):
        b = Binding('q', 'ex')
        self.assertEqual(b.routing_key, '')
        self.assertEqual(b.headers, {})


if __name__ == '__main__':
    unittest.main()
