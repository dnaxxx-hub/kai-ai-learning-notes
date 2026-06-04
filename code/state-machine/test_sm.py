"""测试 — 有限状态机 & 层次状态机"""
import unittest

from fsm import FSM, State, Transition
from machine import StateMachine
from hsm import HSM, HSMachine, HSMState


class TestFSM(unittest.TestCase):
    """1-11: FSM 基础测试"""

    def test_state_creation(self):
        """1. 状态创建"""
        s = State('idle', on_enter=lambda ctx: None, on_exit=lambda ctx: None)
        self.assertEqual(s.name, 'idle')
        self.assertIsNotNone(s.on_enter)
        self.assertIsNotNone(s.on_exit)
        self.assertEqual(s.transitions, {})

    def test_transition_definition(self):
        """2. 转换定义"""
        s = State('a')
        s.add_transition('go', 'b', guard=lambda ctx: True, action=lambda ctx: None)
        self.assertIn('go', s.transitions)
        t = s.transitions['go']
        self.assertEqual(t.event, 'go')
        self.assertEqual(t.target, 'b')
        self.assertTrue(t.guard({}))
        self.assertIsNone(t.action({}))

    def test_event_trigger(self):
        """3. 事件触发"""
        fsm = FSM()
        a = fsm.add_state(State('a'), initial=True)
        fsm.add_state(State('b'))
        fsm.add_transition('a', 'go', 'b')
        m = StateMachine(fsm)
        self.assertEqual(m.current, 'a')
        r = m.send('go')
        self.assertTrue(r)
        self.assertEqual(m.current, 'b')

    def test_enter_exit_callbacks(self):
        """4. 进入/退出回调"""
        events = []
        a = State('a', on_enter=lambda ctx: events.append('enter_a'),
                  on_exit=lambda ctx: events.append('exit_a'))
        b = State('b', on_enter=lambda ctx: events.append('enter_b'))
        fsm = FSM()
        fsm.add_state(a, initial=True)
        fsm.add_state(b)
        fsm.add_transition('a', 'go', 'b')
        m = StateMachine(fsm)
        self.assertEqual(events, ['enter_a'])
        m.send('go')
        self.assertEqual(events, ['enter_a', 'exit_a', 'enter_b'])

    def test_guard_condition(self):
        """5. 守卫条件"""
        fsm = FSM()
        fsm.add_state(State('a'), initial=True)
        fsm.add_state(State('b'))
        fsm.add_transition('a', 'go', 'b', guard=lambda ctx: ctx.get('ok', False))
        m = StateMachine(fsm)
        m.fsm.context['ok'] = True
        self.assertTrue(m.can('go'))

    def test_guard_block_transition(self):
        """6. 守卫阻止转换"""
        fsm = FSM()
        fsm.add_state(State('a'), initial=True)
        fsm.add_state(State('b'))
        fsm.add_transition('a', 'go', 'b', guard=lambda ctx: False)
        m = StateMachine(fsm)
        self.assertFalse(m.can('go'))
        r = m.send('go')
        self.assertFalse(r)
        self.assertEqual(m.current, 'a')

    def test_transition_action(self):
        """7. 转换动作"""
        side_effects = []
        fsm = FSM()
        fsm.add_state(State('a'), initial=True)
        fsm.add_state(State('b'))
        fsm.add_transition('a', 'go', 'b', action=lambda ctx: side_effects.append('acted'))
        m = StateMachine(fsm)
        m.send('go')
        self.assertEqual(side_effects, ['acted'])

    def test_history(self):
        """8. 历史记录"""
        fsm = FSM()
        fsm.add_state(State('a'), initial=True)
        b = fsm.add_state(State('b'))
        c = fsm.add_state(State('c'))
        fsm.add_transition('a', 'to_b', 'b')
        fsm.add_transition('b', 'to_c', 'c')
        m = StateMachine(fsm)
        m.send('to_b')
        m.send('to_c')
        self.assertEqual(len(m.history), 2)
        self.assertEqual(m.history[0], ('a', 'to_b', 'b'))
        self.assertEqual(m.history[1], ('b', 'to_c', 'c'))

    def test_reset(self):
        """9. 重置"""
        events = []
        a = State('a', on_enter=lambda ctx: events.append('enter_a'),
                  on_exit=lambda ctx: events.append('exit_a'))
        b = State('b', on_enter=lambda ctx: events.append('enter_b'),
                  on_exit=lambda ctx: events.append('exit_b'))
        fsm = FSM()
        fsm.add_state(a, initial=True)
        fsm.add_state(b)
        fsm.add_transition('a', 'go', 'b')
        m = StateMachine(fsm)
        m.send('go')
        events.clear()
        m.reset()
        self.assertEqual(m.current, 'a')
        self.assertEqual(m.history, [])
        self.assertIn('exit_b', events)
        self.assertIn('enter_a', events)

    def test_unknown_event(self):
        """10. 错误: 未知事件"""
        fsm = FSM()
        fsm.add_state(State('a'), initial=True)
        m = StateMachine(fsm)
        with self.assertRaises(ValueError) as ctx:
            m.send('nonexistent')
        self.assertIn('不支持事件', str(ctx.exception))

    def test_unknown_state_fsm(self):
        """11. 错误: FSM add_transition 未知状态"""
        fsm = FSM()
        with self.assertRaises(ValueError) as ctx:
            fsm.add_transition('nowhere', 'x', 'y')
        self.assertIn('未知状态', str(ctx.exception))

    def test_traffic_light_rpc(self):
        """12. 交通灯 RPC 调用流程"""
        green_count = []
        yellow_count = []
        red_count = []
        green = State('green', on_enter=lambda ctx: green_count.append(1))
        yellow = State('yellow', on_enter=lambda ctx: yellow_count.append(1))
        red = State('red', on_enter=lambda ctx: red_count.append(1))
        fsm = FSM('traffic_light')
        fsm.add_state(green, initial=True)
        fsm.add_state(yellow)
        fsm.add_state(red)
        fsm.add_transition('green', 'timer', 'yellow')
        fsm.add_transition('yellow', 'timer', 'red')
        fsm.add_transition('red', 'timer', 'green')
        m = StateMachine(fsm)
        # 初始 green
        self.assertEqual(len(green_count), 1)
        # 6 次 timer 走两轮
        for _ in range(6):
            m.send('timer')
        # green → yellow(1) → red(1) → green(2) → yellow(2) → red(2) → green(3)
        self.assertEqual(len(green_count), 3)
        self.assertEqual(len(yellow_count), 2)
        self.assertEqual(len(red_count), 2)


class TestHSM(unittest.TestCase):
    """13-15: HSM 测试"""

    def test_hsm_hierarchical_states(self):
        """13. HSM 层次状态"""
        hsm = HSM('test')
        root = hsm.add_state('root', initial=True,
                             on_enter=lambda ctx: None)
        child = hsm.add_state('child', parent='root', initial=True)
        grandchild = hsm.add_state('grandchild', parent='child', initial=True)
        self.assertIs(root.parent, None)
        self.assertIs(child.parent, root)
        self.assertIs(grandchild.parent, child)
        self.assertIn('child', root.children)
        self.assertIn('grandchild', child.children)

    def test_hsm_parent_event_forwarding(self):
        """14. HSM 父状态事件处理 — 子状态无事件时向上转发"""
        events = []
        hsm = HSM('test')
        hsm.add_state('root', initial=True)
        child = hsm.add_state('child', parent='root', initial=True,
                              on_enter=lambda ctx: events.append('enter_child'),
                              on_exit=lambda ctx: events.append('exit_child'))
        hsm.add_state('target')
        # root 处理事件
        hsm.add_transition('root', 'go', 'target')
        sm = HSMachine(hsm)
        self.assertEqual(sm.active_states, ['root', 'child'])
        sm.send('go')
        # child 没有 'go' 事件，向上转发到 root 处理
        self.assertIn('exit_child', events)
        self.assertEqual(sm.active_states, ['target'])

    def test_hsm_deep_transition(self):
        """15. HSM 深度转换"""
        on_exit_root = []
        on_exit_child = []
        hsm = HSM('test')
        hsm.add_state('root', initial=True,
                      on_exit=lambda ctx: on_exit_root.append(1))
        hsm.add_state('child', parent='root', initial=True,
                      on_exit=lambda ctx: on_exit_child.append(1))
        hsm.add_state('target')
        # child 自己处理事件
        hsm.add_transition('child', 'go', 'target')
        sm = HSMachine(hsm)
        sm.send('go')
        # 退出 child，不退出 root
        self.assertEqual(on_exit_child, [1])
        self.assertEqual(on_exit_root, [])
        self.assertEqual(sm.active_states, ['root', 'target'])


if __name__ == '__main__':
    unittest.main()
