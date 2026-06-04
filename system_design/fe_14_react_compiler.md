# 现代前端框架深度 — React Compiler / RSC / Signals / 微前端

## 一、React Compiler（自动 memo 化）

### 背景
React 19 引入 React Compiler（前身 React Forget），目标是**自动完成 memo 优化**，无需开发者手动写 `useMemo` / `useCallback` / `React.memo`。

### 原理
```
源码 → React Compiler (Babel 插件) → 优化后代码
         ↓
静态分析 + 记忆化推理
         ↓
自动注入 useMemo / useCallback
```

**优化策略**:
- **变量记忆**: 检测纯计算表达式 → 自动 `useMemo`
- **函数记忆**: 检测不依赖 props 的回调 → 自动 `useCallback`
- **组件记忆**: 检测无副作用的组件 → 自动 `memo()`

**对比手写**:
```js
// 手写
function User({name}) {
  const upper = useMemo(() => name.toUpperCase(), [name])
  return <div onClick={useCallback(() => {}, [])}>{upper}</div>
}
// Compiler 输出（等价）
function User({name}) {
  const upper = name.toUpperCase() // 编译器自动记忆
  return <div onClick={() => {}}>{upper}</div>
}
```

**限制**: 需遵守 rules-of-hooks，不支持 mutable 数据

## 二、React Server Components (RSC)

### RSC 协议
```
Server Component → 序列化为 JSON（含特殊 $ 标记）→ 流式发送
Client Component → 保留在 bundle 中
```

**关键设计**:
- **Server Component**: 仅在服务端运行，不可用 hooks/state/effects
- **Client Component**: 使用 `"use client"` 标识，在浏览器运行
- **混合模式**: Server Component 可包含 Client Component 作为子节点

### 流式 SSR + Suspense
```
<Suspense fallback={<Spinner/>}>
  <AsyncComponent/> → 服务端暂停 → 发送 fallback → 就绪后发送补丁
</Suspense>
```

**Suspense 边界**: 每个 Suspense 包裹的组件可独立流式传输，不阻塞整个页面。

**数据传输格式**:
```
// server -> client (streaming JSON with $ markers)
M1:{"id":"$S1","name":"UserCard"}
$S1:{"__typename":"UserCard","props":{"name":"Alice"}}
```

## 三、Signals — 响应式新范式

### Preact Signals
```js
const count = signal(0)
const double = computed(() => count.value * 2)
effect(() => console.log(count.value))
```

**原理**: 依赖收集（类似 Vue reactivity）
- `signal()` 创建订阅源
- `computed()` 惰性求值 + 缓存
- `effect()` 自动追踪依赖变化

**优势**:
- 无虚拟 DOM 比较（精确更新）
- 无需 re-render 整个组件树
- 零依赖

### Solid.js 对比 Preact
| 特性 | Solid.js | Preact Signals |
|------|---------|---------------|
| 编译器 | JSX 编译为 DOM 操作 | 运行时 |
| 更新 | 直接更新 DOM | 标记后批量更新 |
| 组件 | 函数执行一次 | 可多次更新 |
| Tree | 细粒度更新 | 细粒度更新 |

**Solid 原理**: `createSignal` → Proxy 监听 → 编译时决定哪些 DOM 节点需要更新。

## 四、状态管理

### Zustand 原理

**双层架构**:
```
vanilla store (核心) ←→ React bindings (粘合层)
```

**vanilla store**:
```js
const store = createStore((set, get) => ({
  count: 0,
  inc: () => set(s => ({ count: s.count + 1 }))
}))
// 纯 JS：无 React 依赖
store.subscribe(() => console.log(store.getState()))
```

**React bindings**:
```js
const useStore = create((set) => ({...}))
// useSyncExternalStore 桥接 React 18
function useStore(selector) {
  return useSyncExternalStore(store.subscribe, () => selector(store.getState()))
}
```

**核心**: `useSyncExternalStore` — React 18 的外部 store 订阅 API。

### Jotai 原子模型
```js
const countAtom = atom(0)
const doubleAtom = atom(get => get(countAtom) * 2)

// 组件中使用
const [count, setCount] = useAtom(countAtom)
```

**特点**: 原子式状态、按需订阅、内置 Suspense 支持。

## 五、微前端方案对比

| 特性 | Module Federation | SingleSPA | Qiankun |
|------|-----------------|-----------|---------|
| 技术核心 | Webpack 5 插件 | 路由分发 + 生命周期 | SingleSPA + sandbox |
| 运行时隔离 | 无（依赖 webpack 作用域） | 需自行实现 | Proxy sandbox |
| 样式隔离 | 无 | 无 | Shadow DOM / scoped |
| 应用间通信 | shared modules | CustomEvent | initGlobalState |
| 构建耦合 | 强（需 webpack 5） | 弱（任何框架） | 弱（任何框架） |

**Module Federation 优势**: 共享运行时依赖（如 React），减少重复加载。

**Qiankun 优势**: 开箱沙箱隔离，支持存量系统无感接入。

**选型建议**: 同构技术栈选 Module Federation；异构/存量系统选 Qiankun。
