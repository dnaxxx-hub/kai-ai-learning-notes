# React核心

> 日期：2026-05-07 20:34 | 课程：前端路线 Phase 3-1
> 目标：理解"为什么React成了前端标配"

## 核心问题

```javascript
// 没有React时:
// 数据变了 → 手动操作DOM → 容易出错

document.getElementById("count").textContent = newCount;
// 如果还有10个地方要更新 → 到处改
// 这就是"命令式UI"的问题

// React: "数据变了 → 组件自动重新渲染"
// 声明式UI: 你只管数据，React管DOM
```

## React的核心概念

### 1. 组件（Component）

```tsx
// React = 把UI拆成独立、可复用的组件

// 函数组件（现代React）
function Greeting({ name }: { name: string }) {
  return <h1>你好，{name}！</h1>;
}

// 使用
<Greeting name="羽" />
```

### 2. JSX

```tsx
// 在JS里写HTML的感觉

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border rounded p-4 shadow">  {/* className不是class */}
      <h2>{title}</h2>
      <div>{children}</div>
    </div>
  );
}
```

### 3. Props

```tsx
// 组件的"参数" — 父组件传给子组件

interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: "primary" | "secondary";
}

function Button({ label, onClick, variant = "primary" }: ButtonProps) {
  return (
    <button 
      onClick={onClick}
      className={variant === "primary" 
        ? "bg-blue-500 text-white" 
        : "bg-gray-200 text-black"}
    >
      {label}
    </button>
  );
}
```

## Hooks（最核心的部分）

### useState

```tsx
function Counter() {
  const [count, setCount] = useState(0);
  //       ↑当前值    ↑更新函数        ↑初始值

  return (
    <div>
      <p>计数: {count}</p>
      <button onClick={() => setCount(count + 1)}>+1</button>
    </div>
  );
}
```

### useEffect

```tsx
// 副作用: 数据获取/订阅/DOM操作

function UserProfile({ userId }: { userId: number }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    // 组件挂载/更新时执行
    fetchUser(userId).then(setUser);
    
    // 清理函数（组件卸载时）
    return () => {
      // 取消订阅/清除定时器
    };
  }, [userId]); // 依赖数组：只有userId变了才重新执行
}
```

### 其他常用Hooks

```tsx
useMemo:       // 计算缓存（避免重复计算）
useCallback:   // 函数缓存（避免子组件重复渲染）
useRef:        // 引用DOM元素/存可变值
useContext:    // 全局状态（不用层层传props）
```

## 单向数据流

```
父组件
  └─ props（数据往下传）
       │
       ▼
子组件1 ──── 子组件2 ──── 子组件3
                              │
                   事件冒泡（函数往上传）
```

## 今日收获
- React = 声明式UI（数据驱动视图）
- 组件 + Props = UI的"函数式"组合
- **Hooks = React的灵魂**（useState/useEffect/useMemo）
- 单向数据流 = 数据从上往下，事件从下往上
- 以前用class组件，现在都用函数组件+hooks
