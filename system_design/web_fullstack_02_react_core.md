# Web 全栈第2课：React 核心原理

> 日期：2026-05-11 | 课程：Web 全栈 Phase 1-2
> 核心思维：React 不是魔法——VDOM Diff、Hooks 链表、状态管理，每一层都是可理解的

---

## 一、虚拟 DOM（Virtual DOM）

### 1.1 为什么需要 VDOM？

```javascript
// 不用 VDOM = 每次更新都重建全部 DOM
// DOM 操作 ≈ 代价极高（浏览器 Layout + Paint）
// VDOM = 在 JS 内存里做轻量对比，只把最终差异打到 DOM 上

// 真实 DOM（太重！）
const realDOM = document.createElement('div');
realDOM.className = 'old';

// VDOM（轻量对象，几微秒创建）
const vdom = { type: 'div', props: { className: 'old' }, children: [] };
```

**核心收益**：
1. **声明式编程**：你只管"想要什么"，React 管"怎么改 DOM"
2. **批量更新**：一帧内合并多次 setState，只一次 DOM 操作
3. **跨平台**：VDOM 只是 JS 对象 → 可渲染到 DOM/Native/Canvas...

### 1.2 VDOM 数据结构

```typescript
// React VDOM 节点 → 类型定义
interface VNode<P = any> {
  $$typeof: Symbol;          // React 元素标记，防 XSS
  type: string | Function;   // 'div' | MyComponent
  key: string | null;        // 列表优化
  ref: Ref | null;
  props: P & {
    children?: VNode | VNode[];
  };
  _owner: Fiber;             // 属于哪个 Fiber 节点
}
```

**React 元素不是真正的实例，而是"描述"**：
```tsx
// JSX → createElement 调用
const element = <h1 className="title">Hello</h1>;

// 经过编译（Babel / SWC）：
const element = React.createElement(
  'h1',
  { className: 'title' },
  'Hello'
);

// 最终产物：
const element = {
  $$typeof: Symbol.for('react.element'),
  type: 'h1',
  props: { className: 'title', children: 'Hello' },
  key: null,
  ref: null,
};
```

---

## 二、Diff 算法（Reconciliation）

### 2.1 算法核心：O(n) 启发式比较

React 的 Diff 基于**三个假设**（经过实践验证的启发式）：

```
假设 1: 不同 DOM 类型 → 重建整个子树
假设 2: key 属性 → 识别兄弟元素中的同一元素
假设 3: 同层比较 → 不会跨层级移动节点
```

### 2.2 类型比较（Type Comparison）

```tsx
// 场景 1：类型变化 → 卸载旧树，挂载新树
// 旧: <div><Counter /></div>
// 新: <span><Counter /></span>
// → div 和 span 不同 → 整个子树重建，Counter 被销毁重挂！

// 场景 2：同类型 → 更新 props，保留 DOM 节点
// 旧: <div className="old" />
// 新: <div className="new" />
// → 复用 DOM 节点，只更新 className

// 场景 3：组件类型变化 → 同上，卸载旧组件实例，创建新组件
// 旧: <OldComponent />
// 新: <NewComponent />
// → OldComponent 的 useEffect cleanup 会跑，然后创建 NewComponent
```

**为什么不递归比较整个树？**
```
假设有 1000 个节点
跨层级 Diff = O(n³) ≈ 10 亿次计算 ❌
同层级 Diff = O(n)  ≈ 1000 次计算  ✅
```

### 2.3 Key 复用（Key Reconciliation）

```tsx
// 列表渲染的 key 是关键！
function List({ items }: { items: Item[] }) {
  return (
    <ul>
      {items.map(item => (
        <li key={item.id}>{item.text}</li>
      ))}
    </ul>
  );
}
```

**Key 的匹配过程（列表 Diff 算法 — 双端对比）**：

```
旧列表:  [A]  [B]  [C]  [D]      key 相同
新列表:  [B]  [C]  [D]  [E]      

Step 1: 从头匹配
  A vs B → 不同，停止
Step 2: 从尾匹配
  D vs E → 不同，停止
Step 3: 遍历剩余旧元素建映射
  {B: 1, C: 2, D: 3}
Step 4: 遍历新列表，匹配复用：
  B → 已存在，移动位置
  C → 已存在，移动位置  
  D → 已存在，移动位置
  E → 不存在，新建
```

**❌ 反模式：用 index 作 key**：
```tsx
// 危险！如果数组会变化
{items.map((item, index) => <Item key={index} />)}
// 插入/删除/排序 → key 全变了 → 大量非必要重建
// 甚至可能造成 bug（输入框内容串位）
```

**✅ 正确做法**：
```tsx
// 使用唯一 ID
key={item.id}
// 实在没有稳定 ID 时，用 combined key
key={`${item.type}-${item.name}`}
```

---

## 三、Hooks 原理（链表）

### 3.1 Hooks 不是魔法 —— 是链表

```typescript
// 每个组件实例关联一个 Fiber 节点
// Fiber 节点上挂着 hooks 链表

interface Fiber {
  memoizedState: Hook | null;  // 指向第一个 Hook
  // ...
}

interface Hook {
  memoizedState: any;          // 当前状态值
  baseState: any;              // 基础状态
  baseQueue: Update | null;    // 待执行的更新
  queue: UpdateQueue | null;   // 更新队列
  next: Hook | null;           // 指向下一个 Hook ⬅ 链表！
}
```

**Hooks 链表结构**：
```
Fiber.memoizedState
  │
  ▼
┌─────────┐    next    ┌─────────┐    next    ┌──────────┐
│ useState │ ────────→ │ useEffect│ ────────→ │ useRef   │
│ Hook #1  │           │ Hook #2  │           │ Hook #3  │
│ memoized │           │ memoized │           │ memoized │
│ State: 0 │           │ State:   │           │ State:   │
│ queue: ▒▒│           │ createFn │           │ {current}│
└─────────┘           └─────────┘           └──────────┘
```

### 3.2 Hooks 顺序为什么不能变？

```tsx
// ❌ 条件 Hook —— 违反"调用顺序不变"规则
function BadExample({ flag }: { flag: boolean }) {
  if (flag) {
    const [count, setCount] = useState(0);  // 可能跳过 Hook #1
  }
  useEffect(() => {});                       // 可能是 Hook #1 或 #2
  // → 下次渲染时 flag 变了，链表错位！React 崩溃
}

// ✅ 正确：所有 Hook 在顶部无条件调用
function GoodExample({ flag }: { flag: boolean }) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (flag) {
      // 条件逻辑放在 Hook 内部
      setCount(1);
    }
  }, [flag]);
}
```

### 3.3 useState 的工作机制

```python
"""React useState 的底层机制模拟（链表 + 队列）"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class UpdateQueue:
    """状态更新队列"""
    pending: list[Callable[[Any], Any] | Any] = field(default_factory=list)

    def enqueue_update(self, action: Callable | Any):
        """入队一个更新"""
        self.pending.append(action)

    def compute_state(self, base_state: Any) -> Any:
        """计算最终状态（批量合并）"""
        state = base_state
        for action in self.pending:
            if callable(action):
                state = action(state)
            else:
                state = action
        return state


@dataclass
class Hook:
    """单个 Hook 节点"""
    memoized_state: Any = None
    queue: UpdateQueue | None = None
    next: Hook | None = None  # 链表指针


class FakeReact:
    """模拟 React Hooks 运行时"""

    def __init__(self):
        self._currently_rendering_fiber: Fiber | None = None
        self._hook_index = 0

    def useState(self, initial: Any) -> tuple[Any, Callable]:
        fiber = self._currently_rendering_fiber
        hook = self._get_or_create_hook(fiber, self._hook_index)

        # 首次渲染时初始化
        if hook.queue is None:
            hook.memoized_state = initial
            hook.queue = UpdateQueue()

        # 处理待更新队列
        if hook.queue.pending:
            hook.memoized_state = hook.queue.compute_state(hook.memoized_state)
            hook.queue.pending.clear()

        self._hook_index += 1

        def set_state(action):
            """setState: 把更新入队，触发重新渲染"""
            hook.queue.enqueue_update(action)
            self._schedule_rerender(fiber)

        return (hook.memoized_state, set_state)

    def _get_or_create_hook(self, fiber, index: int) -> Hook:
        """从 fiber 的 hooks 链表中获取或创建 hook"""
        if fiber.memoized_state is None:
            fiber.memoized_state = Hook()

        hook = fiber.memoized_state
        for _ in range(index):
            if hook.next is None:
                hook.next = Hook()
            hook = hook.next
        return hook

    def _schedule_rerender(self, fiber):
        print(f"  [Schedule] fiber #{id(fiber)} 重新渲染")


@dataclass
class Fiber:
    memoized_state: Hook | None = None


# === 演示 ===
if __name__ == "__main__":
    print("=== React Hooks 链表模拟 ===")
    fr = FakeReact()

    # 模拟一个组件渲染
    fiber = Fiber()
    fr._currently_rendering_fiber = fiber
    fr._hook_index = 0

    print("首次渲染:")
    count_1, set_count_1 = fr.useState(0)
    text_1, set_text_1 = fr.useState("hello")
    print(f"  count={count_1}, text='{text_1}'")

    # 触发更新
    print("\n触发 set_count_1(42):")
    set_count_1(42)

    # 重新渲染（主流程驱动）
    print("重新渲染:")
    fr._currently_rendering_fiber = fiber
    fr._hook_index = 0
    count_2, _ = fr.useState(0)
    text_2, _ = fr.useState("hello")
    print(f"  count={count_2}, text='{text_2}'")
```

---

## 四、状态管理全景

### 4.1 状态管理的三个层级

```
层级 1: 组件局部状态
  → useState / useReducer
  → 只在当前组件及其子组件（props 传下去）

层级 2: 跨组件共享（Context）
  → React.createContext + useContext
  → 适合 theme / locale / auth 这种"全局但少变"的数据

层级 3: 全局状态（外部状态管理）
  → Redux / Zustand / Jotai
  → 适合跨页面、复杂数据流、需要 middleware 的场景
```

### 4.2 useState — 局部状态

```tsx
function Counter() {
  const [count, setCount] = useState(0);

  // setState 可以是值或函数
  const increment = () => setCount(prev => prev + 1);    // ✅ 函数式更新
  const incrementBad = () => setCount(count + 1);         // ❌ 注意闭包陷阱

  // 复杂对象 — 要创建新引用
  const [user, setUser] = useState({ name: 'Alice', age: 25 });
  const updateName = (name: string) => {
    setUser(prev => ({ ...prev, name }));  // 展开旧值再覆盖
  };

  return <button onClick={increment}>{count}</button>;
}
```

### 4.3 useReducer — 复杂状态逻辑

```tsx
// 当状态逻辑复杂或依赖旧状态时
type Action = { type: 'increment' } | { type: 'decrement' } | { type: 'reset'; payload: number };

function reducer(state: number, action: Action): number {
  switch (action.type) {
    case 'increment': return state + 1;
    case 'decrement': return state - 1;
    case 'reset':     return action.payload;
    default:          return state;
  }
}

function Counter() {
  const [count, dispatch] = useReducer(reducer, 0);
  return (
    <>
      <button onClick={() => dispatch({ type: 'increment' })}>+</button>
      <span>{count}</span>
      <button onClick={() => dispatch({ type: 'decrement' })}>-</button>
    </>
  );
}
```

### 4.4 Context — 跨组件共享

```tsx
// 1. 创建 Context
const ThemeContext = createContext<{ theme: 'light' | 'dark'; toggle: () => void }>(
  { theme: 'light', toggle: () => {} }
);

// 2. Provider 提供值
function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const toggle = () => setTheme(t => t === 'light' ? 'dark' : 'light');

  return (
    <ThemeContext.Provider value={{ theme, toggle }}>
      <Toolbar />
    </ThemeContext.Provider>
  );
}

// 3. 子组件消费
function Toolbar() {
  return <ThemeToggle />;
}

function ThemeToggle() {
  const { theme, toggle } = useContext(ThemeContext);
  return <button onClick={toggle}>当前: {theme}</button>;
}
```

**Context 的坑**：Provider 的 value 每次渲染都是新引用 → 所有 Consumer 都重渲染
```tsx
// ❌ 每次渲染创建新对象 → 全部子组件重渲染
<ThemeContext.Provider value={{ theme: 'dark', toggle }}>

// ✅ 用 useMemo 稳定引用
const ctx = useMemo(() => ({ theme, toggle }), [theme]);
<ThemeContext.Provider value={ctx}>
```

### 4.5 Redux — 可预测状态管理

```typescript
// Redux 三大原则：
// 1. 单一数据源（Single Source of Truth）— 一个 store
// 2. State 只读 — 只能通过 dispatch(action) 修改
// 3. 纯函数修改 — reducer 必须是纯函数

// 完整 Redux Toolkit 示例：
import { createSlice, configureStore, PayloadAction } from '@reduxjs/toolkit';

// Slice = reducer + actions 组合
const counterSlice = createSlice({
  name: 'counter',
  initialState: { value: 0 },
  reducers: {
    incremented: (state) => { state.value += 1; },      // Immer 允许"可变"写法
    decremented: (state) => { state.value -= 1; },
    amountAdded: (state, action: PayloadAction<number>) => {
      state.value += action.payload;
    },
  },
});

export const { incremented, decremented, amountAdded } = counterSlice.actions;

// Store
const store = configureStore({
  reducer: { counter: counterSlice.reducer },
});

// 使用
store.dispatch(incremented());
console.log(store.getState());  // { counter: { value: 1 } }
```

**Redux 数据流**：
```
Component ──dispatch(action)──→ Middleware (thunk/saga/logger)
                                     │
                                     ▼
                                 Reducer (纯函数)
                                     │
                                     ▼
                                 New State
                                     │
                                     ▼
                              subscribe → re-render
```

---

## 五、Python VDOM 模拟

```python
"""
虚拟 DOM + Diff 算法的 Python 实现
模拟 React 的核心机制
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import difflib


# === 虚拟 DOM 节点 ===
@dataclass
class VNode:
    type: str | type  # 'div' 或 类组件
    props: dict[str, Any] = field(default_factory=dict)
    children: list[VNode | str] = field(default_factory=list)
    key: Optional[str] = None

    def render(self, indent: int = 0) -> str:
        """将 VDOM 渲染为字符串（模拟真实渲染）"""
        prefix = "  " * indent
        result = f"{prefix}<{self.type}"

        # props
        for k, v in self.props.items():
            if k == 'children':
                continue
            result += f" {k}={v!r}"

        result += ">"

        if self.children:
            result += "\n"
            for child in self.children:
                if isinstance(child, VNode):
                    result += child.render(indent + 1) + "\n"
                else:
                    result += f"  {'  ' * indent}{child}\n"
            result += f"{prefix}</{self.type}>"
        else:
            result += f"</{self.type}>"

        return result


# === Diff 结果 ===
@dataclass
class Patch:
    type: str  # 'replace' | 'update_props' | 'reorder_children' | 'insert' | 'remove'
    path: list[int]
    payload: Any = None

    def __repr__(self) -> str:
        return f"Patch({self.type}, path={self.path}, payload={self.payload!r})"


class VDOMDiff:
    """虚拟 DOM Diff 算法实现"""

    def diff(self, old: Optional[VNode], new: Optional[VNode],
             path: list[int] | None = None) -> list[Patch]:
        """对比两个 VDOM 树，返回补丁列表"""
        patches: list[Patch] = []
        path = path or []

        # 情况 1: 旧节点不存在 → 插入新节点
        if old is None:
            patches.append(Patch('insert', path, new))
            return patches

        # 情况 2: 新节点不存在 → 删除
        if new is None:
            patches.append(Patch('remove', path))
            return patches

        # 情况 3: 节点类型不同 → 替换整个子树
        if old.type != new.type or old.key != new.key:
            patches.append(Patch('replace', path, new))
            return patches

        # 情况 4: 节点类型相同 → 比较 props
        prop_patches = self._diff_props(old.props, new.props)
        if prop_patches:
            patches.append(Patch('update_props', path, prop_patches))

        # 情况 5: 比较子节点（带 key 优化）
        children_patches = self._diff_children(
            old.children, new.children, list(path) + ['children']
        )
        patches.extend(children_patches)

        return patches

    def _diff_props(self, old_props: dict, new_props: dict) -> dict:
        """比较 props：找出新增、删除、修改的属性"""
        patches: dict[str, Any] = {}
        all_keys = set(old_props.keys()) | set(new_props.keys())

        for key in all_keys:
            if key not in new_props:
                patches[key] = None  # 属性被删除
            elif key not in old_props:
                patches[key] = new_props[key]  # 新增属性
            elif old_props[key] != new_props[key]:
                patches[key] = new_props[key]  # 属性值变更

        return patches

    def _diff_children(self, old_kids: list, new_kids: list, path: list) -> list[Patch]:
        """子节点 Diff：使用 key 进行优化"""
        patches: list[Patch] = []

        if not old_kids and not new_kids:
            return patches

        # 建立 key → index 的映射
        old_map = {}
        for i, kid in enumerate(old_kids):
            if isinstance(kid, VNode) and kid.key:
                old_map[kid.key] = i

        # 标记旧子节点是否被复用
        used_old = [False] * len(old_kids)
        new_order: list[Optional[int]] = [None] * len(new_kids)

        # 第一轮：按 key 匹配
        for i, new_kid in enumerate(new_kids):
            if isinstance(new_kid, VNode) and new_kid.key:
                if new_kid.key in old_map:
                    old_idx = old_map[new_kid.key]
                    new_order[i] = old_idx
                    used_old[old_idx] = True

        # 第二轮：无 key 的节点按顺序匹配
        last_used = 0
        for i, new_kid in enumerate(new_kids):
            if new_order[i] is None:
                while last_used < len(old_kids) and used_old[last_used]:
                    last_used += 1
                if last_used < len(old_kids) and not (isinstance(new_kid, VNode) and new_kid.key):
                    new_order[i] = last_used
                    used_old[last_used] = True

        # 构建操作列表
        for i, (old_idx, new_kid) in enumerate(zip(new_order, new_kids)):
            child_path = list(path) + [i]
            if old_idx is not None and old_idx < len(old_kids):
                old_kid = old_kids[old_idx]
                if isinstance(old_kid, VNode) and isinstance(new_kid, VNode):
                    patches.extend(self.diff(old_kid, new_kid, child_path))
                elif old_kid != new_kid:
                    patches.append(Patch('replace', child_path, new_kid))
            else:
                patches.append(Patch('insert', child_path, new_kid))

        # 标记需要删除的旧节点
        for i, used in enumerate(used_old):
            if not used:
                patches.append(Patch('remove', list(path) + [i]))

        return patches


# === 演示 ===
if __name__ == "__main__":
    print("=== VDOM Diff 算法演示 ===\n")

    # 创建新旧两棵 VDOM 树
    old_tree = VNode('div', {'class': 'container'}, [
        VNode('h1', {'key': 'title'}, ['旧标题']),
        VNode('ul', {'key': 'list'}, [
            VNode('li', {'key': 'a', 'class': 'item'}, ['Item A']),
            VNode('li', {'key': 'b'}, ['Item B']),
            VNode('li', {'key': 'c'}, ['Item C']),
        ]),
        VNode('footer', {}, ['页脚']),
    ])

    new_tree = VNode('div', {'class': 'container new'}, [
        VNode('h1', {'key': 'title', 'style': 'color:red'}, ['新标题']),
        VNode('ul', {'key': 'list'}, [
            VNode('li', {'key': 'b'}, ['Item B (updated)']),
            VNode('li', {'key': 'a', 'class': 'item'}, ['Item A']),
            VNode('li', {'key': 'd'}, ['Item D (new)']),
        ]),
        VNode('footer', {}, ['页脚']),
    ])

    print("旧 VDOM:")
    print(old_tree.render())
    print("\n新 VDOM:")
    print(new_tree.render())

    differ = VDOMDiff()
    patches = differ.diff(old_tree, new_tree)

    print("\nDiff 补丁:")
    for p in patches:
        print(f"  {p}")

    print("\n✅ 关键观察:")
    print("  - h1 复用了，但 props 更新了 (style)")
    print("  - li 按 key 重新排序 (b 移到首位)")
    print("  - li:d 是新增的")
    print("  - footer 完全复用（无变化）")
```

---

## 六、总结

```
┌─────────────────────────────────────────────────────────────┐
│                    React 核心原理（全局图）                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  VDOM 层                       Hooks 层                       │
│  ┌─────────────────────┐     ┌─────────────────────┐         │
│  │  JSX → createElement│     │  useState → 链表     │         │
│  │  VNode 轻量对象     │     │  useEffect → commit  │         │
│  │  ReactElement       │     │  Hooks 顺序不可变    │         │
│  └─────────┬───────────┘     └─────────┬────────────┘         │
│            │                           │                       │
│            ▼                           ▼                       │
│  ┌─────────────────────────────────────────────┐              │
│  │          Reconciliation (协调)                │              │
│  │  Diff: 类型比较 + Key 复用 + 同级遍历          │              │
│  │  输出: 补丁列表 → 批量提交到 DOM              │              │
│  └─────────────────────────────────────────────┘              │
│                                                              │
│  状态管理层                     渲染层                         │
│  ┌──────────┐ ┌──────────┐   ┌─────────────────┐             │
│  │ useState │ │ Context  │   │ Browser DOM     │             │
│  │ useReducer│ │          │   │ React Native    │             │
│  │ Redux     │ │ 跨组件   │   │ Canvas / Three  │             │
│  │ Zustand   │ │ 共享     │   │ (任何平台)       │             │
│  └──────────┘ └──────────┘   └─────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

**一句话总结**：React 用 **VDOM + Diff** 做高效更新，用 **Fiber + 链表** 管理 Hooks 状态，用 **单向数据流** 保证可预测性——每一层都是可理解的计算机科学。

---

> 下一课预告：Web 全栈第3课 — Node.js 后端（libuv 事件循环、Express/Koa 中间件、RESTful、JWT）
