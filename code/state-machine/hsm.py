"""层次状态机 — 父子状态、事件向上转发"""

from fsm import State, Transition


class HSMState:
    """层次状态 — 可以有父状态和子状态"""

    def __init__(self, name, parent=None, on_enter=None, on_exit=None):
        self.name = name
        self.parent = parent
        self.children = {}         # {name: HSMState}
        self.transitions = {}
        self.on_enter = on_enter
        self.on_exit = on_exit
        self.initial_child = None
        self.current_child = None

    def add_child(self, child, initial=False):
        self.children[child.name] = child
        child.parent = self
        if initial or not self.initial_child:
            self.initial_child = child.name

    def add_transition(self, event, target, guard=None, action=None):
        self.transitions[event] = Transition(event, target, guard, action)

    def get_transition(self, event):
        """从当前状态或其父状态找转换"""
        t = self.transitions.get(event)
        if t:
            return t
        if self.parent:
            return self.parent.get_transition(event)
        return None

    def __repr__(self):
        children = f' ({len(self.children)} children)' if self.children else ''
        return f'HSMState({self.name}{children})'


class HSM:
    """层次有限状态机定义"""

    def __init__(self, name='hsm'):
        self.name = name
        self.states = {}
        self.root = None
        self.context = {}

    def add_state(self, name, parent=None, on_enter=None, on_exit=None,
                  initial=False):
        parent_state = self.states.get(parent) if parent else None
        state = HSMState(name, parent_state, on_enter, on_exit)
        self.states[name] = state
        if parent_state:
            parent_state.add_child(state, initial)
        elif self.root is None:
            self.root = state
        return state

    def add_transition(self, state_name, event, target, guard=None,
                       action=None):
        state = self.states.get(state_name)
        if not state:
            raise ValueError(f"未知状态: {state_name}")
        state.add_transition(event, target, guard, action)


class HSMachine:
    """层次状态机运行时"""

    def __init__(self, hsm):
        self.hsm = hsm
        self.active_states = []   # 从根到叶子的路径
        self.history = []
        self._enter_state(hsm.root.name)

    def _enter_state(self, state_name):
        state = self.hsm.states[state_name]
        self.active_states.append(state_name)
        if state.on_enter:
            state.on_enter(self.hsm.context)
        # 如果有初始子状态，递归进入
        if state.initial_child:
            self._enter_state(state.initial_child)

    def _exit_state(self, state_name):
        state = self.hsm.states[state_name]
        # 先退出子状态
        if state.children:
            for child_name in reversed(self.active_states):
                if child_name in state.children:
                    self._exit_state(child_name)
                    break
        if state.on_exit:
            state.on_exit(self.hsm.context)
        if state_name in self.active_states:
            self.active_states.remove(state_name)

    def send(self, event):
        """从当前最内层状态向上查找转换"""
        if not self.active_states:
            return False

        current_name = self.active_states[-1]
        current = self.hsm.states[current_name]
        transition = current.get_transition(event)

        if not transition:
            raise ValueError(f"没有状态可处理事件 {event}")
        if transition.guard and not transition.guard(self.hsm.context):
            return False

        old_state = self.active_states[-1]

        # 找出实际拥有此转换的状态（可能是当前状态的某个祖先）
        handler = current
        while event not in handler.transitions or handler.transitions[event] is not transition:
            handler = handler.parent
            if handler is None:
                break

        # 确定退出范围：
        # - 如果 handler 不是当前叶子（即由父状态处理），退出包含 handler 在内的整条路径
        # - 如果 handler 就是当前叶子，只退出叶子
        if handler and handler.name != current_name:
            # 父状态处理事件 → 退出包含 handler 在内的所有状态
            to_exit = []
            for s in reversed(self.active_states):
                to_exit.append(s)
                if s == handler.name:
                    break  # 也退出 handler
        else:
            # 仅退出当前叶子状态
            to_exit = [current_name]

        for s in to_exit:
            self._exit_state(s)

        self._enter_state(transition.target)
        self.history.append((old_state, event, transition.target))
        return True

    def is_state(self, name):
        return name in self.active_states

    def deepest_state(self):
        return self.active_states[-1] if self.active_states else None

    def reset(self):
        for s in reversed(self.active_states):
            state = self.hsm.states.get(s)
            if state and state.on_exit:
                state.on_exit(self.hsm.context)
        self.active_states = []
        self.history = []
        self._enter_state(self.hsm.root.name)
