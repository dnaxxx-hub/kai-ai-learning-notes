"""FSM 运行时 — 执行状态转换、守卫、回调"""

from fsm import FSM, State, Transition


class StateMachine:
    """状态机运行时"""

    def __init__(self, fsm):
        self.fsm = fsm
        self.current = fsm.initial_state
        self.history = []
        self._enter_state(self.current)

    def _enter_state(self, state_name):
        state = self.fsm.get_state(state_name)
        if state and state.on_enter:
            state.on_enter(self.fsm.context)

    def _exit_state(self, state_name):
        state = self.fsm.get_state(state_name)
        if state and state.on_exit:
            state.on_exit(self.fsm.context)

    def send(self, event):
        """发送事件，触发状态转换"""
        state = self.fsm.get_state(self.current)
        if not state:
            raise ValueError(f"当前状态 {self.current} 不存在")

        transition = state.transitions.get(event)
        if not transition:
            raise ValueError(f"状态 {self.current} 不支持事件 {event}")

        # 守卫条件
        if transition.guard and not transition.guard(self.fsm.context):
            return False  # 守卫未通过

        # 执行转换
        self._exit_state(self.current)
        old_state = self.current
        self.current = transition.target
        self.history.append((old_state, event, self.current))

        # 转换动作
        if transition.action:
            transition.action(self.fsm.context)

        # 进入新状态
        self._enter_state(self.current)
        return True

    def can(self, event):
        """检查事件是否可用"""
        state = self.fsm.get_state(self.current)
        if not state:
            return False
        transition = state.transitions.get(event)
        if not transition:
            return False
        if transition.guard:
            return transition.guard(self.fsm.context)
        return True

    def is_state(self, *names):
        return self.current in names

    def reset(self):
        self._exit_state(self.current)
        self.current = self.fsm.initial_state
        self.history = []
        self._enter_state(self.current)
