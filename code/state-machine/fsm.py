"""FSM 核心 — 状态、转换、有限状态机定义"""


class State:
    """状态 — 包含进入/退出回调及事件转换表"""

    def __init__(self, name, on_enter=None, on_exit=None):
        self.name = name
        self.on_enter = on_enter  # 进入状态时的回调
        self.on_exit = on_exit    # 离开状态时的回调
        self.transitions = {}     # {event: Transition}

    def add_transition(self, event, target, guard=None, action=None):
        self.transitions[event] = Transition(event, target, guard, action)

    def __repr__(self):
        return f'State({self.name})'


class Transition:
    """转换 — 事件、目标状态、守卫条件、转换动作"""

    def __init__(self, event, target, guard=None, action=None):
        self.event = event
        self.target = target
        self.guard = guard or (lambda ctx: True)       # 守卫条件
        self.action = action or (lambda ctx: None)     # 转换动作

    def __repr__(self):
        return f'Transition({self.event} → {self.target})'


class FSM:
    """有限状态机定义"""

    def __init__(self, name='fsm'):
        self.name = name
        self.states = {}
        self.initial_state = None
        self.context = {}  # 运行时上下文

    def add_state(self, state, initial=False):
        self.states[state.name] = state
        if initial:
            self.initial_state = state.name
        return state

    def add_transition(self, from_state, event, to_state, guard=None, action=None):
        state = self.states.get(from_state)
        if not state:
            raise ValueError(f"未知状态: {from_state}")
        state.add_transition(event, to_state, guard, action)

    def get_state(self, name):
        return self.states.get(name)
