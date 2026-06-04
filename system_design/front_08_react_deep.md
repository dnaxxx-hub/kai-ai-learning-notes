# 前端 #8：React 状态管理与性能优化深度实战

> 日期：2026-05-13 | 课程：前端路线 Phase 4-2
> 前置：front_05_react_core、front_06_react_advanced、front_07_engineering

---

## 1. 状态管理架构选择

### 三种状态的边界

| 类型 | 存储位置 | 生命周期 | 典型场景 | 方案 |
|------|----------|----------|----------|------|
| **组件状态** | React tree 内部 | 组件挂载→卸载 | 表单输入、UI toggle | useState/useReducer |
| **全局状态** | JS 内存（store） | 应用启动→关闭 | 用户偏好、主题、权限 | Zustand/Redux/Context |
| **服务端状态** | 服务器 + 缓存 | 请求级 + TTL | API 数据、用户信息 | React Query/SWR |

**黄金法则**：
- 只有**跨组件共享且非服务端来源**的数据才进全局状态
- 其他一切优先：组件状态 → 提升状态 → 服务端状态

### useState vs useReducer

```typescript
// useState：简单的独立状态
const [count, setCount] = useState(0);

// useReducer：复杂关联逻辑、嵌套更新、多子状态
type Action =
  | { type: 'ADD_TODO'; payload: { text: string } }
  | { type: 'TOGGLE_TODO'; payload: { id: string } }
  | { type: 'DELETE_TODO'; payload: { id: string } };

function todoReducer(state: Todo[], action: Action): Todo[] {
  switch (action.type) {
    case 'ADD_TODO':
      return [...state, { id: nanoid(), text: action.payload.text, done: false }];
    case 'TOGGLE_TODO':
      return state.map(t => t.id === action.payload.id ? { ...t, done: !t.done } : t);
    case 'DELETE_TODO':
      return state.filter(t => t.id !== action.payload.id);
  }
}

const [todos, dispatch] = useReducer(todoReducer, []);
```

**选型推演**：>3 个关联子状态、或更新逻辑包含业务规则时 → useReducer 优于 useState。

### Context + useReducer 模式（小型到中型应用）

```typescript
// 专用于中小型应用（<5 个消费者、低更新频率）
const TodoContext = createContext<{
  state: Todo[];
  dispatch: React.Dispatch<Action>;
} | null>(null);

function TodoProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(todoReducer, initialTodos);
  return (
    <TodoContext.Provider value={{ state, dispatch }}>
      {children}
    </TodoContext.Provider>
  );
}

// 消费
function TodoList() {
  const ctx = useContext(TodoContext);
  if (!ctx) throw new Error('Missing TodoProvider');
  return ctx.state.map(todo => <TodoItem key={todo.id} todo={todo} />);
}
```

**⚠️ Context 缺陷**：所有消费者在 Provider value 变化时全部重渲染，无法细粒度订阅。可用 `useContextSelector` 或拆分为多个 Context 缓解。

### Zustand vs Jotai vs Redux Toolkit vs 无状态库

```
                轻量←——————————→重型
Zustand    ─█████████████░░░░░░░░  ~1KB, API 极简
Jotai      ─██████████░░░░░░░░░░  ~2KB, atomic 哲学
RTK        ─░░░░░░░░░███████████  大捆绑, 模式固定
无状态库   ─█████████████████████  0KB, 仅 Context/hooks
```

**选型推演**：
- **无状态库**：应用 < 1K LOC，组件树浅，完全适用
- **Context+useReducer**：5-20 个消费者，中等复杂度
- **Zustand**：中型应用、需要细粒度订阅、想少写样板代码 → **推荐**
- **Redux Toolkit**：大型团队、需要严格规范、Redux DevTools 强依赖
- **Jotai**：需要原子级细粒度、类似 Recoil 的体验

### Zustand 原理（核心）

```typescript
// Zustand ≈ vanilla store + React 桥接
// 核心代码仅 ~100 行：

// 1. 纯 JS store（不依赖 React）
function createStore(createState) {
  let state;                 // 当前状态
  const listeners = new Set();  // 订阅集合
  const api = {
    getState: () => state,
    setState: (partial) => {
      const next = typeof partial === 'function'
        ? partial(state) : partial;
      state = Object.assign({}, state, next);
      listeners.forEach(l => l());  // 通知所有订阅者
    },
    subscribe: (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    destroy: () => listeners.clear(),
  };
  state = createState(setState, getState, api);
  return api;
}

// 2. React hook 桥接（useSyncExternalStore）
// React 18+ 内置的同时并发安全的订阅 hook
function useStore(store, selector = identity) {
  const slice = useSyncExternalStore(
    store.subscribe,           // 注册/取消订阅
    () => selector(store.getState()),  // 获取当前快照
    () => selector(store.getState()),  // SSR snapshot
  );
  return slice;
}
```

**selector + equalityFn 优化**：
```typescript
// 默认严格引用比较（===）
// 如果 selector 返回新对象，每次都会重渲染
const bears = useBearStore(s => s.bears);  // ✅ 基本类型，安全

// ❌ 每次 selector 返回新对象
const settings = useBearStore(s => ({ theme: s.theme, lang: s.lang }));

// ✅ 自定义 equalityFn
const settings = useBearStore(
  s => ({ theme: s.theme, lang: s.lang }),
  shallow,  // 浅比较（Object.keys 逐字段 ===）
);
```

---

## 2. React 渲染机制

### 触发的 3 种方式

```
1. state 更新 ───→ 该组件 re-render
2. 父组件重渲染 ──→ 子组件 re-render（除非子组件跳过）
3. context 变化 ──→ 所有消费者 re-render
```

### 渲染触发链

```
根或变更点
  ↓ 向下遍历（reconciliation）
A(变化) ── 创建新 VNode ── commit
├─ B(无变化) ── 子组件 re-render（默认为 2）
│  └─ E
└─ C(无变化) ── 跳过（如果 memo 且 props 浅相等）
   └─ F
```

### React.memo 原理

```typescript
// 源码等价实现（简化版）
function memo(Component, areEqual) {
  const Memoized = (props) => {
    const prevProps = useRef(props);
    if (areEqual 
      ? areEqual(prevProps.current, props)   // 自定义比较
      : shallowEqual(prevProps.current, props)  // 默认浅比较
    ) {
      // props 无变化 → 跳过子树的 reconciliation
      return usePreviousRender(Component, props);
    }
    prevProps.current = props;
    return <Component {...props} />;
  };
  // displayName 等...
}
```

**shallowEqual = Object.is + 递归 Object.keys() 逐字段 Object.is**。

### useMemo/useCallback：何时用、何时有害

```typescript
// ✅ 何时用：
// 1. 昂贵计算（避免每次渲染都算）
const sorted = useMemo(
  () => items.sort((a, b) => expensiveCompare(a, b)),
  [items]
);

// 2. 保持引用稳定（配合 React.memo）
const handleClick = useCallback(
  (id: string) => dispatch({ type: 'TOGGLE', payload: { id } }),
  [dispatch]
);

// ❌ 何时有害（反模式）：
// 1. 简单计算（useMemo 本身有依赖比较开销 > 计算本身）
const double = useMemo(() => x * 2, [x]);  // 有害！直接 const double = x * 2

// 2. 基本类型 props（没有引用问题，不需稳定）
// 3. 内联回调传给原生 DOM（React 已优化，没有 memo 就没用）
<button onClick={() => setCount(c => c + 1)} />  // ✅ 原生元素无需 useCallback
```

---

## 3. 性能优化实战

### 列表优化：windowing

```typescript
// react-window（简单列表）
import { FixedSizeList as List } from 'react-window';

function VirtualList({ items }: { items: Item[] }) {
  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => (
    <div style={style}>
      <ExpensiveItem item={items[index]} />  {/* 务必 memo */}
    </div>
  );
  const MemoRow = React.memo(Row);  // 关键！

  return (
    <List
      height={600}
      itemCount={items.length}
      itemSize={50}
      width="100%"
    >
      {MemoRow}
    </List>
  );
}

// react-virtuoso（功能更丰富：动态高度、分组、逆向滚动）
import { Virtuoso } from 'react-virtuoso';

function ChatMessages({ messages }) {
  return (
    <Virtuoso
      totalCount={messages.length}
      itemContent={(index) => <MessageItem message={messages[index]} />}
      // 动态高度 ⚡
      itemSize={({ index }) => messages[index].text.length > 100 ? 80 : 50}
      followOutput="smooth"  // 新消息自动滚动
    />
  );
}
```

**key 优化**：用唯一稳定 ID 而非 index（避免帧动画/表单输入的 DOM 复用问题）。

### Concurrent Features

```typescript
// 1. startTransition：标记非紧急更新
import { startTransition, useState } from 'react';

function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Result[]>([]);

  function handleInput(e: ChangeEvent<HTMLInputElement>) {
    setQuery(e.target.value);  // 紧急：输入框立即可见
    startTransition(() => {
      setResults(filterItems(e.target.value));  // 非紧急：可被中断
    });
  }
  // 用户快速输入时，渲染结果可以被新一轮输入中断，保持高优先级的输入流畅
}

// 2. useDeferredValue：延迟派生值
function ProductList({ searchQuery }: { searchQuery: string }) {
  const deferredQuery = useDeferredValue(searchQuery);
  const isStale = searchQuery !== deferredQuery;

  return (
    <>
      {isStale && <Spinner />}  {/* 旧数据有"加载中"视觉提示 */}
      <ExpensiveList query={deferredQuery} />
    </>
  );
}
```

### 瀑布流并行加载

```typescript
// ❌ 瀑布流：A → B → C 串行
const A = () => { /* fetch /api/a */ return <B /> }
const B = () => { /* fetch /api/b */ return <C /> }

// ✅ 并行：同时发起
function Page() {
  // 1. 顶层并行 fetch
  const [aData, bData] = await Promise.all([
    fetch('/api/a'), fetch('/api/b')
  ]);
  return (
    <>
      <A data={aData} />
      <B data={bData} />
    </>
  );
}

// ✅ Suspense + lazy：代码分包 + 加载边界
const Sidebar = lazy(() => import('./Sidebar'));
const MainContent = lazy(() => import('./MainContent'));

function Layout() {
  return (
    <Suspense fallback={<Skeleton />}>
      <Sidebar />
      <MainContent />
      {/* 两个懒加载模块并行加载，而不是串行 */}
    </Suspense>
  );
}
```

### 测量性能

```typescript
// 1. React Profiler 组件（dev 环境）
import { Profiler } from 'react';

function onRender(
  id: string, phase: 'mount' | 'update',
  actualDuration: number, baseDuration: number,
  startTime: number, commitTime: number
) {
  if (actualDuration > 16) { // 超过 16ms（60fps 帧预算）
    console.warn(`[Perf] ${id} 渲染耗时 ${actualDuration.toFixed(1)}ms`);
  }
}

<Profiler id="TodoList" onRender={onRender}>
  <TodoList />
</Profiler>

// 2. why-did-you-render（开发调试）
import whyDidYouRender from '@welldone-software/why-did-you-render';
whyDidYouRender(React, { trackAllPureComponents: true });

// 组件上标记
TodoItem.whyDidYouRender = true;
// 控制台会输出不必要的重渲染：组件名 + 变化/未变化的 props
```

---

## 4. Zustand 深度

### 完整源码级理解

```typescript
// 精简版 Zustand 实现（~50 行）
import { useSyncExternalStore, useDebugValue } from 'react';

function create<T>(createState: (set: SetFn, get: GetFn, api: StoreApi<T>) => T) {
  // === vanilla store ===
  let state: T;
  const listeners = new Set<Listener>();
  const getState: GetFn<T> = () => state;
  const setState: SetFn<T> = (partial) => {
    const next = typeof partial === 'function'
      ? (partial as (s: T) => Partial<T>)(state)
      : partial;
    state = Object.assign({}, state, next);
    listeners.forEach(l => l());
  };
  const subscribe = (fn: Listener) => {
    listeners.add(fn);
    return () => listeners.delete(fn);
  };
  state = createState(setState, getState, { getState, setState, subscribe, destroy });
  const api = { getState, setState, subscribe, destroy: () => listeners.clear() };

  // === React bridge ===
  const useBoundStore: UseBoundStore<T> = <U>(selector?: (s: T) => U, equals?: (a: U, b: U) => boolean): U => {
    const slice = useSyncExternalStore(
      subscribe,
      () => selector ? selector(state) : state as unknown as U,
      () => selector ? selector(state) : state as unknown as U,
    );
    useDebugValue(slice);
    return slice;
  };

  // useBoundStore.getState() = getState 的快捷访问
  useBoundStore.getState = getState;
  useBoundStore.setState = setState;
  useBoundStore.subscribe = subscribe;
  useBoundStore.destroy = api.destroy;

  return useBoundStore;
}
```

### Middleware 机制

```typescript
// middleware ≈ store 创建函数的组合器
// 接收原始 create，返回增强版 create

// persist（把状态同步到 localStorage）
const useStore = create(
  persist(
    (set) => ({
      theme: 'light',
      setTheme: (t: string) => set({ theme: t }),
    }),
    {
      name: 'app-settings',        // localStorage key
      partialize: (s) => ({ theme: s.theme }),  // 只持久化部分字段
    }
  )
);

// immer（不可变更新语法糖）
const useCartStore = create(
  immer((set) => ({
    items: [] as Item[],
    addItem: (item: Item) => set(s => { s.items.push(item); }),  // 直接 push！
    removeItem: (id: string) => set(s => {
      s.items = s.items.filter(i => i.id !== id);
    }),
  }))
);

// devtools（Redux DevTools 支持）
const useStore = create(
  devtools(myStore, { name: 'MyStore' })
);

// logger（状态变化日志）
const useStore = create(
  logger(store, (action, prev, next) => {
    console.log('%c[store]', 'color:blue', action, prev, '→', next);
  })
);
```

### Zustand vs Redux Toolkit 对比

| 维度 | Zustand | Redux Toolkit |
|------|---------|---------------|
| 包体 | ~1KB | ~13KB (RTK) |
| 样板代码 | 近乎 0 | slice + reducer + action 三件套 |
| 灵活性 | 任意 JS 结构 | 固定模式（禁止副作用在 reducer） |
| TypeScript | 原生优秀 | 需额外类型体操 |
| DevTools | 内置 devtools middleware | 内置，更成熟 |
| 生态 | 小（够用） | 大（RTK Query、Listener 等） |
| 学习曲线 | 5 分钟 | 1-2 天 |

**推演**：新项目选 Zustand，大型规范化团队选 RTK。

---

## 5. 服务端状态：TanStack/React Query

### 核心缓存模型：stale-while-revalidate

```typescript
// 默认策略：
// 1. 返回缓存数据（立即展示）
// 2. 后台重新获取（stale 时）
// 3. 新数据覆盖缓存 → 触发 UI 更新

const { data, isLoading, error } = useQuery({
  queryKey: ['todos', { status: 'active' }],
  queryFn: () => fetch('/api/todos?status=active').then(r => r.json()),
  staleTime: 30_000,      // 30s 内数据视为"新鲜"，不触发后台刷新
  gcTime: 5 * 60_000,     // 5min 无消费者后 GC 回收
  refetchOnWindowFocus: true,  // 用户切回页面时自动刷新
});
```

### queryKey 结构设计最佳实践

```typescript
// 分层结构：资源 → 参数 → 变体
['todos']                          // 全部 todos
['todos', id]                      // 单个 todo
['todos', { status: 'active' }]    // 过滤列表
['todos', id, 'comments']          // todo 的评论列表
['project', projectId, 'tasks']    // 项目下的任务

// 缓存失效（精确到颗粒度）
queryClient.invalidateQueries({ queryKey: ['todos'] });        // 全部 todos
queryClient.invalidateQueries({ queryKey: ['todos', 42] });    // 仅 id=42
queryClient.invalidateQueries({ queryKey: ['project', pid] }); // 仅指定项目
```

### 乐观更新 + 缓存失效

```typescript
const mutation = useMutation({
  mutationFn: (newTodo: { text: string }) =>
    fetch('/api/todos', { method: 'POST', body: JSON.stringify(newTodo) }).then(r => r.json()),

  // 乐观更新：立即更新 UI
  onMutate: async (newTodo) => {
    // 1. 取消正在进行的获取（避免覆盖）
    await queryClient.cancelQueries({ queryKey: ['todos'] });
    // 2. 保存快照（用于回滚）
    const previous = queryClient.getQueryData(['todos']);
    // 3. 直接写入缓存
    queryClient.setQueryData(['todos'], (old: Todo[]) => [
      ...old, { ...newTodo, id: 'optimistic-' + Date.now(), done: false },
    ]);
    return { previous };  // context 传递给 onError
  },

  onError: (_err, _newTodo, context) => {
    // 失败回滚
    queryClient.setQueryData(['todos'], context?.previous);
  },

  onSettled: () => {
    // 最终：确保缓存与服务端一致
    queryClient.invalidateQueries({ queryKey: ['todos'] });
  },
});
```

### 预取（Prefetching）

```typescript
// 预判用户行为，提前获取数据
function UserList() {
  const queryClient = useQueryClient();

  // 鼠标悬停时预取用户详情
  const prefetchUser = (userId: string) => {
    queryClient.prefetchQuery({
      queryKey: ['user', userId],
      queryFn: () => fetch(`/api/users/${userId}`).then(r => r.json()),
      staleTime: 60_000,  // 预取数据保留 1min 新鲜
    });
  };

  return users.map(u => (
    <div
      key={u.id}
      onMouseEnter={() => prefetchUser(u.id)}
      onClick={() => navigate(`/users/${u.id}`)}  // 导航时用户数据已就绪
    >
      {u.name}
    </div>
  ));
}
```

---

## 6. React Query + Zustand 黄金搭档

### 分工原则

```
React Query ——— 服务端缓存管理
  - API 请求/缓存/失效/重试
  - WebSocket 实时数据
  - infinite scroll / 分页
  
Zustand ————— 客户端全局状态
  - UI 状态（主题、侧边栏折叠、模态框）
  - 瞬时交互状态（drag-drop 位置、拖拽中数据）
  - 跨页面的筛选器/偏好
  - 非服务端来源的业务状态
```

### 实战架构

```typescript
// ===== store/auth.ts（认证状态 — Zustand）=====
interface AuthState {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      login: async (email, pwd) => {
        const res = await fetch('/api/login', { method: 'POST', body: JSON.stringify({ email, pwd }) });
        const data = await res.json();
        set({ user: data.user, token: data.token });
      },
      logout: () => set({ user: null, token: null }),
    }),
    { name: 'auth-storage', partialize: (s) => ({ token: s.token }) }
  )
);

// ===== queries/todos.ts（服务端数据 — React Query）=====
export function useTodos() {
  return useQuery({
    queryKey: ['todos'],
    queryFn: () => {
      const token = useAuthStore.getState().token;  // Zustand 作为 token 来源
      return fetch('/api/todos', { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json());
    },
  });
}

// ===== pages/Dashboard.tsx（组合使用）=====
function Dashboard() {
  // React Query 管服务器数据
  const { data: todos, isLoading } = useTodos();
  // Zustand 管客户端状态
  const theme = useThemeStore(s => s.theme);
  const sidebarOpen = useUIStore(s => s.sidebarOpen);

  if (isLoading) return <Skeleton />;
  return (
    <div className={theme === 'dark' ? 'dark' : ''}>
      <Sidebar open={sidebarOpen} />
      <TodoList todos={todos} />
    </div>
  );
}
```

---

## 7. 现代 React 模式

### 复合组件（Compound Component）

```typescript
// <Select><SelectTrigger><SelectValue><SelectContent><SelectItem> 模式
// 状态通过 Context 隐式传递，渲染通过子组件组合

interface SelectContextType {
  value: string;
  onChange: (v: string) => void;
  open: boolean;
  setOpen: (v: boolean) => void;
}
const SelectCtx = createContext<SelectContextType | null>(null);

function Select({ children, value, onChange }: SelectProps) {
  const [open, setOpen] = useState(false);
  return (
    <SelectCtx.Provider value={{ value, onChange, open, setOpen }}>
      <div className="relative">{children}</div>
    </SelectCtx.Provider>
  );
}

Select.Trigger = function Trigger({ children }: { children: React.ReactNode }) {
  const ctx = useSelectCtx();
  return <button onClick={() => ctx.setOpen(!ctx.open)}>{children}</button>;
};

Select.Content = function Content({ children }: { children: React.ReactNode }) {
  const ctx = useSelectCtx();
  return ctx.open ? <div className="dropdown">{children}</div> : null;
};

Select.Item = function Item({ value, children }: { value: string; children: React.ReactNode }) {
  const ctx = useSelectCtx();
  return <div onClick={() => { ctx.onChange(value); ctx.setOpen(false); }}>{children}</div>;
};

// 使用：
<Select value={lang} onChange={setLang}>
  <Select.Trigger>{lang}</Select.Trigger>
  <Select.Content>
    <Select.Item value="zh">中文</Select.Item>
    <Select.Item value="en">English</Select.Item>
  </Select.Content>
</Select>
```

### 渲染优化的数据流模式

```typescript
// 1. 提升状态（Lift State Up）
// ❌ 子组件各自 fetch → 重复请求
// ✅ 父组件统一 fetch → 所有子组件共享数据

// 2. 状态下沉（Colocate State）
// ❌ 所有状态放顶层 Provider → 任何变化触发全局重渲染
// ✅ 状态放到最靠近使用它的组件 → 渲染范围最小化

// 3. 状态靠近（State Colocation）
// 例子：一个 Form 的每个字段自己维护 focus/blur 状态，
// 只有提交时才把数据给父组件，而不是所有字段状态都放父组件
```

### SSR/SSG/ISR 渲染策略选择

```
页面类型              推荐策略         原因
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
博客/文档             SSG        内容不变，CDN 静态化，秒开
产品详情页            ISR         内容少变，60s 或按需重生成
用户 Dashboard        SSR/Streaming  每次请求数据不同，首屏要快
实时数据（行情）      CSR+SSR fallback  服务端只负责 SEO，客户端实时更新
管理后台              CSR         无需 SEO，SPA 体验更佳
电商搜索列表          SSR+ISR      初始 SSR，命中缓存 ISR，新数据客户端更新
```

**Next.js 实践**：
```typescript
// SSG（构建时生成）
export async function getStaticProps() { /* ... */ }

// ISR（按时间间隔重生成）
export async function getStaticProps() {
  return { props: {}, revalidate: 60 };  // 60 秒后下次访问触发重建
}

// SSR（每次请求渲染）
export async function getServerSideProps() { /* ... */ }

// App Router（推荐）
// 默认组件是 Server Component（类似 SSG）
// 动态路由配合 revalidate = SSR/ISR
export const revalidate = 60;  // 页面级 ISR
```

---

## 学习路径总览

```
front_01_html_css         ─── 前端基础
front_02_tailwind         ─── CSS 框架
front_03_js_core          ─── JavaScript 核心
front_04_typescript       ─── 类型系统
front_05_react_core       ─── React 入门
front_06_react_advanced   ─── React 进阶
front_07_engineering      ─── 工程化
front_08_react_deep       ─── ✨ 状态管理 + 性能优化（当前）

下一步推荐：
front_09_nextjs_fullstack  ─── 全栈 Next.js（Server Components, Server Actions）
front_10_fullstack_project ─── 完整全栈项目实战
```
