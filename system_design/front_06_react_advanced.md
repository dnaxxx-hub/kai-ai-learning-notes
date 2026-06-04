# React进阶

> 日期：2026-05-07 20:35 | 课程：前端路线 Phase 3-2
> 目标：理解"复杂React应用怎么管理"

## 状态管理的演进

```
组件内部状态 (useState)
    ↓ 太简单了？但数据要跨组件共享...
Context API (React 16.3)
    ↓ 数据层级深了会重复渲染...
Redux/Zustand (外部状态管理)
    ↓ 太复杂了？其实小项目用Context就够了...
React Query / SWR (服务端状态)
    ↓ 现在的主流: 服务端和客户端状态分开管理
```

## Context

```tsx
// 场景: 用户信息被很多组件需要
// 不用Context: 逐层传 props → 中间组件变得臃肿

// 定义Context
const UserContext = createContext<User | null>(null);

// 提供者
function App() {
  const user = { name: "羽", level: "star" };
  return (
    <UserContext.Provider value={user}>
      <Sidebar />
      <MainContent />
    </UserContext.Provider>
  );
}

// 使用者
function Avatar() {
  const user = useContext(UserContext);
  return <img src={user.avatar} />;
  // 直接拿到数据，不用通过props一层层传
}
```

## 路由（React Router）

```tsx
// 单页应用（SPA）：切换页面不刷新，只切换组件

<Routes>
  <Route path="/" element={<Home />} />
  <Route path="/posts" element={<PostList />} />
  <Route path="/posts/:id" element={<PostDetail />} />
  <Route path="/about" element={<About />} />
</Routes>

// <Link to="/posts">文章</Link>  ← 不会刷新页面
// <a href="/posts">文章</a>      ← 会刷新（不推荐）
```

## React Query / TanStack Query

```tsx
// 现代React最关键的一个库：管理服务器状态

function PostList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['posts'],
    queryFn: () => fetchPosts(),
  });
  
  // 自动处理: 加载/错误/缓存/重新获取/分页/无限滚动
  if (isLoading) return <Loading />;
  if (error) return <Error />;
  return data.map(post => <PostCard post={post} />);
}
```

## Next.js（React框架）

```tsx
// React本身只是一个库（不是框架）
// Next.js = 全栈React框架

// 核心功能:
// 1. SSR (服务端渲染) — 首页更快、SEO更好
// 2. RSC (React Server Components) — 减少客户端JS
// 3. API Routes — 后端接口
// 4. 文件路由 — 自动根据文件生成路由
// 5. Image优化/字体优化/代码分割内置

// App Router (Next.js 13+):
// app/
//   page.tsx         → /
//   about/page.tsx   → /about
//   posts/[id]/page.tsx → /posts/123
//   layout.tsx       → 布局组件
//   api/posts/route.ts → API接口
```

## 性能优化

```tsx
// 1. useMemo — 避免重复计算
const sortedList = useMemo(
  () => items.sort((a, b) => a.date - b.date),
  [items]
);

// 2. React.memo — 避免不必要的子组件重渲染
const ExpensiveCard = React.memo(({ data }) => {
  return <ExpensiveComponent data={data} />;
});

// 3. 代码分割
const HeavyPage = lazy(() => import('./HeavyPage'));
// 用户访问时才加载，第一次加载不用下载所有代码
```

## 今日收获
- Context = 避免props层层传递（但滥用会导致重复渲染）
- React Query = 服务端状态管理（比Redux更适合现代React）
- Next.js = React的事实标准框架（SSR + 全栈 + 性能）
- 性能三件套：useMemo + memo + 代码分割
- 现代React项目标准栈：Next.js + TypeScript + TailwindCSS + React Query
