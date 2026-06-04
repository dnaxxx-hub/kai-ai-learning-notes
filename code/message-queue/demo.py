"""
消息队列演示脚本

演示 Exchange 四种类型 + 队列 + 绑定 + 确认
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from queue import MessageEngine


def demo_direct():
    print("\n" + "=" * 60)
    print("📌 Demo 1: Direct Exchange")
    print("=" * 60)
    engine = MessageEngine(data_path='mq_demo_data')

    engine.create_exchange('direct_logs', 'direct')
    engine.create_queue('error_log')
    engine.create_queue('info_log')
    engine.bind('error_log', 'direct_logs', 'error')
    engine.bind('info_log', 'direct_logs', 'info')

    engine.publish('磁盘空间不足！', 'direct_logs', 'error')
    engine.publish('用户登录成功', 'direct_logs', 'info')
    engine.publish('数据库连接超时！', 'direct_logs', 'error')

    print(f"  error_log 队列消息数: {engine.queues['error_log'].message_count()}")
    print(f"  info_log 队列消息数: {engine.queues['info_log'].message_count()}")
    assert engine.queues['error_log'].message_count() == 2
    assert engine.queues['info_log'].message_count() == 1
    print("  ✅ Direct Exchange 测试通过")


def demo_fanout():
    print("\n" + "=" * 60)
    print("📌 Demo 2: Fanout Exchange (广播)")
    print("=" * 60)
    engine = MessageEngine(data_path='mq_demo_data')

    engine.create_exchange('broadcast', 'fanout')
    engine.create_queue('service_a')
    engine.create_queue('service_b')
    engine.create_queue('service_c')
    engine.bind('service_a', 'broadcast')
    engine.bind('service_b', 'broadcast')
    engine.bind('service_c', 'broadcast')

    engine.publish('系统维护通知：今晚 22:00 停机', 'broadcast', '')

    for name in ['service_a', 'service_b', 'service_c']:
        print(f"  {name} 队列消息数: {engine.queues[name].message_count()}")
        assert engine.queues[name].message_count() == 1
    print("  ✅ Fanout Exchange 测试通过")


def demo_topic():
    print("\n" + "=" * 60)
    print("📌 Demo 3: Topic Exchange (通配符)")
    print("=" * 60)
    engine = MessageEngine(data_path='mq_demo_data')

    engine.create_exchange('topic_logs', 'topic')
    engine.create_queue('all_logs')
    engine.create_queue('error_logs')
    engine.create_queue('app_errors')

    engine.bind('all_logs', 'topic_logs', '#')
    engine.bind('error_logs', 'topic_logs', '*.error')
    engine.bind('app_errors', 'topic_logs', 'app.error')

    engine.publish('App 启动', 'topic_logs', 'app.info')
    engine.publish('App 崩溃!', 'topic_logs', 'app.error')
    engine.publish('DB 连接失败', 'topic_logs', 'db.error')

    print(f"  all_logs (#):       {engine.queues['all_logs'].message_count()} 条")
    print(f"  error_logs (*.error): {engine.queues['error_logs'].message_count()} 条")
    print(f"  app_errors (app.error): {engine.queues['app_errors'].message_count()} 条")
    assert engine.queues['all_logs'].message_count() == 3
    assert engine.queues['error_logs'].message_count() == 2
    assert engine.queues['app_errors'].message_count() == 1
    print("  ✅ Topic Exchange 测试通过")


def demo_headers():
    print("\n" + "=" * 60)
    print("📌 Demo 4: Headers Exchange")
    print("=" * 60)
    engine = MessageEngine(data_path='mq_demo_data')

    engine.create_exchange('header_router', 'headers')
    engine.create_queue('json_queue')
    engine.create_queue('xml_queue')
    engine.create_queue('priority_queue')

    engine.bind('json_queue', 'header_router',
                headers={'format': 'json'})
    engine.bind('xml_queue', 'header_router',
                headers={'format': 'xml'})
    engine.bind('priority_queue', 'header_router',
                headers={'format': 'json', 'priority': 'high'})

    engine.publish('{"msg": "hello"}', 'header_router', '',
                   headers={'format': 'json', 'priority': 'high'})
    engine.publish('<msg>hello</msg>', 'header_router', '',
                   headers={'format': 'xml'})

    print(f"  json_queue:        {engine.queues['json_queue'].message_count()} 条")
    print(f"  xml_queue:         {engine.queues['xml_queue'].message_count()} 条")
    print(f"  priority_queue:    {engine.queues['priority_queue'].message_count()} 条")
    assert engine.queues['json_queue'].message_count() == 1
    assert engine.queues['xml_queue'].message_count() == 1
    assert engine.queues['priority_queue'].message_count() == 1
    print("  ✅ Headers Exchange 测试通过")


def demo_ack():
    print("\n" + "=" * 60)
    print("📌 Demo 5: 消息确认 (ACK/NACK)")
    print("=" * 60)
    engine = MessageEngine(data_path='mq_demo_data')

    engine.create_queue('work_queue')
    engine.create_queue('dlq')

    # 发布消息
    tag1 = engine.publish('task_1', '', 'work_queue')
    tag2 = engine.publish('task_2', '', 'work_queue')
    tag3 = engine.publish('task_3', '', 'work_queue')

    print(f"  ACK 前: {engine.queues['work_queue'].message_count()} 条")
    assert engine.queues['work_queue'].message_count() == 3

    # 确认 tag1
    engine.ack(tag1)
    print(f"  ACK tag1 后: {engine.queues['work_queue'].message_count()} 条")
    assert engine.queues['work_queue'].message_count() == 2

    # NACK tag2 不移除（requeue）
    engine.queues['work_queue'].nack(tag2, requeue=True)
    print(f"  NACK tag2 (requeue) 后: {engine.queues['work_queue'].message_count()} 条")
    assert engine.queues['work_queue'].message_count() == 2  # 重新入队

    # NACK tag3 丢弃
    engine.queues['work_queue'].nack(tag3, requeue=False)
    print(f"  NACK tag3 (丢弃) 后: {engine.queues['work_queue'].message_count()} 条")
    assert engine.queues['work_queue'].message_count() == 1  # tag2 + tag3

    print("  ✅ ACK/NACK 测试通过")


def demo_default_exchange():
    print("\n" + "=" * 60)
    print("📌 Demo 6: 默认 Exchange (直连)")
    print("=" * 60)
    engine = MessageEngine(data_path='mq_demo_data')

    engine.create_queue('my_queue')
    engine.publish('直接发送到 my_queue', '', 'my_queue')
    engine.publish('另一条消息', '', 'my_queue')

    print(f"  my_queue: {engine.queues['my_queue'].message_count()} 条")
    assert engine.queues['my_queue'].message_count() == 2
    print("  ✅ 默认 Exchange 测试通过")


def demo_persistence():
    import tempfile
    import shutil

    print("\n" + "=" * 60)
    print("📌 Demo 7: 持久化")
    print("=" * 60)
    test_dir = tempfile.mkdtemp()

    # 创建 engine 并保存一些元数据
    engine = MessageEngine(data_path=test_dir)
    engine.create_exchange('persist_ex', 'direct')
    engine.create_queue('persist_q')
    engine.bind('persist_q', 'persist_ex', 'key')
    print("  创建队列、Exchange 和绑定，已保存到文件")

    # 重新加载验证
    engine2 = MessageEngine(data_path=test_dir)
    assert 'persist_q' in engine2.queues
    assert 'persist_ex' in engine2.exchanges
    assert len(engine2.bindings) == 1
    print("  重新加载后队列、Exchange 和绑定均恢复")
    print("  ✅ 持久化测试通过")

    shutil.rmtree(test_dir, ignore_errors=True)


def cleanup():
    import shutil
    for d in ['mq_demo_data']:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    cleanup()
    demo_direct()
    demo_fanout()
    demo_topic()
    demo_headers()
    demo_ack()
    demo_default_exchange()
    demo_persistence()
    cleanup()
    print("\n" + "=" * 60)
    print("🎉 所有演示通过！")
    print("=" * 60)
